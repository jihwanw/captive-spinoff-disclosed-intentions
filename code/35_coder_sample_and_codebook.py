#!/usr/bin/env python3
"""35_coder_sample_and_codebook.py — stratified filing sample and coding sheet for the HUMAN-coder validation of the disposal signal
(resubmission strategy §4-A item 1; answers the CGIR editor's "how AI bias were corrected": reliability and validity against human readers).

Sample: 150 captive spin-off filings = 120 from the Gate-1 sample (clean label; strata period {2001-08, 2009-16, 2017+} × outcome
{disposed, retained}, allocated proportionally with a floor of 12 per cell) + 30 post-reform filings (announced 2022-10-01 or later, label
mostly unknown) so that the coders also see the mandated-form filings. Drawn with a fixed seed from the Gate-1 construction of 15 (executed
here, not re-implemented). Coders see the filing text (DART viewer link + local text path) and NOT the model's score or the outcome.
Coding sheet columns (all blind): purpose categories as Kang & Lee (2025b) Table 1 (sale / efficiency / specialization / other, 0/1 each),
listing plan (none / stated plan / explicit no-listing), external-investor mention (0/1), sale-or-buyer mention (0/1), shareholder-protection
measures (0/1), disposal probability 0–100 (the coder's own forecast that the parent will not keep 100% within ~3–5 years), most likely path
(retain / ipo / sale_to_third_party / partial_stake_sale_or_investor / intragroup_transfer_or_merger), confidence (1–3), evidence (verbatim
sentence), minutes spent. Two coders code all 150 independently; a third resolves disagreements only after κ is computed.
Analysis (36, after coding): κ / ICC coder–coder and coder–model; AUC of each coder's probability vs the realised label on the 120 labelled
filings; coder probability vs model signal (Spearman); K&L-type purpose dummies hand-coded vs the model's extraction (agreement).
Outputs: data/coding/coder_sample_<date>.csv (sheet, one per coder: coder_A, coder_B), docs/CODEBOOK_disposal_signal_<date>.md
"""
import os, json, glob, datetime as dt, numpy as np, pandas as pd

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f"{P}/data/coding"; os.makedirs(OUT, exist_ok=True); STAMP = dt.date.today().strftime("%Y%m%d")
src = open(f"{P}/code/15_gate1_pooled.py", encoding="utf-8").read(); head = src.split("\ndef panel(")[0]; ns = {"__file__": f"{P}/code/15_gate1_pooled.py", "__name__": "g"}; exec(compile(head, "15", "exec"), ns)
g1 = ns["df"][["rcept_no", "period_src", "y", "division_year", "p_llm"]].copy()
g1["period"] = pd.cut(g1.division_year, [2000, 2008, 2016, 2026], labels=["2001-2008", "2009-2016", "2017+"]).astype(str)
idx_new = json.load(open(f"{P}/data/processed/disclosure_text_index.json", encoding="utf-8")); idx_old = json.load(open(f"{P}/data/processed/disclosure_text_index_2001_2016.json", encoding="utf-8"))
dd = {r["rcept_no"]: r for r in json.load(open(f"{P}/data/raw/dart_division_decisions_2017_2026.json", encoding="utf-8"))}
old = {}
for r in json.load(open(f"{P}/data/processed/carveout_disposal_tracking_2001_2016.json", encoding="utf-8")): old[r["rcept_no"]] = r
def meta(rn):
    e = idx_new.get(rn) or idx_old.get(rn) or {}; r = dd.get(rn) or old.get(rn) or {}
    text_rn = e.get("text_rcept_no") or rn
    return {"corp_name": r.get("corp_name") or e.get("corp_name"), "corp_cls": r.get("corp_cls") or e.get("corp_cls"), "board_date": r.get("board_date") or e.get("board_date"), "text_path": e.get("path"), "text_rcept_no": text_rn, "dart_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={text_rn}"}
rng = np.random.default_rng(20261110)
# 120 labelled: proportional allocation with floor 12 per (period, outcome) cell
cells = g1.groupby(["period", "y"]).size(); alloc = (cells / cells.sum() * 120).round().astype(int).clip(lower=12)
while alloc.sum() != 120:
    k = alloc.idxmax() if alloc.sum() > 120 else alloc.idxmin(); alloc[k] += -1 if alloc.sum() > 120 else 1
