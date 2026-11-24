import { PROBLEMS, dayDate } from "./winter.js";

const NS = "http://www.w3.org/2000/svg";
const ASPECTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const R0 = 9;
const STEP = 9.5;

export function compass(deg) {
  return ASPECTS[Math.round(deg / 45) % 8];
}

function sector(a, ring) {
  const r0 = R0 + ring * STEP;
  const r1 = r0 + STEP;
  const t0 = ((a * 45 - 22.5 - 90) * Math.PI) / 180;
  const t1 = ((a * 45 + 22.5 - 90) * Math.PI) / 180;
  const p = (r, t) => `${(r * Math.cos(t)).toFixed(2)} ${(r * Math.sin(t)).toFixed(2)}`;
  return `M${p(r0, t0)} L${p(r1, t0)} A${r1} ${r1} 0 0 1 ${p(r1, t1)} L${p(r0, t1)} A${r0} ${r0} 0 0 0 ${p(r0, t0)} Z`;
}

// the recent wind that did the loading, scored the way the model builds wind slab: on slopes
// facing downwind, stronger up to 22 m/s, fading over the days after, and only where there
// was snow lying to move
export function windCause(winter, d, aspect, band) {
  let best = null;
  for (let k = d; k >= Math.max(0, d - 5); k--) {
    const w = winter.w.wind_ms[k];
    const from = winter.w.wind_from_deg[k];
    const lee = Math.cos(((aspect * 45 - from - 180) * Math.PI) / 180);
    if (w < 7 || lee < 0.3 || winter.value("swe", k, band, aspect) <= 1) continue;
    const score = Math.min(w - 7, 15) * lee * Math.exp(-(d - k) / 2.5);
    if (!best || score > best.score) best = { d: k, speed: w, from, score };
  }
  return best;
}

function windiestCell(winter, d) {
  let best = { a: 0, b: 0, v: 0 };
  for (let b = 0; b < 5; b++) for (let a = 0; a < 8; a++) {
    const v = winter.value("wind", d, b, a);
    if (v > best.v) best = { a, b, v };
  }
  return best;
}

const FT_DEFS = `<defs>
  <pattern id="ft-cycle" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)"><rect width="1.3" height="5" fill="var(--ink)"/></pattern>
  <pattern id="ft-corn" width="7" height="7" patternUnits="userSpaceOnUse"><circle cx="3.5" cy="3.5" r="2.2" fill="none" stroke="var(--ink)" stroke-width="0.9"/></pattern>
  <pattern id="ft-ice" width="4.5" height="4.5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="1" height="4.5" fill="var(--ink)"/><rect width="4.5" height="1" fill="var(--ink)"/></pattern>
</defs>`;

export function ftState(winter, d, b, a) {
  if (winter.value("swe", d, b, a) <= 20) return "bare";
  if (winter.value("corn", d, b, a) >= 0.5) return "corn";
  if (winter.value("ft", d, b, a) >= 0.5) return "cycle";
  if (winter.value("ice", d, b, a) >= 1) return "ice";
  return "snow";
}

const FT_TEXT = {
  bare: "No snow cover",
  corn: "Corn: thawed and refroze again, after several cycles",
  cycle: "Thawed by day, refroze at night",
  ice: "Refrozen ice that stayed hard all day",
  snow: "Snow, no freeze-thaw cycle today",
};

export class Roses {
  constructor(el, tip, meta, onHover) {
    this.el = el;
    this.tip = tip;
    this.meta = meta;
    this.onHover = onHover;
    this.cells = {};
    this.why = null;
    el.innerHTML = "";
    for (const [key, label] of Object.entries(PROBLEMS)) {
      const fig = document.createElement("figure");
      fig.className = "rose";
      const svg = document.createElementNS(NS, "svg");
      svg.setAttribute("viewBox", "-62 -62 124 124");
      svg.setAttribute("role", "img");
      svg.setAttribute("aria-label", `${label} index by aspect and elevation`);
      this.cells[key] = [];
      for (let ring = 0; ring < 5; ring++) {
        const band = 4 - ring;
        for (let a = 0; a < 8; a++) {
          const path = document.createElementNS(NS, "path");
          path.setAttribute("d", sector(a, ring));
          path.dataset.band = band;
          path.dataset.aspect = a;
          path.addEventListener("pointerenter", (e) => this.enter(e, key, a, band));
          path.addEventListener("pointermove", (e) => this.move(e));
          path.addEventListener("pointerleave", () => this.leave());
          svg.append(path);
          this.cells[key].push({ path, a, band });
        }
      }
      for (const [t, x, y] of [["N", 0, -58], ["E", 58, 0], ["S", 0, 58], ["W", -58, 0]]) {
        const tx = document.createElementNS(NS, "text");
        tx.setAttribute("class", "axis");
        tx.setAttribute("x", x);
        tx.setAttribute("y", y);
        tx.textContent = t;
        svg.append(tx);
      }
      const cap = document.createElement("figcaption");
      cap.innerHTML = `<i style="background:var(--p-${key})"></i>${label}`;
      fig.append(svg, cap);
      if (key === "wind") {
        this.why = document.createElement("span");
        this.why.className = "why";
        fig.append(this.why);
      }
      el.append(fig);
    }
    this.buildFreeze(document.getElementById("ft-rose"));
  }

