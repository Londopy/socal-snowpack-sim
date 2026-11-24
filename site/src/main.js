import "@fontsource/barlow/400.css";
import "@fontsource/barlow/500.css";
import "@fontsource/barlow/600.css";
import "@fontsource/barlow-condensed/500.css";
import "@fontsource/barlow-condensed/600.css";
import "./style.css";
import * as THREE from "three";
import { Scene } from "./scene.js";
import { loadHeights, loadImage, heightAt } from "./terrain.js";
import { stitch } from "./imagery.js";
import { Winter, PROBLEMS } from "./winter.js";
import { Roses } from "./roses.js";
import { Strip, weatherLine } from "./strip.js";
import { renderFindings } from "./findings.js";
import { aboutHTML } from "./about.js";
import { Tour } from "./tour.js";
import { sunAt, clockLabel } from "./sun.js";

const BASE = import.meta.env.BASE_URL;
const R = 6378137;
const FT = 3.28084;
const REGION_EXAG = 2.2;
const PEAK_EXAG = 1.0;
const $ = (id) => document.getElementById(id);

const LAYERS = [
  { key: "relief", name: "Painted relief", sw: "linear-gradient(135deg, #d9d09c 0 55%, #5d6f8f 55%)" },
  { key: "imagery", name: "Satellite", hint: "USGS National Map imagery", sw: "linear-gradient(135deg, #5d6248 0 40%, #9a9478 40% 70%, #3f4733 70%)" },
  { key: "topo", name: "USGS topo", hint: "USGS National Map topo", sw: "repeating-linear-gradient(160deg, #f4f1e6 0 3px, #b07a4a 3px 4px)" },
  { key: "lidar", name: "Lidar hillshade", hint: "USGS 3DEP, 1 m lidar where flown. Open a peak to see it.", peakOnly: true, sw: "linear-gradient(135deg, #f2f2ee 0 45%, #3a3d48 45%)" },
  { key: "slope", name: "Slope angle", sw: "linear-gradient(90deg, #f6e58d 0 25%, #f0932b 25% 50%, #d63031 50% 75%, #6c1d6f 75%)" },
  { key: "aspect", name: "Aspect", sw: "conic-gradient(#e3a46a, #a6c36f, #6fb7a8, #8f8fd0, #e3a46a)" },
];

const HATCH = {
  storm: "repeating-linear-gradient(45deg, var(--p-storm) 0 2px, transparent 2px 6px)",
  wind: "repeating-linear-gradient(-45deg, var(--p-wind) 0 2px, transparent 2px 6px)",
  wet: "radial-gradient(circle, var(--p-wet) 1.6px, transparent 2px) 0 0 / 6px 6px",
  persistent: "repeating-linear-gradient(0deg, var(--p-persistent) 0 2px, transparent 2px 6px)",
};
const OVERPRINTS = [
  { key: "off", name: "None" },
  { key: "all", name: "Main problem", sw: "conic-gradient(var(--p-storm) 0 25%, var(--p-wind) 0 50%, var(--p-wet) 0 75%, var(--p-persistent) 0)" },
  ...Object.entries(PROBLEMS).map(([key, name]) => ({ key, name, sw: HATCH[key] })),
  { key: "freeze", name: "Freeze-thaw", sw: "repeating-linear-gradient(45deg, var(--ink) 0 1px, transparent 1px 4px), repeating-linear-gradient(-45deg, var(--ink) 0 1px, transparent 1px 4px)" },
];

const state = { peak: null, layer: "relief", over: "all", snow: true, winter: "typical", day: null };
let meta;
let winters;
let model;
let scene;
let roses;
let strip;
let tour;
let current;
let loadToken = 0;
let abort = null;
const texCache = new Map();
const markers = new Map();

function merc(lat, lon) {
  return [R * THREE.MathUtils.degToRad(lon), R * Math.log(Math.tan(Math.PI / 4 + THREE.MathUtils.degToRad(lat) / 2))];
}

function readHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  if (h.has("p") && meta.peaks.some((p) => p.slug === h.get("p"))) state.peak = h.get("p");
  if (LAYERS.some((l) => l.key === h.get("l"))) state.layer = h.get("l");
  if (OVERPRINTS.some((o) => o.key === h.get("o"))) state.over = h.get("o");
  if (h.has("s")) state.snow = h.get("s") !== "0";
  if (Object.hasOwn(winters, h.get("w") ?? "")) state.winter = h.get("w");
  const d = parseInt(h.get("d"), 10);
  if (d >= 0 && d < meta.days) state.day = d;
}

