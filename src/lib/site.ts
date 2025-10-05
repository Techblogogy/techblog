export const SITE = {
  name: 'techblogogy',
  author: 'Fedor Bobylev',
  description:
    'Fedor Bobylev learns by playing with things (code, sound, hardware) and writes about what he tried and what he found out.',
  github: 'https://github.com/Techblogogy',
};

// Deterministic PRNG so a post's trace is the same on every build.
export function seeded(str: string) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) h = Math.imul(h ^ str.charCodeAt(i), 16777619);
  return () => {
    h += 0x6d2b79f5;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A short "signal" for a post: a few partials under an envelope, as an SVG path. */
export function tracePath(slug: string, width = 240, height = 40, points = 120) {
  const rnd = seeded(slug);
  const partials = Array.from({ length: 3 + Math.floor(rnd() * 3) }, () => ({
    f: 1 + Math.floor(rnd() * 14),
    a: 0.25 + rnd() * 0.75,
    p: rnd() * Math.PI * 2,
  }));
  const attack = 0.05 + rnd() * 0.3;
  const decay = 1.5 + rnd() * 4;
  const norm = partials.reduce((s, p) => s + p.a, 0);
  let d = '';
  for (let i = 0; i <= points; i++) {
    const x = i / points;
    const env = x < attack ? x / attack : Math.exp(-(x - attack) * decay);
    const y = partials.reduce((s, p) => s + p.a * Math.sin(2 * Math.PI * p.f * x + p.p), 0) / norm;
    const px = (x * width).toFixed(1);
    const py = (height / 2 - y * env * (height / 2 - 2)).toFixed(1);
    d += `${i ? 'L' : 'M'}${px} ${py}`;
  }
  return d;
}

export function formatDate(d: Date) {
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function readingMinutes(body = '') {
  return Math.max(1, Math.round(body.split(/\s+/).length / 230));
}
