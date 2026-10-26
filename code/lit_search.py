#!/usr/bin/env python3
"""lit_search.py — literature map for the division paper (CGIR target), built from OpenAlex and verified on Crossref.

Why: the project's literature folder held two empty search files; CGIR's cover letter must state the contribution relative to studies
published in CGIR, and every cited work must be verified (citation gate). This script does the first pass mechanically; the author
selects from it. Nothing here is written into the manuscript.

Strands (OpenAlex `search` on title/abstract, journal articles, sorted by citations; top N per query):
  A  equity carve-outs / spin-offs / divestitures: announcement returns, long-run performance, second events (sell-off, re-acquisition, IPO)
  B  Korean business groups, controlling shareholders, tunnelling, minority-shareholder expropriation, principal–principal conflict
  C  text analysis / LLMs in finance and accounting: disclosure informativeness, return and outcome prediction from filings
  D  Korean corporate divisions (물적분할/인적분할) in English and Korean-indexed journals
  V  venue scan: Corporate Governance: An International Review, 2022–2026, filtered by governance keywords relevant to the paper
Each record: OpenAlex id, DOI, title, first authors, year, venue, cited_by_count, strand, query. DOIs of the top records are checked on
Crossref (title/year/container returned), and the result is written to literature/lit_records_<date>.json and docs/LITERATURE_MAP_<date>.md.
"""
import os, re, json, time, datetime as dt, urllib.request, urllib.parse, collections

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OA = "https://api.openalex.org"; MAILTO = "jihwan.woo@gmail.com"; UA = {"User-Agent": f"division-paper-lit-map (mailto:{MAILTO})"}
QUERIES = {
 "A_carveouts": ["equity carve-out", "equity carve-outs + long-run", "carve-out + subsidiary + initial public offering", "spin-off + long-run performance", "spin-off announcement + shareholder wealth", "divestiture + carve-out + sell-off", "corporate spin-offs + information asymmetry", "second event + carve-out", "parent + subsidiary + partial IPO"],
 "B_korea_groups": ["business groups + tunneling", "chaebol + minority shareholders", "controlling shareholders + expropriation + Korea", "principal-principal conflict", "related party transactions + controlling shareholder", "pyramidal ownership + firm value", "Korea + corporate governance + minority shareholder", "propping + business groups"],
 "C_text_llm": ["large language model + stock returns", "ChatGPT + financial", "large language models + financial statement analysis", "textual analysis + 10-K + returns", "machine learning + corporate disclosure + text", "language model + earnings + prediction", "LLM + corporate filings"],
 "D_korea_division": ["물적분할", "인적분할", "corporate division + Korea", "spin-off + Korea + announcement", "split-off + Korea", "carve-out + Korea", "holding company conversion + Korea + spin-off"],
}
CGIR_TERMS = ["business group", "controlling shareholder", "spin-off", "carve-out", "divestiture", "minority shareholders", "tunneling", "Korea", "disclosure", "ownership structure", "family firm", "related party", "principal-principal", "regulation shareholder protection"]


def get(url, tries=3):
    for a in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r: return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if a == tries - 1: print("  ERR", url[:120], str(e)[:80]); return None
            time.sleep(2 + 2 * a)


def oa_search(q, n=40, extra_filter=""):
    """Phrase match on title+abstract (quoted), relevance order (OpenAlex default); the free-text `search` sorted by citations returned
    off-topic classics (checked 2026-10-25). Multi-word queries are split into quoted phrases joined by AND when they contain a '+'."""
    phrases = [x.strip() for x in q.split("+")] if "+" in q else [q]
    f = "type:article," + ",".join(f'title_and_abstract.search:"{ph}"' for ph in phrases) + (("," + extra_filter) if extra_filter else "")
    url = f"{OA}/works?filter={urllib.parse.quote(f, safe=':,\"')}&per-page={n}&mailto={MAILTO}"
    d = get(url); return (d or {}).get("results", [])


def rec(w, strand, q):
    src = ((w.get("primary_location") or {}).get("source") or {})
    return {"openalex": w.get("id"), "doi": (w.get("doi") or "").replace("https://doi.org/", ""), "title": w.get("title") or w.get("display_name"), "year": w.get("publication_year"),
            "venue": src.get("display_name"), "authors": [a.get("author", {}).get("display_name") for a in (w.get("authorships") or [])[:3]], "n_authors": len(w.get("authorships") or []),
            "cited_by": w.get("cited_by_count"), "strand": strand, "query": q, "abstract_available": bool(w.get("abstract_inverted_index"))}


def crossref(doi):
    d = get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")
    if not d: return None
    m = d.get("message", {}); return {"title": (m.get("title") or [None])[0], "container": (m.get("container-title") or [None])[0], "year": ((m.get("issued") or {}).get("date-parts") or [[None]])[0][0], "volume": m.get("volume"), "page": m.get("page") or m.get("article-number")}


