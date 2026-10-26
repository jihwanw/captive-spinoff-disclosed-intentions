#!/usr/bin/env python3
"""03_fetch_disclosure_text.py — plain text of each 회사분할결정 filing (DART original document API).

DART DS001 '공시서류원본파일' endpoint: https://opendart.fss.or.kr/api/document.xml?crtfc_key=...&rcept_no=...
returns a zip containing the filing XML; we strip tags and keep the text. Output: one JSON per event list.
"""
import io, json, os, re, html, time, zipfile, configparser, urllib.request, sys

P = "/Users/jihwanw/PhD/Finance/0_pipeline/물적분할-인적분할"
EVENTS = f"{P}/data/raw/dart_division_decisions_2017_2026.json"
OUTDIR = f"{P}/data/raw/disclosure_text"; os.makedirs(OUTDIR, exist_ok=True)
INDEX = f"{P}/data/processed/disclosure_text_index.json"
cfg = configparser.ConfigParser(); cfg.read("/Users/jihwanw/PhD/code/api_info/api_keys.ini")
KEY = cfg["dart"].get("api_key") or cfg["dart"].get("key") or list(cfg["dart"].values())[0]


def to_text(raw: bytes) -> str:
    for enc in ("utf-8", "cp949", "euc-kr"):
        try: s = raw.decode(enc); break
        except Exception: s = None
    if s is None: s = raw.decode("utf-8", "replace")
    s = re.sub(r"<(TD|TH|TR|P|BR|TABLE|TU|TE)[^>]*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s); s = html.unescape(s).replace("&cr;", "\n")
    s = re.sub(r"[ \t\xa0]+", " ", s); s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def fetch(rcept_no: str) -> str | None:
    url = f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={KEY}&rcept_no={rcept_no}"
    for a in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r: data = r.read()
            if data[:2] != b"PK":  # error JSON/XML instead of zip
                msg = data[:200].decode("utf-8", "replace")
                if "020" in msg or "800" in msg: print("STOP:", msg, flush=True); sys.exit(2)
                return None
            z = zipfile.ZipFile(io.BytesIO(data))
            texts = [to_text(z.read(n)) for n in z.namelist()]
            return "\n\n".join(texts)
        except Exception:
            time.sleep(2 + 3 * a)
    return None


events = json.load(open(EVENTS, encoding="utf-8"))
index = json.load(open(INDEX, encoding="utf-8")) if os.path.exists(INDEX) else {}
t0 = time.time(); ok = 0
for i, e in enumerate(events, 1):
    rn = e["rcept_no"]
    path = f"{OUTDIR}/{rn}.txt"
    if rn in index and os.path.exists(path): ok += 1; continue
    txt = fetch(rn)
    if txt:
        open(path, "w", encoding="utf-8").write(txt)
        index[rn] = {"corp_code": e["corp_code"], "corp_name": e["corp_name"], "type": e["type"], "board_date": e["board_date"],
                     "division_date": e["division_date"], "chars": len(txt), "path": os.path.relpath(path, P)}
        ok += 1
    else:
        index[rn] = {"corp_code": e["corp_code"], "corp_name": e["corp_name"], "type": e["type"], "board_date": e["board_date"], "chars": 0, "path": None}
    time.sleep(0.15)
    if i % 50 == 0 or i == len(events):
        json.dump(index, open(INDEX, "w"), ensure_ascii=False, indent=1)
        print(f"{i}/{len(events)} fetched_ok={ok} [{time.time()-t0:.0f}s]", flush=True)
json.dump(index, open(INDEX, "w"), ensure_ascii=False, indent=1)
print("done", ok, "/", len(events))
