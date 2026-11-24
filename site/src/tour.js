import { dayDate } from "./winter.js";
import { windCause, compass } from "./roses.js";

const $ = (id) => document.getElementById(id);

function argmax(n, f) {
  let best = 0;
  let bv = -Infinity;
  for (let i = 0; i < n; i++) {
    const v = f(i);
    if (v > bv) {
      bv = v;
      best = i;
    }
  }
  return best;
}

// stops are picked from the exported winters, so the tour shows what the data actually does
function buildSteps({ winters, model }) {
  const typ = winters.typical;
  // last day of the storm that dropped the most water
  let lastDay = 0;
  let most = -1;
  for (let d = 0, total = 0; d < typ.days; d++) {
    total = typ.w.storm[d] ? total + typ.w.precip_mm[d] : 0;
    if (typ.w.storm[d] && !typ.w.storm[d + 1] && total > most) {
      most = total;
      lastDay = d;
    }
  }
  const fade = Math.min(lastDay + 3, typ.days - 1);
  const n = model.after_storm.N;

  // north-east wind slab built by the usual south-west storm flow
  let wind = { w: "typical", d: 0, v: -1, cause: null };
  for (const w of Object.values(winters)) {
    for (let d = 0; d < w.days; d++) {
      const v = w.value("wind", d, 4, 1) + w.value("wind", d, 3, 1);
      if (v <= wind.v) continue;
      const cause = windCause(w, d, 1, 4);
      if (cause && cause.from >= 170 && cause.from <= 280) wind = { w: w.key, d, v, cause };
    }
  }

  const ice = argmax(typ.days, (d) => {
    if (typ.w.storm[d] || Math.abs(d - lastDay) < 8 || typ.value("swe", d, 2, 4) < 20) return -1;
    let v = 0;
    for (let b = 1; b <= 3; b++) for (const a of [3, 4, 5]) v += typ.value("ice", d, b, a);
    return v + typ.value("swe", d, 2, 4) / 1000;
  });
  const big = winters.big;
  const peak = argmax(big.days, (d) => big.value("swe", d, 2, 0));

  return [
    {
      title: "Three ranges, one made-up winter",
      text: `This is the typical simulated winter on ${dayDate(lastDay).label}, the last day of its biggest storm. The same weather falls on every range; only aspect and elevation change what the snow does. Hatching marks the main avalanche problem on slopes of 30° and up.`,
      winter: "typical",
      day: lastDay,
      over: "all",
    },
    {
      title: "Storm slab on every aspect",
      text: "On Mt. Baldy the new snow is a storm-slab problem all the way round the mountain. Hover the small charts on the right to light up a single aspect and elevation on the terrain.",
      peak: "baldy",
      winter: "typical",
      day: lastDay,
      over: "storm",
    },
    {
      title: "Three days later",
      text: `Averaged over storms, the index on north slopes at 9,500-10,500 ft is ${n[0].toFixed(2)} on the last storm day, ${n[2].toFixed(2)} two days later and ${n[3].toFixed(2)} after three. The elevated line is 0.45. In SoCal it spikes in storms and fades in days.`,
      peak: "baldy",
      winter: "typical",
      day: fade,
      over: "storm",
    },
    {
      title: "Wind slab on the lee",
      text: `San Gorgonio's high north-east slopes, ${dayDate(wind.d).label} in the ${winters[wind.w].label.toLowerCase()}. ${wind.cause ? `${wind.cause.speed.toFixed(0)} m/s wind from the ${compass(wind.cause.from)} on ${dayDate(wind.cause.d).label}` : "Storm wind"} stripped the windward side and loaded the lee. The wind chart on the right names the wind behind each cell.`,
      peak: "san_gorgonio",
      winter: wind.w,
      day: wind.d,
      over: "wind",
    },
    {
      title: "Freeze-thaw and ice between storms",
      text: `${dayDate(ice).label}: sunny slopes thaw by day and refreeze at night. With no new snow on top, that crust is hard ice, the slide-for-life surface behind many winter deaths on Baldy. Diagonal ink marks slopes that cycled today, rings mark corn, cross-hatching marks ice that stayed hard all day. Try the day clock in the corner of the map.`,
      peak: "baldy",
      winter: "typical",
      day: ice,
      over: "freeze",
      layer: "relief",
    },
    {
      title: "Big winter, dry winter",
      text: `The big winter at its deepest, ${dayDate(peak).label}. Switch to Dry at the bottom to see the same date with almost nothing on the ground. Across 400 winters, days with an elevated problem at 8,500-9,500 ft range from ${model.season_any_days.p10} to ${model.season_any_days.p90}.`,
      peak: "baldy",
      winter: "big",
      day: peak,
      over: "all",
    },
  ];
}

export class Tour {
  constructor(ctx) {
    this.ctx = ctx;
    this.active = false;
    $("tour-next").addEventListener("click", () => this.show(this.i + 1));
    $("tour-prev").addEventListener("click", () => this.show(this.i - 1));
    $("tour-end").addEventListener("click", () => this.end());
  }

  start() {
    this.steps ||= buildSteps(this.ctx);
    this.active = true;
    $("open-tour").setAttribute("aria-pressed", "true");
    $("tour").hidden = false;
    this.show(0);
  }

  async show(i) {
    if (i >= this.steps.length) return this.end();
    this.i = Math.max(0, i);
    const s = this.steps[this.i];
    $("tour-step").textContent = `${this.i + 1} of ${this.steps.length}`;
    $("tour-title").textContent = s.title;
    $("tour-text").textContent = s.text;
    $("tour-prev").disabled = this.i === 0;
    $("tour-next").textContent = this.i === this.steps.length - 1 ? "Finish" : "Next";
    $("tour-next").focus({ preventScroll: true });
    await this.ctx.go(s);
  }

  end() {
    this.active = false;
    $("tour").hidden = true;
    $("open-tour").setAttribute("aria-pressed", "false");
  }
}