picks = []
for (per, y), n in alloc.items():
    pool = g1[(g1.period == per) & (g1.y == y)]; picks.append(pool.sample(min(n, len(pool)), random_state=int(rng.integers(0, 1e9))))
lab = pd.concat(picks); lab["stratum"] = lab.period + "|" + lab.y.map({1: "disposed", 0: "retained"})
# 30 post-reform filings (listed parents preferred), not already drawn
post = [rn for rn, r in dd.items() if rn[:8] >= "20221001" and r["type"] in ("carve_out", "mixed") and rn not in set(lab.rcept_no)]
post_listed = [rn for rn in post if dd[rn]["corp_cls"] in ("Y", "K")]; post_pick = list(rng.choice(post_listed, size=min(30, len(post_listed)), replace=False))
rows = []
for r in lab.itertuples(): rows.append({"rcept_no": r.rcept_no, "stratum": r.stratum, **meta(r.rcept_no)})
for rn in post_pick: rows.append({"rcept_no": rn, "stratum": "post-reform|unknown", **meta(rn)})
sheet = pd.DataFrame(rows); sheet.insert(0, "item_id", [f"C{i+1:03d}" for i in range(len(sheet))])
sheet = sheet.sample(frac=1, random_state=7).reset_index(drop=True); sheet["item_id"] = [f"C{i+1:03d}" for i in range(len(sheet))]   # shuffled so strata are not visible in order
# hidden key (model score, label) kept separately — never in the coder sheets
key = sheet[["item_id", "rcept_no", "stratum"]].merge(g1[["rcept_no", "y", "p_llm", "division_year"]], on="rcept_no", how="left"); key.to_csv(f"{OUT}/coder_sample_KEY_{STAMP}_DO_NOT_SHARE.csv", index=False)
CODE_COLS = ["purpose_sale", "purpose_efficiency", "purpose_specialization", "purpose_other", "listing_plan", "mentions_external_investor", "mentions_sale_or_buyer", "mentions_protection_measures", "disposal_prob_0_100", "most_likely_path", "confidence_1_3", "evidence_sentence", "minutes"]
public = sheet[["item_id", "corp_name", "board_date", "dart_url", "text_path", "text_rcept_no"]].copy()
for c in CODE_COLS: public[c] = ""
for coder in ("A", "B"): public.to_csv(f"{OUT}/coder_sample_{STAMP}_coder_{coder}.csv", index=False, encoding="utf-8-sig")
summary = {"n_items": int(len(sheet)), "labelled": int(len(lab)), "post_reform": len(post_pick), "allocation": {f"{k[0]}|{k[1]}": int(v) for k, v in alloc.items()}, "stratum_counts": sheet.stratum.value_counts().to_dict(), "text_available": int(sheet.text_path.notna().sum())}
print(json.dumps(summary, ensure_ascii=False, indent=1))
cb = f"""# 코드북 — 물적분할 공시 판독(사람 코더용), {STAMP}

목적: 두 언어모델이 공시 본문에서 읽어낸 "처분 신호"가 사람이 읽어도 같은지 확인한다(신뢰도·타당성). 코더는 **모델 점수와 실제 결과를 모른 채** 공시만 읽고 아래 항목을 채운다.

자료: `data/coding/coder_sample_{STAMP}_coder_A.csv`(코더 A), `..._coder_B.csv`(코더 B) — 같은 150건, 순서 섞음. 각 행의 `dart_url`을 열면 DART 원문(회사분할결정 / 주요사항보고서)이 보인다. `text_path`는 같은 공시의 텍스트 파일.
표본: 150건 = 라벨 있는 120건(2001–08 / 2009–16 / 2017+ × 처분 / 보유, 비례배분·칸당 최소 12) + 2022-10 이후 공시 30건. 코더에게는 층이 보이지 않는다.

## 읽는 범위
공시 본문 전체(분할의 목적·방법, 분할신설회사 개요·재무, 상장 계획, 주주보호방안, 기타 투자판단 사항). 첨부·외부 정보·회사 이름에서 떠오르는 기억은 쓰지 않는다. 회사의 이후 행적을 알고 있어도 **공시에 쓰인 것만** 근거로 삼는다.

## 항목(열 이름 → 값)
| 열 | 값 | 설명(공시에서 확인할 것) |
|---|---|---|
| purpose_sale | 0/1 | 분할 목적에 매각·처분·지분 매각·외부 자본 유치가 들어 있는가 (Kang & Lee 2025b의 'Purpose: Sale') |
| purpose_efficiency | 0/1 | 경영 효율·비용 절감·구조조정이 목적으로 적혔는가 ('Purpose: Efficiency') |
| purpose_specialization | 0/1 | 사업 전문화·집중·독립경영이 목적으로 적혔는가 ('Purpose: Specialization') |
| purpose_other | 0/1 | 위 셋에 들지 않는 목적(지주회사 전환, 규제 대응, 회생 등) |
| listing_plan | none / plan / no_listing | 신설회사 상장 계획: 언급 없음 / 상장(예비심사) 계획·검토 명시 / 상장하지 않겟다는 명시(기간 포함) |
| mentions_external_investor | 0/1 | 외부 투자자·전략적 투자자·투자 유치 언급 |
| mentions_sale_or_buyer | 0/1 | 신설회사 지분의 매각·양도·매수인 언급(그룹 내 이전 포함) |
| mentions_protection_measures | 0/1 | 주주보호방안(비상장 유지, 상장 시 주총 결의, 배당, 매수청구권 안내 등) 언급 |
| disposal_prob_0_100 | 0–100 | **코더의 예측**: 분할 뒤 3–5년 안에 모회사가 신설회사 지분 100%를 유지하지 **않을**(일부·전부 매각, 상장, 그룹 내 이전) 확률 |
| most_likely_path | retain / ipo / sale_to_third_party / partial_stake_sale_or_investor / intragroup_transfer_or_merger | 가장 가능성 높은 경로 하나 |
| confidence_1_3 | 1/2/3 | 자신의 판단 확신(1 낮음, 3 높음) |
| evidence_sentence | 문장 | 판단의 근거가 된 공시 문장 1–2개를 **그대로** 복사 |
| minutes | 숫자 | 이 건에 쓴 시간(분) |

## 규칙
1. 한 건에 10–15분을 넘기지 않는다. 모르면 disposal_prob 50, confidence 1.
2. 두 코더는 서로 상의하지 않는다. 전부 끝낸 뒤 κ·ICC를 계산하고, 불일치 건만 제3자가 본다.
3. 공시가 둘 이상(정정 포함)인 회사는 `text_rcept_no`의 공시만 읽는다.
4. 2022-10 이후 공시에는 '물적분할의 경우 주주보호방안' 항목이 있다 — 그 내용을 mentions_protection_measures와 listing_plan에 반영한다.
5. 열을 비워 두지 않는다(해당 없음은 0 또는 none).

## 분석 계획(코딩 뒤, `code/36`)
- 코더–코더: 이진 항목 Cohen's κ, disposal_prob ICC(2,1); 코더–모델: 같은 지표.
- 라벨 120건: 코더 disposal_prob의 AUC vs 모델 신호의 AUC(쌍 부트스트랩).
- K&L형 목적 더미(손 코딩) vs 모델 추출(판정 다수결) 일치율 — 27번 내포 모형의 M1·M2를 손 코딩 더미로 재추정.
- 2022-10 이후 30건: 코더와 모델의 처분 확률 분포 비교(라벨 없음).
"""
open(f"{P}/docs/CODEBOOK_disposal_signal_{STAMP}.md", "w").write(cb)
json.dump(summary, open(f"{OUT}/coder_sample_{STAMP}_summary.json", "w"), ensure_ascii=False, indent=1)
print(f"saved {OUT}/coder_sample_{STAMP}_coder_A.csv, _coder_B.csv, KEY (do not share), docs/CODEBOOK_disposal_signal_{STAMP}.md")
