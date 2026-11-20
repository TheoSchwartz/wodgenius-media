"""Rend les Reels WOD Genius (1080x1920, 30 fps) à partir de scènes HTML animées.
Usage : python3 reels.py <sortie_dir> [slug ...] [--frames t1,t2]  (--frames : PNG de contrôle seulement)
"""
import sys, os, subprocess, wave
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from parts import SVG
from render_slides import font_faces
from playwright.sync_api import sync_playwright

W, H, FPS = 1080, 1920, 30
BEEPS = False  # bips jugés pénibles : la musique vient de loop.py / music.py
FONTS = HERE.parent / 'fonts'

CSS = """
html,body{margin:0;background:#0e1013}
#v{position:relative;width:1080px;height:1920px;overflow:hidden;background:#0e1013;color:#f2efe8;font-family:Inter,sans-serif}
.a{position:absolute;left:96px;right:150px;opacity:0;will-change:transform,opacity}
.tag{display:inline-flex;align-items:center;height:64px;padding:0 32px;border-radius:999px;font-family:'JetBrains Mono',monospace;font-size:30px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;background:#f3c34f;color:#0e1013}
.tag.ol{background:transparent;border:3px solid #f3c34f;color:#f3c34f;height:58px}
.mono{font-family:'JetBrains Mono',monospace}
.ch{color:#f3c34f}.muted{color:#9ba1a8}
.tc{font-family:Anton,sans-serif;font-size:170px;line-height:200px;text-transform:uppercase;margin:0}
.ts{font-family:Anton,sans-serif;font-size:110px;line-height:132px;text-transform:uppercase;margin:0}
.hero{font-family:'JetBrains Mono',monospace;font-weight:700;letter-spacing:-.04em;color:#f3c34f;margin:0}
.b{font-size:50px;line-height:66px;margin:0}
.row{display:flex;justify-content:space-between;align-items:baseline;padding:30px 0;border-top:2px solid #2a2e35;font-size:48px;line-height:58px}
.rk{font-family:'JetBrains Mono',monospace;font-size:32px;color:#9ba1a8}
.brand{position:absolute;left:96px;top:262px;display:inline-flex;align-items:center;gap:20px;font-family:'JetBrains Mono',monospace;font-size:34px;line-height:40px;font-weight:600;color:#9ba1a8}
.brand svg{width:48px;height:78px;display:block;transform:translateY(-15px)}
.brand .acc{fill:#f3c34f}.brand .accs{stroke:#f3c34f}
.hl{color:#5e646c;transition:none}
.vbar{width:46px;border-radius:8px 8px 0 0;transform-origin:bottom center}
.grp{flex:1;display:flex;justify-content:center;align-items:flex-end;gap:10px}
.col{display:flex;flex-direction:column;align-items:center;gap:8px}
.v{font-family:'JetBrains Mono',monospace;font-size:28px;line-height:32px;color:#9ba1a8}
.vA{color:#f3c34f;font-weight:700}
.xl{flex:1;text-align:center;font-family:'JetBrains Mono',monospace;font-size:30px;color:#9ba1a8}
.pill{display:inline-flex;align-items:center;height:76px;padding:0 36px;border-radius:999px;border:3px solid #f3c34f;color:#f2efe8;font-size:42px}
.step2{display:flex;align-items:baseline;gap:24px;padding:28px 0;border-top:2px solid #2a2e35}
.card2{background:#1a1d22;border-radius:24px;padding:36px 48px}
.stamp{display:inline-block;padding:8px 36px;border:6px solid #f3c34f;border-radius:16px;color:#f3c34f;font-family:Anton,sans-serif;font-size:110px;line-height:130px;text-transform:uppercase;transform:rotate(-6deg)}
.bar{height:56px;border-radius:0 10px 10px 0;background:#5e646c;transform-origin:left center}
"""

JS = """
const ease = x => 1 - Math.pow(1 - Math.min(Math.max(x,0),1), 3);
function frame(t){
  for (const e of document.querySelectorAll('.a')){
    const i = +e.dataset.in, o = e.dataset.out ? +e.dataset.out : 1e9;
    const pi = ease((t - i) / 0.4), po = ease((t - o) / 0.3);
    e.style.opacity = (pi * (1 - po)).toFixed(3);
    e.style.transform = `translateY(${((1 - pi) * 48 - po * 24).toFixed(1)}px)`;
  }
  for (const e of document.querySelectorAll('.cnt')){
    const [a, b, t0, t1] = [+e.dataset.from, +e.dataset.to, +e.dataset.t0, +e.dataset.t1];
    const p = Math.min(Math.max((t - t0) / (t1 - t0), 0), 1);
    const v = a + (b - a) * (e.dataset.lin ? p : ease(p));
    const f = e.dataset.fmt;
    if (f === 'time') { const s = Math.floor(v); e.textContent = Math.floor(s/60) + ':' + String(s%60).padStart(2,'0'); }
    else if (f === 'half') { const r = Math.round(v*2)/2; e.textContent = String(r).replace('.', ','); }
    else e.textContent = Math.round(v);
  }
  for (const e of document.querySelectorAll('.hl')){
    e.style.color = t >= +e.dataset.on ? '#f3c34f' : '#5e646c';
  }
  for (const e of document.querySelectorAll('.growy')){
    const p = ease((t - +e.dataset.t0) / 0.6);
    e.style.transform = `scaleY(${p.toFixed(3)})`;
  }
  for (const e of document.querySelectorAll('.grow')){
    const p = ease((t - +e.dataset.t0) / 0.6);
    e.style.transform = `scaleX(${p.toFixed(3)})`;
  }
}
"""

OFFSET = 150   # contenu centré dans la zone utile (sous la barre du haut, au-dessus du pseudo et de la légende)

