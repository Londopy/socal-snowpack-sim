export const PROBLEMS = {
  storm: "Storm slab",
  wind: "Wind slab",
  wet: "Wet snow",
  persistent: "Persistent slab",
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// season runs 15 Nov to 30 Apr; a non-leap year keeps it at the model's 167 days
export function dayDate(d) {
  const t = new Date(Date.UTC(2025, 10, 15 + d));
  return { month: t.getUTCMonth(), day: t.getUTCDate(), label: `${MONTHS[t.getUTCMonth()]} ${t.getUTCDate()}` };
}

export function monthStarts(days) {
  const out = [];
  for (let d = 0; d < days; d++) {
    const { day, month } = dayDate(d);
    if (day === 1) out.push({ d, label: MONTHS[month] });
  }
  return out;
}

export class Winter {
  constructor(raw, meta) {
    this.raw = raw;
    this.key = raw.key;
    this.label = raw.label;
    this.days = meta.days;
    this.nb = meta.bands.length;
    this.na = meta.aspects.length;
    this.scale = meta.index_scale;
    this.w = raw.weather;
  }

  value(field, d, b, a) {
    const v = this.raw.grid[field][(d * this.nb + b) * this.na + a];
    return field === "swe" ? v : v / this.scale;
  }

  // per-day textures for the shader: rows are bands, columns aspects
  textures(d) {
    const A = new Float32Array(this.nb * this.na * 4);
    const B = new Float32Array(this.nb * this.na * 4);
    for (let b = 0; b < this.nb; b++) {
      for (let a = 0; a < this.na; a++) {
        const i = (b * this.na + a) * 4;
        A.set([this.value("swe", d, b, a), this.value("storm", d, b, a), this.value("wind", d, b, a), this.value("wet", d, b, a)], i);
        B.set([this.value("persistent", d, b, a), this.value("ice", d, b, a), this.value("ft", d, b, a), this.value("corn", d, b, a)], i);
      }
    }
    return [A, B];
  }

  stormDay(d) {
    if (!this.w.storm[d]) return 0;
    let n = 1;
    while (d - n >= 0 && this.w.storm[d - n]) n++;
    return n;
  }

  daysSinceStorm(d) {
    for (let n = 0; n <= d; n++) if (this.w.storm[d - n]) return n;
    return null;
  }
}
