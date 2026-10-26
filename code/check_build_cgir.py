"""check_build_cgir.py (adapted from the JFS project) — errors / undefined references / overfull boxes from main.log (with the source file of each overfull box),
plus a page-by-page measurement of the rightmost glyph in the PDF against the text block. Exit 1 on any error, undefined reference,
overfull box, or glyph beyond the text block. Written 2026-10-23 after a shell check with a double-escaped grep pattern reported
'overfull: 0' for a log that held six."""
import re, subprocess, sys
from pathlib import Path
T = Path(__file__).resolve().parents[1] / "paper/tex"
log = (T / "main.log").read_text(errors="ignore")
errors = len(re.findall(r"^! ", log, re.M)); undefined = log.count("undefined")
over = [(m.group(1), m.group(2)) for m in re.finditer(r"Overfull \\hbox \(([0-9.]+)pt too wide\) (.*)", log)]
# source file of each overfull box: the last "(./file" or "(../file" opened before it in the log
srcs = []
for m in re.finditer(r"Overfull \\hbox", log):
    opened = re.findall(r"\((\.{1,2}/[^\s()]+\.tex)", log[:m.start()]); srcs.append(opened[-1] if opened else "?")
pages = int(re.search(r"\((\d+) pages", log).group(1))
paperw = float(re.search(r"paperwidth=([0-9.]+)pt", log).group(1)); textw = float(re.search(r"\\textwidth=([0-9.]+)pt", log).group(1))
margin = (paperw - textw) / 2   # equal margins on both axes (geometry margin=1in)
info = subprocess.run(["pdfinfo", "-f", "1", "-l", str(pages), str(T / "main.pdf")], capture_output=True, text=True).stdout
size = {int(m.group(1)): (float(m.group(2)), float(m.group(3))) for m in re.finditer(r"Page +(\d+) size: +([0-9.]+) x ([0-9.]+)", info)}
rot = {int(m.group(1)): int(m.group(2)) for m in re.finditer(r"Page +(\d+) rot: +(\d+)", info)}
beyond = {}
for p in range(1, pages + 1):
    pw, ph = size[p]; shown_w = ph if rot.get(p, 0) in (90, 270) else pw   # pdftotext -bbox reports the displayed (rotated) frame
    right = shown_w - margin
    bbox = subprocess.run(["pdftotext", "-bbox", "-f", str(p), "-l", str(p), str(T / "main.pdf"), "-"], capture_output=True, text=True).stdout
    words = [(float(a), float(b), float(c), float(d), t) for a, b, c, d, t in re.findall(r'<word xMin="([0-9.]+)" yMin="([0-9.]+)" xMax="([0-9.]+)" yMax="([0-9.]+)">([^<]*)</word>', bbox)]
    xs = [c for a, b, c, d, t in words if not (t.isdigit() and len(t) <= 3 and d > ph - margin)]   # ignore the page number in the footer
    if xs and max(xs) > right + 1.0: beyond[p] = round(max(xs) - right, 1)
print(f"errors {errors} | undefined {undefined} | overfull {len(over)} | pages {pages} | text block right edge {paperw - margin:.1f}pt (portrait)")
for (w, where), s in zip(over, srcs): print(f"  overfull {w}pt {where}  <- {s}")
for p, d in beyond.items(): print(f"  page {p}: glyphs {d}pt beyond the text block")
sys.exit(1 if (errors or undefined or over or beyond) else 0)