def A(t_in, t_out, top, inner, extra=''):
    top += OFFSET
    o = f' data-out="{t_out}"' if t_out else ''
    return f'<div class="a" data-in="{t_in}"{o} style="top:{top}px;{extra}">{inner}</div>'

BRAND = f'<div class="brand">{SVG}<span>@wodgenius</span></div>'

# ---------------- Fran (17 s) ----------------
def fran():
    e = []
    e.append(A(0.0, 3.2, 300, '<span class="tag">Benchmark</span>'))
    e.append(A(0.15, 3.2, 420, '<h1 class="tc" style="font-size:300px;line-height:320px">Fran</h1>'))
    e.append(A(0.45, 3.2, 760, '<p class="hero" style="font-size:190px;line-height:200px">21-15-9</p>'))
    e.append(A(0.9, 3.2, 1010, '<p class="b" style="font-size:60px;line-height:76px">Tu connais ton temps ?</p>'))
    e.append(A(3.4, 7.8, 300, '<h2 class="ts">Le WOD</h2>'))
    rows = [('FORMAT', 'Pour le temps'), ('REPS', '<span class="mono ch" style="font-weight:700">21-15-9</span>'),
            ('MOUVEMENT 1', 'Thruster'), ('MOUVEMENT 2', 'Pull-up'), ('CHARGE RX', '43 kg · 29 kg')]
    for k, (a, b) in enumerate(rows):
        e.append(A(3.7 + k * 0.4, 7.8, 500 + k * 120, f'<div class="row"><span class="rk">{a}</span><span style="font-weight:600">{b}</span></div>'))
    e.append(A(8.0, 12.4, 300, '<span class="tag ol">Exemple illustratif</span>'))
    e.append(A(8.1, 12.4, 440, '<p class="b muted">Fran scaled, chrono en main</p>'))
    e.append(A(8.1, 12.4, 560, '<p class="hero cnt" data-from="0" data-to="365" data-t0="8.4" data-t1="11.0" data-fmt="time" data-lin="1" style="font-size:280px;line-height:300px">0:00</p>'))
    e.append(A(8.2, 12.4, 920, '<p class="mono" style="font-size:110px;line-height:130px;font-weight:700;margin:0">'
               '<span class="hl" data-on="8.4">21</span> <span class="muted">·</span> <span class="hl" data-on="9.4">15</span> <span class="muted">·</span> <span class="hl" data-on="10.2">9</span></p>'))
    e.append(A(11.1, 12.4, 1110, '<p class="b">Temps final : <span class="mono ch" style="font-weight:700">6:05</span></p>'))
    e.append(A(12.6, None, 420, '<h2 class="tc">Note<br>ton temps</h2>'))
    e.append(A(13.0, None, 860, '<p class="b">Même version, même standards. Refais-le dans quelques mois : le chrono dira le reste.</p>'))
    e.append(A(13.6, None, 1150, '<p class="mono ch" style="font-size:42px;line-height:56px;font-weight:700;margin:0">Enregistre · Partage à ton binôme</p>'))
    return ''.join(e), 17.0, []

# ---------------- RPE (20 s) ----------------
def rpe():
    e = []
    e.append(A(0.0, 3.2, 300, '<span class="tag">Data</span>'))
    e.append(A(0.15, 3.2, 440, '<p class="hero" style="font-size:300px;line-height:300px">8/10</p>'))
    e.append(A(0.5, 3.2, 780, '<h1 class="tc">Ton effort<br>a une note</h1>'))
    e.append(A(3.4, 9.6, 300, '<h2 class="ts">L\'échelle RPE</h2>'))
    scale = [('10', 'Plus aucune rep possible', 100, True), ('9', '1 rep en réserve', 85, False),
             ('8', '2 reps en réserve', 70, False), ('7', '3 reps en réserve', 55, False)]
    for k, (n, lab, w, acc) in enumerate(scale):
        t = 3.8 + k * 0.8
        col = '#f3c34f' if acc else '#5e646c'
        e.append(A(t, 9.6, 480 + k * 205,
                   f'<div style="display:flex;align-items:baseline;gap:28px"><span class="mono" style="font-size:72px;font-weight:700;width:110px;color:{"#f3c34f" if acc else "#f2efe8"}">{n}</span>'
                   f'<span class="b">{lab}</span></div>'
                   f'<div class="bar grow" data-t0="{t}" style="width:{w}%;margin-top:18px;background:{col}"></div>'))
    e.append(A(9.8, 15.0, 300, '<span class="tag ol">Exemple illustratif</span>'))
    e.append(A(9.9, 15.0, 440, '<h2 class="ts">Même charge,<br>moins d\'effort</h2>'))
    e.append(A(10.3, 15.0, 740, '<p class="b muted">Squat 80 kg × 5 · 4 semaines</p>'))
    e.append(A(10.5, 15.0, 860, '<p class="hero" style="font-size:190px;line-height:220px">RPE&nbsp;<span class="cnt" data-from="9" data-to="7" data-t0="11.0" data-t1="12.8" data-fmt="half">9</span></p>'))
    e.append(A(13.0, 15.0, 1180, '<p class="b">Le même travail coûte moins cher : tu progresses.</p>'))
    e.append(A(15.2, None, 420, '<h2 class="tc">Note-le</h2>'))
    e.append(A(15.6, None, 680, '<p class="b">Un chiffre de 1 à 10 après chaque WOD. Dix secondes, et tes séances deviennent comparables.</p>'))
    e.append(A(16.3, None, 1040, '<p class="mono ch" style="font-size:40px;line-height:56px;font-weight:700;margin:0">L\'app WOD Genius arrive.<br>Suis @wodgenius</p>'))
    return ''.join(e), 20.0, []