  buildFreeze(box) {
    box.innerHTML = `<svg viewBox="-62 -62 124 124" role="img" aria-label="Freeze-thaw state by aspect and elevation">${FT_DEFS}</svg>`;
    const svg = box.querySelector("svg");
    this.ft = [];
    for (let ring = 0; ring < 5; ring++) {
      const band = 4 - ring;
      for (let a = 0; a < 8; a++) {
        const path = document.createElementNS(NS, "path");
        path.setAttribute("d", sector(a, ring));
        path.addEventListener("pointerenter", (e) => this.enterFreeze(e, a, band));
        path.addEventListener("pointermove", (e) => this.move(e));
        path.addEventListener("pointerleave", () => this.leave());
        svg.append(path);
        this.ft.push({ path, a, band });
      }
    }
    for (const [t, x, y] of [["N", 0, -58], ["E", 58, 0], ["S", 0, 58], ["W", -58, 0]]) {
      const tx = document.createElementNS(NS, "text");
      tx.setAttribute("class", "axis");
      tx.setAttribute("x", x);
      tx.setAttribute("y", y);
      tx.textContent = t;
      svg.append(tx);
    }
  }

  updateFreeze(winter, d, summitM) {
    const edges = this.meta.band_edges_m;
    for (const { path, a, band } of this.ft) {
      const st = ftState(winter, d, band, a);
      const above = summitM != null && edges[band] > summitM;
      path.style.fill = above || st === "bare" ? "none" : st === "snow" ? "var(--paper-2)" : `url(#ft-${st})`;
      path.style.stroke = "var(--rule)";
      path.style.strokeWidth = 0.6;
      path.style.opacity = above ? 0.3 : 1;
      path.dataset.above = above ? "1" : "";
    }
  }

  enterFreeze(e, a, band) {
    const w = this.winter;
    let n = 0;
    for (let k = 0; k <= this.d; k++) n += w.value("ft", k, band, a) >= 0.5 ? 1 : 0;
    const above = e.currentTarget.dataset.above;
    this.tip.innerHTML = above
      ? `<b>${ASPECTS[a]}, ${this.meta.bands[band]}</b><br>Above this summit`
      : `<b>${ASPECTS[a]}, ${this.meta.bands[band]}</b><br>${FT_TEXT[ftState(w, this.d, band, a)]}<br>${n} freeze-thaw cycle${n === 1 ? "" : "s"} so far this winter`;
    this.tip.hidden = false;
    this.move(e);
    this.onHover(a, band);
  }

  update(winter, d, summitM) {
    this.winter = winter;
    this.d = d;
    this.updateFreeze(winter, d, summitM);
    const edges = this.meta.band_edges_m;
    for (const [key, cells] of Object.entries(this.cells)) {
      for (const { path, a, band } of cells) {
        const v = winter.value(key, d, band, a);
        const above = summitM != null && edges[band] > summitM;
        path.style.fill = `var(--p-${key})`;
        path.style.fillOpacity = above ? 0.04 : (0.07 + 0.93 * Math.min(v / 1.0, 1)).toFixed(3);
        path.style.stroke = v >= this.meta.elevated && !above ? "var(--ink)" : "var(--rule)";
        path.style.strokeWidth = v >= this.meta.elevated && !above ? 1.6 : 0.6;
        path.dataset.above = above ? "1" : "";
      }
    }
    const top = windiestCell(winter, d);
    const cause = top.v >= 0.2 ? windCause(winter, d, top.a, top.b) : null;
    this.why.textContent = cause
      ? `Most on ${ASPECTS[top.a]} slopes, loaded by ${cause.speed.toFixed(0)} m/s wind from the ${compass(cause.from)} on ${dayDate(cause.d).label}`
      : "";
  }

  enter(e, key, a, band) {
    const v = this.winter.value(key, this.d, band, a);
    const above = e.currentTarget.dataset.above;
    const level = v >= this.meta.high ? "high" : v >= this.meta.elevated ? "elevated" : "below the elevated line";
    let text = `<b>${ASPECTS[a]}, ${this.meta.bands[band]}</b><br>${PROBLEMS[key]} index ${v.toFixed(2)}, ${level}`;
    if (above) text = `<b>${ASPECTS[a]}, ${this.meta.bands[band]}</b><br>Above this summit`;
    if (key === "wind" && v >= 0.2 && !above) {
      const c = windCause(this.winter, this.d, a, band);
      if (c) text += `<br>Lee to ${c.speed.toFixed(0)} m/s wind from the ${compass(c.from)} on ${dayDate(c.d).label}`;
    }
    this.tip.innerHTML = text;
    this.tip.hidden = false;
    this.move(e);
    this.onHover(a, band);
  }

  move(e) {
    this.tip.style.left = `${Math.min(e.clientX + 14, innerWidth - 290)}px`;
    this.tip.style.top = `${e.clientY + 14}px`;
  }

  leave() {
    this.tip.hidden = true;
    this.onHover(-1, -1);
  }
}
