"""Boucle électro WOD Genius, 150 BPM, la mineur, 13,5 s, drop calé sur le départ du chrono (7,2 s).
Usage : python3 loop.py sortie.wav [duree]
"""
import sys, wave
import numpy as np
from scipy.signal import butter, sosfilt

SR = 48000
BPM = float(sys.argv[3]) if len(sys.argv) > 3 else 128
BEAT = 60 / BPM            # 0,4 s
BAR = 4 * BEAT             # 1,6 s
OUT_DUR = float(sys.argv[2]) if len(sys.argv) > 2 else 13.5
CHRONO = float(sys.argv[4]) if len(sys.argv) > 4 else 7.1               # départ du chrono dans la vidéo
DROP_BAR = 4
DROP = DROP_BAR * BAR
PRE = DROP - CHRONO        # on génère PRE s en trop au début, coupées à la fin, pour caler le drop sur le chrono
while PRE < 0: DROP_BAR += 1; DROP = DROP_BAR * BAR; PRE = DROP - CHRONO
DUR = OUT_DUR + PRE
N = int(SR * DUR)
L = np.zeros(N); R = np.zeros(N)
rng = np.random.default_rng(7)

def add(sig, t, gain=1.0, pan=0.0):
    s = int(t * SR)
    if s >= N: return
    sig = sig[: N - s]
    L[s:s + len(sig)] += sig * gain * np.sqrt(0.5 * (1 - pan))
    R[s:s + len(sig)] += sig * gain * np.sqrt(0.5 * (1 + pan))

def tt(d): return np.arange(int(d * SR)) / SR
def lp(x, f): return sosfilt(butter(2, f, 'low', fs=SR, output='sos'), x)
def hp(x, f): return sosfilt(butter(2, f, 'high', fs=SR, output='sos'), x)
def bp(x, f1, f2): return sosfilt(butter(2, [f1, f2], 'band', fs=SR, output='sos'), x)

def kick():
    t = tt(0.35)
    f = 45 + 110 * np.exp(-t / 0.03)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.12)
    click = hp(rng.standard_normal(len(t)), 3000) * np.exp(-t / 0.004) * 0.3
    return np.tanh(1.6 * (body + click))

def snare():
    t = tt(0.22)
    noise = bp(rng.standard_normal(len(t)), 1500, 8000) * np.exp(-t / 0.06)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.04)
    return 0.7 * noise + 0.5 * tone

def hat(open_=False):
    t = tt(0.12 if open_ else 0.04)
    return hp(rng.standard_normal(len(t)), 7000) * np.exp(-t / (0.04 if open_ else 0.012))

def saw(f, d, harm=24):
    t = tt(d); x = np.zeros(len(t))
    for k in range(1, harm + 1):
        if f * k > 16000: break
        x += np.sin(2 * np.pi * f * k * t) / k
    return x * (2 / np.pi)

def bass(f, d):
    t = tt(d)
    x = lp(saw(f, d, 12), 380) * 1.6 + np.sin(2 * np.pi * f * t) * 0.6
    env = np.minimum(1, t / 0.005) * np.minimum(1, (d - t) / 0.02)
    return np.tanh(1.3 * x) * env

def pluck(f, cutoff):
    d = 0.32; t = tt(d)
    x = saw(f, d) + 0.5 * saw(f * 1.005, d)
    return lp(x, cutoff) * np.exp(-t / 0.09) * np.minimum(1, t / 0.002)

def note(n):  # n : demi-tons depuis la4 (440 Hz)
    return 440 * 2 ** (n / 12)

# Progression la mineur : Am - F - C - G (une mesure chacune)
CHORDS = [[0, 3, 7, 12], [-4, 0, 3, 8], [3, 7, 10, 15], [-2, 2, 5, 10]]
ROOTS = [note(-36), note(-40), note(-33), note(-38)]   # la1, fa1, do2, sol1

beats = int(DUR / BEAT) + 1
kick_times = []
for b in range(beats):
    t = b * BEAT
    pre_drop_gap = DROP - BAR / 2 <= t < DROP          # demi-mesure sans kick avant le drop
    if not pre_drop_gap:
        kick_times.append(t)
    if b % 2 == 1 and t >= DROP:
        add(snare(), t, 0.55)
    if b % 4 == 3 and t < DROP - BAR / 2:
        add(snare(), t, 0.35)                           # clap léger en intro
    for k in range(4):                                  # charley en doubles-croches
        th = t + k * BEAT / 4
        g = (0.16 if k % 2 else 0.10) * (1.0 if th >= DROP else 0.8)
        add(hat(open_=(k == 2 and t >= DROP)), th, g, pan=0.25)

# roulement de caisse claire + montée de bruit avant le drop
roll_start = DROP - BAR
for k in range(16):
    add(snare(), roll_start + k * BAR / 16, 0.05 + 0.2 * k / 15)
t = tt(BAR); riser = rng.standard_normal(len(t))
riser = hp(riser, 600) * (t / BAR) ** 2
add(lp(riser, 9000), roll_start, 0.12)
# impact au drop
t = tt(1.2)
add(lp(rng.standard_normal(len(t)), 2500) * np.exp(-t / 0.35), DROP, 0.2)

# basse en croches
eighths = int(DUR / (BEAT / 2)) + 1
for k in range(eighths):
    t0 = k * BEAT / 2
    if DROP - BAR / 2 <= t0 < DROP: continue
    bar = int(t0 // BAR) % 4
    f = ROOTS[bar] * (2 if k % 4 == 3 else 1)
    add(bass(f, BEAT / 2 * 0.9), t0, 0.45)

# arpège : filtré en intro, ouvert après le drop
sixteenths = int(DUR / (BEAT / 4)) + 1
pattern = [0, 1, 2, 3, 2, 1, 2, 3]
for k in range(sixteenths):
    t0 = k * BEAT / 4
    bar = int(t0 // BAR) % 4
    n = CHORDS[bar][pattern[k % 8]]
    if t0 < DROP:
        cutoff = 900 + 2600 * max(0, (t0 - (DROP - 2 * BAR)) / (2 * BAR))
        g = 0.13
    else:
        cutoff = 5200; g = 0.16
    pan = -0.35 if k % 2 else 0.35
    add(pluck(note(n), cutoff), t0, g, pan)
    add(pluck(note(n), cutoff * 0.7), t0 + 3 * BEAT / 4, g * 0.35, -pan)   # écho

# compression « pompe » : la basse et l'arpège respirent avec le kick
duck = np.ones(N)
for kt in kick_times:
    s = int(kt * SR); n = min(int(0.18 * SR), N - s)
    if n > 0:
        duck[s:s + n] = np.minimum(duck[s:s + n], 0.45 + 0.55 * (np.arange(n) / n) ** 0.6)
L *= duck; R *= duck
K = kick()
for kt in kick_times:                                   # kick ajouté après le ducking
    add(K, kt, 0.9)

# fin : fondu sur la dernière demi-seconde
fade = np.ones(N); fl = int(0.6 * SR); fade[-fl:] = np.linspace(1, 0, fl) ** 1.5
L *= fade; R *= fade
st = np.stack([L, R], 1)[int(PRE * SR):]
fi = int(0.01 * SR); st[:fi] *= np.linspace(0, 1, fi)[:, None]
st = np.tanh(st * 1.2) / np.tanh(1.2)
st *= 0.89 / np.max(np.abs(st))                         # crête à -1 dB
pcm = (st * 32767).astype('<i2')
with wave.open(sys.argv[1], 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('ok', OUT_DUR, 's,', BPM, 'BPM, drop à', round(DROP - PRE, 3), 's')