# ---------------- Hollow ----------------
def figure(step):
    s = 'stroke="#f2efe8" stroke-width="26" stroke-linecap="round" stroke-linejoin="round" fill="none"'
    out = ['<line x1="0" y1="392" x2="900" y2="392" stroke="#2a2e35" stroke-width="4"/>']
    arm = (30, 196) if step == 4 else (420, 282)
    out.append(f'<line x1="215" y1="290" x2="{arm[0]}" y2="{arm[1]}" {s}/>')
    out.append(f'<path d="M215 290 Q330 362 470 364" {s}/>')
    tuck = '<polyline points="470,364 545,215 665,245" ' + s + '/>'
    ext = '<line x1="470" y1="364" x2="850" y2="282" ' + s + '/>'
    out += {1: [tuck], 2: [ext, tuck], 3: [ext], 4: [ext]}[step]
    out.append('<circle cx="150" cy="246" r="40" fill="#0e1013" stroke="#f2efe8" stroke-width="20"/>')
    out.append('<circle cx="380" cy="376" r="14" fill="#f3c34f"/>')
    return f'<svg viewBox="0 0 900 420" width="834" height="389">{"".join(out)}</svg>'

def hollow():
    e = []
    e.append(A(0.0, 3.2, 300, '<span class="tag">Scaling</span>'))
    e.append(A(0.15, 3.2, 420, '<h1 class="tc">Le hollow<br>avant le<br>kipping</h1>'))
    e.append(A(0.7, 3.2, 1080, '<p class="b muted">La position de base de la gym, en 4 étapes.</p>'))
    e.append(A(3.4, 14.1, 300, '<h2 class="ts">4 étapes</h2>'))
    steps = ['Genoux pliés, bras le long du corps', 'Une jambe tendue, l\'autre pliée',
             'Deux jambes tendues, bras le long du corps', 'Jambes tendues, bras derrière la tête']
    for k, txt in enumerate(steps):
        t0 = 3.7 + k * 2.6
        t1 = t0 + 2.6 if k < 3 else 14.1
        e.append(A(t0, t1, 540, figure(k + 1)))
        e.append(A(t0, t1, 980, f'<p class="mono ch" style="font-size:44px;font-weight:700;margin:0">ÉTAPE 0{k+1}</p><p class="b" style="margin-top:16px">{txt}</p>'))
    e.append(A(3.8, 14.1, 1250, '<p class="b muted" style="font-size:40px;line-height:54px"><span class="ch">●</span> bas du dos plaqué au sol</p>'))
    e.append(A(14.3, None, 420, '<h2 class="tc">Gaine<br>d\'abord</h2>'))
    e.append(A(14.7, None, 860, '<p class="b">Le bas du dos décolle ? Reviens à l\'étape d\'avant.</p>'))
    e.append(A(15.2, None, 1060, '<p class="mono ch" style="font-size:42px;line-height:56px;font-weight:700;margin:0">Enregistre · Partage</p>'))
    return ''.join(e), 18.5, []

# ---------------- Reels du lot 1 (novembre, week-ends) ----------------
def vbars(pairs, t0, step, scale, hmax):
    out = []
    for k, (a, b) in enumerate(pairs):
        t = t0 + k * step
        def bar(v, acc):
            if v is None:
                return '<div class="col"><span class="v">–</span><div style="width:46px;height:0"></div></div>'
            return (f'<div class="col"><span class="v{" vA" if acc else ""}">{v}</span>'
                    f'<div class="vbar growy" data-t0="{t}" style="height:{int(v*scale)}px;background:{"#f3c34f" if acc else "#5e646c"}"></div></div>')
        out.append(f'<div class="grp">{bar(a, True)}{bar(b, False)}</div>')
    return f'<div style="display:flex;align-items:flex-end;height:{hmax}px;border-bottom:2px solid #2a2e35">{"".join(out)}</div>'

def pacing():
    e = []
    e.append(A(0.0, 3.2, 300, '<span class="tag">Data</span>'))
    e.append(A(0.15, 3.2, 420, '<p class="hero" style="font-size:230px;line-height:240px">8 vs 6</p>'))
    e.append(A(0.5, 3.2, 700, '<h1 class="tc">Départ<br>canon ?</h1>'))
    e.append(A(0.9, 3.2, 1120, '<p class="b muted">AMRAP 12 min : qui fait le plus de tours ?</p>'))
    e.append(A(3.4, 9.4, 300, '<span class="tag ol">Exemple illustratif</span>'))
    e.append(A(3.5, 9.4, 400, '<h2 class="ts">Temps par tour</h2>'))
    e.append(A(3.7, 9.4, 560, '<div style="display:flex;gap:40px"><span class="b" style="font-size:38px"><span class="ch">■</span> Rythme régulier</span><span class="b muted" style="font-size:38px">■ Départ canon</span></div>'))
    pairs = [(88, 70), (88, 80), (89, 95), (90, 110), (90, 125), (91, 140)]
    e.append(A(3.9, 9.4, 660, vbars(pairs, 4.1, 0.5, 3.4, 520)))
    e.append(A(4.0, 9.4, 1200, '<div style="display:flex">' + ''.join(f'<span class="xl">T{k+1}</span>' for k in range(6)) + '</div>'))
    e.append(A(7.0, 9.4, 1270, '<p class="b muted" style="font-size:40px;line-height:54px">Secondes par tour. Le départ canon ralentit à chaque tour.</p>'))
    e.append(A(9.6, 13.8, 340, '<h2 class="ts">En 12 minutes</h2>'))
    e.append(A(10.0, 13.8, 560, '<p class="hero" style="font-size:220px;line-height:230px">8<span style="font-size:70px;letter-spacing:0;margin-left:28px">tours</span></p><p class="b ch">Rythme régulier</p>'))
    e.append(A(10.6, 13.8, 900, '<p class="hero" style="font-size:220px;line-height:230px;color:#5e646c">6<span style="font-size:70px;letter-spacing:0;margin-left:28px">tours</span></p><p class="b muted">Départ canon</p>'))
    e.append(A(14.0, None, 300, '<h2 class="ts">Ton plan</h2>'))
    for k, (l, txt) in enumerate([('A', 'Premier tour à 85–90 % de ton max'), ('B', 'Même découpage des reps à chaque tour'), ('C', 'Accélère dans les 2 dernières minutes')]):
        e.append(A(14.3 + k * 0.6, None, 500 + k * 170, f'<div class="step2"><span class="mono ch" style="font-size:56px;font-weight:700;width:80px">{l}</span><span class="b">{txt}</span></div>'))
    e.append(A(16.3, None, 1080, '<p class="mono ch" style="font-size:42px;line-height:56px;font-weight:700;margin:0">Enregistre · Partage</p>'))
    return ''.join(e), 19.5, []

