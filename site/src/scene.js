import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { terrainGeometry } from "./terrain.js";
import { vertex, fragment, skirtVertex, skirtFragment, LAYERS, OVERPRINTS } from "./shaders.js";

const SUN_AZ = THREE.MathUtils.degToRad(315);
const SUN_ALT = THREE.MathUtils.degToRad(40);
export const PROBLEM_COLORS = ["#2b4ea2", "#009a8f", "#7f6a12", "#a3348e"];

function gridTexture() {
  const t = new THREE.DataTexture(new Float32Array(8 * 5 * 4), 8, 5, THREE.RGBAFormat, THREE.FloatType);
  t.magFilter = t.minFilter = THREE.NearestFilter;
  t.needsUpdate = true;
  return t;
}

const blank = new THREE.DataTexture(new Uint8Array([255, 255, 255, 255]), 1, 1);
blank.needsUpdate = true;

export class Scene {
  constructor(canvas) {
    this.canvas = canvas;
    this.renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(34, 1, 10, 600000);
    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.maxPolarAngle = THREE.MathUtils.degToRad(82);
    this.controls.screenSpacePanning = false;
    this.listeners = [];
    this.gridA = gridTexture();
    this.gridB = gridTexture();
    const sun = new THREE.Vector3(
      Math.sin(SUN_AZ) * Math.cos(SUN_ALT),
      Math.sin(SUN_ALT),
      -Math.cos(SUN_AZ) * Math.cos(SUN_ALT),
    );
    this.uniforms = {
      uExag: { value: 1 },
      uLayer: { value: 0 },
      uOverprint: { value: 1 },
      uSnow: { value: true },
      uHasTex: { value: false },
      uHasLidar: { value: false },
      uTex: { value: blank },
      uLidar: { value: blank },
      uGridA: { value: this.gridA },
      uGridB: { value: this.gridB },
      uSun: { value: sun },
      uPaper: { value: new THREE.Color("#eef0ea") },
      uFogFar: { value: 100000 },
      uHatch: { value: 7 },
      uPixelRatio: { value: this.renderer.getPixelRatio() },
      uHighlight: { value: new THREE.Vector2(-1, -1) },
      uElevated: { value: 0.45 },
      uProblemColor: { value: PROBLEM_COLORS.map((c) => new THREE.Color(c)) },
      uInk: { value: new THREE.Color("#2b2a33") },
      uClock: { value: false },
      uDaylight: { value: 1 },
    };
    this.mapSun = sun;
    this.skirtUniforms = {
      uExag: this.uniforms.uExag,
      uSide: { value: new THREE.Color("#d9dcd3") },
      uLine: { value: new THREE.Color("#2b2a33") },
    };
    this.material = new THREE.ShaderMaterial({ vertexShader: vertex, fragmentShader: fragment, uniforms: this.uniforms });
    this.skirtMaterial = new THREE.ShaderMaterial({
      vertexShader: skirtVertex,
      fragmentShader: skirtFragment,
      uniforms: this.skirtUniforms,
      side: THREE.DoubleSide,
    });
    new ResizeObserver(() => this.resize()).observe(canvas.parentElement);
    this.resize();
    this.renderer.setAnimationLoop(() => this.frame());
  }

  setPaper(paper, side, ink) {
    this.uniforms.uPaper.value.set(paper);
    this.skirtUniforms.uSide.value.set(side);
    this.skirtUniforms.uLine.value.set(ink);
    this.renderer.setClearColor(paper);
  }

