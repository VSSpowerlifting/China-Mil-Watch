// Draws the prototype plates for the Indo-Pacific Record prototype.
//
// Halftone expects a picture on every article. IPR has no licensed image pipeline for Briefs yet,
// and a stock or borrowed photograph beside an official-source brief would imply a provenance it
// does not have. So these plates are generated, and every article credits them as such.
//
// The look follows IPR's Signal Veil (DECISION_LOG 2026-07-12): a navy-duotone field keyed to the
// ground it sits on, strongest at the upper right and shaped by a soft radial mask union so no
// hard rectangle ever reads as a photo card. Production's veil is a duotone of a credited source
// photograph; this one is abstract -- layered swell bands, a few thin signal traces, a fine dot
// mesh, scanlines and grain. Nothing in it depicts a place, vessel or event.
//
//   node scripts/make-ipr-plates.mjs
import sharp from 'sharp';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

const out = new URL('../src/assets/plates/', import.meta.url).pathname;
mkdirSync(out, { recursive: true });

// Deterministic per name, so regenerating does not churn the repository.
const rand = (seed) => {
  let s = [...seed].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7);
  return () => (s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32;
};

// The ground is the Night Desk page colour (tokens.css --plate), so a plate's edge disappears
// into the page. [deep, mid, light, trace] per desk: one teal family, shifted per desk.
const ground = '#0b121c';
const palettes = {
  china: ['#0d3038', '#17606a', '#4fb3ad', '#8fe0d8'],
  singapore: ['#0b3140', '#16627a', '#4fb0c8', '#93dbea'],
  regional: ['#12283c', '#28536f', '#7aa3bc', '#b4d2e2'],
  archive: ['#16252f', '#34505c', '#8aa8b0', '#bfd4d8'],
  default: ['#0d3038', '#17606a', '#4fb3ad', '#8fe0d8'],
};

const f = (n) => n.toFixed(1);

