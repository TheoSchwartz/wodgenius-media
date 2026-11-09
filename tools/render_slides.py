"""Rend les artboards LABO WOD (.dc.html) en PNG, une image par slide.

Usage : python3 render_slides.py <dossier_dc_html> <dossier_polices> <dossier_sortie>

- Chaque <section class="s"> devient un PNG 1080 × 1350.
- Logo-sombre.dc.html et Logo-craie.dc.html deviennent logo-sombre.png et logo-craie.png (1080 × 1080).
- Les polices viennent de fichiers locaux (Anton, JetBrains Mono, Inter) : le script
  s'arrête si l'une d'elles ne se charge pas, pour ne jamais livrer une police de secours.
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

FOLDERS = {
    "Main.dc.html": "01-formats",
    "C02-WOD01.dc.html": "02-wod-01",
    "C03-EMOM.dc.html": "03-emom",
    "C04-Pacing.dc.html": "04-pacing",
    "C05-Scaling.dc.html": "05-scaling",
    "C06-Lexique.dc.html": "06-lexique",
    "C07-PR.dc.html": "07-progression",
    "C08-Echauffement.dc.html": "08-echauffement",
    "C09-Tabata.dc.html": "09-tabata",
    "Logo-sombre.dc.html": "logo",
    "Logo-craie.dc.html": "logo",
}

FONT_FILES = {
    "Anton": [("Anton-Regular.ttf", "400")],
    "JetBrains Mono": [("JetBrainsMono.ttf", "100 800")],
    "Inter": [
        ("/usr/share/fonts/opentype/inter/Inter-Regular.otf", "400"),
        ("/usr/share/fonts/opentype/inter/Inter-SemiBold.otf", "600"),
    ],
}

CHECK_FONTS = """async () => {
  const out = [];
  for (const f of ['Anton', 'JetBrains Mono', 'Inter']) {
    const faces = await document.fonts.load(`40px '${f}'`);
    if (!faces.length) out.push(f);
  }
  return out;
}"""


def font_faces(font_dir: Path) -> str:
    rules = []
    for family, files in FONT_FILES.items():
        for name, weight in files:
            path = Path(name) if Path(name).is_absolute() else font_dir / name
            if path.exists():
                rules.append(
                    f"@font-face{{font-family:'{family}';src:url('{path.as_uri()}');font-weight:{weight};font-style:normal}}"
                )
    return "\n".join(rules)


def standalone(dc_html: str, faces: str) -> str:
    inner = re.search(r"<x-dc>(.*)</x-dc>", dc_html, re.S).group(1)
    helmet = re.search(r"<helmet>(.*?)</helmet>", inner, re.S)
    styles = "\n".join(re.findall(r"<style>(.*?)</style>", helmet.group(1), re.S)) if helmet else ""
    body = re.sub(r"<helmet>.*?</helmet>", "", inner, flags=re.S)
    return f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><style>{faces}\n{styles}</style></head><body>{body}</body></html>"


def main(src: Path, font_dir: Path, out: Path) -> None:
    faces = font_faces(font_dir)
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 1400}, device_scale_factor=1)
        jobs = dict(FOLDERS)
        # Lots suivants : tout fichier "NN-slug.dc.html" est rendu dans le dossier "NN-slug"
        for extra in sorted(src.glob("[0-9][0-9]-*.dc.html")):
            jobs.setdefault(extra.name, extra.name.replace(".dc.html", ""))
        for file_name, folder in jobs.items():
            path = src / file_name
            if not path.exists():
                continue
            if ONLY and folder not in ONLY:
                continue
            html_path = out / f".{path.stem}.html"
            html_path.write_text(standalone(path.read_text(encoding="utf-8"), faces), encoding="utf-8")
            page.goto(html_path.as_uri())
            missing = page.evaluate(CHECK_FONTS)
            if missing and not ALLOW_FALLBACK:
                sys.exit(f"Police non chargée pour {file_name} : {', '.join(missing)}")
            page.evaluate("document.fonts.ready")
            target = out / folder
            target.mkdir(exist_ok=True)
            if folder == "logo":
                name = file_name.replace(".dc.html", "").lower()
                page.locator("body > div").first.screenshot(path=str(target / f"{name}.png"))
                count += 1
            else:
                slides = page.locator("section.s")
                for i in range(slides.count()):
                    slides.nth(i).screenshot(path=str(target / f"{folder}-{i + 1:02d}.png"))
                    count += 1
            html_path.unlink()
        browser.close()
    print(f"{count} images dans {out}")


ALLOW_FALLBACK = "--test" in sys.argv
# --only=03-emom,04-pacing : ne rendre que ces dossiers
ONLY = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), [])

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(Path(args[0]), Path(args[1]), Path(args[2]))
