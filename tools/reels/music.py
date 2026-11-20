"""Musiques maison WOD Genius, une ambiance par Reel (libres de droits, synthétisées ici).
Usage : python3 music.py <style> sortie.wav [duree]
Styles : lofi (88 BPM, RPE), house (120 BPM, Hollow). La boucle électro 128 BPM (Fran) est dans loop.py.
"""
import sys, wave
import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
rng = np.random.default_rng(11)

def tt(d): return np.arange(int(d * SR)) / SR
def lp(x, f): return sosfilt(butter(2, f, 'low', fs=SR, output='sos'), x)
def hp(x, f): return sosfilt(butter(2, f, 'high', fs=SR, output='sos'), x)
def bp(x, f1, f2): return sosfilt(butter(2, [f1, f2], 'band', fs=SR, output='sos'), x)
def note(n): return 440 * 2 ** (n / 12)          # demi-tons depuis la4

class Mix:
    def __init__(self, dur, pre):
        self.pre = pre; self.n = int(SR * (dur + pre))
        self.L = np.zeros(self.n); self.R = np.zeros(self.n)
    def add(self, sig, t, gain=1.0, pan=0.0):
        s = int((t + self.pre) * SR)          # t en temps vidéo
        if s < 0: sig = sig[-s:]; s = 0
        if s >= self.n or len(sig) == 0: return
        sig = sig[: self.n - s]
        self.L[s:s + len(sig)] += sig * gain * np.sqrt(0.5 * (1 - pan))
        self.R[s:s + len(sig)] += sig * gain * np.sqrt(0.5 * (1 + pan))
    def render(self, path, fade_out=0.8):
        st = np.stack([self.L, self.R], 1)[int(self.pre * SR):]
        fi = int(0.01 * SR); st[:fi] *= np.linspace(0, 1, fi)[:, None]
        fo = int(fade_out * SR); st[-fo:] *= (np.linspace(1, 0, fo) ** 1.5)[:, None]
        st = np.tanh(st * 1.1) / np.tanh(1.1)
        st *= 0.89 / np.max(np.abs(st))
        with wave.open(path, 'wb') as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((st * 32767).astype('<i2').tobytes())

def saw(f, d, harm=20):
    t = tt(d); x = np.zeros(len(t))
    for k in range(1, harm + 1):
        if f * k > 15000: break
        x += np.sin(2 * np.pi * f * k * t) / k
    return x * (2 / np.pi)

def kick(soft=False):
    t = tt(0.4)
    f = 48 + (80 if soft else 120) * np.exp(-t / (0.04 if soft else 0.03))
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (0.16 if soft else 0.11))
    click = hp(rng.standard_normal(len(t)), 2500) * np.exp(-t / 0.003) * (0.08 if soft else 0.25)
    x = np.tanh(1.4 * (body + click))
    return lp(x, 3500) if soft else x

def snare(soft=False):
    t = tt(0.3)
    nz = bp(rng.standard_normal(len(t)), 1200, 6000 if soft else 9000) * np.exp(-t / (0.09 if soft else 0.05))
    tone = np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.05)
    return 0.7 * nz + 0.45 * tone

def clap():
    t = tt(0.25); x = np.zeros(len(t))
    for k, o in enumerate([0, 0.011, 0.022]):
        s = int(o * SR); n = len(t) - s
        x[s:] += bp(rng.standard_normal(n), 900, 5000) * np.exp(-np.arange(n) / SR / (0.012 if k < 2 else 0.08))
    return x

def hat(dec=0.012, d=0.05, cut=7000):
    t = tt(d); return hp(rng.standard_normal(len(t)), cut) * np.exp(-t / dec)

def epiano(freqs, d):
    t = tt(d); x = np.zeros(len(t))
    for f in freqs:
        x += (np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t) + 0.08 * np.sin(6 * np.pi * f * t)) * np.exp(-t / 1.3)
    x *= (1 + 0.15 * np.sin(2 * np.pi * 4.5 * t)) * np.minimum(1, t / 0.01) * np.minimum(1, (d - t) / 0.05)
    return lp(x, 2800) / len(freqs)

def delay(m, time, fb=0.35, mix=0.25):
    for ch in (m.L, m.R):
        d = int(time * SR); y = ch.copy()
        for k in range(1, 4):
            y[d * k:] += ch[: len(ch) - d * k] * (fb ** k)
        ch[:] = ch * (1 - mix) + y * mix