  resize() {
    const el = this.canvas.parentElement;
    const w = el.clientWidth;
    const h = el.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  onFrame(fn) {
    this.listeners.push(fn);
  }

  frame() {
    if (this.tween) this.tween();
    this.controls.update();
    // haze the far side of whatever is in view, like aerial perspective on a painted relief
    this.uniforms.uFogFar.value = this.camera.position.distanceTo(this.controls.target) * 2.2;
    this.renderer.render(this.scene, this.camera);
    for (const fn of this.listeners) fn();
  }

  setTerrain(dem, widthM, depthM, exag) {
    for (const m of [this.mesh, this.skirt]) {
      if (!m) continue;
      this.scene.remove(m);
      m.geometry.dispose();
    }
    this.uniforms.uExag.value = exag;
    this.mesh = new THREE.Mesh(terrainGeometry(dem, widthM, depthM), this.material);
    this.skirt = new THREE.Mesh(skirtGeometry(dem, widthM, depthM), this.skirtMaterial);
    this.scene.add(this.mesh, this.skirt);
    this.extent = Math.max(widthM, depthM);
    this.controls.maxDistance = this.extent * 3.5;
    this.controls.minDistance = this.extent * 0.04;
  }

  setTexture(tex) {
    this.uniforms.uTex.value = tex || blank;
    this.uniforms.uHasTex.value = Boolean(tex);
  }

  setLidar(tex) {
    this.uniforms.uLidar.value = tex || blank;
    this.uniforms.uHasLidar.value = Boolean(tex);
  }

  setLayer(name) {
    this.uniforms.uLayer.value = LAYERS.indexOf(name);
  }

  setOverprint(name) {
    this.uniforms.uOverprint.value = OVERPRINTS.indexOf(name);
  }

  setSnow(on) {
    this.uniforms.uSnow.value = on;
  }

  // null puts back the north-west cartographic light
  setSun(sun) {
    this.uniforms.uClock.value = Boolean(sun);
    this.uniforms.uSun.value = sun ? sun.dir : this.mapSun;
    this.uniforms.uDaylight.value = sun ? sun.daylight : 1;
  }

  setHighlight(aspect, band) {
    this.uniforms.uHighlight.value.set(aspect, band);
  }

  setGrid(a, b) {
    this.gridA.image.data.set(a);
    this.gridB.image.data.set(b);
    this.gridA.needsUpdate = true;
    this.gridB.needsUpdate = true;
  }

  view() {
    return { position: this.camera.position.clone(), target: this.controls.target.clone() };
  }

  // a new flight settles the one it replaces, so nothing awaiting the old one hangs
  fly(position, target, duration = 1400) {
    this.settle?.();
    this.settle = null;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce || duration === 0) {
      this.camera.position.copy(position);
      this.controls.target.copy(target);
      this.tween = null;
      return Promise.resolve();
    }
    const p0 = this.camera.position.clone();
    const t0 = this.controls.target.clone();
    // lift the path so a long flight arcs over the ranges instead of through them
    const lift = p0.distanceTo(position) * 0.25;
    const start = performance.now();
    return new Promise((resolve) => {
      this.settle = resolve;
      this.tween = () => {
        const k = Math.min((performance.now() - start) / duration, 1);
        const e = 1 - Math.pow(1 - k, 3);
        this.camera.position.lerpVectors(p0, position, e);
        this.camera.position.y += Math.sin(Math.PI * e) * lift;
        this.controls.target.lerpVectors(t0, target, e);
        if (k === 1) {
          this.tween = null;
          this.settle = null;
          resolve();
        }
      };
    });
  }

  project(x, y, z) {
    const v = new THREE.Vector3(x, y * this.uniforms.uExag.value, z).project(this.camera);
    const el = this.canvas;
    return {
      x: (v.x * 0.5 + 0.5) * el.clientWidth,
      y: (-v.y * 0.5 + 0.5) * el.clientHeight,
      visible: v.z < 1 && Math.abs(v.x) < 1.05 && Math.abs(v.y) < 1.05,
    };
  }

  // metres per css pixel at the orbit target, for the scale bar
  metresPerPixel() {
    const d = this.camera.position.distanceTo(this.controls.target);
    const h = 2 * d * Math.tan(THREE.MathUtils.degToRad(this.camera.fov / 2));
    return h / this.canvas.clientHeight;
  }

  // compass bearing the camera looks toward, 0 = north
  heading() {
    const dx = this.controls.target.x - this.camera.position.x;
    const dz = this.controls.target.z - this.camera.position.z;
    return (THREE.MathUtils.radToDeg(Math.atan2(dx, -dz)) + 360) % 360;
  }
}

function skirtGeometry(dem, widthM, depthM) {
  const { width: w, height: h, heights } = dem;
  const floor = dem.min - Math.max(150, (dem.max - dem.min) * 0.12);
  const pos = [];
  const edge = (i0, j0, di, dj, n) => {
    for (let k = 0; k < n - 1; k++) {
      const a = [i0 + di * k, j0 + dj * k];
      const b = [i0 + di * (k + 1), j0 + dj * (k + 1)];
      const pa = [(a[0] / (w - 1) - 0.5) * widthM, heights[a[1] * w + a[0]], (a[1] / (h - 1) - 0.5) * depthM];
      const pb = [(b[0] / (w - 1) - 0.5) * widthM, heights[b[1] * w + b[0]], (b[1] / (h - 1) - 0.5) * depthM];
      pos.push(...pa, pa[0], floor, pa[2], ...pb, ...pb, pa[0], floor, pa[2], pb[0], floor, pb[2]);
    }
  };
  edge(0, 0, 1, 0, w);
  edge(0, h - 1, 1, 0, w);
  edge(0, 0, 0, 1, h);
  edge(w - 1, 0, 0, 1, h);
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  return g;
}