def tabata():
    e = []
    e.append(A(0.0, 3.2, 300, '<span class="tag">Tabata</span>'))
    e.append(A(0.15, 3.2, 420, '<p class="hero" style="font-size:240px;line-height:250px">20/10</p>'))
    e.append(A(0.5, 3.2, 700, '<h1 class="tc">3 erreurs<br>à éviter</h1>'))
    e.append(A(0.9, 3.2, 1120, '<p class="b muted">8 rounds, 4 minutes. Pas le droit de les gâcher.</p>'))
    errs = [('Partir<br>à 100 %', 'Ton score, c\'est ton round le plus faible. Un départ à fond le fait chuter.', None),
            ('Un mouvement<br>trop technique', 'À la fatigue, la technique se dégrade. Privilégie :', ['Air squats', 'Burpees', 'Rameur', 'Vélo']),
            ('Ne pas<br>compter', 'Note tes reps à chaque round : c\'est le seul moyen de connaître ton vrai score.', None)]
    for k, (title, txt, pills) in enumerate(errs):
        t0 = 3.4 + k * 4.2; t1 = t0 + 4.0
        e.append(A(t0, t1, 300, f'<p class="mono ch" style="font-size:48px;font-weight:700;margin:0">ERREUR {k+1}</p>'))
        e.append(A(t0 + 0.2, t1, 400, f'<h2 class="ts">{title}</h2>'))
        e.append(A(t0 + 0.7, t1, 700, f'<p class="b">{txt}</p>'))
        if pills:
            e.append(A(t0 + 1.2, t1, 920, '<div style="display:flex;flex-wrap:wrap;gap:20px">' + ''.join(f'<span class="pill">{p}</span>' for p in pills) + '</div>'))
    e.append(A(16.2, None, 420, '<h2 class="tc">4 minutes<br>bien faites</h2>'))
    e.append(A(16.6, None, 860, '<p class="b">Un mouvement simple, un rythme régulier, et de quoi noter.</p>'))
    e.append(A(17.1, None, 1060, '<p class="mono ch" style="font-size:42px;line-height:56px;font-weight:700;margin:0">Enregistre · Partage</p>'))
    return ''.join(e), 20.0, []

def emom():
    e = []
    e.append(A(0.0, 3.2, 300, '<span class="tag">EMOM</span>'))
    e.append(A(0.15, 3.2, 420, '<p class="hero" style="font-size:240px;line-height:250px">00:40</p>'))
    e.append(A(0.5, 3.2, 700, '<h1 class="tc">La règle<br>des 40 s</h1>'))
    e.append(A(0.9, 3.2, 1120, '<p class="b muted">Pour tenir jusqu\'à la dernière minute.</p>'))
    e.append(A(3.4, 8.4, 300, '<h2 class="ts">Le principe</h2>'))
    e.append(A(3.8, 8.4, 480, '<p class="b">Chaque minute se partage entre travail et repos.</p>'))
    e.append(A(4.3, 8.4, 700, '<div style="display:flex;height:96px;border-radius:12px;overflow:hidden">'
               '<div class="grow" data-t0="4.5" style="width:66.7%;background:#f3c34f;transform-origin:left"></div>'
               '<div class="grow" data-t0="5.0" style="width:33.3%;background:#5e646c;transform-origin:left"></div></div>'
               '<div style="display:flex;justify-content:space-between;margin-top:20px" class="mono"><span class="ch" style="font-size:36px;font-weight:700">TRAVAIL · 40 s</span><span class="muted" style="font-size:36px">REPOS · 20 s</span></div>'))
    e.append(A(5.6, 8.4, 960, '<p class="b">Si le travail mange toute la minute, tout s\'effondre.</p>'))
    e.append(A(8.6, 13.0, 360, '<p class="hero" style="font-size:180px;line-height:200px">30–40 s</p>'))
    e.append(A(9.0, 13.0, 620, '<h2 class="ts">de travail<br>par minute</h2>'))
    e.append(A(9.6, 13.0, 930, '<p class="b">Garde au moins <span class="ch" style="font-weight:600">20 s de repos</span> : c\'est ce qui te fait tenir.</p>'))
    e.append(A(13.2, None, 300, '<h2 class="ts">Ajuste<br>en direct</h2>'))
    e.append(A(13.6, None, 600, '<div class="card2"><p class="rk" style="margin:0">MINUTE 1 FINIE APRÈS 45 S ?</p><p class="b" style="margin-top:12px;font-weight:600">Retire 2 reps dès la minute 2.</p></div>'))
    e.append(A(14.4, None, 870, '<div class="card2"><p class="rk" style="margin:0">FINIE EN 25 S ?</p><p class="b" style="margin-top:12px;font-weight:600">Ajoute 1 à 2 reps la prochaine fois.</p></div>'))
    e.append(A(15.4, None, 1160, '<p class="mono ch" style="font-size:42px;line-height:56px;font-weight:700;margin:0">Enregistre · Partage à ton binôme</p>'))
    return ''.join(e), 19.0, []

