export const LAYERS = ["relief", "imagery", "topo", "lidar", "slope", "aspect"];
export const OVERPRINTS = ["off", "all", "storm", "wind", "wet", "persistent", "freeze"];

export const vertex = /* glsl */ `
uniform float uExag;
varying vec3 vNormal;
varying vec2 vUv;
varying float vElev;
varying float vDist;

void main() {
  vUv = uv;
  vElev = position.y;
  vec3 p = vec3(position.x, position.y * uExag, position.z);
  vec4 world = modelMatrix * vec4(p, 1.0);
  vNormal = normalize(vec3(normal.x, normal.y / uExag, normal.z));
  vec4 mv = viewMatrix * world;
  vDist = -mv.z;
  gl_Position = projectionMatrix * mv;
}
`;

// winter grid: 8 aspects x 5 bands per texture, nearest-sampled and interpolated here
// so the bands blend by elevation and the aspects wrap around north
export const fragment = /* glsl */ `
precision highp float;
uniform int uLayer;
uniform int uOverprint;
uniform bool uSnow;
uniform bool uHasTex;
uniform bool uHasLidar;
uniform sampler2D uTex;
uniform sampler2D uLidar;
uniform sampler2D uGridA;   // swe, storm, wind, wet
uniform sampler2D uGridB;   // persistent, ice, freeze-thaw, corn
uniform vec3 uSun;
uniform vec3 uPaper;
uniform float uFogFar;
uniform float uHatch;
uniform float uPixelRatio;
uniform vec2 uHighlight;    // aspect index, band index; -1 for none
uniform float uElevated;
uniform float uExag;
uniform vec3 uProblemColor[4];
uniform vec3 uInk;
uniform bool uClock;
uniform float uDaylight;

varying vec3 vNormal;
varying vec2 vUv;
varying float vElev;
varying float vDist;

const float BAND0 = 2000.0;
const float BANDW = 300.0;

vec3 srgb(vec3 c) { return pow(c, vec3(2.2)); }

vec3 ramp(float e) {
  vec3 c0 = srgb(vec3(0.53, 0.60, 0.47));
  vec3 c1 = srgb(vec3(0.64, 0.69, 0.52));
  vec3 c2 = srgb(vec3(0.78, 0.77, 0.56));
  vec3 c3 = srgb(vec3(0.88, 0.84, 0.64));
  vec3 c4 = srgb(vec3(0.94, 0.91, 0.80));
  vec3 c5 = srgb(vec3(0.97, 0.95, 0.89));
  if (e < 1200.0) return mix(c0, c1, smoothstep(600.0, 1200.0, e));
  if (e < 1900.0) return mix(c1, c2, (e - 1200.0) / 700.0);
  if (e < 2500.0) return mix(c2, c3, (e - 1900.0) / 600.0);
  if (e < 3100.0) return mix(c3, c4, (e - 2500.0) / 600.0);
  return mix(c4, c5, clamp((e - 3100.0) / 400.0, 0.0, 1.0));
}

vec4 cell(sampler2D t, float a, float b) {
  return texture2D(t, vec2((mod(a, 8.0) + 0.5) / 8.0, (b + 0.5) / 5.0));
}

vec4 grid(sampler2D t, float aspect, float elev) {
  float a = aspect / 45.0;
  float b = clamp((elev - BAND0) / BANDW - 0.5, 0.0, 4.0);
  float a0 = floor(a);
  float b0 = floor(b);
  float fa = a - a0;
  float fb = b - b0;
  float b1 = min(b0 + 1.0, 4.0);
  vec4 lo = mix(cell(t, a0, b0), cell(t, a0 + 1.0, b0), fa);
  vec4 hi = mix(cell(t, a0, b1), cell(t, a0 + 1.0, b1), fa);
  return mix(lo, hi, fb);
}

float lines(vec2 p, vec2 dir, float spacing, float width) {
  float d = abs(fract(dot(p, dir) / spacing) - 0.5) * spacing;
  return 1.0 - smoothstep(width * 0.5 - 0.6, width * 0.5 + 0.6, d);
}

float dots(vec2 p, float spacing, float r) {
  vec2 q = mod(p, spacing) - spacing * 0.5;
  return 1.0 - smoothstep(r - 0.7, r + 0.7, length(q));
}

float rings(vec2 p, float spacing, float r) {
  float d = abs(length(mod(p, spacing) - spacing * 0.5) - r);
  return 1.0 - smoothstep(0.45, 1.15, d);
}

float pattern(int k, float v) {
  vec2 p = gl_FragCoord.xy / uPixelRatio;
  float w = mix(0.9, 2.6, clamp((v - 0.2) / 0.9, 0.0, 1.0));
  float s = uHatch;
  if (k == 0) return lines(p, normalize(vec2(1.0, 1.0)), s, w);
  if (k == 1) return lines(p, normalize(vec2(1.0, -1.0)), s, w);
  if (k == 2) return dots(p, s * 0.8, w * 0.75 + 0.6);
  if (k == 3) return lines(p, vec2(0.0, 1.0), s * 0.9, w);
  if (k == 4) return max(lines(p, normalize(vec2(1.0, 1.0)), s * 0.8, 1.3), lines(p, normalize(vec2(1.0, -1.0)), s * 0.8, 1.3));
  if (k == 5) return rings(p, s * 1.3, s * 0.38);
  if (k == 6) return lines(p, normalize(vec2(1.0, 1.0)), s, 1.4);
  return dots(p, s * 1.2, 1.3);
}

void main() {
  vec3 n = normalize(vNormal);
  // n is the exaggerated normal, right for shading; slope classes need the true-scale one
  vec3 nt = normalize(vec3(n.x, n.y * uExag, n.z));
  float slope = degrees(acos(clamp(nt.y, -1.0, 1.0)));
  float aspect = mod(degrees(atan(n.x, -n.z)) + 360.0, 360.0);
  float shade = clamp(dot(n, uSun), 0.0, 1.0);
  float lit = pow(shade, 0.85);
  vec3 shadow = srgb(vec3(0.31, 0.37, 0.53));
  vec3 col;

  if (uLayer == 0 || !uHasTex) {
    vec3 base = ramp(vElev);
    vec3 warm = mix(base, srgb(vec3(0.96, 0.88, 0.62)), smoothstep(0.62, 1.0, shade) * 0.4);
    float detail = 1.0;
    if (uHasLidar) detail = mix(1.0, texture2D(uLidar, vUv).r * 1.45, 0.45);
    col = mix(shadow, warm, 0.2 + 0.8 * lit) * detail;
  } else if (uLayer == 3) {
    float g = pow(clamp((texture2D(uTex, vUv).r - 0.28) / 0.66, 0.0, 1.0), 1.15);
    col = mix(srgb(vec3(0.17, 0.19, 0.26)), srgb(vec3(0.95, 0.95, 0.92)), g);
  } else {
    vec3 t = texture2D(uTex, vUv).rgb;
    col = t * (0.72 + 0.42 * lit);
  }

  if (uLayer == 4) {
    vec3 g = vec3(dot(col, vec3(0.3, 0.55, 0.15)));
    col = mix(col, g * 1.1, 0.6);
    vec3 c = vec3(-1.0);
    if (slope >= 45.0) c = srgb(vec3(0.42, 0.11, 0.44));
    else if (slope >= 35.0) c = srgb(vec3(0.84, 0.19, 0.19));
    else if (slope >= 30.0) c = srgb(vec3(0.94, 0.58, 0.17));
    else if (slope >= 25.0) c = srgb(vec3(0.96, 0.90, 0.55));
    if (c.x >= 0.0) col = mix(col, c * (0.6 + 0.5 * lit), 0.78);
  } else if (uLayer == 5) {
    float h = radians(aspect);
    vec3 c = 0.55 + 0.33 * vec3(cos(h), cos(h - 2.094), cos(h + 2.094));
    col = srgb(c) * (0.55 + 0.55 * lit);
    col = mix(col, vec3(dot(col, vec3(0.33))), smoothstep(12.0, 4.0, slope));
  }

  vec4 A = grid(uGridA, aspect, vElev);
  vec4 B = grid(uGridB, aspect, vElev);
  float onModel = smoothstep(BAND0 - 180.0, BAND0, vElev);

  // the day clock lights the terrain from the real sun, so night has to go dark
  if (uClock) col *= mix(srgb(vec3(0.45, 0.5, 0.66)), vec3(1.0), uDaylight);

  if (uSnow) {
    float swe = A.x * onModel;
    float cover = smoothstep(12.0, 45.0, swe) * (1.0 - smoothstep(52.0, 62.0, slope));
    vec3 snow = mix(srgb(vec3(0.43, 0.50, 0.70)), srgb(vec3(0.99, 0.99, 0.97)), pow(shade, 1.3));
    if (B.y > 0.5 && uLayer == 0) snow = mix(snow, srgb(vec3(0.70, 0.80, 0.90)) * (0.6 + 0.5 * lit), 0.35);
    col = mix(col, snow, cover * (uLayer == 0 ? 1.0 : 0.85));
  }

  if (uOverprint == 6) {
    float cover = smoothstep(12.0, 45.0, A.x * onModel) * (1.0 - smoothstep(52.0, 62.0, slope));
    float cycled = smoothstep(0.35, 0.65, B.z);
    float corn = smoothstep(0.35, 0.65, B.w);
    float iceAllDay = smoothstep(0.7, 0.9, B.y) * (1.0 - cycled);
    float m;
    if (uClock) {
      // illustration only: the model knows a slope thawed and refroze that day, not when, so
      // slopes it flags soften while the real sun is on them and are frozen the rest of the day
      float thawed = max(cycled, corn);
      float soft = thawed * smoothstep(0.25, 0.5, dot(n, uSun)) * smoothstep(0.3, 0.7, uDaylight);
      float frozen = max(thawed * (1.0 - soft), iceAllDay);
      col = mix(col, srgb(vec3(0.93, 0.86, 0.72)) * (0.55 + 0.5 * lit), soft * cover * 0.6);
      m = max(pattern(4, 1.0) * frozen, pattern(7, 1.0) * soft * 0.8);
    } else {
      m = max(max(pattern(5, 1.0) * corn, pattern(6, 1.0) * cycled * (1.0 - corn)), pattern(4, 1.0) * iceAllDay);
    }
    col = mix(col, uInk, m * cover * 0.78);
  }

  if (uOverprint > 0 && uOverprint < 6) {
    float terrain = smoothstep(28.0, 30.0, slope) * (1.0 - smoothstep(50.0, 55.0, slope)) * onModel;
    float vals[4];
    vals[0] = A.y; vals[1] = A.z; vals[2] = A.w; vals[3] = B.x;
    int k = uOverprint - 2;
    if (uOverprint == 1) {
      k = 0;
      for (int i = 1; i < 4; i++) if (vals[i] > vals[k]) k = i;
    }
    float v = 0.0;
    for (int i = 0; i < 4; i++) if (i == k) v = vals[i];
    float show = smoothstep(0.18, 0.26, v) * terrain;
    if (show > 0.0) {
      vec3 pc = vec3(0.0);
      for (int i = 0; i < 4; i++) if (i == k) pc = uProblemColor[i];
      float m = pattern(k, v) * show * (v >= uElevated ? 0.82 : 0.4);
      col = mix(col, pc, m);
    }
  }

  if (uHighlight.x >= 0.0) {
    float da = abs(mod(aspect - uHighlight.x * 45.0 + 540.0, 360.0) - 180.0);
    float lo = BAND0 + uHighlight.y * BANDW;
    bool inside = da < 22.5 && vElev >= lo && vElev < lo + BANDW && slope >= 25.0;
    col = inside ? mix(col, srgb(vec3(0.76, 0.27, 0.18)), 0.55) : mix(col, vec3(dot(col, vec3(0.33))), 0.35);
  }

  float fog = smoothstep(uFogFar * 0.45, uFogFar, vDist);
  col = mix(col, uPaper, fog * 0.55);
  gl_FragColor = vec4(col, 1.0);
  #include <colorspace_fragment>
}
`;

export const skirtVertex = /* glsl */ `
uniform float uExag;
varying float vElev;
void main() {
  vElev = position.y;
  gl_Position = projectionMatrix * viewMatrix * modelMatrix * vec4(position.x, position.y * uExag, position.z, 1.0);
}
`;

export const skirtFragment = /* glsl */ `
uniform vec3 uSide;
uniform vec3 uLine;
varying float vElev;
void main() {
  float d = abs(fract(vElev / 500.0 + 0.5) - 0.5) * 500.0;
  float line = 1.0 - smoothstep(4.0, 9.0, d);
  gl_FragColor = vec4(mix(uSide, uLine, line * 0.55), 1.0);
  #include <colorspace_fragment>
}
`;
