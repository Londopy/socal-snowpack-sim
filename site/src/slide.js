import * as THREE from "three";
import { heightAt } from "./terrain.js";

const G = 9.81;
const CRACK_SPEED = 45;
const MAX_PUFFS = 2400;

// sliding-block run-out: gravity along the local fall line, Coulomb friction and a
// velocity-squared drag (a point-mass take on the Voellmy model). It shapes an
// illustration; it is not a calibrated avalanche model.
const STYLES = {
  slab: { mu: 0.24, drag: 0.0085, puffs: true, crown: true },
  wet: { mu: 0.42, drag: 0.016, puffs: false, crown: false },
};

function puffTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d");
  const r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, "rgba(255,255,255,0.9)");
  r.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = r;
  g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

export class Slide {
  constructor(scene, place, bowl, { kind, depth, color, cells }) {
    this.scene = scene;
    this.place = place;
    this.dem = place.dem;
    this.kind = kind;
    this.style = STYLES[kind];
    this.depth = depth;
    this.group = new THREE.Group();
    scene.scene.add(this.group);
    this.light = new THREE.DirectionalLight("#ffffff", 2.2);
    this.light.position.set(-0.6, 1, -0.4);
    this.group.add(this.light, new THREE.AmbientLight("#c9d2e6", 1.1));

    const n = bowl.grid;
    const cell = bowl.cell_m;
    this.toWorld = (i, j) => [(j / (n - 1) - 0.5) * place.width, (i / (n - 1) - 0.5) * place.depth];
    this.blocks = bowl.blocks.filter(([, , a, b]) => cells.has(`${a},${b}`)).map(([i, j]) => {
      const [x, z] = this.toWorld(i, j);
      return { x, z, x0: x, z0: z, y: this.ground(x, z), vx: 0, vz: 0, t0: 0, moving: false, done: false, spin: Math.random() * 6, axis: new THREE.Vector3(Math.random() - 0.5, 0.3, Math.random() - 0.5).normalize(), travel: 0 };
    });
    this.size = cell * bowl.block_stride;

    // the crown is the uphill edge of the zone; the crack starts at its middle and runs both ways
    const top = Math.max(...this.blocks.map((b) => b.y));
    const crown = this.blocks.filter((b) => b.y > top - 18);
    const start = crown[Math.floor(crown.length / 2)];
    for (const b of this.blocks) {
      const d = Math.hypot(b.x - start.x, b.z - start.z);
      b.t0 = kind === "wet" ? d / 6 : d / CRACK_SPEED + (top - b.y) / 120;
    }
    this.crownY = start.y;

    const geo = new THREE.BoxGeometry(this.size * 0.92, 1, this.size * 0.92);
    const mat = new THREE.MeshLambertMaterial({ color });
    this.mesh = new THREE.InstancedMesh(geo, mat, this.blocks.length);
    this.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    this.group.add(this.mesh);

    if (this.style.crown) {
      const pts = [];
      for (const b of this.blocks) {
        const uphill = this.blocks.some((o) => o !== b && Math.hypot(o.x - b.x, o.z - b.z) < this.size * 1.5 && o.y > b.y + 2);
        if (!uphill) pts.push(b);
      }
      const cg = new THREE.BoxGeometry(this.size * 1.05, 1, this.size * 0.6);
      this.crown = new THREE.InstancedMesh(cg, new THREE.MeshBasicMaterial({ color: "#2b2a33" }), pts.length);
      this.crownBlocks = pts;
      this.crown.count = 0;
      this.group.add(this.crown);
    }

    if (this.style.puffs) {
      this.puffPos = new Float32Array(MAX_PUFFS * 3);
      this.puffLife = new Float32Array(MAX_PUFFS);
      this.puffVel = new Float32Array(MAX_PUFFS * 3);
      const pg = new THREE.BufferGeometry();
      pg.setAttribute("position", new THREE.BufferAttribute(this.puffPos, 3));
      this.puffs = new THREE.Points(pg, new THREE.PointsMaterial({ size: 26, map: puffTexture(), transparent: true, depthWrite: false, opacity: 0.55, sizeAttenuation: true }));
      this.puffNext = 0;
      this.group.add(this.puffs);
    }
    for (const o of [this.mesh, this.crown, this.puffs]) if (o) o.frustumCulled = false;
    this.t = 0;
    this.draw();
  }

  ground(x, z) {
    return heightAt(this.dem, x / this.place.width + 0.5, z / this.place.depth + 0.5);
  }

  slopeAt(x, z) {
    const h = 4;
    return [(this.ground(x + h, z) - this.ground(x - h, z)) / (2 * h), (this.ground(x, z + h) - this.ground(x, z - h)) / (2 * h)];
  }