def scaling():
    e = []
    e.append(A(0.0, 3.2, 300, '<span class="tag">Scaling</span>'))
    e.append(A(0.15, 3.2, 420, '<p class="hero" style="font-size:220px;line-height:220px">3</p>'))
    e.append(A(0.5, 3.2, 660, '<h1 class="tc">Scaler<br>n\'est pas<br>tricher</h1>'))
    e.append(A(3.4, 7.6, 300, '<h2 class="ts">La règle d\'or</h2>'))
    e.append(A(3.8, 7.6, 520, '<p class="b">Garde le stimulus : même durée, même intensité.</p>'))
    e.append(A(4.6, 7.6, 720, '<p class="b" style="font-weight:600">Change tout le reste.</p>'))
    levers = [('La charge', 'Thruster', '40 kg', '30 kg'), ('Le volume', 'Reps', '21-15-9', '15-12-9'), ('Le mouvement', 'Gym', 'Pull-up', 'Ring row')]
    for k, (name, what, a, b) in enumerate(levers):
        t0 = 7.8 + k * 2.8; t1 = t0 + 2.6
        e.append(A(t0, t1, 300, f'<p class="mono ch" style="font-size:48px;font-weight:700;margin:0">LEVIER {k+1}</p>'))
        e.append(A(t0 + 0.15, t1, 400, f'<h2 class="ts">{name}</h2>'))
        e.append(A(t0 + 0.5, t1, 640, f'<p class="rk" style="margin:0">{what.upper()}</p><p class="mono" style="font-size:72px;line-height:90px;font-weight:700;margin:12px 0 0"><span class="muted">{a}</span> <span class="ch">→ {b}</span></p>'))
    e.append(A(16.4, None, 420, '<h2 class="tc">Pas d\'ego</h2>'))
    e.append(A(16.8, None, 680, '<p class="b">Le meilleur WOD est celui que tu finis avec une technique propre.</p>'))
    e.append(A(17.3, None, 920, '<p class="mono ch" style="font-size:42px;line-height:56px;font-weight:700;margin:0">Enregistre · Partage à ton binôme</p>'))
    return ''.join(e), 20.0, []

# ---------------- Nouveaux formats (week-ends de novembre) ----------------
def cindy():
    e = []
    e.append(A(0.0, 3.4, 300, '<span class="tag">WOD du week-end</span>'))
    e.append(A(0.15, 3.4, 420, '<p class="hero" style="font-size:230px;line-height:240px">20:00</p>'))
    e.append(A(0.5, 3.4, 700, '<h1 class="tc" style="font-size:240px;line-height:260px">Cindy</h1>'))
    e.append(A(0.9, 3.4, 1000, '<p class="b muted">Un benchmark classique à faire ce week-end.</p>'))
    e.append(A(3.6, 9.0, 300, '<h2 class="ts">Le WOD</h2>'))
    rows = [('FORMAT', 'AMRAP 20 min'), ('1', '5 pull-ups'), ('2', '10 push-ups'), ('3', '15 air squats'), ('SCORE', 'Tours + reps')]
    for k, (a, b) in enumerate(rows):
        e.append(A(4.0 + k * 0.5, 9.0, 500 + k * 120, f'<div class="row"><span class="rk">{a}</span><span style="font-weight:600">{b}</span></div>'))
    e.append(A(9.2, 13.6, 300, '<h2 class="ts">Version<br>scaled</h2>'))
    e.append(A(9.6, 13.6, 600, '<div class="row"><span class="rk">PULL-UP</span><span style="font-weight:600"><span class="ch">→</span> Ring row</span></div>'))
    e.append(A(10.1, 13.6, 720, '<div class="row"><span class="rk">PUSH-UP</span><span style="font-weight:600"><span class="ch">→</span> Mains surélevées</span></div>'))
    e.append(A(10.6, 13.6, 880, '<p class="b">Même durée, même rythme : garde-toi en mouvement 20 minutes.</p>'))
    e.append(A(13.8, None, 300, '<span class="tag ol">Top départ</span>'))
    e.append(A(13.9, None, 420, '<p class="hero cnt" data-from="1200" data-to="1194" data-t0="14.2" data-t1="20.2" data-fmt="time" data-lin="1" style="font-size:280px;line-height:300px">20:00</p>'))
    e.append(A(14.4, None, 800, '<p class="b">Poste ton score en commentaire : <span class="ch" style="font-weight:600">tours + reps</span>, RX ou scaled.</p>'))
    e.append(A(15.0, None, 1060, '<p class="mono ch" style="font-size:42px;line-height:56px;font-weight:700;margin:0">Enregistre pour ce week-end</p>'))
    return ''.join(e), 19.5, []

