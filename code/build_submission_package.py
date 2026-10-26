#!/usr/bin/env python3
"""build_submission_package.py — assemble the Wiley Research Exchange upload set for CGIR from the pipeline outputs.

Outputs (paper/submission_build/):
  01_Main_Manuscript.pdf          anonymous main document (\\anontrue), compiled from paper/tex
  01_Main_Manuscript_LaTeX.zip    the LaTeX bundle Wiley accepts for the main manuscript: tex, bib, generated tables, numbers.tex,
                                  archive_ids.tex, the manually installed endfloat.sty, and the PDF
  02_Title_Page.docx              from src/title_page.md (archive DOIs filled from paper/tex/archive_ids.tex)
  03_Area_of_Literature.docx      from src/area_of_literature.md
  04_Supporting_Information.pdf   supplement.pdf (anonymous)
  05_Cover_Letter.docx            from src/cover_letter.md with {NScored}, {AUCPooledLLM}, ... filled from numbers.tex and the build
  06_Replication_Archive_anonymized.zip   code, results, labels, tables and manuscript sources with author identifiers removed
                                  (for "Additional File for Review but Not for Publication")
  main_author.pdf                 author copy (\\anonfalse) used only for the G35-G37 audit (contains the DOI and the GitHub URL)
  PACKAGE_MANIFEST.md             sizes, sha256, identity-scan results
Identity scan: every anonymous file (PDF text + PDF metadata + zip members) must contain none of the author identifiers.
"""
import os, re, sys, json, shutil, zipfile, hashlib, subprocess, datetime as dt, tempfile
from pathlib import Path
P = Path(__file__).resolve().parent.parent
TEX = P / "paper/tex"; TAB = P / "paper/tables"; OUT = P / "paper/submission_build"; SRC = OUT / "src"
OUT.mkdir(exist_ok=True)
IDENT = ["Jihwan", "Woo, J", "jihwan", "jihwanw", "Amazon Web Services", "0000-0002-0424-0242", "KAIST", "Korea University", "Shinhan", "KakaoBank", "Samsung Electronics", "우지환"]
PDFLATEX = ["pdflatex", "-interaction=nonstopmode"]

def run(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0 and "pdflatex" not in cmd[0] and "bibtex" not in cmd[0]:
        raise SystemExit(f"command failed: {cmd}\n{r.stderr[-800:]}")
    return r
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
def pdftext(p): return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout
def pdfinfo(p): return subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True).stdout
def compile_main(anon: bool, out_pdf: Path):
    main = (TEX / "main.tex").read_text()
    main2 = main.replace("\\newif\\ifanon\\anontrue", "\\newif\\ifanon" + ("\\anontrue" if anon else "\\anonfalse"))
    assert main2 != main or anon, "anon switch not found in main.tex"
    tmp = TEX / "main_build.tex"; tmp.write_text(main2)
    for _ in range(2): run(PDFLATEX + ["main_build.tex"], cwd=TEX, check=False)
    run(["bibtex", "main_build"], cwd=TEX, check=False)
    for _ in range(2): run(PDFLATEX + ["main_build.tex"], cwd=TEX, check=False)
    log = (TEX / "main_build.log").read_text(errors="ignore")
    errs, und = log.count("\n! "), len(re.findall(r"undefined", log, re.I))
    if errs or und: raise SystemExit(f"build ({'anon' if anon else 'author'}): {errs} errors, {und} undefined")
    shutil.copy(TEX / "main_build.pdf", out_pdf)
    for ext in (".aux", ".bbl", ".blg", ".out", ".ttt", ".fff", ".tex"):
        (TEX / f"main_build{ext}").unlink(missing_ok=True)
    shutil.copy(TEX / "main_build.log", OUT / ("main_anon.log" if anon else "main_author.log")); (TEX / "main_build.log").unlink(missing_ok=True)
    return out_pdf

# ---- 1. PDFs
anon_pdf = compile_main(True, OUT / "01_Main_Manuscript.pdf")
author_pdf = compile_main(False, OUT / "main_author.pdf")
shutil.copy(TEX / "supplement.pdf", OUT / "04_Supporting_Information.pdf")

