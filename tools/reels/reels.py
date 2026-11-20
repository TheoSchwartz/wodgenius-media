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
BEEPS = False  # bips jugés pénibles : la musique vient de loop.py
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

# ---------------- Fran ----------------
def fran():
    e = []
    e.append(A(0.0, 3.0, 300, '<span class="tag">Benchmark</span>'))
    e.append(A(0.15, 3.0, 420, '<h1 class="tc" style="font-size:300px;line-height:320px">Fran</h1>'))
    e.append(A(0.45, 3.0, 760, '<p class="hero" style="font-size:190px;line-height:200px">21-15-9</p>'))
    e.append(A(0.9, 3.0, 1010, '<p class="b" style="font-size:60px;line-height:76px">Tu connais ton temps ?</p>'))
    e.append(A(3.2, 6.6, 300, '<h2 class="ts">Le WOD</h2>'))
    rows = [('FORMAT', 'Pour le temps'), ('REPS', '<span class="mono ch" style="font-weight:700">21-15-9</span>'),
            ('MOUVEMENT 1', 'Thruster'), ('MOUVEMENT 2', 'Pull-up'), ('CHARGE RX', '43 kg · 29 kg')]
    for k, (a, b) in enumerate(rows):
        e.append(A(3.45 + k * 0.25, 6.6, 500 + k * 120, f'<div class="row"><span class="rk">{a}</span><span style="font-weight:600">{b}</span></div>'))
    e.append(A(6.8, 10.4, 300, '<span class="tag ol">Exemple illustratif</span>'))
    e.append(A(6.9, 10.4, 440, '<p class="b muted">Fran scaled, chrono en main</p>'))
    e.append(A(6.9, 10.4, 560, '<p class="hero cnt" data-from="0" data-to="365" data-t0="7.1" data-t1="9.6" data-fmt="time" data-lin="1" style="font-size:280px;line-height:300px">0:00</p>'))
    e.append(A(7.0, 10.4, 920, '<p class="mono" style="font-size:110px;line-height:130px;font-weight:700;margin:0">'
               '<span class="hl" data-on="7.1">21</span> <span class="muted">·</span> <span class="hl" data-on="8.1">15</span> <span class="muted">·</span> <span class="hl" data-on="8.9">9</span></p>'))
    e.append(A(9.7, 10.4, 1110, '<p class="b">Temps final : <span class="mono ch" style="font-weight:700">6:05</span></p>'))
    e.append(A(10.6, None, 420, '<h2 class="tc">Note<br>ton temps</h2>'))
    e.append(A(10.9, None, 860, '<p class="b">Même version, même standards. Refais-le dans quelques mois : le chrono dira le reste.</p>'))
    e.append(A(11.3, None, 1150, '<p class="mono ch" style="font-size:42px;line-height:56px;font-weight:700;margin:0">Enregistre · Partage à ton binôme</p>'))
    sounds = [(0.0, 'click'), (3.2, 'click'), (6.8, 'click'), (7.1, 'go'), (9.6, 'stop'), (10.6, 'click')]
    return ''.join(e), 13.5, sounds