def quiz():
    e = []
    e.append(A(0.0, 3.0, 300, '<span class="tag">Quiz</span>'))
    e.append(A(0.15, 3.0, 420, '<h1 class="tc">Devine<br>le WOD</h1>'))
    e.append(A(0.6, 3.0, 860, '<p class="b muted">3 benchmarks célèbres. Réponds avant la fin du compte à rebours.</p>'))
    wods = [('Grace', ['30 clean & jerks', '61 kg · 43 kg', 'Pour le temps']),
            ('Helen', ['3 tours', '400 m de course', '21 kettlebell swings', '12 pull-ups']),
            ('Murph', ['1,6 km de course', '100 pull-ups', '200 push-ups', '300 squats', '1,6 km de course'])]
    for k, (name, lines) in enumerate(wods):
        t0 = 3.2 + k * 5.2; t1 = t0 + 5.0
        e.append(A(t0, t1, 300, f'<p class="mono muted" style="font-size:40px;font-weight:700;margin:0">WOD {k+1}/3</p>'))
        body = ''.join(f'<div class="row" style="padding:22px 0"><span style="font-weight:600">{l}</span></div>' for l in lines)
        e.append(A(t0 + 0.2, t1, 400, f'<div style="border-bottom:2px solid #2a2e35">{body}</div>'))
        e.append(A(t0 + 1.4, t0 + 3.4, 1080, f'<p class="hero cnt" data-from="3" data-to="0.6" data-t0="{t0 + 1.4}" data-t1="{t0 + 3.4}" data-lin="1" style="font-size:150px;line-height:160px">3</p>'))
        e.append(A(t0 + 3.5, t1, 1060, f'<h2 class="tc ch" style="font-size:180px;line-height:200px">{name}</h2>'))
    e.append(A(18.8, None, 420, '<h2 class="tc">Ton score ?</h2>'))
    e.append(A(19.2, None, 660, '<p class="b">Combien en as-tu trouvé sur 3 ? Dis-le en commentaire.</p>'))
    e.append(A(19.7, None, 880, '<p class="mono ch" style="font-size:42px;line-height:56px;font-weight:700;margin:0">Partage à ton binôme</p>'))
    return ''.join(e), 22.0, []

def sac():
    e = []
    e.append(A(0.0, 3.2, 300, '<span class="tag">Box</span>'))
    e.append(A(0.15, 3.2, 420, '<p class="hero" style="font-size:240px;line-height:240px">7</p>'))
    e.append(A(0.5, 3.2, 680, '<h1 class="tc"><span class="ch">Essentiels</span><br>dans ton<br>sac de box</h1>'))
    items = ['Corde à sauter', 'Gourde', 'Serviette', 'Maniques', 'Bandes de poignets', 'Chaussures stables', 'De quoi noter tes scores']
    e.append(A(3.4, 12.2, 300, '<h2 class="ts">Les essentiels</h2>'))
    for k, it in enumerate(items):
        last = k == len(items) - 1
        e.append(A(3.8 + k * 0.7, 12.2, 460 + k * 122,
                   f'<div style="display:flex;align-items:center;gap:28px;padding:24px 0;border-top:2px solid #2a2e35">'
                   f'<span class="mono ch" style="font-size:44px;font-weight:700">✓</span><span class="b"{" style=\"font-weight:600;color:#f3c34f\"" if last else ""}>{it}</span></div>'))
    e.append(A(12.4, 16.2, 300, '<p class="mono ch" style="font-size:44px;font-weight:700;margin:0">LE PLUS OUBLIÉ</p>'))
    e.append(A(12.6, 16.2, 400, '<h2 class="ts">Noter<br>ses scores</h2>'))
    e.append(A(13.2, 16.2, 700, '<p class="b">Sans trace de tes séances, impossible de voir ta progression.</p>'))
    e.append(A(16.4, None, 420, '<h2 class="tc">Et dans<br>ton sac ?</h2>'))
    e.append(A(16.8, None, 860, '<p class="b">Dis-nous ce qu\'on a oublié en commentaire.</p>'))
    e.append(A(17.3, None, 1060, '<p class="mono ch" style="font-size:40px;line-height:56px;font-weight:700;margin:0">L\'app WOD Genius arrive :<br>timer + suivi des PR</p>'))
    return ''.join(e), 20.5, []

def mythes():
    e = []
    e.append(A(0.0, 3.2, 300, '<span class="tag">Mythe ou réalité</span>'))
    e.append(A(0.15, 3.2, 420, '<h1 class="tc"><span class="ch">3 idées<br>reçues</span><br>de box</h1>'))
    myths = [('« Pas de courbatures = séance ratée »', 'Les courbatures ne disent pas si ta séance était bonne. Ta progression se lit dans tes scores.'),
             ('« Scaled = moins efficace »', 'Un WOD bien scalé garde le stimulus prévu. Souvent plus utile qu\'un RX subi.'),
             ('« Plus lourd = mieux »', 'Une charge que tu bouges proprement et vite sert mieux le WOD qu\'une charge qui te bloque.')]
    for k, (claim, real) in enumerate(myths):
        t0 = 3.4 + k * 5.4; t1 = t0 + 5.2
        e.append(A(t0, t1, 300, f'<p class="mono muted" style="font-size:40px;font-weight:700;margin:0">IDÉE {k+1}/3</p>'))
        e.append(A(t0 + 0.2, t1, 400, f'<p class="b" style="font-size:66px;line-height:84px;font-weight:600">{claim}</p>'))
        e.append(A(t0 + 1.4, t1, 680, '<span class="stamp">Mythe</span>'))
        e.append(A(t0 + 2.0, t1, 900, f'<p class="b">{real}</p>'))
    e.append(A(19.8, None, 420, '<h2 class="tc">Et toi ?</h2>'))
    e.append(A(20.2, None, 660, '<p class="b">Quelle idée reçue t\'a le plus marqué en box ?</p>'))
    e.append(A(20.7, None, 880, '<p class="mono ch" style="font-size:42px;line-height:56px;font-weight:700;margin:0">Enregistre · Partage</p>'))
    return ''.join(e), 23.0, []

# ---------------- Lot du 2 au 8 décembre (accroche visible dès la frame 0 : data-in négatif) ----------------
H0 = -1.0   # entrée avant 0 s : l'accroche est déjà en place sur la première image

