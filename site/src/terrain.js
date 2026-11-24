import * as THREE from "three";

export async function loadImage(url, signal) {
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`${url} answered ${res.status}`);
  return createImageBitmap(await res.blob());
}

function pixels(img) {
  const c = new OffscreenCanvas(img.width, img.height);
  const ctx = c.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(img, 0, 0);
  return ctx.getImageData(0, 0, img.width, img.height).data;
}

// terrarium encoding, same as the AWS tiles the Python side reads
export async function loadHeights(url, signal) {
  const img = await loadImage(url, signal);
  const px = pixels(img);
  const h = new Float32Array(img.width * img.height);
  let min = Infinity;
  let max = -Infinity;
  for (let i = 0; i < h.length; i++) {
    const v = px[i * 4] * 256 + px[i * 4 + 1] + px[i * 4 + 2] / 256 - 32768;
    h[i] = v;
    if (v < min) min = v;
    if (v > max) max = v;
  }
  return { heights: h, width: img.width, height: img.height, min, max };
}

// a plane in metres, x east, z south, y up; uv (0,0) is the north-west corner
export function terrainGeometry(dem, widthM, depthM) {
  const { width: w, height: h, heights } = dem;
  const geo = new THREE.PlaneGeometry(widthM, depthM, w - 1, h - 1);
  geo.rotateX(-Math.PI / 2);
  const pos = geo.attributes.position;
  for (let i = 0; i < pos.count; i++) pos.setY(i, heights[i]);
  const uv = geo.attributes.uv;
  for (let i = 0; i < uv.count; i++) uv.setY(i, 1 - uv.getY(i));
  geo.computeVertexNormals();
  geo.computeBoundingSphere();
  return geo;
}

export function heightAt(dem, u, v) {
  const x = Math.min(Math.max(u * (dem.width - 1), 0), dem.width - 1.001);
  const y = Math.min(Math.max(v * (dem.height - 1), 0), dem.height - 1.001);
  const x0 = Math.floor(x);
  const y0 = Math.floor(y);
  const fx = x - x0;
  const fy = y - y0;
  const H = dem.heights;
  const i = y0 * dem.width + x0;
  const a = H[i] * (1 - fx) + H[i + 1] * fx;
  const b = H[i + dem.width] * (1 - fx) + H[i + dem.width + 1] * fx;
  return a * (1 - fy) + b * fy;
}
