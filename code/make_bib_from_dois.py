#!/usr/bin/env python3
"""make_bib_from_dois.py — paper/tex/refs.bib from Crossref for a curated, verified DOI list (CGIR division paper).

Sources of entries
  1. WANT: title fragments matched in literature/lit_records_20261025.json (OpenAlex search, Crossref-checked DOIs).
  2. ADD : DOIs verified one by one on 2026-10-26 through the Crossref REST API (title, journal, volume, issue, pages read back
           and recorded in paper/reviews/CITATION_CHANGES.md).
Every entry's BibTeX is fetched from doi.org by content negotiation and then post-processed:
  * year = Crossref `published-print` year when the article has appeared in a volume/issue (APA 7); online-first year otherwise;
  * key  = <first-author surname><printed year>[letter];
  * `month` fields dropped (apacite.bst has no month strings); `url` dropped (duplicate of DOI);
  * all-caps author fields from Crossref normalised; proper nouns and the first word after a colon/question mark braced so that
    apacite's sentence-case titles keep them capitalised;
  * OVERRIDES fix metadata that Crossref carries incompletely (JSTOR-registered DOIs give the first page only) — each override
    names its source.
Regulator documents (FSC press releases) are not in Crossref and live in paper/tex/refs_manual.bib (hand-written, sources in the entry).
"""
import os, re, json, time, urllib.request, urllib.parse, unicodedata
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(f"{P}/literature/lit_records_20261025.json", encoding="utf-8"))
UA = {"User-Agent": "division-paper (mailto:jihwan.woo@gmail.com)"}

