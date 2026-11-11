#!/usr/bin/env python3
"""build_submission_package_jifma.py — assemble the JIFMA (ScholarOne) upload set from the pipeline outputs.

JIFMA author information (secondary copy read 2026-11-10; Wiley page not reachable by script — the user confirms in a browser): manuscripts
generally not over 30 pages including endnotes, references, exhibits and appendices; double-spaced except quotations, endnotes and references;
a separate cover page with title, author, affiliation, address, phone and acknowledgements; the manuscript anonymous, abstract <= 250 words.

Outputs (paper/submission_build_jifma/):
  01_Main_Manuscript_anonymous.pdf   compiled from paper/tex_jifma with \\anontrue; tables and figures in place (inline floats)
  01_Main_Manuscript_LaTeX.zip       flat LaTeX bundle (main.tex at the root; section files, bib, generated tables, numbers.tex, figures); test-compiled
  02_Cover_Page.docx                 from src/cover_page.md (archive identifiers filled from paper/tex_jifma/archive_ids.tex)
  03_Cover_Letter.docx               from src/cover_letter.md with {NScored}, {AUCPooledLLM}, {DiDCxP}, {MAIN_PAGES}, ... filled from numbers.tex and the build
  04_Supporting_Information.pdf      compiled from paper/tex_jifma/supplement.tex (anonymous; cross-references resolved against main.aux)
  05_Replication_Archive_anonymized.zip   replication_repo with author identifiers removed (for review, not for publication)
  main_author.pdf                    author copy (\\anonfalse; carries the data availability statement) — for the archive audit only
  main_merged.tex                    sections inlined, for the submission gate
  PACKAGE_MANIFEST.md                sizes, sha256, identity-scan results, length checks
Guards: abstract <= 250 words; identity scan of every anonymous file; LaTeX bundle compiles standalone to the same text; page count reported
(a count above 30 is reported, not blocked — the guideline says "generally").
"""
import os, re, sys, json, shutil, zipfile, hashlib, subprocess, datetime as dt, tempfile
from pathlib import Path
P = Path(__file__).resolve().parent.parent
TEX = P / "paper/tex_jifma"; BIB = P / "paper/tex"; TAB = P / "paper/tables"; FIG = P / "paper/figures"; OUT = P / "paper/submission_build_jifma"; SRC = OUT / "src"
OUT.mkdir(exist_ok=True)
IDENT = ["Jihwan", "Woo, J", "jihwan", "jihwanw", "Amazon Web Services", "0000-0002-0424-0242", "KAIST", "Korea University", "Shinhan", "KakaoBank", "Samsung Electronics", "우지환"]
PDFLATEX = ["pdflatex", "-interaction=nonstopmode"]
SUBMISSION_DATE = os.environ.get("SUBMISSION_DATE", "DATE_TO_BE_SET")   # set when the user submits (planned 2027 Q1); the letter is not dated before that

def run(cmd, cwd=None): return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]
def pdftext(p): return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout
def pdfinfo(p): return subprocess.run(["pdfinfo", str(p)], capture_output=True, text=True).stdout
def pages(p): return int(re.search(r"Pages:\s+(\d+)", pdfinfo(p)).group(1))
def latex(stem, cwd):
    for _ in range(2): run(PDFLATEX + [f"{stem}.tex"], cwd=cwd)
    run(["bibtex", stem], cwd=cwd)
    for _ in range(2): run(PDFLATEX + [f"{stem}.tex"], cwd=cwd)
    log = (cwd / f"{stem}.log").read_text(errors="ignore")
    return log.count("\n! "), len(re.findall(r"undefined", log, re.I)), re.findall(r"File `([^']+)' not found", log)
def compile_main(anon: bool, out_pdf: Path):
    main = (TEX / "main.tex").read_text()
    main2 = main.replace("\\newif\\ifanon\\anontrue", "\\newif\\ifanon" + ("\\anontrue" if anon else "\\anonfalse"))
    assert main2 != main or anon, "anon switch not found in main.tex"
    (TEX / "main_build.tex").write_text(main2)
    errs, und, missing = latex("main_build", TEX)
    if errs or und or missing: raise SystemExit(f"build ({'anon' if anon else 'author'}): {errs} errors, {und} undefined, missing {missing}")
    shutil.copy(TEX / "main_build.pdf", out_pdf); shutil.copy(TEX / "main_build.log", OUT / ("main_anon.log" if anon else "main_author.log"))
    for ext in (".aux", ".bbl", ".blg", ".out", ".log", ".tex", ".pdf"): (TEX / f"main_build{ext}").unlink(missing_ok=True)
    return out_pdf

# ---- 1. PDFs (main.aux of the plain compile is needed by the supplement's xr-hyper)
e, u, m = latex("main", TEX)
if e or u or m: raise SystemExit(f"main.tex: {e} errors, {u} undefined, missing {m}")
anon_pdf = compile_main(True, OUT / "01_Main_Manuscript_anonymous.pdf")
author_pdf = compile_main(False, OUT / "main_author.pdf")
e, u, m = latex("supplement", TEX)
if e or u or m: raise SystemExit(f"supplement.tex: {e} errors, {u} undefined, missing {m}")
shutil.copy(TEX / "supplement.pdf", OUT / "04_Supporting_Information.pdf")