let hashTimer = null;
function writeHash() {
  if (hashTimer) return;
  hashTimer = setTimeout(() => {
    hashTimer = null;
    const h = new URLSearchParams();
    if (state.peak) h.set("p", state.peak);
    h.set("l", state.layer);
    h.set("o", state.over);
    if (!state.snow) h.set("s", "0");
    h.set("w", state.winter);
    h.set("d", state.day);
    history.replaceState(null, "", `#${h}`);
  }, 300);
}

function status(text, error = false) {
  const s = $("status");
  s.textContent = text;
  s.classList.toggle("error", error);
}

async function getJSON(name) {
  const res = await fetch(`${BASE}data/${name}`);
  if (!res.ok) throw new Error(`data/${name} answered ${res.status}`);
  return res.json();
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function applyPaper() {
  scene.setPaper(cssVar("--paper"), cssVar("--side"), cssVar("--ink"));
}


function buildIndex() {
  const list = $("index-list");
  const areas = new Map();
  for (const p of meta.peaks) {
    if (!areas.has(p.area)) areas.set(p.area, []);
    areas.get(p.area).push(p);
  }
  for (const [area, peaks] of areas) {
    const h = document.createElement("h3");
    h.textContent = area;
    const ul = document.createElement("ul");
    for (const p of peaks) {
      const li = document.createElement("li");
      const b = document.createElement("button");
      b.type = "button";
      b.dataset.slug = p.slug;
      b.innerHTML = `<span>${p.name}</span><span>${p.stats.summit_ft.toLocaleString()}</span>`;
      b.addEventListener("click", () => goPeak(p.slug));
      b.addEventListener("pointerenter", () => hoverPeak(p.slug, true));
      b.addEventListener("pointerleave", () => hoverPeak(p.slug, false));
      li.append(b);
      ul.append(li);
    }
    list.append(h, ul);
  }
  $("region-link").addEventListener("click", () => goRegion());
}

function hoverPeak(slug, on) {
  markers.get(slug)?.el.classList.toggle("hover", on);
  document.querySelector(`.index button[data-slug="${slug}"]`)?.classList.toggle("hover", on);
}

function option(group, item, checked, onChange) {
  const label = document.createElement("label");
  label.className = "opt";
  label.innerHTML = `<input type="radio" name="${group}" value="${item.key}"><span class="sw"></span><span class="name">${item.name}</span>`;
  if (item.hint) label.title = item.hint;
  const input = label.querySelector("input");
  input.checked = checked;
  if (item.sw) label.querySelector(".sw").style.background = item.sw;
  input.addEventListener("change", () => onChange(item.key));
  return label;
}

function buildControls() {
  const layers = $("layers");
  for (const l of LAYERS) layers.append(option("layer", l, l.key === state.layer, setLayer));
  const ov = $("overprints");
  for (const o of OVERPRINTS) ov.append(option("over", o, o.key === state.over, setOverprint));
  $("snow").checked = state.snow;
  $("snow").addEventListener("change", (e) => {
    state.snow = e.target.checked;
    scene.setSnow(state.snow);
    writeHash();
  });
  const wb = $("winters");
  for (const w of Object.values(winters)) {
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("role", "radio");
    b.dataset.key = w.key;
    b.textContent = w.label.replace(" winter", "");
    b.title = `${w.label}: ${w.raw.percentile}th percentile snowfall of 400 simulated winters`;
    b.addEventListener("click", () => setWinter(w.key));
    wb.append(b);
  }
  $("play").addEventListener("click", () => (playing ? stop() : play()));
  $("speed").addEventListener("change", (e) => (speed = Number(e.target.value)));

  for (const [tab, target] of [["tab-index", "index"], ["tab-legend", "legend"]]) {
    $(tab).addEventListener("click", () => setTab(target));
  }
  setTab("legend");
}

function setTab(name) {
  $("sheet").dataset.tab = name;
  $("tab-index").setAttribute("aria-selected", name === "index");
  $("tab-legend").setAttribute("aria-selected", name === "legend");
}

function syncControls() {
  for (const i of document.querySelectorAll('input[name="layer"]')) {
    i.checked = i.value === state.layer;
    i.disabled = !state.peak && LAYERS.find((l) => l.key === i.value).peakOnly;
  }
  for (const i of document.querySelectorAll('input[name="over"]')) i.checked = i.value === state.over;
  $("snow").checked = state.snow;
  for (const b of document.querySelectorAll("#winters button")) b.setAttribute("aria-checked", b.dataset.key === state.winter);
  for (const b of document.querySelectorAll(".index li button")) b.setAttribute("aria-current", b.dataset.slug === state.peak);
  $("region-link").setAttribute("aria-current", !state.peak);
}


function finishTexture(tex, colorSpace) {
  tex.colorSpace = colorSpace;
  tex.flipY = false;
  tex.anisotropy = scene.renderer.capabilities.getMaxAnisotropy();
  tex.needsUpdate = true;
  return tex;
}

async function lidarTexture(slug, signal) {
  const key = `${slug}:lidar`;
  if (!texCache.has(key)) {
    const img = await loadImage(`${BASE}data/lidar/${slug}.jpg`, signal);
    texCache.set(key, finishTexture(new THREE.Texture(img), THREE.NoColorSpace));
  }
  return texCache.get(key);
}

// textures are cached per place; the cache key and the bbox both come from the place
// on screen, so a slow download can never land on the wrong one
async function texture(kind) {
  const place = current;
  if (kind === "lidar") return lidarTexture(place.id, abort.signal);
  const key = `${place.id}:${kind}`;
  if (texCache.has(key)) return texCache.get(key);
  const bbox = place.bbox;
  const region = place.kind === "region";
  const w = region ? 2560 : 2048;
  const h = region ? Math.round((w * (bbox[3] - bbox[1])) / (bbox[2] - bbox[0])) : 2048;
  const res = await stitch(kind, bbox, region ? 11 : 15, w, h, abort.signal);
  if (res.missing) status(`${res.missing} of ${res.total} USGS map tiles didn't load, so parts of this layer are blank.`, true);
  const tex = finishTexture(new THREE.CanvasTexture(res.canvas), THREE.SRGBColorSpace);
  texCache.set(key, tex);
  return tex;
}

// peak textures are 2048 px each; let them go when the peak is left
function dropTextures(place) {
  if (!place || place.kind !== "peak") return;
  for (const [key, tex] of texCache) {
    if (!key.startsWith(`${place.id}:`)) continue;
    tex.dispose();
    texCache.delete(key);
  }
}

const LAYER_SOURCE = { imagery: "USGS satellite imagery", topo: "the USGS topo map", lidar: "the 3DEP lidar hillshade" };

async function setLayer(key) {
  state.layer = key;
  scene.setLayer(key);
  writeHash();
  syncControls();
  if (!LAYER_SOURCE[key]) {
    scene.setTexture(null);
    return;
  }
  const token = loadToken;
  status(`Loading ${LAYER_SOURCE[key]}...`);
  try {
    const place = current;
    const tex = await texture(key);
    if (token !== loadToken || state.layer !== key || place !== current) return;
    scene.setTexture(tex);
    if (!$("status").classList.contains("error")) status("");
  } catch (err) {
    if (err.name === "AbortError") return;
    scene.setTexture(null);
    status(`Couldn't load ${LAYER_SOURCE[key]} (${err.message}). Showing painted relief instead.`, true);
  }
}

function setOverprint(key) {
  state.over = key;
  scene.setOverprint(key);
  $("clock").hidden = key !== "freeze";
  if (key !== "freeze") setClock(false);
  writeHash();
  syncControls();
}


let playing = false;
let speed = 5;
let lastTick = 0;
let acc = 0;

function viewBands() {
  if (!state.peak) return 5;
  return meta.band_edges_m.filter((e, i) => i < 5 && e < summitM()).length;
}

function setWinter(key) {
  state.winter = key;
  strip.setWinter(winters[key], viewBands());
  setDay(state.day);
  syncControls();
}

function setDay(d) {
  const w = winters[state.winter];
  state.day = Math.max(0, Math.min(w.days - 1, d));
  const [A, B] = w.textures(state.day);
  scene.setGrid(A, B);
  $("dayline").innerHTML = weatherLine(w, state.day);
  if (clock.on) scene.setSun(sunAt(state.day, clock.hour));
  roses.update(w, state.day, state.peak ? summitM() : null);
  strip.setDay(state.day);
  writeHash();
}

function summitM() {
  return peakBy(state.peak).stats.summit_ft / FT;
}

function play() {
  if (state.day >= meta.days - 1) setDay(0);
  clock.running = false;
  clockIcon();
  playing = true;
  acc = 0;
  lastTick = performance.now();
  $("play-icon").setAttribute("d", "M3 2 H6.5 V14 H3 Z M9.5 2 H13 V14 H9.5 Z");
  $("play").setAttribute("aria-label", "Pause winter");
}

function stop() {
  playing = false;
  $("play-icon").setAttribute("d", "M4 2 L13 8 L4 14 Z");
  $("play").setAttribute("aria-label", "Play winter");
}

let lastFrame = performance.now();
function tick() {
  const t = performance.now();
  tickClock(Math.min((t - lastFrame) / 1000, 0.1));
  lastFrame = t;
  if (!playing) return;
  const now = performance.now();
  // cap one frame's step so a stalled or hidden tab doesn't jump weeks ahead
  acc += Math.min((now - lastTick) / 1000, 0.25) * speed;
  lastTick = now;
  if (acc >= 1) {
    const step = Math.floor(acc);
    acc -= step;
    if (state.day + step >= meta.days - 1) {
      setDay(meta.days - 1);
      stop();
    } else setDay(state.day + step);
  }
}


const clock = { on: false, running: false, hour: 7 };
const CLOCK_HOURS_PER_SECOND = 2.4;

function setClock(on) {
  clock.on = on;
  $("clock-toggle").setAttribute("aria-pressed", on);
  $("clock-body").hidden = !on;
  if (!on) {
    clock.running = false;
    clockIcon();
  }
  scene.setSun(on ? sunAt(state.day, clock.hour) : null);
}

function setHour(h) {
  clock.hour = h;
  $("clock-hour").value = h;
  $("clock-label").textContent = clockLabel(h);
  if (clock.on) scene.setSun(sunAt(state.day, h));
}

function clockIcon() {
  $("clock-icon").setAttribute("d", clock.running ? "M3 2 H6.5 V14 H3 Z M9.5 2 H13 V14 H9.5 Z" : "M4 2 L13 8 L4 14 Z");
  $("clock-play").setAttribute("aria-label", clock.running ? "Stop the clock" : "Run the clock");
}

// the clock runs dawn to dusk, then rolls on to the next simulated day
function tickClock(dt) {
  if (!clock.running) return;
  let h = clock.hour + dt * CLOCK_HOURS_PER_SECOND;
  if (h > 21) {
    h = 5;
    if (state.day >= meta.days - 1) {
      clock.running = false;
      clockIcon();
    } else setDay(state.day + 1);
  }
  setHour(h);
}

function buildClock() {
  $("clock-toggle").addEventListener("click", () => setClock(!clock.on));
  $("clock-hour").addEventListener("input", (e) => setHour(Number(e.target.value)));
  $("clock-play").addEventListener("click", () => {
    clock.running = !clock.running;
    if (clock.running) stop();
    clockIcon();
  });
  $("clock").hidden = state.over !== "freeze";
  setHour(clock.hour);
}


function peakBy(slug) {
  return meta.peaks.find((p) => p.slug === slug);
}

function regionPlace(dem) {
  const r = meta.region;
  const k = r.size_m[0] / (r.bbox[2] - r.bbox[0]);
  const cx = (r.bbox[0] + r.bbox[2]) / 2;
  const cy = (r.bbox[1] + r.bbox[3]) / 2;
  return {
    kind: "region",
    id: "region",
    bbox: r.bbox,
    dem,
    exag: REGION_EXAG,
    width: r.size_m[0],
    depth: r.size_m[1],
    pos(lat, lon) {
      const [mx, my] = merc(lat, lon);
      const u = (mx - r.bbox[0]) / (r.bbox[2] - r.bbox[0]);
      const v = (r.bbox[3] - my) / (r.bbox[3] - r.bbox[1]);
      return new THREE.Vector3((mx - cx) * k, heightAt(dem, u, v), -(my - cy) * k);
    },
  };
}

function peakPlace(p, dem) {
  const b = p.bbox;
  const k = p.size_m / (b[2] - b[0]);
  const cx = (b[0] + b[2]) / 2;
  const cy = (b[1] + b[3]) / 2;
  return {
    kind: "peak",
    id: p.slug,
    bbox: b,
    dem,
    exag: PEAK_EXAG,
    width: p.size_m,
    depth: p.size_m,
    pos(lat, lon) {
      const [mx, my] = merc(lat, lon);
      const u = (mx - b[0]) / (b[2] - b[0]);
      const v = (b[3] - my) / (b[3] - b[1]);
      if (u < 0.02 || u > 0.98 || v < 0.02 || v > 0.98) return null;
      return new THREE.Vector3((mx - cx) * k, heightAt(dem, u, v), -(my - cy) * k);
    },
  };
}

// pull back far enough that the whole width fits, whatever shape the frame is
function fitDistance(width, depth) {
  const cam = scene.camera;
  const v = THREE.MathUtils.degToRad(cam.fov / 2);
  const h = Math.atan(Math.tan(v) * cam.aspect);
  return Math.max(width / 2 / Math.tan(h), depth / 2 / Math.tan(v));
}

// frame the 34 peaks, not the padded data box; a tall phone frame looks east so the
// long east-west line of ranges runs up the screen
function overviewCamera(place) {
  const pts = meta.peaks.map((p) => place.pos(p.lat, p.lon));
  const xs = pts.map((p) => p.x);
  const zs = pts.map((p) => p.z);
  const w = Math.max(...xs) - Math.min(...xs);
  const d = Math.max(...zs) - Math.min(...zs);
  const target = new THREE.Vector3((Math.max(...xs) + Math.min(...xs)) / 2, 900 * place.exag, (Math.max(...zs) + Math.min(...zs)) / 2);
  const tall = scene.camera.aspect < 1;
  const dir = tall ? new THREE.Vector3(-0.55, 1.5, 0.08) : new THREE.Vector3(0, 1.6, 0.5);
  const dist = tall ? fitDistance(d * 1.35, w * 1.12) : fitDistance(w * 1.16, d * 1.65);
  return { pos: target.clone().add(dir.normalize().multiplyScalar(dist)), target };
}

function peakCamera(place, p) {
  const top = place.pos(p.lat, p.lon);
  const target = new THREE.Vector3(top.x, (top.y - 380) * place.exag, top.z);
  const tall = scene.camera.aspect < 1;
  const pos = target.clone().add(tall ? new THREE.Vector3(-1100, 8800, 5600) : new THREE.Vector3(-1700, 3800, 7400));
  return { pos, target };
}

function placeMarkers() {
  const box = $("markers");
  box.innerHTML = "";
  markers.clear();
  const major = new Set();
  if (current.kind === "region") {
    const best = new Map();
    for (const p of meta.peaks) if (!best.has(p.area) || best.get(p.area).stats.summit_ft < p.stats.summit_ft) best.set(p.area, p);
    for (const p of best.values()) major.add(p.slug);
  }
  for (const p of meta.peaks) {
    const at = current.pos(p.lat, p.lon);
    if (!at) continue;
    const b = document.createElement("button");
    b.type = "button";
    const isMajor = current.kind === "peak" || major.has(p.slug);
    b.className = `marker${isMajor ? "" : " minor"}`;
    b.dataset.rank = (p.slug === state.peak ? 3e4 : 0) + (isMajor ? 2e4 : 0) + p.stats.summit_ft;
    const short = p.name.replace(" (San Antonio)", "");
    b.innerHTML = `<span>${short}</span>`;
    b.setAttribute("aria-label", `${p.name}, ${p.stats.summit_ft.toLocaleString()} ft`);
    if (p.slug === state.peak) b.setAttribute("aria-current", "true");
    b.addEventListener("click", () => goPeak(p.slug));
    b.addEventListener("pointerenter", () => hoverPeak(p.slug, true));
    b.addEventListener("pointerleave", () => hoverPeak(p.slug, false));
    box.append(b);
    markers.set(p.slug, { el: b, at });
  }
}

// greedy label placement: higher-ranked peaks place first; each label tries above its
// triangle, then to the right, then to the left, and stays hidden (until hovered or
// focused) only if all three would hit another label or a summit triangle
function updateMarkers() {
  const shown = [];
  for (const m of markers.values()) {
    const s = scene.project(m.at.x, m.at.y, m.at.z);
    m.el.style.display = s.visible ? "" : "none";
    m.el.style.transform = `translate(${s.x}px, ${s.y}px) translate(-50%, -100%)`;
    m.s = s;
    if (s.visible) shown.push(m);
  }
  const boxes = shown.map((m) => ({ x0: m.s.x - 6, x1: m.s.x + 6, y0: m.s.y - 10, y1: m.s.y }));
  // the map furniture in the frame counts as taken ground too
  const frame = $("frame").getBoundingClientRect();
  for (const id of ["scale", "exag", "sheet-note", "north"]) {
    const r = $(id).getBoundingClientRect();
    if (r.width) boxes.push({ x0: r.left - frame.left, x1: r.right - frame.left, y0: r.top - frame.top, y1: r.bottom - frame.top });
  }
  const dayTop = $("dayline").parentElement.offsetTop;
  const inside = (r) => r.x0 >= 2 && r.x1 <= frame.width - 2 && r.y0 >= 2 && r.y1 <= dayTop - 2;
  const triangles = shown.length;
  const overlaps = (r, from) => boxes.some((b, i) => i >= from && r.x0 < b.x1 && r.x1 > b.x0 && r.y0 < b.y1 && r.y1 > b.y0);
  const hit = (r) => !inside(r) || overlaps(r, 0);
  // an area's main peak may sit over a neighbour's triangle rather than lose its name
  const hitLabels = (r) => !inside(r) || overlaps(r, triangles);
  shown.sort((a, b) => b.el.dataset.rank - a.el.dataset.rank);
  for (const m of shown) {
    m.label ||= m.el.querySelector("span");
    m.w ||= m.label.offsetWidth;
    m.h ||= m.label.offsetHeight;
    const { x, y } = m.s;
    const side = m.w / 2 + 9;
    const spots = [
      { dx: 0, dy: 0, r: { x0: x - m.w / 2 - 2, x1: x + m.w / 2 + 2, y0: y - 12 - m.h, y1: y - 11 } },
      { dx: side, dy: m.h - 1, r: { x0: x + 7, x1: x + 9 + m.w, y0: y - m.h - 1, y1: y + 1 } },
      { dx: -side, dy: m.h - 1, r: { x0: x - 9 - m.w, x1: x - 7, y0: y - m.h - 1, y1: y + 1 } },
      ...[16, 32].map((up) => ({
        dx: 0,
        dy: -up,
        lead: up,
        r: { x0: x - m.w / 2 - 2, x1: x + m.w / 2 + 2, y0: y - 12 - m.h - up, y1: y - 11 - up },
        line: { x0: x - 1, x1: x + 1, y0: y - 11 - up, y1: y - 11 },
      })),
    ];
    const major = m.el.dataset.rank >= 2e4;
    const spot =
      spots.find((c) => !hit(c.r) && !(c.line && hit(c.line))) ||
      (major ? spots.find((c) => !hitLabels(c.r) && !(c.line && hitLabels(c.line))) : null);
    m.el.classList.toggle("nolabel", !spot);
    m.label.style.transform = spot ? `translate(${spot.dx}px, ${spot.dy}px)` : "";
    m.el.style.setProperty("--lead", `${spot?.lead || 0}px`);
    if (spot) boxes.push(spot.r);
    if (spot?.line) boxes.push(spot.line);
  }
}

const NICE = [50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000, 25000, 50000];
function updateScale() {
  const mpp = scene.metresPerPixel();
  const want = mpp * 110;
  const len = NICE.reduce((a, b) => (Math.abs(b - want) < Math.abs(a - want) ? b : a));
  $("scale").querySelector(".bar").style.width = `${len / mpp}px`;
  $("scale-label").textContent = len >= 1000 ? `${len / 1000} km` : `${len} m`;
  $("north").style.transform = `rotate(${-scene.heading()}deg)`;
}

async function showPlace(place, cam) {
  scene.setTerrain(place.dem, place.width, place.depth, place.exag);
  if (current?.id !== place.id) dropTextures(current);
  current = place;
  placeMarkers();
  $("exag").textContent = place.exag === 1 ? "True scale, no vertical exaggeration" : `Vertical exaggeration ${place.exag}x`;
  scene.setLidar(null);
  scene.setTexture(null);
  scene.uniforms.uHatch.value = 8;
  if (cam) {
    scene.camera.position.copy(cam.pos);
    scene.controls.target.copy(cam.target);
  }
}

let regionDem;
async function goRegion(fly = true) {
  const token = ++loadToken;
  abort?.abort();
  abort = new AbortController();
  stop();
  status("");
  try {
    regionDem ||= await loadHeights(`${BASE}data/terrain/region.png`, abort.signal);
  } catch (err) {
    if (err.name !== "AbortError") status(`Couldn't load the terrain for the three ranges (${err.message}).`, true);
    return;
  }
  if (token !== loadToken) return;
  const from = state.peak ? peakBy(state.peak) : null;
  const fromView = scene.view();
  state.peak = null;
  if (state.layer === "lidar") state.layer = "relief";
  const place = regionPlace(regionDem);
  let start = null;
  if (from && fly && current?.kind === "peak") {
    // keep the camera where it was relative to the summit, then pull back
    const top = place.pos(from.lat, from.lon);
    const old = current.pos(from.lat, from.lon);
    const off = fromView.position.clone().sub(fromView.target);
    const target = new THREE.Vector3(top.x, (old.y - 380) * place.exag, top.z);
    start = { pos: target.clone().add(off), target };
  }
  await showPlace(place, start || overviewCamera(place));
  setTitle();
  setLayer(state.layer);
  strip.setWinter(winters[state.winter], viewBands());
  setDay(state.day);
  syncControls();
  const cam = overviewCamera(place);
  scene.fly(cam.pos, cam.target, start ? 1600 : 0);
}

async function goPeak(slug) {
  const p = peakBy(slug);
  if (!p) return;
  const token = ++loadToken;
  abort?.abort();
  abort = new AbortController();
  status(`Loading ${p.name}...`);
  const signal = abort.signal;
  const demP = loadHeights(`${BASE}data/terrain/${slug}.png`, signal);
  let approach = null;
  if (current?.kind === "region") {
    const at = current.pos(p.lat, p.lon);
    const target = new THREE.Vector3(at.x, at.y * current.exag, at.z);
    approach = scene.fly(target.clone().add(new THREE.Vector3(-1800, 9000, 12000)), target, 1300);
  }
  let dem;
  try {
    [dem] = await Promise.all([demP, approach]);
  } catch (err) {
    if (err.name !== "AbortError") status(`Couldn't load the terrain for ${p.name} (${err.message}).`, true);
    return;
  }
  if (token !== loadToken) return;
  const fromRegion = current?.kind === "region";
  const fromView = scene.view();
  state.peak = slug;
  const place = peakPlace(p, dem);
  let start = null;
  if (fromRegion) {
    const off = fromView.position.clone().sub(fromView.target);
    const top = place.pos(p.lat, p.lon);
    const target = new THREE.Vector3(top.x, top.y * place.exag, top.z);
    start = { pos: target.clone().add(off), target };
  }
  const cam = peakCamera(place, p);
  await showPlace(place, start || cam);
  status("");
  setTitle();
  try {
    const lidar = await lidarTexture(slug, signal);
    if (token !== loadToken) return;
    scene.setLidar(lidar);
  } catch (err) {
    if (err.name === "AbortError") return;
    status(`Couldn't load the lidar hillshade for ${p.name} (${err.message}). The relief is drawn without its fine detail.`, true);
  }
  setLayer(state.layer);
  strip.setWinter(winters[state.winter], viewBands());
  setDay(state.day);
  renderFacts(p);
  syncControls();
  await scene.fly(cam.pos, cam.target, start ? 900 : 0);
}

function setTitle() {
  const p = state.peak && peakBy(state.peak);
  if (!p) {
    $("sheet-title").textContent = "SoCal Snowpack Sim";
    $("sheet-sub").textContent = `${meta.peaks.length} ski-touring peaks in the San Gabriel, San Bernardino and San Jacinto Mountains. Real terrain, simulated winters. Pick a peak to fly in.`;
    $("sheet-note").textContent = `${meta.peaks.length} peaks · 3 ranges`;
    $("facts").hidden = true;
    document.title = "SoCal Snowpack Sim: 34 peaks, simulated winters, 3D terrain";
    return;
  }
  const i = meta.peaks.indexOf(p) + 1;
  $("sheet-note").textContent = `Sheet ${i} of ${meta.peaks.length} · ${p.area}`;
  $("sheet-title").textContent = p.name;
  $("sheet-sub").textContent = `${p.stats.summit_ft.toLocaleString()} ft · ${p.stats.pct_30_45}% of the steep zone around the summit is 30-45° · steep terrain mostly faces ${p.stats.dominant_aspect}`;
  document.title = `${p.name} · SoCal Snowpack Sim`;
}

function steepRose(shares) {
  const max = Math.max(...shares);
  const paths = shares
    .map((s, a) => {
      const r = 6 + (s / max) * 34;
      const t0 = ((a * 45 - 20 - 90) * Math.PI) / 180;
      const t1 = ((a * 45 + 20 - 90) * Math.PI) / 180;
      return `<path d="M0 0 L${(r * Math.cos(t0)).toFixed(1)} ${(r * Math.sin(t0)).toFixed(1)} A${r} ${r} 0 0 1 ${(r * Math.cos(t1)).toFixed(1)} ${(r * Math.sin(t1)).toFixed(1)} Z" fill="var(--ink)" fill-opacity="${(0.25 + 0.6 * (s / max)).toFixed(2)}"><title>${["N", "NE", "E", "SE", "S", "SW", "W", "NW"][a]}: ${s}%</title></path>`;
    })
    .join("");
  return `<svg viewBox="-44 -44 88 88" role="img" aria-label="Aspect of the 30-45 degree terrain">${paths}<text x="0" y="-38" font-size="9" text-anchor="middle" fill="var(--ink-2)">N</text></svg>`;
}

function renderFacts(p) {
  const s = p.stats;
  $("facts").hidden = false;
  $("facts").innerHTML = `
    <h2>${p.name.replace(" (San Antonio)", "")} in 400 winters</h2>
    <div class="steep">${steepRose(s.aspect_share_of_30_45_pct)}<span>Which way the 30-45° slopes near the summit face. ${s.lee_share_pct}% face N, NE or E, the usual lee of storm winds.</span></div>
    <dl>
      <dt>Storm slab days</dt><dd>${s.model_days_storm}</dd>
      <dt>Wind slab days</dt><dd>${s.model_days_wind}</dd>
      <dt>Wet, share of snow days</dt><dd>${s.wet_share_of_snow_days_pct}%</dd>
      <dt>Persistent slab days</dt><dd>${s.model_days_persistent}</dd>
      <dt>Freeze-thaw cycles</dt><dd>${s.model_days_ft}</dd>
      <dt>Snow days with a cycle</dt><dd>${s.freeze_thaw_share_of_snow_days_pct}%</dd>
      <dt>Snow days with refrozen ice</dt><dd>${s.ice_share_of_snow_days_pct}%</dd>
      <dt>Snow-cover days</dt><dd>${s.model_days_snow}</dd>
    </dl>
    <p class="note">Averages per simulated winter over this peak's steep terrain (30° and up, within 1.5 km of the summit and no more than 750 m below it), weighted by its real aspects and elevations.</p>`;
}


function openPanel(id, button) {
  for (const p of ["findings", "about"]) {
    $(p).hidden = p !== id;
    $(`open-${p}`).setAttribute("aria-pressed", p === id);
  }
  const panel = $(id);
  if (id === "findings" && !panel.dataset.ready) {
    renderFindings($("findings-body"), model, meta, $("tip"), (slug) => {
      closePanels();
      goPeak(slug);
    });
    panel.dataset.ready = "1";
  }
  if (id === "about" && !panel.dataset.ready) {
    $("about-body").innerHTML = aboutHTML(meta.peaks.length);
    panel.dataset.ready = "1";
  }
  panel.returnFocus = button;
  panel.querySelector("h2").setAttribute("tabindex", "-1");
  panel.querySelector("h2").focus();
}

function closePanels() {
  for (const p of ["findings", "about"]) {
    if ($(p).hidden) continue;
    $(p).hidden = true;
    $(`open-${p}`).setAttribute("aria-pressed", "false");
    $(p).returnFocus?.focus();
  }
}

function keys(e) {
  if (e.altKey || e.ctrlKey || e.metaKey) return;
  if (e.target.closest("input, select, textarea")) return;
  if (e.key === "Escape") {
    closePanels();
    if (tour.active) tour.end();
    return;
  }
  if (!$("findings").hidden || !$("about").hidden) return;
  const n = Number(e.key);
  if (n >= 1 && n <= LAYERS.length) {
    const l = LAYERS[n - 1];
    if (!l.peakOnly || state.peak) setLayer(l.key);
  } else if (e.key === " " && !e.target.closest("button")) {
    e.preventDefault();
    playing ? stop() : play();
  } else if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
    if (e.target.closest(".opt, button") && !e.target.closest("#timeline")) return;
    e.preventDefault();
    stop();
    setDay(state.day + (e.key === "ArrowRight" ? 1 : -1) * (e.shiftKey ? 7 : 1));
  }
}


