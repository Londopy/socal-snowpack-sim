import { dayDate, monthStarts } from "./winter.js";
import { compass } from "./roses.js";

const NS = "http://www.w3.org/2000/svg";
const FT = 3.28084;

function el(tag, attrs, parent) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  parent?.append(n);
  return n;
}

export function weatherLine(winter, d) {
  const w = winter.w;
  const parts = [`<b>${dayDate(d).label}</b>`];
  const sd = winter.stormDay(d);
  if (sd) parts.push(`storm day ${sd}`);
  else {
    const since = winter.daysSinceStorm(d);
    parts.push(since == null ? "no storm yet" : `${since} day${since === 1 ? "" : "s"} since the last storm`);
  }
  if (w.precip_mm[d] > 0) parts.push(`${w.precip_mm[d].toFixed(0)} mm water`);
  if (w.snow_level_m[d] != null) parts.push(`snow level ${(Math.round((w.snow_level_m[d] * FT) / 100) * 100).toLocaleString()} ft`);
  if (w.santa_ana[d]) parts.push("Santa Ana");
  parts.push(`wind ${w.wind_ms[d].toFixed(0)} m/s from ${compass(w.wind_from_deg[d])}`);
  parts.push(`${w.tmin_c[d].toFixed(0)} to ${w.tmax_c[d].toFixed(0)} °C at 8,500 ft`);
  return parts.join(" · ");
}

export class Strip {
  constructor(el, tip, onScrub) {
    this.el = el;
    this.tip = tip;
    this.onScrub = onScrub;
    this.day = 0;
    new ResizeObserver(() => this.winter && this.draw()).observe(el);
    const pick = (e) => {
      const r = this.el.getBoundingClientRect();
      const k = Math.min(Math.max((e.clientX - r.left - this.pad) / (r.width - this.pad), 0), 0.9999);
      return Math.floor(k * this.winter.days);
    };
    el.addEventListener("pointerdown", (e) => {
      el.setPointerCapture(e.pointerId);
      this.dragging = true;
      onScrub(pick(e));
    });
    el.addEventListener("pointermove", (e) => {
      if (!this.winter) return;
      const d = pick(e);
      if (this.dragging) onScrub(d);
      this.showTip(e, d);
    });
    el.addEventListener("pointerup", () => (this.dragging = false));
    el.addEventListener("pointerleave", () => (tip.hidden = true));
  }

  // bands is how many elevation bands the current view reaches, so the freeze-thaw row
  // only counts slopes that exist on this peak
  setWinter(winter, bands = 5) {
    this.winter = winter;
    this.bands = bands;
    this.draw();
  }

  freezeShare(d) {
    let snowy = 0;
    let cycled = 0;
    for (let b = 0; b < this.bands; b++) {
      for (let a = 0; a < 8; a++) {
        if (this.winter.value("swe", d, b, a) <= 20) continue;
        snowy++;
        if (this.winter.value("ft", d, b, a) >= 0.5) cycled++;
      }
    }
    return snowy ? cycled / snowy : 0;
  }

  draw() {
    const w = this.winter;
    const W = this.el.clientWidth;
    const H = this.el.clientHeight;
    this.pad = 0;
    this.el.innerHTML = "";
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, "aria-hidden": "true" }, this.el);
    const top = 16;
    const base = H - 22;
    const dx = W / w.days;
    const maxP = Math.max(60, ...w.w.precip_mm);
    for (let d = 0; d < w.days; d++) {
      if (w.w.storm[d]) el("rect", { class: "stormband", x: d * dx, y: top, width: dx, height: base - top }, svg);
    }
    for (const m of monthStarts(w.days)) {
      el("line", { class: "month", x1: m.d * dx, x2: m.d * dx, y1: 0, y2: H }, svg);
      el("text", { class: "mlabel", x: m.d * dx + 4, y: 11 }, svg).textContent = m.label;
    }
    for (let d = 0; d < w.days; d++) {
      const p = w.w.precip_mm[d];
      if (p <= 0) continue;
      const h = (p / maxP) * (base - top);
      el("rect", { class: "rain", x: d * dx + 0.5, y: base - h, width: Math.max(dx - 1, 1), height: h }, svg);
    }
    for (let d = 0; d < w.days; d++) {
      if (w.w.santa_ana[d]) el("rect", { class: "santa", x: d * dx, y: base + 3, width: Math.max(dx, 2), height: 4 }, svg);
    }
    this.share = [];
    for (let d = 0; d < w.days; d++) {
      const f = this.freezeShare(d);
      this.share.push(f);
      if (f > 0) el("rect", { class: "ftcell", x: d * dx, y: base + 11, width: dx + 0.3, height: 9, "fill-opacity": (0.12 + 0.88 * f).toFixed(2) }, svg);
    }
    el("line", { class: "base", x1: 0, x2: W, y1: base, y2: base }, svg);
    this.head = el("line", { class: "head", y1: 0, y2: base }, svg);
    this.cap = el("rect", { class: "headcap", y: 0, width: 8, height: 8 }, svg);
    this.dx = dx;
    this.setDay(this.day);
  }

  setDay(d) {
    this.day = d;
    if (!this.head) return;
    const x = (d + 0.5) * this.dx;
    this.head.setAttribute("x1", x);
    this.head.setAttribute("x2", x);
    this.cap.setAttribute("x", x - 4);
    this.el.setAttribute("aria-valuenow", d);
    this.el.setAttribute("aria-valuetext", dayDate(d).label);
  }

  showTip(e, d) {
    const w = this.winter.w;
    const bits = [`<b>${dayDate(d).label}</b>`];
    bits.push(w.precip_mm[d] > 0 ? `${w.precip_mm[d].toFixed(0)} mm water at 8,500 ft` : "dry");
    if (w.storm[d]) bits.push("storm");
    if (w.santa_ana[d]) bits.push("Santa Ana wind");
    if (this.share[d] > 0) bits.push(`${Math.round(this.share[d] * 100)}% of snowy slopes thawed and refroze`);
    this.tip.innerHTML = bits.join(" · ");
    this.tip.hidden = false;
    this.tip.style.left = `${Math.min(e.clientX + 12, innerWidth - 290)}px`;
    this.tip.style.top = `${e.clientY - 44}px`;
  }
}