# ---- 2. counts for the cover letter
nums = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}", (TAB / "numbers.tex").read_text()))
ids = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}", (TEX / "archive_ids.tex").read_text()))
txt = pdftext(anon_pdf); i = txt.find("Abstract"); j = txt.find("Keywords"); a = txt[i + 8:j]
for lab in ("Research Question/Issue:", "Research Findings/Insights:", "Theoretical/Academic Implications:", "Practitioner/Policy Implications:"): a = a.replace(lab, " ")
abstract_words = len(re.findall(r"[A-Za-z][A-Za-z\-']*", a))
k = txt.find("1    Introduction"); m = txt.find("Data availability", k)
main_words = len(re.findall(r"[A-Za-z][A-Za-z\-']*", txt[k:m]))
main_pages = int(re.search(r"Pages:\s+(\d+)", pdfinfo(anon_pdf)).group(1)); supp_pages = int(re.search(r"Pages:\s+(\d+)", pdfinfo(OUT / "04_Supporting_Information.pdf")).group(1))
def plain(v): return v.replace("$-$", "−").replace("$<$", "<")
fill = {k2: plain(v) for k2, v in nums.items()}
fill.update({"MAIN_PAGES": str(main_pages), "SUPP_PAGES": str(supp_pages), "MAIN_WORDS": f"{(main_words // 100) * 100:,}" if main_words < 10000 else f"{main_words:,}", "ABSTRACT_WORDS": str(abstract_words)})
fill["MAIN_WORDS"] = f"about {main_words:,}"

# ---- 3. Word documents
for src, dst in (("title_page.md", "02_Title_Page.docx"), ("area_of_literature.md", "03_Area_of_Literature.docx"), ("cover_letter.md", "05_Cover_Letter.docx")):
    s = (SRC / src).read_text()
    s = s.replace("DATE_PLACEHOLDER", dt.date.today().strftime("%d %B %Y")).replace("ARCHIVE_VERSION_DOI", ids.get("ArchiveVersionDOI", "PENDING")).replace("ARCHIVE_CONCEPT_DOI", ids.get("ArchiveConceptDOI", "PENDING"))
    s = re.sub(r"\{([A-Za-z_]+)\}", lambda mm: fill.get(mm.group(1), mm.group(0)), s)
    left = re.findall(r"\{[A-Za-z_]+\}", s)
    if left: raise SystemExit(f"{src}: unfilled placeholders {left}")
    tmp = OUT / ("_" + src); tmp.write_text(s); run(["pandoc", str(tmp), "-o", str(OUT / dst)]); tmp.unlink()

# ---- 4. LaTeX bundle
bundle = OUT / "01_Main_Manuscript_LaTeX.zip"
with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(TEX.glob("*.tex")):
        if f.name in ("main_author.tex", "main_build.tex"): continue
        if f.name == "sec7_availability.tex":   # anonymous branch only — the author branch names the repository
            s7 = f.read_text(); anon_branch = re.search(r"\\ifanon\s*(.*?)\\else", s7, re.S).group(1).strip()
            z.writestr(f"manuscript/tex/{f.name}", "\\section*{Data availability statement}\n" + anon_branch + "\n"); continue
        if f.name == "archive_ids.tex":          # DOI and tag are given on the title page, not in the anonymous source
            z.writestr(f"manuscript/tex/{f.name}", "\\newcommand{\\ArchiveTag}{(see title page)}\n\\newcommand{\\ArchiveVersionDOI}{(see title page)}\n\\newcommand{\\ArchiveConceptDOI}{(see title page)}\n"); continue
        z.write(f, f"manuscript/tex/{f.name}")
    for f in sorted(TEX.glob("*.bib")): z.write(f, f"manuscript/tex/{f.name}")
    for f in sorted(TAB.glob("*.tex")): z.write(f, f"manuscript/tables/{f.name}")
    endfloat = Path.home() / "Library/texmf/tex/latex/endfloat/endfloat.sty"
    if endfloat.exists(): z.write(endfloat, "manuscript/tex/endfloat.sty")
    z.write(anon_pdf, "manuscript/01_Main_Manuscript.pdf")
    z.writestr("manuscript/README.txt", "Compile from manuscript/tex: pdflatex main; bibtex main; pdflatex main; pdflatex main. Tables are \\input from ../tables. endfloat.sty is included in case it is absent from the TeX installation.\n")

