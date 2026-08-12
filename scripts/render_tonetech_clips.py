"""Render demo clips for the ToneTech post.

Input is a synthetic Karplus-Strong "DI guitar" riff; output is that riff run
through ToneTech's factory presets with the offline engine.
Run with tonetech's venv:  ../tonetech/.venv/bin/python scripts/render_tonetech_clips.py
"""
import subprocess, sys, wave
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tonetech" / "src"))
from tonetech.engine import NullEngine
from tonetech.library import preset
from tonetech.rig import RigState

SR = 48000
rng = np.random.default_rng(7)


def pluck(freq, dur, damp=0.996):
    n = int(SR * dur)
    period = int(SR / freq)
    buf = rng.uniform(-1, 1, period)
    out = np.empty(n)
    for i in range(n):
        out[i] = buf[i % period]
        buf[i % period] = damp * 0.5 * (buf[i % period] + buf[(i + 1) % period])
    return out


def riff():
    # E minor pentatonic-ish lick + a chord stab, in (midi, start_s, dur_s)
    notes = [(40, 0.0, 0.5), (47, 0.0, 0.5), (52, 0.0, 0.5),
             (52, 0.6, 0.3), (55, 0.9, 0.3), (57, 1.2, 0.3), (59, 1.5, 0.6),
             (57, 2.1, 0.3), (55, 2.4, 0.3), (52, 2.7, 0.9),
             (40, 3.8, 1.6), (47, 3.8, 1.6), (52, 3.8, 1.6), (55, 3.8, 1.6), (59, 3.8, 1.6)]
    total = int(SR * 6.5)
    sig = np.zeros(total)
    for midi, start, dur in notes:
        f = 440 * 2 ** ((midi - 69) / 12)
        s = int(SR * start)
        tone = pluck(f, dur + 0.8)
        env = np.ones_like(tone); env[int(SR * dur):] = np.linspace(1, 0, len(tone) - int(SR * dur))
        seg = (tone * env)[: total - s]
        sig[s : s + len(seg)] += seg * 0.3
    return sig.astype(np.float32)


def write_mp3(audio, path):
    audio = np.atleast_2d(audio)
    if audio.shape[0] == 1:
        audio = np.vstack([audio, audio])
    audio = audio / max(1e-6, np.max(np.abs(audio))) * 0.89
    pcm = (audio.T * 32767).astype(np.int16)
    wav = path.with_suffix(".wav")
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "160k", str(path)], check=True)
    wav.unlink()


out = Path(__file__).resolve().parents[1] / "public" / "audio"
dry = riff()
write_mp3(dry, out / "tonetech-dry.mp3")
for name, slug in [("Glassy Clean", "glassy-clean"), ("Plexi Crunch", "plexi-crunch"), ("Comfortably Wet", "comfortably-wet")]:
    engine = NullEngine(RigState(preset(name)))
    write_mp3(engine.render(dry[np.newaxis, :], SR), out / f"tonetech-{slug}.mp3")
    print("rendered", name)