function biggestStormDay(w) {
  let best = 0;
  for (let d = 0; d < w.days; d++) if (w.w.precip_mm[d] > w.w.precip_mm[best]) best = d;
  return best;
}

async function boot() {
  try {
    [meta, model] = await Promise.all([getJSON("site.json"), getJSON("model.json")]);
    const raw = await getJSON("winters.json");
    winters = Object.fromEntries(raw.map((r) => [r.key, new Winter(r, meta)]));
  } catch (err) {
    status(`Couldn't load the map data (${err.message}). Try reloading the page.`, true);
    return;
  }
  try {
    scene = new Scene($("map"));
  } catch (err) {
    $("nogl").hidden = false;
    $("nogl-reason").textContent = err.message;
    $("map").hidden = true;
    return;
  }
  applyPaper();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", applyPaper);
  readHash();
  if (state.day == null) state.day = biggestStormDay(winters[state.winter]);
  roses = new Roses($("roses"), $("tip"), meta, (a, b) => scene.setHighlight(a, b));
  strip = new Strip($("timeline"), $("tip"), (d) => {
    stop();
    setDay(d);
  });
  strip.setWinter(winters[state.winter]);
  setDay(state.day);
  buildIndex();
  buildControls();
  scene.setOverprint(state.over);
  scene.setSnow(state.snow);
  scene.setLayer(state.layer);
  buildClock();
  scene.onFrame(() => {
    tick();
    updateMarkers();
    updateScale();
  });
  $("timeline").addEventListener("keydown", (e) => {
    if (e.key === "Home") setDay(0);
    if (e.key === "End") setDay(meta.days - 1);
  });
  document.addEventListener("keydown", keys);
  const legend = $("legend");
  const fade = () => legend.classList.toggle("more", legend.scrollHeight - legend.scrollTop - legend.clientHeight > 4);
  legend.addEventListener("scroll", fade);
  new ResizeObserver(fade).observe($("legend-body"));
  $("open-findings").addEventListener("click", (e) => ($("findings").hidden ? openPanel("findings", e.currentTarget) : closePanels()));
  $("open-about").addEventListener("click", (e) => ($("about").hidden ? openPanel("about", e.currentTarget) : closePanels()));
  for (const b of document.querySelectorAll("[data-close]")) b.addEventListener("click", closePanels);
  tour = new Tour({
    winters,
    meta,
    model,
    go: async (step) => {
      stop();
      closePanels();
      state.winter = step.winter;
      state.day = step.day;
      state.snow = true;
      scene.setSnow(true);
      setOverprint(step.over);
      if (step.peak) {
        if (state.peak !== step.peak) await goPeak(step.peak);
      } else if (state.peak || !current) await goRegion();
      setLayer(step.layer || "relief");
      strip.setWinter(winters[step.winter], viewBands());
      setDay(step.day);
      syncControls();
    },
  });
  $("open-tour").addEventListener("click", () => tour.start());
  if (state.peak) await goPeak(state.peak);
  else await goRegion(false);
  syncControls();
}

boot();

