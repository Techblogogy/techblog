"""Tiny procedural music generator: numpy in, mp3 out.

    python gen.py --seed 3 --mood dusk --bars 16 out.mp3

Harmony is a Markov chain over scale degrees, the melody is a weighted random
walk that prefers chord tones on strong beats, drums come from probability
grids, and every sound is synthesised from scratch.
"""
import argparse, subprocess, wave
import numpy as np

SR = 44100
MOODS = {
    #        root  scale                     bpm  swing
    "dusk":  (57, [0, 2, 3, 5, 7, 8, 10],    84, 0.12),   # A minor, lazy
    "neon":  (50, [0, 2, 3, 5, 7, 9, 10],   118, 0.0),    # D dorian, driving
}
# Which scale degree tends to follow which (0 = i, 3 = iv, 4 = v, 5 = VI ...)
CHORD_MARKOV = {
    0: {3: 0.35, 5: 0.3, 4: 0.2, 6: 0.15},
    3: {0: 0.3, 4: 0.4, 6: 0.3},
    4: {0: 0.6, 5: 0.4},
    5: {3: 0.5, 6: 0.3, 4: 0.2},
    6: {0: 0.7, 3: 0.3},
}
DRUMS = {  # probability of a hit on each 16th
    "kick":  [1, 0, 0, 0, .1, 0, .5, 0, .9, 0, .2, 0, .1, 0, .3, .1],
    "snare": [0, 0, 0, 0, 1, 0, 0, .1, 0, 0, 0, 0, 1, 0, .1, .2],
    "hat":   [.9, .4, .8, .4] * 4,
}


def midi_hz(m): return 440.0 * 2 ** ((m - 69) / 12)


def adsr(n, a=.01, d=.1, s=.6, r=.2):
    a, d, r = (max(1, int(x * SR)) for x in (a, d, r))
    env = np.full(n, s)
    env[:a] = np.linspace(0, 1, a)[: n]
    env[a:a + d] = np.linspace(1, s, d)[: max(0, n - a)]
    env[-r:] *= np.linspace(1, 0, r)[-min(r, n):]
    return env


def saw_pad(freq, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    detune = [0.997, 1.0, 1.003]
    x = sum(2 * ((t * freq * d) % 1) - 1 for d in detune) / 3
    # one-pole lowpass whose cutoff breathes over the note
    cutoff = 600 + 900 * np.sin(np.pi * t / dur)
    alpha = 1 - np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty(n); acc = 0.0
    for i in range(n):
        acc += alpha[i] * (x[i] - acc); y[i] = acc
    return y * adsr(n, .3, .4, .7, .6)


def pluck_lead(freq, dur):
    t = np.arange(int(dur * SR)) / SR
    mod = 1.5 * np.sin(2 * np.pi * freq * 2 * t) * np.exp(-t * 6)   # decaying modulator
    return np.sin(2 * np.pi * freq * t + mod) * adsr(len(t), .005, .15, .3, .1)


def kick(): t = np.arange(int(.35 * SR)) / SR; return np.sin(2 * np.pi * (45 + 90 * np.exp(-t * 30)) * t) * np.exp(-t * 9)
def snare(rng): t = np.arange(int(.2 * SR)) / SR; return (rng.uniform(-1, 1, len(t)) * .6 + np.sin(2 * np.pi * 190 * t) * .4) * np.exp(-t * 22)
def hat(rng): t = np.arange(int(.05 * SR)) / SR; return np.diff(rng.uniform(-1, 1, len(t) + 1)) * np.exp(-t * 90) * .5


def generate(seed, mood, bars):
    rng = np.random.default_rng(seed)
    root, scale, bpm, swing = MOODS[mood]
    step = 60 / bpm / 4  # a 16th note
    total = int((bars * 16 * step + 2) * SR)
    mix = {k: np.zeros(total) for k in ("pad", "lead", "drums")}

    def put(track, sig, t):
        s = int(t * SR); e = min(total, s + len(sig)); mix[track][s:e] += sig[: e - s]

    def degree_note(deg, octave=0):
        return root + scale[deg % 7] + 12 * (deg // 7 + octave)

    chord, prev_note = 0, 7
    for bar in range(bars):
        chord_tones = [chord, chord + 2, chord + 4]
        for d in chord_tones:
            put("pad", saw_pad(midi_hz(degree_note(d, -1)), 16 * step * 1.05), bar * 16 * step)
        for s16 in range(16):
            t = (bar * 16 + s16) * step + (swing * step if s16 % 2 else 0)
            for name, grid in DRUMS.items():
                if rng.random() < grid[s16]:
                    put("drums", {"kick": kick, "snare": lambda: snare(rng), "hat": lambda: hat(rng)}[name](), t)
            if s16 % 2 == 0 and rng.random() < (.85 if s16 % 4 == 0 else .45):
                # random walk, pulled toward chord tones on strong beats
                cands = np.arange(prev_note - 4, prev_note + 5)
                w = np.exp(-np.abs(cands - prev_note) / 2.0)
                if s16 % 4 == 0:
                    w *= np.where(np.isin(cands % 7, [c % 7 for c in chord_tones]), 4.0, 1.0)
                prev_note = int(np.clip(rng.choice(cands, p=w / w.sum()), 3, 14))
                put("lead", pluck_lead(midi_hz(degree_note(prev_note)), step * 2.5), t)
        nxt = CHORD_MARKOV[chord]
        chord = int(rng.choice(list(nxt), p=list(nxt.values())))

    out = mix["pad"] * .25 + mix["lead"] * .22 + mix["drums"] * .5
    # cheap stereo: short delay on one side for width
    d = int(.013 * SR)
    left, right = out, np.concatenate([np.zeros(d), out[:-d]])
    stereo = np.vstack([left, right])
    return stereo / np.max(np.abs(stereo)) * .89


def write_mp3(stereo, path):
    pcm = (stereo.T * 32767).astype(np.int16)
    wav = path.rsplit(".", 1)[0] + ".wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-b:a", "160k", path], check=True)
    subprocess.run(["rm", wav])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--mood", choices=MOODS, default="dusk"); ap.add_argument("--bars", type=int, default=8)
    a = ap.parse_args()
    write_mp3(generate(a.seed, a.mood, a.bars), a.out)