# ---- 2. counts for the cover letter and the manifest
nums = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}", (TAB / "numbers.tex").read_text()))
ids = dict(re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}", (TEX / "archive_ids.tex").read_text()))
txt = pdftext(anon_pdf); i = txt.find("Abstract"); j = txt.find("Keywords"); abstract = txt[i + 8:j]
abstract_words = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9\-'\.]*", abstract))
if abstract_words > 250: raise SystemExit(f"abstract has {abstract_words} words (JIFMA limit 250)")
k = txt.find("Introduction"); m_ref = re.search(r"\n\s*References\s*\n", txt[k:]); m = k + m_ref.start() if m_ref else len(txt)
main_words = len(re.findall(r"[A-Za-z][A-Za-z\-']*", txt[k:m]))
main_pages = pages(anon_pdf); supp_pages = pages(OUT / "04_Supporting_Information.pdf")
if "data availability" in txt.lower(): raise SystemExit("the anonymous main document contains a data availability statement (it names the repository) — keep it on the cover page")
def plain(v): return v.replace("$-$", "−").replace("$<$", "<").replace("\\%", "%")
fill = {k2: plain(v) for k2, v in nums.items()}
fill.update({"MAIN_PAGES": str(main_pages), "SUPP_PAGES": str(supp_pages), "MAIN_WORDS": f"about {main_words:,}", "ABSTRACT_WORDS": str(abstract_words)})

# ---- 3. Word documents
for src, dst in (("cover_page.md", "02_Cover_Page.docx"), ("cover_letter.md", "03_Cover_Letter.docx")):
    s = (SRC / src).read_text()
    s = s.replace("DATE_PLACEHOLDER", SUBMISSION_DATE).replace("ARCHIVE_VERSION_DOI", ids.get("ArchiveVersionDOI", "PENDING")).replace("ARCHIVE_CONCEPT_DOI", ids.get("ArchiveConceptDOI", "PENDING")).replace("ARCHIVE_TAG", ids.get("ArchiveTag", "PENDING"))
    s = re.sub(r"\{([A-Za-z_]+)\}", lambda mm: fill.get(mm.group(1), mm.group(0)), s)
    left = re.findall(r"\{[A-Za-z_]+\}", s)
    if left: raise SystemExit(f"{src}: unfilled placeholders {left}")
    tmp = OUT / ("_" + src); tmp.write_text(s); r = run(["pandoc", str(tmp), "-o", str(OUT / dst)]); tmp.unlink()
    if r.returncode: raise SystemExit(f"pandoc failed for {src}: {r.stderr[-300:]}")

# ---- 4. flat LaTeX bundle (main.tex at the root; ../tables, ../figures, ../tex paths rewritten)
bundle = OUT / "01_Main_Manuscript_LaTeX.zip"
def flat(s): return s.replace("../tables/", "").replace("../figures/", "").replace("../tex/", "")
used_tables = set(re.findall(r"\\input\{\.\./tables/([A-Za-z_]+)\}", "".join(f.read_text() for f in TEX.glob("sec*.tex")))) | {"numbers"}
used_figs = set(re.findall(r"\{\.\./figures/([A-Za-z0-9_]+\.pdf)\}", "".join(f.read_text() for f in TEX.glob("sec*.tex"))))
with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(TEX.glob("*.tex")):
        if f.name in ("supplement.tex", "sec7_availability.tex", "main_build.tex"): continue
        if f.name == "archive_ids.tex":
            z.writestr(f.name, "\\newcommand{\\ArchiveTag}{(see cover page)}\n\\newcommand{\\ArchiveVersionDOI}{(see cover page)}\n\\newcommand{\\ArchiveConceptDOI}{(see cover page)}\n"); continue
        z.writestr(f.name, flat(f.read_text()))
    for f in sorted(BIB.glob("*.bib")): z.write(f, f.name)
    for t in sorted(used_tables): z.write(TAB / f"{t}.tex", f"{t}.tex")
    for g in sorted(used_figs): z.write(FIG / g, g)
    z.writestr("README.txt", "Main document: main.tex (anonymous). Compile: pdflatex main; bibtex main; pdflatex main; pdflatex main. Section files, generated tables (T_*.tex, numbers.tex), figures and the bibliography are at the root.\n")
with tempfile.TemporaryDirectory() as td:
    with zipfile.ZipFile(bundle) as z: z.extractall(td)
    btex = Path(td); e, u, m = latex("main", btex)
    if e or u or m or not (btex / "main.pdf").exists(): raise SystemExit(f"LaTeX bundle does not compile standalone: {e} errors, {u} undefined, missing {m}")
    if pages(btex / "main.pdf") != main_pages: raise SystemExit(f"bundle compiles to {pages(btex / 'main.pdf')} pages, the submitted PDF has {main_pages}")
    if pdftext(btex / "main.pdf") != pdftext(anon_pdf): raise SystemExit("LaTeX bundle PDF text differs from the submitted PDF")

