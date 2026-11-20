"""Musiques maison WOD Genius, une ambiance par Reel (libres de droits, synthétisées ici).
Usage : python3 music.py <style> sortie.wav [duree]
Styles : lofi (88 BPM, RPE), house (120 BPM, Hollow), synthwave, trap, boombap, phonk, phonk118, garage (126 BPM). La boucle électro 128 BPM (Fran) est dans loop.py.
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


# ---------------------------------------------------------------- styles ajoutés le 20 nov. 2026
def _grid(dur, bpm, cue):
    beat = 60 / bpm; bar = 4 * beat
    k = int(np.ceil(cue / bar)); pre = k * bar - cue
    return beat, bar, pre, Mix(dur, pre), int((dur + pre) / bar) + 1

def pluck(f, d=0.3, cut=3000, dec=0.09, harm=18):
    t = tt(d); x = saw(f, d, harm) + 0.4 * saw(f * 1.004, d, harm)
    return lp(x, cut) * np.exp(-t / dec) * np.minimum(1, t / 0.002)

def pad(freqs, d, cut=1500):
    t = tt(d); x = np.zeros(len(t))
    for f in freqs:
        x += saw(f, d, 10) + saw(f * 1.006, d, 10) + saw(f * 0.994, d, 10)
    env = np.minimum(1, t / 0.25) * np.minimum(1, (d - t) / 0.3)
    return lp(x / (3 * len(freqs)), cut) * env

def bell(f, d=0.8):
    t = tt(d)
    return (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * f * 3.01 * t) * np.exp(-t / 0.15)) * np.exp(-t / 0.35) * np.minimum(1, t / 0.002)

def sub808(f, d):
    t = tt(d); fr = f * (1 + 0.6 * np.exp(-t / 0.03))
    x = np.sin(2 * np.pi * np.cumsum(fr) / SR)
    return np.tanh(1.8 * x) * np.exp(-t / (d / 2.5)) * np.minimum(1, t / 0.003)

def synthwave(path, dur, cue=3.4):
    """Synthwave 108 BPM, la mineur : nappes, arpège en croches, caisse claire ample."""
    beat, bar, pre, m, nb = _grid(dur, 108, cue)
    chords = [[-12, -9, -5, 0], [-16, -12, -9, -4], [-9, -5, -2, 3], [-14, -10, -7, -2]]   # Am F C G
    roots = [note(-36), note(-40), note(-33), note(-38)]
    for b in range(nb):
        t0 = b * bar - pre; c = b % 4; full = t0 >= cue - 0.01
        m.add(pad([note(n) for n in chords[c]], bar, 1400 if full else 900), t0, 0.5)
        for k in range(8):
            tk = t0 + k * beat / 2
            n = chords[c][[0, 1, 2, 3, 2, 1, 2, 3][k]] + 12
            m.add(pluck(note(n), 0.28, 2600 if full else 1500, 0.08), tk, 0.14, -0.3 if k % 2 else 0.3)
            if full:
                tb = tt(beat / 2 * 0.85)
                m.add(lp(saw(roots[c] * (2 if k % 2 else 1), beat / 2 * 0.85, 10), 500) * np.minimum(1, tb / 0.004), tk, 0.32)
        if full:
            for k in range(4):
                tk = t0 + k * beat
                if k in (0, 2): m.add(kick(), tk, 0.75)
                if k in (1, 3):
                    t = tt(0.6); big = bp(rng.standard_normal(len(t)), 900, 7000) * np.exp(-t / 0.18)
                    m.add(big, tk, 0.13)
                    m.add(snare(), tk, 0.3)
                for h in range(2): m.add(hat(0.01, 0.04, 8000), tk + h * beat / 2, 0.06, 0.2)
    delay(m, beat * 0.75, 0.4, 0.28)
    m.render(path, 1.0); return 108

def funk(path, dur, cue=3.4):
    """Funk 112 BPM, mi mineur : basse syncopée, accords courts à contretemps, caisse claire avec notes fantômes."""
    beat, bar, pre, m, nb = _grid(dur, 112, cue)
    s16 = beat / 4
    bass_pat = [(0, -29), (3, -29), (6, -26), (8, -29), (10, -24), (11, -22), (14, -29)]   # mi2, sol2, la2, si2
    stab = [note(n) for n in (-5, -1, 2, 7)]                                                 # mi9 en position médium
    for b in range(nb):
        t0 = b * bar - pre; full = t0 >= cue - 0.01
        for st, n in bass_pat:
            d = s16 * 1.6; tb = tt(d); f = note(n - 12)
            x = lp(saw(f, d, 14), 900) * np.exp(-tb / 0.12) * np.minimum(1, tb / 0.003)
            m.add(np.tanh(1.5 * x), t0 + st * s16, 0.45)
        for k in range(16):
            tk = t0 + k * s16
            m.add(hat(0.008, 0.03, 8000), tk + (0.012 if k % 2 else 0), 0.06 if k % 2 else 0.09, 0.25)
            if not full: continue
            if k in (0, 7, 10): m.add(kick(), tk, 0.75)
            if k in (4, 12): m.add(snare(), tk, 0.4)
            if k in (6, 9, 15): m.add(snare(soft=True), tk, 0.08)
            if k in (2, 6, 14):
                d = 0.12; ts = tt(d)
                x = sum(np.sign(np.sin(2 * np.pi * f * ts)) for f in stab) / len(stab)
                m.add(lp(x, 2400) * np.exp(-ts / 0.05), tk, 0.16, -0.25)
    m.render(path, 1.0); return 112

def trap(path, dur, cue=3.4):
    """Hip-hop « trap » posé, 72 BPM, do mineur : 808, charleys en doubles-croches avec roulements, cloche."""
    beat, bar, pre, m, nb = _grid(dur, 72, cue)
    s16 = beat / 4
    mel = [-9, -6, -2, 1, -2, -6, -4, -9]      # do, mib, sol, sib… (pentatonique de do mineur)
    roots = [note(-33 - 12), note(-37 - 12)]  # do1, lab0
    for b in range(nb):
        t0 = b * bar - pre; full = t0 >= cue - 0.01
        for k in range(8):
            m.add(bell(note(mel[k] + 12), 0.7), t0 + k * beat / 2, 0.16, 0.2 if k % 2 else -0.2)
        m.add(pad([note(n) for n in (-21, -18, -14)], bar, 1100), t0, 0.28)
        if not full: continue
        r = roots[b % 2]
        m.add(sub808(r * 2, beat * 1.5), t0, 0.6); m.add(sub808(r * 2, beat), t0 + 2.5 * beat, 0.5)
        m.add(kick(), t0, 0.5); m.add(kick(), t0 + 2.5 * beat, 0.4)
        m.add(clap(), t0 + 2 * beat, 0.35)
        for k in range(16):
            tk = t0 + k * s16
            if b % 2 and k in (13, 14, 15):        # roulement en triples-croches
                for r3 in range(2): m.add(hat(0.006, 0.02, 9000), tk + r3 * s16 / 2, 0.06, 0.3)
            else:
                m.add(hat(0.008, 0.03, 9000), tk, 0.07 if k % 2 else 0.09, 0.3)
    delay(m, beat * 0.5, 0.3, 0.18)
    m.render(path, 1.0); return 72

def boombap(path, dur, cue=3.4):
    """Boom-bap 94 BPM, ré mineur : piano jazzy, contrebasse, batterie qui balance."""
    beat, bar, pre, m, nb = _grid(dur, 94, cue)
    chords = [[-19, -16, -12, -7], [-14, -10, -7, -3], [-21, -17, -14, -10], [-12, -9, -5, 0]]   # Dm9, G7, Cmaj7, A7-ish
    roots = [note(-31 - 12), note(-26 - 12), note(-33 - 12), note(-24 - 12)]
    sw = beat / 2 * 0.16
    for b in range(nb):
        t0 = b * bar - pre; c = b % 4; full = t0 >= cue - 0.01
        m.add(epiano([note(n) for n in chords[c]], beat * 1.8), t0, 0.6)
        m.add(epiano([note(n) for n in chords[c]], beat * 1.4), t0 + 2.5 * beat + sw, 0.4)
        if not full:
            continue
        for k, st in enumerate([0, 1.5, 2, 3]):
            d = beat * 0.9; tb = tt(d); f = roots[c] * (1.5 if k == 2 else 1)
            m.add(np.sin(2 * np.pi * f * tb) * np.exp(-tb / 0.35) * np.minimum(1, tb / 0.01), t0 + st * beat, 0.5)
        for k in range(8):
            tk = t0 + k * beat / 2 + (sw if k % 2 else 0)
            if k in (0, 3, 5): m.add(kick(soft=True), tk, 0.8)
            if k in (2, 6): m.add(snare(), tk, 0.45)
            m.add(hat(0.015, 0.05, 7000), tk, 0.07 if k % 2 else 0.1, 0.2)
    n = m.n; crackle = np.zeros(n); idx = rng.integers(0, n, size=int((dur + pre) * 10)); crackle[idx] = rng.uniform(-1, 1, len(idx))
    c = hp(crackle, 1500) * 0.08; m.L += c; m.R += np.roll(c, 97)
    m.L = lp(m.L, 9000); m.R = lp(m.R, 9000)
    m.render(path, 1.0); return 94

def cowbell(f, d=0.22):
    t = tt(d)
    x = np.sign(np.sin(2 * np.pi * f * t)) + np.sign(np.sin(2 * np.pi * f * 1.48 * t))
    return bp(x, 450, 2600) * np.exp(-t / 0.07) * np.minimum(1, t / 0.001)

def phonk(path, dur, cue=3.6, drop=13.8, bpm=125, tr=0):
    """Phonk de salle de sport, 125 BPM, fa mineur : cloche (cowbell) mélodique, 808 saturé, caisse claire en demi-temps.
    bpm et tr (transposition en demi-tons) permettent une variante (ex. 118 BPM, sol mineur : tr=2)."""
    beat, bar, pre, m, nb = _grid(dur, bpm, cue)
    s16 = beat / 4
    riff = [0, None, 3, None, 7, 5, None, 3, 0, None, 3, 5, None, 3, -2, None]      # fa, lab, do, sib… (fa mineur)
    roots = [note(-40 + tr), note(-40 + tr), note(-45 + tr), note(-43 + tr)]          # fa0… réb0, mib0 (808)
    for b in range(nb):
        t0 = b * bar - pre
        full = t0 >= cue - 0.01; big = t0 >= drop - 0.05
        for k, n in enumerate(riff):
            if n is None: continue
            m.add(cowbell(note(n - 4 + tr)), t0 + k * s16, 0.22 if big else 0.17, 0.15 if k % 2 else -0.15)
        if not full:
            continue
        r = roots[b % 4]
        m.add(np.tanh(2.2 * sub808(r * 2, beat * 1.6)), t0, 0.55)
        m.add(np.tanh(2.2 * sub808(r * 2, beat * 1.2)), t0 + 2.5 * beat, 0.45)
        for k in range(4):
            tk = t0 + k * beat
            if k in (0, 2) or (big and k == 3): m.add(kick(), tk, 0.8)
            if k == 2: m.add(clap(), tk, 0.45); m.add(snare(), tk, 0.25)
        for k in range(8 if not big else 16):
            step = beat / 2 if not big else s16
            m.add(hat(0.008, 0.03, 9000), t0 + k * step, 0.06 if k % 2 else 0.09, 0.3)
    # montée et impact au « Top départ »
    t = tt(bar); riser = hp(rng.standard_normal(len(t)), 800) * (t / bar) ** 2
    m.add(lp(riser, 9000), drop - bar, 0.12)
    t = tt(1.0); m.add(lp(rng.standard_normal(len(t)), 3000) * np.exp(-t / 0.3), drop, 0.18)
    m.render(path, 0.9); return bpm

def phonk118(path, dur, cue=3.6, drop=15.2):
    """Variante du phonk : 118 BPM, sol mineur (Reel 21)."""
    return phonk(path, dur, cue, drop, bpm=118, tr=2)

# ---------------------------------------------------------------- UK garage 2-step (ajouté le 21 nov. 2026)
def garage(path, dur, cue=3.4):
    """UK garage « 2-step », 126 BPM, si bémol mineur : grosse caisse décalée, shuffle, basse sub, accords d'orgue hachés."""
    beat, bar, pre, m, nb = _grid(dur, 126, cue)
    s16 = beat / 4; sw = s16 * 0.22                       # shuffle sur les doubles-croches paires
    chords = [[-11, -8, -4, 1], [-16, -13, -9, -4], [-9, -6, -2, 3], [-13, -9, -6, -1]]   # Sibm7, Solb, Réb, Lab (registre médium)
    roots = [note(-35), note(-40), note(-32), note(-37)]
    kick_steps = [0, 10]                                  # 2-step : 1er temps puis contretemps du 3e
    for b in range(nb):
        t0 = b * bar - pre; c = b % 4; full = t0 >= cue - 0.01
        # accords hachés (orgue) : motif syncopé
        for st in (2, 5, 10, 13):
            d = s16 * 1.3; ts = tt(d)
            x = sum(np.sin(2 * np.pi * note(n) * ts) + 0.5 * np.sin(4 * np.pi * note(n) * ts) for n in chords[c]) / len(chords[c])
            m.add(lp(x, 2600 if full else 1400) * np.exp(-ts / 0.07) * np.minimum(1, ts / 0.002), t0 + st * s16 + (sw if st % 2 else 0), 0.3, 0.2 if st % 4 else -0.2)
        if not full:
            m.add(pad([note(n) for n in chords[c]], bar, 900), t0, 0.25)
            continue
        for st in kick_steps: m.add(kick(), t0 + st * s16, 0.8)
        for st in (4, 12): m.add(clap(), t0 + st * s16, 0.32, 0.05); m.add(snare(), t0 + st * s16, 0.18)
        for k in range(16):
            tk = t0 + k * s16 + (sw if k % 2 else 0)
            m.add(hat(0.007, 0.03, 9500), tk, 0.08 if k % 2 else 0.05, -0.25)
            if k % 4 == 2: m.add(hat(0.04, 0.12, 8000), tk, 0.07, 0.3)
        # basse sub qui glisse
        for st, mult, d in ((0, 1, beat * 1.4), (7, 1, beat * 0.6), (10, 1.5, beat * 0.9)):
            tb = tt(d); f = roots[c] * mult
            fr = f * (1 + 0.15 * np.exp(-tb / 0.05))
            x = np.tanh(1.6 * np.sin(2 * np.pi * np.cumsum(fr) / SR)) * np.minimum(1, tb / 0.004) * np.minimum(1, (d - tb) / 0.02)
            m.add(x, t0 + st * s16, 0.45)
    delay(m, beat * 0.75, 0.3, 0.18)
    m.render(path, 1.0); return 126

STYLES = {'lofi': lofi, 'house': house, 'synthwave': synthwave, 'funk': funk, 'trap': trap, 'boombap': boombap, 'phonk': phonk, 'phonk118': phonk118, 'garage': garage}
if __name__ == '__main__':
    style, out = sys.argv[1], sys.argv[2]
    dur = float(sys.argv[3]) if len(sys.argv) > 3 else 13.5
    print('ok', style, STYLES[style](out, dur), 'BPM')