const svg = (w, h, palette, seed) => {
  const r = rand(seed);
  const [deep, mid, light, trace] = palettes[palette];

  // Atmosphere: broad, heavily blurred masses -- the "duotone" body of the veil.
  const masses = Array.from({ length: 5 }, (_, i) => {
    const fill = [deep, mid, mid, light, deep][i];
    return `<ellipse cx="${f(w * (0.45 + r() * 0.5))}" cy="${f(h * (0.1 + r() * 0.55))}" rx="${f(w * (0.18 + r() * 0.22))}" ry="${f(h * (0.12 + r() * 0.18))}" fill="${fill}" opacity="${(0.55 + r() * 0.35).toFixed(2)}"/>`;
  }).join('');

  // Swell bands: long, gently curving strata, softly blurred. Layered, not literal.
  const bands = Array.from({ length: 9 }, (_, i) => {
    const y = h * (0.08 + i * 0.09 + r() * 0.03);
    const a = h * (0.02 + r() * 0.04);
    const t = h * (0.006 + r() * 0.012);
    const c1 = w * (0.25 + r() * 0.2);
    const c2 = w * (0.6 + r() * 0.2);
    return `<path d="M0 ${f(y)} C${f(c1)} ${f(y - a)} ${f(c2)} ${f(y + a)} ${w} ${f(y - a * 0.4)} L${w} ${f(y - a * 0.4 + t)} C${f(c2)} ${f(y + a + t)} ${f(c1)} ${f(y - a + t)} 0 ${f(y + t)} Z" fill="${i % 3 === 0 ? light : mid}" opacity="${(0.18 + r() * 0.22).toFixed(2)}"/>`;
  }).join('');

  // Signal traces: a few thin, unblurred lines with a low, irregular oscillation.
  const traces = Array.from({ length: 4 }, () => {
    const y0 = h * (0.14 + r() * 0.5);
    const amp = h * (0.004 + r() * 0.012);
    const freq = 2 + r() * 5;
    const phase = r() * Math.PI * 2;
    const pts = [];
    for (let x = 0; x <= w; x += 12) {
      const u = x / w;
      const y = y0 + Math.sin(u * Math.PI * freq + phase) * amp + Math.sin(u * Math.PI * freq * 3.7) * amp * 0.25;
      pts.push(`${x},${f(y)}`);
    }
    return `<polyline points="${pts.join(' ')}" fill="none" stroke="${trace}" stroke-width="1.2" opacity="${(0.16 + r() * 0.16).toFixed(2)}"/>`;
  }).join('');

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
  <defs>
    <filter id="haze" filterUnits="userSpaceOnUse" x="0" y="0" width="${w}" height="${h}"><feGaussianBlur stdDeviation="${f(w / 16)}"/></filter>
    <filter id="soft" filterUnits="userSpaceOnUse" x="0" y="0" width="${w}" height="${h}"><feGaussianBlur stdDeviation="${f(w / 260)}"/></filter>
    <filter id="grain" filterUnits="userSpaceOnUse" x="0" y="0" width="${w}" height="${h}">
      <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed="${Math.floor(r() * 100)}" result="n"/>
      <feColorMatrix in="n" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.55 0"/>
    </filter>
    <pattern id="mesh" width="7" height="7" patternUnits="userSpaceOnUse"><circle cx="3.5" cy="3.5" r="0.9" fill="${trace}"/></pattern>
    <pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1" fill="#000"/></pattern>
    <!-- The veil's mask: production's radial union, strongest at 78% / 32%, a faint pool low left. -->
    <radialGradient id="m1" gradientUnits="userSpaceOnUse" cx="${f(w * 0.78)}" cy="${f(h * 0.32)}" r="${f(w * 0.78)}" gradientTransform="translate(${f(w * 0.78)} ${f(h * 0.32)}) scale(1 ${f((1.1 * h) / (0.78 * w))}) translate(${f(-w * 0.78)} ${f(-h * 0.32)})">
      <stop offset="0.28" stop-color="#fff"/><stop offset="0.52" stop-color="#fff" stop-opacity="0.68"/><stop offset="0.74" stop-color="#fff" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="m2" gradientUnits="userSpaceOnUse" cx="${f(w * 0.3)}" cy="${f(h * 0.92)}" r="${f(w * 0.38)}" gradientTransform="translate(${f(w * 0.3)} ${f(h * 0.92)}) scale(1 ${f((0.52 * h) / (0.38 * w))}) translate(${f(-w * 0.3)} ${f(-h * 0.92)})">
      <stop offset="0" stop-color="#fff" stop-opacity="0.35"/><stop offset="0.62" stop-color="#fff" stop-opacity="0"/>
    </radialGradient>
    <mask id="veil" maskUnits="userSpaceOnUse" x="0" y="0" width="${w}" height="${h}">
      <rect width="${w}" height="${h}" fill="url(#m1)"/>
      <rect width="${w}" height="${h}" fill="url(#m2)"/>
    </mask>
  </defs>
  <rect width="${w}" height="${h}" fill="${ground}"/>
  <g mask="url(#veil)">
    <rect width="${w}" height="${h}" fill="${deep}" opacity="0.55"/>
    <g filter="url(#haze)">${masses}</g>
    <g filter="url(#soft)">${bands}</g>
    <rect width="${w}" height="${h}" fill="url(#mesh)" opacity="0.07"/>
    ${traces}
    <rect width="${w}" height="${h}" fill="url(#scan)" opacity="0.14"/>
  </g>
  <rect width="${w}" height="${h}" filter="url(#grain)" opacity="0.045"/>
</svg>`;
};

const plates = [
  ['pla-exercise-messaging', 'china'],
  ['mindef-procurement-record', 'singapore'],
  ['regional-statement-tracker', 'regional'],
  ['preserving-official-records', 'archive'],
  ['default', 'default'],
];

await Promise.all(
  plates.map(([name, palette]) =>
    sharp(Buffer.from(svg(1800, 1200, palette, name)))
      .avif({ quality: 60 })
      .toFile(join(out, `${name}.avif`)),
  ),
);
console.log(`${plates.length} plates → src/assets/plates/`);