# ---- 5. anonymized replication archive for review
repo = P / "replication_repo"
SCRUB = [(re.escape(x), "[redacted]") for x in ("jihwan.woo@gmail.com", "Jihwan Woo", "jihwanw", "Woo, Jihwan", "0000-0002-0424-0242", "Amazon Web Services, Seoul, Republic of Korea", "Amazon Web Services")]
rep = OUT / "05_Replication_Archive_anonymized.zip"
with zipfile.ZipFile(rep, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(repo.rglob("*")):
        if not f.is_file() or ".git" in f.parts or "__pycache__" in f.parts: continue
        rel = f.relative_to(repo).as_posix()
        if rel in ("CITATION.cff", ".zenodo.json", "LICENSE") or rel.startswith("code/build_submission_package"): continue
        if f.suffix in (".py", ".md", ".tex", ".bib", ".txt", ".json", ".jsonl", ".csv", ".cff", ".yml", ".yaml"):
            s = f.read_text(errors="ignore")
            for pat, repl in SCRUB: s = re.sub(pat, repl, s)
            s = re.sub(r"/Users/[A-Za-z0-9_]+/", "/Users/[redacted]/", s); z.writestr("replication/" + rel, s)
        else: z.write(f, "replication/" + rel)
    z.writestr("replication/ANONYMIZED_COPY.txt", "This copy of the replication archive has author identifiers removed for double-blind review. The public release (with its DOI) is named on the cover page.\n")

# ---- 6. identity scan
report = []
def scan_text(label, s): hits = sorted({x for x in IDENT if x.lower() in s.lower()}); report.append((label, hits))
scan_text("01_Main_Manuscript_anonymous.pdf text", pdftext(anon_pdf)); scan_text("01_Main_Manuscript_anonymous.pdf metadata", pdfinfo(anon_pdf))
scan_text("04_Supporting_Information.pdf text", pdftext(OUT / "04_Supporting_Information.pdf")); scan_text("04_Supporting_Information.pdf metadata", pdfinfo(OUT / "04_Supporting_Information.pdf"))
for zname in (bundle, rep):
    with zipfile.ZipFile(zname) as z:
        hits_all = {}
        for n in z.namelist():
            if n.endswith((".pdf", ".png", ".parquet", ".sty")): continue
            s = z.read(n).decode("utf-8", "ignore")
            ident_set = IDENT if not n.endswith((".json", ".jsonl", ".csv")) else [x for x in IDENT if x not in ("KAIST", "Korea University", "Shinhan", "KakaoBank", "Samsung Electronics", "Amazon Web Services")]
            h = [x for x in ident_set if x.lower() in s.lower()]
            if h: hits_all[n] = h
        report.append((zname.name + " members", hits_all))
bad = [(l, h) for l, h in report if h]

# ---- 6b. merged tex for the submission gate
main_src = (TEX / "main.tex").read_text()
merged = re.sub(r"\\input\{(sec[0-9a-z_]+|archive_ids)\}", lambda mm: "\n" + (TEX / (mm.group(1) + ".tex")).read_text().rstrip() + "\n", main_src)
(OUT / "main_merged.tex").write_text(merged)

# ---- 7. manifest
lines = [f"# JIFMA submission package — built {dt.datetime.now():%Y-%m-%d %H:%M}", "",
         f"Anonymous main PDF: {main_pages} pages including tables, figures and references (JIFMA: 'generally should not exceed 30'); text from the Introduction to the reference list about {main_words:,} words (tables inline); abstract {abstract_words} words (limit 250). Supporting Information: {supp_pages} pages.",
         f"Cover-letter date: {SUBMISSION_DATE} (set SUBMISSION_DATE at submission time).", "", "| File | Size | sha256 (16) |", "|---|---|---|"]
for f in sorted(OUT.iterdir()):
    if f.is_file() and (not f.name.startswith(("PACKAGE_", "_", ".", "main_")) or f.name == "main_author.pdf"): lines.append(f"| {f.name} | {f.stat().st_size:,} | {sha(f)} |")
lines += ["", "## Identity scan (anonymous files must be clean)", ""] + [f"- {l}: {'CLEAN' if not h else 'HITS ' + str(h)}" for l, h in report]
lines += ["", f"Archive identifiers on the cover page: tag {ids.get('ArchiveTag')}, version DOI {ids.get('ArchiveVersionDOI')}, concept DOI {ids.get('ArchiveConceptDOI')} — these are the CGIR-era release until the JIFMA release is made; update archive_ids.tex and rebuild before upload."]
(OUT / "PACKAGE_MANIFEST.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines)); print("\nIDENTITY SCAN:", "FAIL" if bad else "PASS")
sys.exit(1 if bad else 0)