# ---- 5. anonymized replication archive for review
repo = P / "replication_repo"
SCRUB = [(re.escape(x), "[redacted]") for x in ("jihwan.woo@gmail.com", "Jihwan Woo", "jihwanw", "Woo, Jihwan", "0000-0002-0424-0242", "Amazon Web Services, Seoul, Republic of Korea", "Amazon Web Services")]
rep = OUT / "06_Replication_Archive_anonymized.zip"
with zipfile.ZipFile(rep, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(repo.rglob("*")):
        if not f.is_file() or ".git" in f.parts or "__pycache__" in f.parts: continue
        rel = f.relative_to(repo).as_posix()
        if rel in ("CITATION.cff", ".zenodo.json", "LICENSE"): continue   # carry the author's name by design
        if f.suffix in (".py", ".md", ".tex", ".bib", ".txt", ".json", ".jsonl", ".csv", ".cff", ".yml", ".yaml"):
            s = f.read_text(errors="ignore")
            for pat, repl in SCRUB: s = re.sub(pat, repl, s)
            s = re.sub(r"/Users/[A-Za-z0-9_]+/", "/Users/[redacted]/", s)
            z.writestr("replication/" + rel, s)
        else:
            z.write(f, "replication/" + rel)
    z.writestr("replication/ANONYMIZED_COPY.txt", "This copy of the replication archive has author identifiers removed for double-blind review. The public release (with its DOI) is named on the title page.\n")

# ---- 6. identity scan on anonymous files
report = []
def scan_text(label, s):
    hits = sorted({x for x in IDENT if x.lower() in s.lower()})
    report.append((label, hits)); return hits
scan_text("01_Main_Manuscript.pdf text", pdftext(anon_pdf)); scan_text("01_Main_Manuscript.pdf metadata", pdfinfo(anon_pdf))
scan_text("04_Supporting_Information.pdf text", pdftext(OUT / "04_Supporting_Information.pdf")); scan_text("04_Supporting_Information.pdf metadata", pdfinfo(OUT / "04_Supporting_Information.pdf"))
for zname in (bundle, rep):
    with zipfile.ZipFile(zname) as z:
        hits_all = {}
        for n in z.namelist():
            if n.endswith((".pdf", ".png", ".parquet", ".sty")): continue
            s = z.read(n).decode("utf-8", "ignore")
            # data files (judgments, literature records, filings) name Korean companies that coincide with the author's past employers; scan them for personal identifiers only
            ident_set = IDENT if not n.endswith((".json", ".jsonl", ".csv")) else [x for x in IDENT if x not in ("KAIST", "Korea University", "Shinhan", "KakaoBank", "Samsung Electronics", "Amazon Web Services")]
            h = [x for x in ident_set if x.lower() in s.lower()]
            if h: hits_all[n] = h
        report.append((zname.name + " members", hits_all))
bad = [(l, h) for l, h in report if h]

# ---- 7. manifest
lines = [f"# Submission package — built {dt.datetime.now():%Y-%m-%d %H:%M}", "", f"Anonymous main PDF: {main_pages} pages; main text {main_words:,} words (to the data availability statement); abstract {abstract_words} words. Supporting Information: {supp_pages} pages.", "", "| File | Size | sha256 (16) |", "|---|---|---|"]
for f in sorted(OUT.iterdir()):
    if f.is_file() and not f.name.startswith(("PACKAGE_", "_", "main_")) or f.name == "main_author.pdf":
        lines.append(f"| {f.name} | {f.stat().st_size:,} | {sha(f)} |")
lines += ["", "## Identity scan (anonymous files must be clean)", ""] + [f"- {l}: {'CLEAN' if not h else 'HITS ' + str(h)}" for l, h in report]
lines += ["", f"Archive identifiers in the author copy: tag {ids.get('ArchiveTag')}, version DOI {ids.get('ArchiveVersionDOI')}, concept DOI {ids.get('ArchiveConceptDOI')}."]
(OUT / "PACKAGE_MANIFEST.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
print("\nIDENTITY SCAN:", "FAIL" if bad else "PASS")
sys.exit(1 if bad else 0)