WANT = [  # (title fragment, strand) — docs/LITERATURE_MAP_20261025.md §0 shortlist plus the CGIR conversation
 ("Do “captive” spin-offs create value", "anchor"), ("comparison of equity carve-outs and seasoned", "A"), ("On the Good News in Equity Carve-Outs", "A"), ("two stages of an equity carve", "A"),
 ("Value Creation from Equity Carve-Outs", "A"), ("comparison of the information conveyed by equity carve-outs", "A"), ("Deciphering the Motives for Equity Carve", "A"), ("Information asymmetry, valuation, and the corporate spin-off", "A"),
 ("Effect of Voluntary Spin-off Announcements", "A"), ("Equity Carve-Outs and Managerial Discretion", "A"), ("Pricing of Equity Carve-Outs", "A"),
 ("Review of the Principal–Principal Perspective", "B"), ("Ferreting out Tunneling", "B"), ("Tunneling or Value Added? Evidence from Mergers by Korean", "B"), ("Private Securities Offerings by Korean Chaebols", "B"),
 ("Corporate governance and firm profitability: evidence from Korea", "B"), ("structure and formation of business groups", "B"), ("impact of corporate governance on the East Asian financial crisis", "B"), ("Intragroup Propping", "B"), ("internal capital markets of business groups", "B"),
 ("Textual Analysis, Dictionaries, and 10", "C"), ("Disclosure Sentiment: Machine Learning vs", "C"), ("Look-Ahead Bias in Stock Return Predictions", "C"), ("News in Earnings Announcement Disclosures: Capturing Word Context", "C"),
 ("Corporate Governance of Business Groups Around the World", "V"), ("Minority Shareholders' Online Voice", "V"), ("Mandatory Operating Information Disclosure on Related", "V"), ("Excess control rights in family firms", "V"),
 ("Ownership and corporate governance across institutional contexts", "V"), ("Large Owner Expropriation Threat", "V"), ("role of managerial ownership in dividend tunneling", "V"), ("Corporate Governance Reporting, Disclosures, Monitoring", "V"),
]
ADD = {  # DOI: (strand, verification note) — all read back from api.crossref.org/works/<doi> on 2026-10-26
 "10.37197/ARFR.2025.38.1.1": ("anchor", "Kang & Lee, Asian Review of Financial Research 38(1) 1-36, 2025; DOI from the PDF header"),
 "10.1257/aer.90.2.22": ("B", "Johnson, La Porta, Lopez-de-Silanes & Shleifer, AER 90(2) 22-27, 2000"),
 "10.1016/s0304-405x(00)00067-2": ("B", "Claessens, Djankov & Lang, JFE 58(1-2) 81-112, 2000"),
 "10.1111/1540-6261.00511": ("B", "Claessens, Djankov, Fan & Lang, JF 57(6) 2741-2771, 2002"),
 "10.1111/0022-1082.00115": ("B", "La Porta, Lopez-de-Silanes & Shleifer, JF 54(2) 471-517, 1999"),
 "10.1016/j.jfineco.2010.05.002": ("B", "Jiang, Lee & Yue, JFE 98(1) 1-20, 2010"),
 "10.1093/rfs/hhr052": ("B", "Masulis, Pham & Zein, RFS 24(11) 3556-3600, 2011"),
 "10.1111/j.1540-6261.2004.00642.x": ("B", "Dyck & Zingales, JF 59(2) 537-600, 2004"),
 "10.1093/jleo/ewj018": ("B", "Black, Jang & Kim, JLEO 22(2) 366-413, 2006"),
 "10.1111/0022-1082.65022": ("A", "Allen & McConnell, JF 53(1) 163-186, 1998"),
 "10.1086/323508": ("A", "Vijh, Journal of Business 75(1) 153-190, 2002"),
 "10.1016/0304-405x(83)90042-9": ("A", "Hite & Owers, JFE 12(4) 409-436, 1983"),
 "10.1016/s0304-405x(96)00890-2": ("M", "Barber & Lyon, JFE 43(3) 341-372, 1997"),
 "10.1111/0022-1082.00101": ("M", "Lyon, Barber & Tsai, JF 54(1) 165-201, 1999"),
 "10.1016/s0304-405x(98)00026-9": ("M", "Fama, JFE 49(3) 283-306, 1998"),
 "10.1086/209645": ("M", "Mitchell & Stafford, Journal of Business 73(3) 287-329, 2000"),
 "10.1111/corg.12661": ("V", "Na & Jung, CGIR 33(6) 1567-1597, 2025 (Korea; controlling shareholders' inheritance tax and dividends)"),
 "10.1111/corg.12640": ("V", "Uchida & Yoshikawa, CGIR 33(5) 1107-1125, 2025 (Japan; disclosure of voting records and shareholder dissent)"),
 "10.1111/corg.12484": ("V", "Tanyeri Günsür & Alp, CGIR 31(4) 625-646, 2023 (family firms; shareholder rights and the pricing of control events)"),
 "10.1111/corg.12658": ("V", "Anand, Huan & Pathak, CGIR 34(1) 18-40, 2026 (10-K readability and retail investors' proposals)"),
 "10.1016/j.jacceco.2003.10.002": ("T", "Hirshleifer & Teoh, JAE 36(1-3) 337-386, 2003 (limited attention and disclosure) — verified 2026-10-28"),
 "10.1111/j.1540-6261.2009.01447.x": ("T", "DellaVigna & Pollet, JF 64(2) 709-749, 2009 (investor inattention) — verified 2026-10-28"),
}
OVERRIDES = {  # DOI: {field: value}; source in the comment
 "10.2307/3666322": {"pages": "83–100"},           # Hulburt, Miles & Woolridge 2002, FM 31(1): Penn State Pure record (pure.psu.edu, J. R. Woolridge); JSTOR DOI carries first page only
 "10.2307/2327589": {"DOI": "10.1111/j.1540-6261.1983.tb03843.x", "pages": "1597–1606"},   # Miles & Rosenfeld 1983, JF 38(5): Wiley DOI (Crossref page 1597-1606)
 "10.1016/s0304-405x(98)00026-9": {"title": "Market efficiency, long-term returns, and behavioral finance"},   # Crossref embeds the acknowledgement footnote in the title; JFE 49(3) 283-306
}
PROPER = ["Korean", "Korea", "Indian", "India", "China", "Chinese", "East Asian", "Asian", "GPT", "U.S.", "10-Ks", "10-K", "ROC", "LLM", "Japan", "Japanese", "South Korea", "Plain Writing Act"]

def norm(s): return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
def crossref(doi):
    req = urllib.request.Request(f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}", headers=UA)
    return json.loads(urllib.request.urlopen(req, timeout=60).read())["message"]
def bibtex(doi):
    req = urllib.request.Request(f"https://doi.org/{doi}", headers={"Accept": "application/x-bibtex", **UA})
    return urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace").strip()
