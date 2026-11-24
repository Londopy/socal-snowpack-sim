import { PROBLEMS } from "./winter.js";

const NS = "http://www.w3.org/2000/svg";
const MONTHS = new Map([["11", "Nov"], ["12", "Dec"], ["1", "Jan"], ["2", "Feb"], ["3", "Mar"], ["4", "Apr"]]);
const ASPECTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];

function el(tag, attrs = {}, parent) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  parent?.append(n);
  return n;
}

function text(parent, x, y, s, attrs = {}) {
  const t = el("text", { x, y, ...attrs }, parent);
  t.textContent = s;
  return t;
}

function card(parent, title, blurb, wide = false) {
  const c = document.createElement("section");
  c.className = `chart${wide ? " wide" : ""}`;
  c.innerHTML = `<h3>${title}</h3><p>${blurb}</p>`;
  parent.append(c);
  return c;
}

function tipper(tip) {
  return {
    show(e, html) {
      tip.innerHTML = html;
      tip.hidden = false;
      tip.style.left = `${Math.min(e.clientX + 14, innerWidth - 290)}px`;
      tip.style.top = `${e.clientY + 14}px`;
    },
    hide() {
      tip.hidden = true;
    },
  };
}

function yAxis(svg, x0, x1, y, ticks) {
  const g = el("g", { class: "axis" }, svg);
  for (const t of ticks) {
    el("line", { x1: x0, x2: x1, y1: y(t), y2: y(t) }, g);
    text(g, x0 - 6, y(t) + 4, t, { "text-anchor": "end" });
  }
}