# ---------------------------------------------------------------- lo-fi (RPE)
def lofi(path, dur, accent=9.8, full_at=3.4):
    bpm = 88; beat = 60 / bpm; bar = 4 * beat
    pre = 3 * bar - accent         # temps fort calé sur l'exemple chiffré
    while pre < 0: pre += bar
    m = Mix(dur, pre)
    # Fmaj7 - Em7 - Dm7 - Cmaj7 (accords en position serrée, tessiture médium)
    chords = [[-4, 0, 3, 7], [-5, -2, 2, 5], [-7, -4, 0, 3], [-9, -5, -2, 2]]
    roots = [note(-28), note(-29), note(-31), note(-33)]   # fa2, mi2, ré2, do2
    nbars = int((dur + pre) / bar) + 1
    for b in range(nbars):
        t0 = b * bar - pre
        c = b % 4
        m.add(epiano([note(n) for n in chords[c]], bar * 0.98), t0, 0.55)
        tb = tt(bar * 0.95)
        bass = np.sin(2 * np.pi * roots[c] * tb) * np.minimum(1, tb / 0.02) * np.exp(-tb / 2.0)
        m.add(bass, t0, 0.5)
        for k in range(4):
            tk = t0 + k * beat
            full = tk >= full_at - 0.01
            if k in (0,) or (k == 2 and full) or (k == 2 and b % 2):
                m.add(kick(soft=True), tk, 0.75 if full else 0.5)
            if k in (1, 3) and full:
                m.add(snare(soft=True), tk + 0.012, 0.32)
            for h in range(2):                          # croches avec swing
                th = tk + h * beat / 2 + (0.06 if h else 0)
                m.add(hat(0.02, 0.06, 6000), th, (0.07 if h else 0.1) * (1 if full else 0.6), 0.3)
    # crépitement vinyle + souffle
    n = m.n; crackle = np.zeros(n)
    idx = rng.integers(0, n, size=int((dur + pre) * 18)); crackle[idx] = rng.uniform(-1, 1, len(idx))
    crackle = hp(crackle, 1500) * 0.12 + lp(rng.standard_normal(n), 6000) * 0.005
    m.L += crackle; m.R += np.roll(crackle, 113)
    delay(m, beat * 0.75, 0.3, 0.2)
    # légère « usure » : passe-bas global
    m.L = lp(m.L, 7000); m.R = lp(m.R, 7000)
    m.render(path, 1.0)
    return bpm

# ---------------------------------------------------------------- minimal house (Hollow)
def house(path, dur, start=3.4, cta=14.3):
    bpm = 120; beat = 0.5; bar = 2.0
    pre = 2 * bar - start          # mesure 3 calée sur l'apparition des étapes
    m = Mix(dur, pre)
    stab = [note(n) for n in (-17, -10, -5, -2, 2)]     # mi, si, mi, sol, si : accord Em(add9) ouvert
    bassline = [note(-41), None, note(-41), note(-29), None, note(-41), note(-38), None]   # mi1 / mi2 / sol1
    nbars = int((dur + pre) / bar) + 1
    breakdown = start + bar * np.ceil((cta - start) / bar)   # première mesure après le message final
    for b in range(nbars):
        t0 = b * bar - pre
        for k in range(4):
            tk = t0 + k * beat
            intro = tk < start - 0.01; brk = tk >= breakdown - 0.01
            if not brk: m.add(kick(), tk, 0.7 if intro else 0.85)
            if k in (1, 3) and not intro and not brk: m.add(clap(), tk, 0.3, -0.1)
            m.add(hat(0.05, 0.14, 8000), tk + beat / 2, 0.11 if not brk else 0.06, 0.2)       # charley ouvert à contretemps
            if not intro:
                m.add(hat(0.008, 0.03, 9000), tk + beat / 4, 0.05, -0.3)
                m.add(hat(0.008, 0.03, 9000), tk + 3 * beat / 4, 0.05, -0.3)
        # basse en croches
        if t0 >= start - bar - 0.01:
            for k, f in enumerate(bassline):
                if f is None: continue
                tk = t0 + k * beat / 2
                if tk < start - 0.01 or tk >= breakdown: continue
                d = beat / 2 * 0.85; tb = tt(d)
                x = lp(saw(f, d, 10), 300) + 0.6 * np.sin(2 * np.pi * f * tb)
                m.add(np.tanh(1.4 * x) * np.minimum(1, tb / 0.004) * np.minimum(1, (d - tb) / 0.015), tk, 0.42)
        # accord « stab » sur le contretemps du 2e temps, filtre qui s'ouvre au fil des étapes
        for k in (1.5, 3.5) if b % 2 else (1.5,):
            tk = t0 + k * beat
            cutoff = 900 + 2600 * min(1, max(0, (tk - start) / 9.0))
            d = 0.3; ts = tt(d)
            x = sum(saw(f, d, 14) for f in stab) / len(stab)
            m.add(lp(x, cutoff) * np.exp(-ts / 0.09) * np.minimum(1, ts / 0.003), tk, 0.45, 0.15)
    # nappe sur la fin (fin calme pour le message « Gaine d'abord »)
    t = tt(dur - breakdown + 0.5)
    pad = sum(np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.003 * t) for f in stab) / len(stab)
    m.add(lp(pad, 1800) * np.minimum(1, t / 0.6), breakdown - 0.3, 0.22)
    delay(m, beat * 0.75, 0.35, 0.22)
    m.render(path, 0.9)
    return bpm

STYLES = {'lofi': lofi, 'house': house}
if __name__ == '__main__':
    style, out = sys.argv[1], sys.argv[2]
    dur = float(sys.argv[3]) if len(sys.argv) > 3 else 13.5
    print('ok', style, STYLES[style](out, dur), 'BPM')