def fix_author(a):
    a = re.sub(r"[\u2010\u2011\u2012\u2013]", "-", a)      # Unicode hyphens in Crossref names -> ASCII (Jae-Seung, Lopez-de-Silanes)
    a = re.sub(r"^\s*and\s+", "", a.strip())            # Crossref quirk: leading empty author (ARFR 38(1) record)
    a = a.replace("Lopez-De-Silanes", "Lopez-de-Silanes")
    def cap(tok): return "-".join(w[:1].upper() + w[1:].lower() if w.isupper() and len(w) > 1 else w for w in tok.split("-"))
    if not re.search(r"[A-Z]{4,}", a): return a.replace("Mcdonald", "McDonald")
    out = " and ".join(", ".join(" ".join(cap(w) for w in part.split(" ")) for part in name.split(", ")) for name in a.split(" and "))
    out = out.replace("‐", "-").replace("Mcdonald", "McDonald")
    return out
def fix_title(s):
    s = re.sub(r"[\u2010\u2011\u2012]", "-", s)                     # Unicode hyphens -> ASCII (10-K, carve-outs)
    s = re.sub(r"[☆★]|\s*\d$", "", s).strip()                      # Elsevier footnote markers that Crossref keeps in the title
    s = re.sub(r"\s+:", ":", s)                                      # no space before a colon (ARFR record)
    s = re.sub(r"([:?]\s+)([a-z])", lambda k: k.group(1) + k.group(2).upper(), s)   # APA: capital after a colon or question mark
    for w in sorted(PROPER, key=len, reverse=True):
        s = re.sub(r"(?<![{\w])%s(?![}\w])" % re.escape(w), "{%s}" % w, s)
    return re.sub(r"([:?]\s+)([A-Z])(?!\})", lambda k: k.group(1) + "{" + k.group(2) + "}", s)

sel = []
for frag, strand in WANT:
    hits = [r for r in R if norm(frag) in norm(r.get("title")) and r.get("doi")]
    hits.sort(key=lambda r: -(r["cited_by"] or 0))
    if hits: sel.append((hits[0]["doi"], strand, f"OpenAlex cites {hits[0]['cited_by']}"))
    else: print("NOT FOUND:", frag)
for doi, (strand, note) in ADD.items(): sel.append((doi, strand, note))

entries, keys, seen = [], [], set()
for doi, strand, note in sel:
    doi_l = doi.lower()
    if doi_l in seen: continue
    seen.add(doi_l)
    try:
        m = crossref(doi); bib = bibtex(doi); time.sleep(0.3)
    except Exception as e:
        print("ERR", doi, str(e)[:80]); continue
    if "journal" not in bib: print("INCOMPLETE:", doi, bib[:80].replace("\n", " ")); continue
    yr = ((m.get("published-print") or m.get("issued") or {}).get("date-parts") or [[None]])[0][0]
    bib = re.sub(r",\s*month=\{?[A-Za-z]+\}?", "", bib); bib = re.sub(r",\s*url=\{[^}]*\}", "", bib)
    bib = re.sub(r"year=\{\d{4}\}", f"year={{{yr}}}", bib, 1)
    bib = re.sub(r"author=\{([^}]*)\}", lambda k: "author={" + fix_author(k.group(1)) + "}", bib, 1)
    bib = re.sub(r"title=\{(.*?)\}(?=,\s*\w+=)", lambda k: "title={" + fix_title(k.group(1)) + "}", bib, 1, flags=re.S)
    for field, val in OVERRIDES.get(doi, {}).items():
        bib = re.sub(r"%s=\{[^}]*\}" % field, f"{field}={{{val}}}", bib, 1) if re.search(r"%s=\{" % field, bib) else bib.replace(" }", f", {field}={{{val}}} }}", 1)
    first = re.search(r"author=\{(.+?)\}", bib, re.S).group(1).split(" and ")[0]
    surname = first.split(",")[0] if "," in first else first.split()[-1]
    key = re.sub(r"[^a-z]", "", norm(surname)) + str(yr); k0, i = key, 0
    while key in keys: i += 1; key = f"{k0}{'abcdefgh'[i-1]}"
    keys.append(key)
    bib = re.sub(r"^@\w+\{[^,]+,", f"@article{{{key},", bib, 1)
    entries.append(f"% strand {strand}; Crossref DOI {doi}; {note}\n" + bib)
open(f"{P}/paper/tex/refs.bib", "w", encoding="utf-8").write("\n\n".join(entries) + "\n")
print(f"bib entries: {len(entries)} -> paper/tex/refs.bib"); print("keys:", keys)