  // advance the run-out by dt seconds of simulated time
  step(dt) {
    this.t += dt;
    let active = 0;
    for (const b of this.blocks) {
      if (b.done || this.t < b.t0) continue;
      b.moving = true;
      active++;
      const [gx, gz] = this.slopeAt(b.x, b.z);
      const grad = Math.hypot(gx, gz);
      const theta = Math.atan(grad);
      const speed = Math.hypot(b.vx, b.vz);
      let ax = 0;
      let az = 0;
      if (grad > 1e-4) {
        const push = G * Math.sin(theta);
        ax = (-gx / grad) * push;
        az = (-gz / grad) * push;
      }
      const brake = G * Math.cos(theta) * this.style.mu + this.style.drag * speed * speed;
      if (speed > 1e-3) {
        ax -= (b.vx / speed) * brake;
        az -= (b.vz / speed) * brake;
      } else if (Math.hypot(ax, az) <= G * Math.cos(theta) * this.style.mu) {
        ax = az = 0;
      }
      b.vx += ax * dt;
      b.vz += az * dt;
      const v = Math.hypot(b.vx, b.vz);
      b.x += b.vx * dt;
      b.z += b.vz * dt;
      b.travel += v * dt;
      b.spin += v * dt * 0.08;
      b.y = this.ground(b.x, b.z);
      // a block rocking in a hollow would never settle, so cap the run
      if ((this.t - b.t0 > 2 && v < 0.6 && theta < Math.atan(this.style.mu) + 0.05) || this.t - b.t0 > 60) {
        b.done = true;
        b.vx = b.vz = 0;
      }
      if (this.puffs && v > 14 && Math.random() < 0.5) this.puff(b, v);
    }
    if (this.puffs) this.agePuffs(dt);
    this.finished = this.t > 3 && active === 0;
    return !this.finished;
  }

  puff(b, v) {
    const i = this.puffNext;
    this.puffNext = (i + 1) % MAX_PUFFS;
    this.puffPos.set([b.x + (Math.random() - 0.5) * 10, b.y + 2, b.z + (Math.random() - 0.5) * 10], i * 3);
    this.puffVel.set([b.vx * 0.5, 2 + Math.random() * 4 + v * 0.1, b.vz * 0.5], i * 3);
    this.puffLife[i] = 1;
  }

  agePuffs(dt) {
    for (let i = 0; i < MAX_PUFFS; i++) {
      if (this.puffLife[i] <= 0) continue;
      this.puffLife[i] -= dt * 0.22;
      for (let k = 0; k < 3; k++) {
        this.puffPos[i * 3 + k] += this.puffVel[i * 3 + k] * dt;
        this.puffVel[i * 3 + k] *= 1 - dt * 0.6;
      }
      if (this.puffLife[i] <= 0) this.puffPos[i * 3 + 1] = -1e5;
    }
    this.puffs.geometry.attributes.position.needsUpdate = true;
  }

  draw() {
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const s = new THREE.Vector3();
    const exag = this.place.exag;
    this.blocks.forEach((b, i) => {
      const moved = Math.min(b.travel / 120, 1);
      const shrink = 1 - 0.45 * moved;
      const thick = this.depth * (1 - 0.3 * moved);
      q.setFromAxisAngle(b.axis, b.moving ? b.spin : 0);
      s.set(shrink, thick, shrink);
      m.compose(new THREE.Vector3(b.x, b.y * exag + thick / 2 + (b.moving ? 0.6 : 0.15), b.z), q, s);
      this.mesh.setMatrixAt(i, m);
    });
    this.mesh.instanceMatrix.needsUpdate = true;
    if (this.crown) {
      let n = 0;
      for (const b of this.crownBlocks) {
        if (this.t < b.t0) continue;
        const [gx, gz] = this.slopeAt(b.x0, b.z0);
        q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.atan2(gx, gz));
        m.compose(new THREE.Vector3(b.x0, this.ground(b.x0, b.z0) * exag + 0.4, b.z0), q, new THREE.Vector3(1, 1.2, 1));
        this.crown.setMatrixAt(n++, m);
      }
      this.crown.count = n;
      this.crown.instanceMatrix.needsUpdate = true;
    }
  }

  extent() {
    const pts = this.blocks.flatMap((b) => [[b.x0, this.ground(b.x0, b.z0), b.z0], [b.x, b.y, b.z]]);
    const lo = [0, 1, 2].map((k) => Math.min(...pts.map((p) => p[k])));
    const hi = [0, 1, 2].map((k) => Math.max(...pts.map((p) => p[k])));
    const center = new THREE.Vector3((lo[0] + hi[0]) / 2, ((lo[1] + hi[1]) / 2) * this.place.exag, (lo[2] + hi[2]) / 2);
    return { center, size: Math.max(hi[0] - lo[0], hi[2] - lo[2]) };
  }

  // run the whole slide at once, for reduced motion
  settle() {
    while (this.step(0.1) && this.t < 240);
    if (this.puffs) this.puffLife.fill(0);
    if (this.puffs) this.puffPos.fill(-1e5);
    this.draw();
  }

  stats() {
    const moved = this.blocks.filter((b) => b.travel > 5);
    const lead = moved.reduce((a, b) => (b.travel > a.travel ? b : a), { travel: 0, y: this.crownY });
    return { far: Math.round(lead.travel), drop: Math.round(this.crownY - lead.y) };
  }

  dispose() {
    this.scene.scene.remove(this.group);
    this.group.traverse((o) => {
      if (o.isInstancedMesh) o.dispose();
      o.geometry?.dispose();
      o.material?.map?.dispose();
      o.material?.dispose();
    });
  }
}
