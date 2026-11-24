import { loadImage } from "./terrain.js";

const WORLD = 2 * Math.PI * 6378137;

export const BASEMAPS = {
  imagery: "https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/{z}/{y}/{x}",
  topo: "https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}",
};

export async function stitch(kind, bbox, zoom, width, height, signal) {
  const [x0, y0, x1, y1] = bbox;
  const scale = (256 * 2 ** zoom) / WORLD;
  const px0 = (x0 + WORLD / 2) * scale;
  const px1 = (x1 + WORLD / 2) * scale;
  const py0 = (WORLD / 2 - y1) * scale;
  const py1 = (WORLD / 2 - y0) * scale;
  const tx0 = Math.floor(px0 / 256);
  const tx1 = Math.floor(px1 / 256);
  const ty0 = Math.floor(py0 / 256);
  const ty1 = Math.floor(py1 / 256);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  const kx = width / (px1 - px0);
  const ky = height / (py1 - py0);
  const jobs = [];
  for (let ty = ty0; ty <= ty1; ty++) {
    for (let tx = tx0; tx <= tx1; tx++) {
      const url = BASEMAPS[kind].replace("{z}", zoom).replace("{x}", tx).replace("{y}", ty);
      jobs.push(
        loadImage(url, signal).then((img) => {
          ctx.drawImage(img, (tx * 256 - px0) * kx, (ty * 256 - py0) * ky, 256 * kx + 0.5, 256 * ky + 0.5);
        }),
      );
    }
  }
  const results = await Promise.allSettled(jobs);
  const failed = results.filter((r) => r.status === "rejected");
  if (signal?.aborted) throw new DOMException("aborted", "AbortError");
  if (failed.length === results.length) throw failed[0].reason;
  return { canvas, missing: failed.length, total: results.length };
}