function fadeChart(root, model, tip) {
  const c = card(
    root,
    "Danger spikes in storms and fades in days",
    "Average index after the last day of a storm, north and south slopes at 9,500-10,500 ft. It drops below the model's elevated line (0.45) about two to three days out.",
  );
  const W = 520;
  const H = 240;
  const m = { l: 36, r: 64, t: 10, b: 30 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Index by days after a storm, north vs south" }, c);
  const n = model.after_storm.N.length;
  const x = (d) => m.l + (d / (n - 1)) * (W - m.l - m.r);
  const y = (v) => H - m.b - (v / 1.2) * (H - m.t - m.b);
  yAxis(svg, m.l, W - m.r, y, [0, 0.3, 0.6, 0.9, 1.2]);
  const ax = el("g", { class: "axis" }, svg);
  for (let d = 0; d < n; d++) text(ax, x(d), H - 10, d === 0 ? "storm" : `+${d}`, { "text-anchor": "middle" });
  el("line", { class: "thresh", x1: m.l, x2: W - m.r, y1: y(0.45), y2: y(0.45) }, svg);
  text(svg, W - m.r + 6, y(0.45) + 4, "elevated", { class: "lbl", fill: "var(--red)" });
  const series = [
    ["N", "North", "var(--ink)"],
    ["S", "South", "var(--muted)"],
  ];
  for (const [k, label, color] of series) {
    const vals = model.after_storm[k];
    el("polyline", { points: vals.map((v, d) => `${x(d)},${y(v)}`).join(" "), fill: "none", stroke: color, "stroke-width": 2 }, svg);
    for (let d = 0; d < n; d++) el("circle", { cx: x(d), cy: y(vals[d]), r: 3.5, fill: color, stroke: "var(--paper)", "stroke-width": 2 }, svg);
    text(svg, x(n - 1) + 8, y(vals[n - 1]) + (k === "N" ? -2 : 12), label, { class: "lbl" });
  }
  const t = tipper(tip);
  const cross = el("line", { x1: 0, x2: 0, y1: m.t, y2: H - m.b, stroke: "var(--ink)", "stroke-opacity": 0, "stroke-width": 1 }, svg);
  const hit = el("rect", { class: "hit", x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b }, svg);
  hit.addEventListener("pointermove", (e) => {
    const r = svg.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const d = Math.max(0, Math.min(n - 1, Math.round(((px - m.l) / (W - m.l - m.r)) * (n - 1))));
    cross.setAttribute("x1", x(d));
    cross.setAttribute("x2", x(d));
    cross.setAttribute("stroke-opacity", 0.4);
    t.show(e, `<b>${d === 0 ? "Last storm day" : `${d} day${d > 1 ? "s" : ""} after`}</b><br>North ${model.after_storm.N[d].toFixed(2)} · South ${model.after_storm.S[d].toFixed(2)}`);
  });
  hit.addEventListener("pointerleave", () => {
    cross.setAttribute("stroke-opacity", 0);
    t.hide();
  });
}

function monthChart(root, model, tip) {
  const c = card(
    root,
    "Which problem, which month",
    `Days per winter with each problem at or above the elevated line, at ${model.summary_band}, averaged over the eight aspects. Wet snow takes over in spring.`,
  );
  const keys = Object.keys(PROBLEMS);
  const row = document.createElement("div");
  row.className = "keyrow";
  row.innerHTML = keys.map((k) => `<span><i style="background:var(--p-${k})"></i>${PROBLEMS[k]}</span>`).join("");
  c.append(row);
  const W = 520;
  const H = 230;
  const m = { l: 30, r: 8, t: 8, b: 26 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Problem days by month" }, c);
  const months = [...MONTHS.keys()];
  const max = Math.ceil(Math.max(...months.flatMap((mo) => keys.map((k) => model.monthly[mo][k]))));
  const y = (v) => H - m.b - (v / max) * (H - m.t - m.b);
  yAxis(svg, m.l, W - m.r, y, Array.from({ length: max + 1 }, (_, i) => i).filter((i) => i % Math.ceil(max / 4) === 0));
  const gw = (W - m.l - m.r) / months.length;
  const bw = (gw - 18) / keys.length;
  const t = tipper(tip);
  months.forEach((mo, i) => {
    text(svg, m.l + gw * i + gw / 2, H - 8, MONTHS.get(mo), { class: "lbl", "text-anchor": "middle" });
    keys.forEach((k, j) => {
      const v = model.monthly[mo][k];
      const x0 = m.l + gw * i + 9 + j * bw;
      const h = Math.max(H - m.b - y(v), v > 0 ? 1 : 0);
      el("rect", { x: x0 + 1, y: H - m.b - h, width: bw - 2, height: h, fill: `var(--p-${k})`, rx: 1.5 }, svg);
      const hit = el("rect", { class: "hit", x: x0, y: m.t, width: bw, height: H - m.b - m.t }, svg);
      hit.addEventListener("pointermove", (e) => t.show(e, `<b>${MONTHS.get(mo)}, ${PROBLEMS[k]}</b><br>${v.toFixed(2)} days per winter`));
      hit.addEventListener("pointerleave", t.hide);
    });
  });
  el("line", { class: "zero", x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b }, svg);
}

function spreadChart(root, model, tip) {
  const s = model.season_any_days;
  const f = model.snowfall_mm_water_by_band;
  const c = card(
    root,
    "Winters vary enormously",
    `Days with any elevated problem at ${model.summary_band} run from ${s.p10} in a dry winter to ${s.p90} in a big one (10th to 90th percentile), median ${s.median}. Below: snowfall by elevation, as water, across the same 400 winters.`,
  );
  const W = 520;
  const H = 230;
  const m = { l: 112, r: 60, t: 10, b: 28 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Snowfall range by elevation band" }, c);
  const max = Math.ceil(Math.max(...f.p90) / 200) * 200;
  const x = (v) => m.l + (v / max) * (W - m.l - m.r);
  const ax = el("g", { class: "axis" }, svg);
  for (let v = 0; v <= max; v += max / 4) {
    el("line", { x1: x(v), x2: x(v), y1: m.t, y2: H - m.b }, ax);
    text(ax, x(v), H - 10, `${v} mm`, { "text-anchor": "middle" });
  }
  const bands = model.bands;
  const rh = (H - m.t - m.b) / bands.length;
  const t = tipper(tip);
  bands.forEach((_, i) => {
    const j = bands.length - 1 - i;
    const cy = m.t + rh * i + rh / 2;
    text(svg, m.l - 10, cy + 4, bands[j], { class: "lbl", "text-anchor": "end" });
    el("line", { x1: x(f.p10[j]), x2: x(f.p90[j]), y1: cy, y2: cy, stroke: "var(--muted)", "stroke-width": 6, "stroke-linecap": "round", "stroke-opacity": 0.45 }, svg);
    el("circle", { cx: x(f.p50[j]), cy, r: 5, fill: "var(--ink)", stroke: "var(--paper)", "stroke-width": 2 }, svg);
    const hit = el("rect", { class: "hit", x: m.l, y: cy - rh / 2, width: W - m.l - m.r, height: rh }, svg);
    hit.addEventListener("pointermove", (e) => t.show(e, `<b>${bands[j]}</b><br>Snowfall as water: ${f.p10[j]} / ${f.p50[j]} / ${f.p90[j]} mm (dry / median / big)`));
    hit.addEventListener("pointerleave", t.hide);
  });
}

function heatmaps(root, model, tip) {
  const c = card(
    root,
    "Where each problem lives",
    "Days per winter at or above the elevated line, by aspect (across) and elevation (down, highest at the top). Each map has its own scale; the darkest cell is that problem's maximum.",
    true,
  );
  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:20px 28px";
  c.append(grid);
  const t = tipper(tip);
  for (const [k, name] of Object.entries(PROBLEMS)) {
    const days = model.days[k];
    const max = Math.max(...days.flat());
    const box = document.createElement("div");
    box.innerHTML = `<div class="keyrow"><span><i style="background:var(--p-${k})"></i>${name}, up to ${max.toFixed(1)} days</span></div>`;
    const W = 260;
    const H = 150;
    const m = { l: 44, t: 4, b: 18 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${name} days by aspect and elevation` }, box);
    const cw = (W - m.l) / 8;
    const ch = (H - m.t - m.b) / 5;
    for (let a = 0; a < 8; a++) text(svg, m.l + cw * a + cw / 2, H - 4, ASPECTS[a], { class: "lbl", "text-anchor": "middle", "font-size": 11 });
    for (let b = 0; b < 5; b++) {
      const row = 4 - b;
      text(svg, m.l - 6, m.t + ch * row + ch / 2 + 4, model.bands[b].split("-")[0], { class: "lbl", "text-anchor": "end", "font-size": 11 });
      for (let a = 0; a < 8; a++) {
        const v = days[b][a];
        const r = el("rect", { x: m.l + cw * a + 1, y: m.t + ch * row + 1, width: cw - 2, height: ch - 2, fill: `var(--p-${k})`, "fill-opacity": (0.06 + 0.94 * (v / max)).toFixed(3) }, svg);
        r.addEventListener("pointermove", (e) => t.show(e, `<b>${name}, ${ASPECTS[a]}, ${model.bands[b]}</b><br>${v.toFixed(1)} days per winter`));
        r.addEventListener("pointerleave", t.hide);
      }
    }
    grid.append(box);
  }
}

function inkGrid(parent, title, values, fmt, tipText, t, model) {
  const box = document.createElement("div");
  const max = Math.max(...values.flat());
  box.innerHTML = `<div class="keyrow"><span><i style="background:var(--ink)"></i>${title}</span></div>`;
  const W = 260;
  const H = 150;
  const m = { l: 44, t: 4, b: 18 };
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": title }, box);
  const cw = (W - m.l) / 8;
  const ch = (H - m.t - m.b) / 5;
  for (let a = 0; a < 8; a++) text(svg, m.l + cw * a + cw / 2, H - 4, ASPECTS[a], { class: "lbl", "text-anchor": "middle", "font-size": 11 });
  for (let b = 0; b < 5; b++) {
    const row = 4 - b;
    text(svg, m.l - 6, m.t + ch * row + ch / 2 + 4, model.bands[b].split("-")[0], { class: "lbl", "text-anchor": "end", "font-size": 11 });
    for (let a = 0; a < 8; a++) {
      const v = values[b][a];
      const k = max ? v / max : 0;
      const x = m.l + cw * a;
      const y = m.t + ch * row;
      const r = el("rect", { x: x + 1, y: y + 1, width: cw - 2, height: ch - 2, fill: "var(--ink)", "fill-opacity": (0.05 + 0.8 * k).toFixed(3) }, svg);
      text(svg, x + cw / 2, y + ch / 2 + 4, fmt(v), { "text-anchor": "middle", "font-size": 10.5, fill: k > 0.5 ? "var(--paper)" : "var(--ink)", "pointer-events": "none" });
      r.addEventListener("pointermove", (e) => t.show(e, `<b>${ASPECTS[a]}, ${model.bands[b]}</b><br>${tipText(v)}`));
      r.addEventListener("pointerleave", t.hide);
    }
  }
  parent.append(box);
}

function freezeCard(root, model, tip) {
  const ft = model.days.ft;
  const snow = model.days.snow;
  const share = ft.map((row, b) => row.map((v, a) => (100 * v) / Math.max(snow[b][a], 1)));
  const mid = 2;
  const pct = (a) => Math.round(share[mid][a]);
  const c = card(
    root,
    "Freeze-thaw, SoCal's daily cycle",
    `A cycle is a day when the snow surface thaws in the sun or warm air and the night drops below freezing. At ${model.bands[mid]}, a south slope cycles on ${pct(4)}% of its snow-covered days, an east slope on ${pct(2)}%, a north slope on ${pct(0)}%. Each cycle builds crust: hard ice between storms, a slick bed for the next storm's snow, and after a few cycles, corn.`,
    true,
  );
  const grid = document.createElement("div");
  grid.style.cssText = "display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:20px 28px";
  c.append(grid);
  const t = tipper(tip);
  inkGrid(grid, "Share of snow days with a cycle", share, (v) => Math.round(v), (v) => `${v.toFixed(0)}% of snow-covered days`, t, model);
  inkGrid(grid, "Freeze-thaw cycles per winter", ft, (v) => Math.round(v), (v) => `${v.toFixed(1)} cycles per winter`, t, model);
  inkGrid(grid, "Days of refrozen ice per winter", model.days.ice, (v) => Math.round(v), (v) => `${v.toFixed(1)} days with a refrozen surface and no new snow`, t, model);
  inkGrid(grid, "Corn days per winter", model.days.corn, (v) => Math.round(v), (v) => `${v.toFixed(1)} days of corn after three or more cycles`, t, model);
}

const COLS = [
  ["name", "Peak", (p) => p.name],
  ["summit_ft", "Summit ft", (p) => p.stats.summit_ft.toLocaleString()],
  ["pct_30_45", "30-45°", (p) => `${p.stats.pct_30_45}%`],
  ["dominant_aspect", "Faces", (p) => p.stats.dominant_aspect],
  ["lee_share_pct", "N+NE+E", (p) => `${p.stats.lee_share_pct}%`],
  ["model_days_storm", "Storm", (p) => p.stats.model_days_storm],
  ["model_days_wind", "Wind", (p) => p.stats.model_days_wind],
  ["wet_share_of_snow_days_pct", "Wet", (p) => `${p.stats.wet_share_of_snow_days_pct}%`],
  ["model_days_persistent", "Persistent", (p) => p.stats.model_days_persistent],
  ["model_days_ft", "Freeze-thaw", (p) => p.stats.model_days_ft],
  ["model_days_snow", "Snow days", (p) => p.stats.model_days_snow],
];

function peakTable(root, meta, onPeak) {
  const c = card(
    root,
    `All ${meta.peaks.length} peaks`,
    "Model days per winter over each peak's real steep terrain (30° and up, within 1.5 km of the summit). Wet is the share of snow-covered days. Click a column to sort, a name to fly there.",
    true,
  );
  const wrap = document.createElement("div");
  wrap.className = "tablewrap";
  const table = document.createElement("table");
  table.className = "peaks";
  wrap.append(table);
  c.append(wrap);
  let sortKey = "summit_ft";
  let asc = false;
  const val = (p, k) => (k === "name" || k === "dominant_aspect" ? p[k] ?? p.stats[k] : p.stats[k]);
  const draw = () => {
    const rows = [...meta.peaks].sort((a, b) => {
      const x = val(a, sortKey);
      const y = val(b, sortKey);
      const r = typeof x === "string" ? x.localeCompare(y) : x - y;
      return asc ? r : -r;
    });
    table.innerHTML = `<thead><tr>${COLS.map(([k, label]) => `<th scope="col"><button type="button" data-k="${k}" ${k === sortKey ? `aria-sort="${asc ? "ascending" : "descending"}"` : ""}>${label}</button></th>`).join("")}</tr></thead>
      <tbody>${rows.map((p) => `<tr>${COLS.map(([k, , f], i) => (i === 0 ? `<td><button type="button" data-slug="${p.slug}">${f(p)}</button></td>` : `<td>${f(p)}</td>`)).join("")}</tr>`).join("")}</tbody>`;
  };
  table.addEventListener("click", (e) => {
    const h = e.target.closest("th button");
    if (h) {
      asc = h.dataset.k === sortKey ? !asc : h.dataset.k === "name";
      sortKey = h.dataset.k;
      draw();
      table.querySelector(`th button[data-k="${sortKey}"]`).focus();
    }
    const p = e.target.closest("td button");
    if (p) onPeak(p.dataset.slug);
  });
  draw();
}

export function renderFindings(root, model, meta, tip, onPeak) {
  root.innerHTML = "";
  const intro = document.createElement("p");
  intro.className = "prose";
  intro.style.marginTop = "0";
  intro.textContent =
    "These come from 400 randomly generated winters run through the repo's snowpack model on a 38° slope. The weather is made up and the model runs snowy, so read the patterns more than the counts.";
  root.append(intro);
  const charts = document.createElement("div");
  charts.className = "charts";
  root.append(charts);
  fadeChart(charts, model, tip);
  monthChart(charts, model, tip);
  spreadChart(charts, model, tip);
  heatmaps(charts, model, tip);
  freezeCard(charts, model, tip);
  peakTable(charts, meta, onPeak);
}