# ---------------- RPE ----------------
def rpe():
    e = []
    e.append(A(0.0, 3.0, 300, '<span class="tag">Data</span>'))
    e.append(A(0.15, 3.0, 440, '<p class="hero" style="font-size:300px;line-height:300px">8/10</p>'))
    e.append(A(0.5, 3.0, 780, '<h1 class="tc">Ton effort<br>a une note</h1>'))
    e.append(A(3.2, 7.0, 300, '<h2 class="ts">L\'échelle RPE</h2>'))
    scale = [('10', 'Plus aucune rep possible', 100, True), ('9', '1 rep en réserve', 85, False),
             ('8', '2 reps en réserve', 70, False), ('7', '3 reps en réserve', 55, False)]
    for k, (n, lab, w, acc) in enumerate(scale):
        t = 3.5 + k * 0.45
        col = '#f3c34f' if acc else '#5e646c'
        e.append(A(t, 7.0, 480 + k * 205,
                   f'<div style="display:flex;align-items:baseline;gap:28px"><span class="mono" style="font-size:72px;font-weight:700;width:110px;color:{"#f3c34f" if acc else "#f2efe8"}">{n}</span>'
                   f'<span class="b">{lab}</span></div>'
                   f'<div class="bar grow" data-t0="{t}" style="width:{w}%;margin-top:18px;background:{col}"></div>'))
    e.append(A(7.2, 10.6, 300, '<span class="tag ol">Exemple illustratif</span>'))
    e.append(A(7.3, 10.6, 440, '<h2 class="ts">Même charge,<br>moins d\'effort</h2>'))
    e.append(A(7.5, 10.6, 740, '<p class="b muted">Squat 80 kg × 5 · 4 semaines</p>'))
    e.append(A(7.6, 10.6, 860, '<p class="hero" style="font-size:190px;line-height:220px">RPE&nbsp;<span class="cnt" data-from="9" data-to="7" data-t0="7.9" data-t1="9.4" data-fmt="half">9</span></p>'))
    e.append(A(9.6, 10.6, 1180, '<p class="b">Le même travail coûte moins cher : tu progresses.</p>'))
    e.append(A(10.8, None, 420, '<h2 class="tc">Note-le</h2>'))
    e.append(A(11.1, None, 680, '<p class="b">Un chiffre de 1 à 10 après chaque WOD. Dix secondes, et tes séances deviennent comparables.</p>'))
    e.append(A(11.5, None, 1040, '<p class="mono ch" style="font-size:40px;line-height:56px;font-weight:700;margin:0">L\'app WOD Genius arrive.<br>Suis @wodgenius</p>'))
    sounds = [(0.0, 'click'), (3.2, 'click')] + [(3.5 + k * 0.45, 'tick') for k in range(4)] + [(7.2, 'click'), (9.4, 'stop'), (10.8, 'click')]
    return ''.join(e), 13.5, sounds

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
    e.append(A(0.0, 3.0, 300, '<span class="tag">Scaling</span>'))
    e.append(A(0.15, 3.0, 420, '<h1 class="tc">Le hollow<br>avant le<br>kipping</h1>'))
    e.append(A(0.7, 3.0, 1080, '<p class="b muted">La position de base de la gym, en 4 étapes.</p>'))
    e.append(A(3.2, 10.2, 300, '<h2 class="ts">4 étapes</h2>'))
    steps = ['Genoux pliés, bras le long du corps', 'Une jambe tendue, l\'autre pliée',
             'Deux jambes tendues, bras le long du corps', 'Jambes tendues, bras derrière la tête']
    for k, txt in enumerate(steps):
        t0 = 3.5 + k * 1.6
        t1 = t0 + 1.6 if k < 3 else 10.2
        e.append(A(t0, t1, 540, figure(k + 1)))
        e.append(A(t0, t1, 980, f'<p class="mono ch" style="font-size:44px;font-weight:700;margin:0">ÉTAPE 0{k+1}</p><p class="b" style="margin-top:16px">{txt}</p>'))
    e.append(A(3.6, 10.2, 1250, '<p class="b muted" style="font-size:40px;line-height:54px"><span class="ch">●</span> bas du dos plaqué au sol</p>'))
    e.append(A(10.4, None, 420, '<h2 class="tc">Gaine<br>d\'abord</h2>'))
    e.append(A(10.7, None, 860, '<p class="b">Le bas du dos décolle ? Reviens à l\'étape d\'avant.</p>'))
    e.append(A(11.1, None, 1060, '<p class="mono ch" style="font-size:42px;line-height:56px;font-weight:700;margin:0">Enregistre · Partage</p>'))
    sounds = [(0.0, 'click'), (3.2, 'click')] + [(3.5 + k * 1.6, 'tick') for k in range(4)] + [(10.4, 'click')]
    return ''.join(e), 13.5, sounds

REELS = {'10-fran': fran, '11-rpe': rpe, '12-hollow': hollow}

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