def main():
    recs = {}
    for strand, qs in QUERIES.items():
        for q in qs:
            for w in oa_search(q):
                r = rec(w, strand, q); key = r["doi"] or r["openalex"]
                if key not in recs: recs[key] = r
                else: recs[key]["query"] += f" | {q}"
            time.sleep(0.3)
        print(f"{strand}: {sum(1 for r in recs.values() if r['strand'] == strand)} records", flush=True)
    # CGIR venue scan: resolve the source id, then search within it
    s = get(f"{OA}/sources?search={urllib.parse.quote('Corporate Governance An International Review')}&mailto={MAILTO}")
    src = next((x for x in (s or {}).get("results", []) if "international review" in (x.get("display_name") or "").lower()), None)
    cgir = []
    if src:
        sid = src["id"].split("/")[-1]
        for term in CGIR_TERMS:
            for w in oa_search(term, n=25, extra_filter=f"primary_location.source.id:{sid},publication_year:2022-2026"):
                r = rec(w, "V_cgir", term); key = r["doi"] or r["openalex"]
                if key not in recs: recs[key] = r; cgir.append(key)
                elif recs[key]["strand"] != "V_cgir": recs[key]["also_in_cgir_scan"] = True
            time.sleep(0.3)
        print(f"CGIR ({src['display_name']}, {sid}): {len(cgir)} records 2022–2026", flush=True)
    # anchor papers: Kang & Lee (2025) FRL 85:107826 by DOI pattern (Elsevier FRL DOIs are 10.1016/j.frl.<year>.<article>), plus FRL carve-out search
    for doi in ["10.1016/j.frl.2025.107826"]:
        c = crossref(doi); w = get(f"{OA}/works/https://doi.org/{doi}?mailto={MAILTO}")
        if w: r = rec(w, "anchor_candidates", f"doi:{doi}"); r["crossref"] = c; recs[r["doi"] or r["openalex"]] = r
        else: recs[doi] = {"doi": doi, "title": (c or {}).get("title"), "year": (c or {}).get("year"), "venue": (c or {}).get("container"), "authors": [], "n_authors": 0, "cited_by": None, "strand": "anchor_candidates", "query": f"doi:{doi}", "crossref": c, "openalex": None, "abstract_available": False}
    for w in oa_search("carve-out + Korea", n=20): 
        r = rec(w, "anchor_candidates", "carve-out + Korea"); key = r["doi"] or r["openalex"]
        if key not in recs: recs[key] = r
    # Crossref verification of the top-cited records per strand (and all CGIR records)
    by = collections.defaultdict(list)
    for r in recs.values(): by[r["strand"]].append(r)
    checked = 0
    for strand, rs in by.items():
        rs.sort(key=lambda r: -(r["cited_by"] or 0))
        for r in (rs if strand in ("V_cgir", "anchor_candidates") else rs[:25]):
            if r["doi"]:
                c = crossref(r["doi"]); r["crossref"] = c; checked += 1; time.sleep(0.15)
    print("crossref checked:", checked)
    stamp = dt.date.today().strftime("%Y%m%d")
    json.dump(list(recs.values()), open(f"{P}/literature/lit_records_{stamp}.json", "w"), ensure_ascii=False, indent=1)
    # Markdown map
    L = [f"# Literature map — division paper (CGIR target) — {stamp}", "", "Source: OpenAlex works search (journal articles, sorted by citations) per strand; DOIs of the top records verified on Crossref (✓ = Crossref returned title/year/venue). "
         "This is a candidate list for the author to select from, not a reference list. Relevance to our tests must be judged from the papers themselves.", ""]
    for strand, rs in by.items():
        L += [f"## {strand}  ({len(rs)} records)", "", "| # | Year | Authors | Title | Venue | Cites | DOI | CR |", "|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(rs[:45 if strand != "V_cgir" else 90], 1):
            cr = "✓" if r.get("crossref") else ("" if r.get("crossref") is None and "crossref" not in r else "✗")
            L.append(f"| {i} | {r['year']} | {', '.join(a or '' for a in r['authors'])}{' et al.' if r['n_authors'] > 3 else ''} | {(r['title'] or '')[:110]} | {(r['venue'] or '')[:40]} | {r['cited_by']} | {r['doi']} | {cr} |")
        L.append("")
    L += ["## How to use", "", "1. Strand A gives the carve-out/spin-off antecedents (announcement effect, long-run drift, second events) — the closest tests to ours must be mirrored in a table (G4).",
          "2. Strand B gives the principal–principal / tunnelling frame for the controlling-block results (Section on governance).", "3. Strand C positions the LLM reading as measurement, not method novelty.",
          "4. Strand D and the anchor candidates must contain Kang & Lee (2025, FRL 85:107826 and 재무연구 38(1)); if OpenAlex missed them, add by DOI.",
          "5. Strand V (CGIR 2022–2026) is for the cover letter's 'contribution relative to studies published in CGIR' and for the citation distribution rule (≥40% from the target journal and close outlets)."]
    open(f"{P}/docs/LITERATURE_MAP_{stamp}.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"saved literature/lit_records_{stamp}.json, docs/LITERATURE_MAP_{stamp}.md | total records {len(recs)}")


if __name__ == "__main__":
    main()