def ab_burpees():
    e = []
    e.append(A(H0, 3.6, 260, '<span class="tag">A ou B ?</span>'))
    e.append(A(H0, 3.6, 390, '<h1 class="tc" style="font-size:190px;line-height:210px"><span class="ch">100<br>burpees</span></h1>'))
    e.append(A(H0, 3.6, 840, '<p class="b" style="font-size:78px;line-height:96px;font-weight:600">Lequel est<br>le plus dur ?</p>'))
    for k, (lt, name, rows, t0) in enumerate([
            ('A', 'Pour le temps', ['100 burpees', 'Le plus vite possible', 'Pause quand tu veux'], 3.8),
            ('B', 'EMOM 10 min', ['10 burpees par minute', 'Repos : le reste de la minute', '10 minutes, pas une de plus'], 8.2)]):
        t1 = t0 + 4.2
        e.append(A(t0, t1, 260, f'<p class="hero" style="font-size:260px;line-height:260px">{lt}</p>'))
        e.append(A(t0 + 0.4, t1, 560, f'<h2 class="ts">{name}</h2>'))
        for j, r in enumerate(rows):
            e.append(A(t0 + 0.9 + j * 0.5, t1, 740 + j * 120, f'<div class="row"><span style="font-weight:600">{r}</span></div>'))
    e.append(A(12.6, 16.6, 260, '<p class="mono muted" style="font-size:40px;font-weight:700;margin:0">MÊME TOTAL</p>'))
    e.append(A(12.8, 16.6, 360, '<h2 class="ts">Deux pièges<br>différents</h2>'))
    e.append(A(13.4, 16.6, 680, '<div class="card2"><p class="rk" style="margin:0">A</p><p class="b" style="margin-top:8px;font-weight:600">Tu gères ton rythme… et tes pauses.</p></div>'))
    e.append(A(14.0, 16.6, 960, '<div class="card2"><p class="rk" style="margin:0">B</p><p class="b" style="margin-top:8px;font-weight:600">Le chrono décide. Ton repos fond.</p></div>'))
    e.append(A(16.8, None, 360, '<h2 class="tc" style="font-size:220px;line-height:240px">A ou B ?</h2>'))
    e.append(A(17.2, None, 660, '<p class="b">Vote en commentaire : <span style="font-weight:600">lequel est le plus dur ?</span></p>'))
    e.append(A(17.7, None, 900, '<p class="mono ch" style="font-size:42px;line-height:58px;font-weight:700;margin:0">Envoie-le à ton binôme :<br>il fait l\'autre.</p>'))
    return ''.join(e), 21.0, []

def defi_binome():
    e = []
    e.append(A(H0, 3.6, 260, '<span class="tag">Défi à deux</span>'))
    e.append(A(H0, 3.6, 400, '<h1 class="tc" style="font-size:150px;line-height:178px">Qui lâche<br>en premier ?</h1>'))
    e.append(A(H0, 3.6, 820, '<p class="b muted" style="font-size:56px;line-height:72px">Toi ou ton binôme de box.</p>'))
    e.append(A(3.8, 10.4, 260, '<h2 class="ts">Les règles</h2>'))
    rules = [('A', '10 burpees'), ('B', 'Tient la planche pendant ce temps'), ('↻', 'Vous inversez les rôles')]
    for k, (l, txt) in enumerate(rules):
        e.append(A(4.2 + k * 0.7, 10.4, 440 + k * 170, f'<div class="step2"><span class="mono ch" style="font-size:56px;font-weight:700;width:80px">{l}</span><span class="b">{txt}</span></div>'))
    e.append(A(6.4, 10.4, 980, '<p class="hero" style="font-size:180px;line-height:190px">5 tours</p>'))
    e.append(A(10.6, 15.2, 260, '<h2 class="ts">Qui perd ?</h2>'))
    e.append(A(11.0, 15.2, 460, '<p class="b" style="font-size:60px;line-height:78px">Le premier qui pose les genoux pendant sa planche.</p>'))
    e.append(A(11.8, 15.2, 820, '<div class="card2"><p class="rk" style="margin:0">LE GAGE</p><p class="b" style="margin-top:8px;font-weight:600">Il range le matériel des deux.</p></div>'))
    e.append(A(15.4, None, 360, '<h2 class="tc">Ton binôme<br>est prêt ?</h2>'))
    e.append(A(15.8, None, 800, '<p class="b">Scaled : planche sur les genoux, burpees sans saut.</p>'))
    e.append(A(16.4, None, 1020, '<p class="mono ch" style="font-size:44px;line-height:60px;font-weight:700;margin:0">Envoie-le à ton binôme de box</p>'))
    return ''.join(e), 20.5, []

def no_rep():
    e = []
    e.append(A(H0, 3.2, 260, '<span class="tag">Standards</span>'))
    e.append(A(H0, 3.2, 400, '<h1 class="tc" style="font-size:130px;line-height:158px"><span class="ch">4 reps</span><br>que ton coach<br>ne compte pas</h1>'))
    moves = [('Push-up', 'La poitrine ne touche pas le sol.'),
             ('Pull-up', 'Le menton ne passe pas au-dessus de la barre.'),
             ('Toes-to-bar', 'Les deux pieds ne touchent pas la barre ensemble.'),
             ('Box jump', 'Pas debout, hanches tendues, en haut de la box.')]
    for k, (name, why) in enumerate(moves):
        t0 = 3.4 + k * 3.9; t1 = t0 + 3.7
        e.append(A(t0, t1, 260, f'<p class="mono muted" style="font-size:40px;font-weight:700;margin:0">{k+1}/4</p>'))
        e.append(A(t0 + 0.1, t1, 360, f'<h2 class="ts" style="font-size:130px;line-height:150px">{name}</h2>'))
        e.append(A(t0 + 0.6, t1, 590, '<span class="stamp">No rep</span>'))
        e.append(A(t0 + 1.1, t1, 840, f'<p class="b" style="font-size:58px;line-height:76px">{why}</p>'))
    e.append(A(19.2, None, 360, '<h2 class="tc">Avoue.</h2>'))
    e.append(A(19.6, None, 620, '<p class="b">Laquelle tu fais encore ? Dis-le en commentaire.</p>'))
    e.append(A(20.1, None, 860, '<p class="mono ch" style="font-size:42px;line-height:58px;font-weight:700;margin:0">Envoie-le à celui<br>qui compte large</p>'))
    return ''.join(e), 22.6, []

