import * as THREE from "three";

const LAT = THREE.MathUtils.degToRad(34.28);

// same declination and hour-angle formulas as solar_tables() in src/model.py, at local solar time
export function sunAt(day, hour) {
  const doy = Math.round((Date.UTC(2025, 10, 15 + day) - Date.UTC(2025, 0, 1)) / 86400000) + 1;
  const dec = THREE.MathUtils.degToRad(23.44) * Math.sin((2 * Math.PI * (284 + doy)) / 365);
  const ha = THREE.MathUtils.degToRad(15 * (hour - 12));
  const sinEl = Math.sin(LAT) * Math.sin(dec) + Math.cos(LAT) * Math.cos(dec) * Math.cos(ha);
  const el = Math.asin(sinEl);
  const az = Math.atan2(-Math.cos(dec) * Math.sin(ha), Math.sin(dec) * Math.cos(LAT) - Math.cos(dec) * Math.cos(ha) * Math.sin(LAT));
  return {
    dir: new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.sin(el), -Math.cos(az) * Math.cos(el)),
    daylight: THREE.MathUtils.smoothstep(sinEl, -0.05, 0.12),
  };
}

export function clockLabel(hour) {
  const h = Math.floor(hour);
  const m = Math.floor((hour - h) * 60 / 15) * 15;
  return `${((h + 11) % 12) + 1}:${String(m).padStart(2, "0")} ${h < 12 ? "am" : "pm"}`;
}