def apres_wod():
    e = []
    e.append(A(H0, 3.4, 260, '<span class="tag">Récup</span>'))
    e.append(A(H0, 3.4, 400, '<h1 class="tc" style="font-size:150px;line-height:178px">WOD fini ?<br>Ne t\'assieds<br>pas.</h1>'))
    e.append(A(H0, 3.4, 980, '<p class="b muted">5 réflexes pour bien finir.</p>'))
    e.append(A(3.6, 10.6, 260, '<h2 class="ts">Les <span class="ch">5</span> réflexes</h2>'))
    items = ['Marche quelques minutes', 'Bois de l\'eau', 'Note ton score', 'Range ton matériel', 'Mange un vrai repas ensuite']
    for k, it in enumerate(items):
        e.append(A(4.0 + k * 0.7, 10.6, 440 + k * 130,
                   f'<div style="display:flex;align-items:center;gap:28px;padding:26px 0;border-top:2px solid #2a2e35">'
                   f'<span class="mono ch" style="font-size:44px;font-weight:700">✓</span><span class="b">{it}</span></div>'))
    e.append(A(10.8, 15.0, 260, '<p class="mono ch" style="font-size:44px;font-weight:700;margin:0">LE PLUS ZAPPÉ</p>'))
    e.append(A(11.0, 15.0, 360, '<h2 class="ts">Ranger<br>son matos</h2>'))
    e.append(A(11.6, 15.0, 680, '<p class="b">Barre, disques, balle : tout reprend sa place. La box, c\'est aussi les autres.</p>'))
    e.append(A(15.2, None, 360, '<h2 class="tc" style="font-size:150px;line-height:175px">On a tous<br>un binôme<br>allongé<br>par terre</h2>'))
    e.append(A(16.2, None, 1110, '<p class="mono ch" style="font-size:44px;line-height:60px;font-weight:700;margin:0">Envoie-le-lui</p>'))
    return ''.join(e), 20.0, []

REELS = {'10-fran': fran, '11-rpe': rpe, '12-hollow': hollow,
         '13-cindy': cindy, '14-quiz-benchmarks': quiz, '15-sac-de-box': sac, '16-mythes': mythes,
         '17-a-ou-b-burpees': ab_burpees, '18-defi-binome': defi_binome, '20-no-rep': no_rep, '21-apres-wod': apres_wod}

def page_html(body):
    return (f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><style>{font_faces(FONTS)}\n{CSS}</style></head>"
            f"<body><div id='v'>{body}{BRAND}</div><script>{JS}</script></body></html>")

def audio(path, dur, sounds):
    sr = 48000
    x = np.zeros(int(sr * dur))
    def tone(t0, f, d, vol):
        n = int(sr * d); tt = np.arange(n) / sr
        env = np.minimum(1, tt / 0.004) * np.exp(-tt / (d / 3))
        s = int(sr * t0); x[s:s + n] += vol * env * np.sin(2 * np.pi * f * tt)
    for t, kind in (sounds if BEEPS else []):
        if kind == 'click': tone(t, 1800, 0.05, 0.18)
        elif kind == 'tick': tone(t, 1400, 0.04, 0.12)
        elif kind == 'go':
            for k in range(3): tone(t - 0.9 + k * 0.3, 880, 0.12, 0.3)
            tone(t, 1320, 0.35, 0.35)
        elif kind == 'stop': tone(t, 1320, 0.6, 0.35)
    pcm = (np.clip(x, -1, 1) * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm.tobytes())

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = Path(args[0]); out.mkdir(parents=True, exist_ok=True)
    slugs = args[1:] or list(REELS)
    frames = next((a.split('=', 1)[1] for a in sys.argv if a.startswith('--frames=')), None)
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
        for slug in slugs:
            body, dur, sounds = REELS[slug]()
            hp = out / f'.{slug}.html'; hp.write_text(page_html(body), encoding='utf-8')
            pg.goto(hp.as_uri())
            miss = pg.evaluate("""async () => { const o=[]; for (const f of ['Anton','JetBrains Mono','Inter']) { if(!(await document.fonts.load(`40px '${f}'`)).length) o.push(f);} return o; }""")
            if miss: sys.exit(f'Police manquante : {miss}')
            pg.evaluate('document.fonts.ready')
            el = pg.locator('#v')
            if frames:
                for t in frames.split(','):
                    pg.evaluate(f'frame({t})'); el.screenshot(path=str(out / f'{slug}-t{t}.png'))
                continue
            # couverture
            pg.evaluate('frame(2.0)'); el.screenshot(path=str(out / f'{slug}-cover.jpg'), type='jpeg', quality=92)
            wav = out / f'.{slug}.wav'; audio(wav, dur, sounds)
            tmp = out / f'.{slug}.tmp.mp4'
            ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-',
                                   '-i', str(wav), '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p',
                                   '-r', str(FPS), '-c:a', 'aac', '-b:a', '128k', '-ar', '48000', '-shortest', '-movflags', '+faststart', str(tmp)],
                                  stdin=subprocess.PIPE)
            for i in range(int(dur * FPS)):
                pg.evaluate(f'frame({i / FPS})')
                ff.stdin.write(el.screenshot(type='jpeg', quality=95))
            ff.stdin.close()
            if ff.wait() == 0:
                tmp.rename(out / f'{slug}-reel.mp4')
            else:
                sys.exit(f'ffmpeg a échoué pour {slug}')
            wav.unlink(); hp.unlink()
            print('ok', slug)
        b.close()

main()
