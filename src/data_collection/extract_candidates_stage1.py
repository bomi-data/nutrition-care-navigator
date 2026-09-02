"""
1단계: data/raw/{central,local}_welfare_all.xml (목록조회 원문)에서
키워드 기반으로 넓게 후보를 스크리닝한다. API를 추가로 호출하지 않는다.

검색 대상 필드(목록조회에 실제로 존재하는 자연어 필드만 사용):
  - servNm   (서비스명)
  - servDgst (서비스 요약 — 지원대상/선정기준/지원내용의 축약 설명에 해당)

지원대상/선정기준/지원내용/신청방법 "원문"은 상세조회에만 존재하므로 이 단계에서는
다루지 않는다(2단계 detail 보강 스크립트에서 후보에 한해 상세조회로 채운다).

각 매치에 대해 matched_keyword/matched_field를 기록하고, lifeArray(중앙)/lifeNmArray(지자체)
값만으로 1차 senior_relevance 판단(가능한 범위 내에서만)과 exclusion_reason 후보를 남긴다.
이 판단은 최종 확정이 아니라 사람이 검토할 실마리일 뿐이다.
"""
import csv
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

KEYWORDS = [
    "영양", "식사", "급식", "도시락", "밑반찬", "반찬", "식생활", "결식", "식품",
    "방문건강", "건강관리", "통합돌봄", "통합지원", "노인돌봄", "퇴원", "재가",
]

# 이 값만 있고 다른 생애주기가 전혀 없으면 "고령자와 무관"으로 잠정 표시할 생애주기 값
INFANT_CHILD_YOUTH_MATERNAL_ONLY = {"영유아", "아동", "청소년", "임신 · 출산", "임신·출산"}


def find_keyword_matches(text, keywords):
    if not text:
        return []
    return [kw for kw in keywords if kw in text]


def classify_life_stage(life_str):
    """lifeArray/lifeNmArray 원문 문자열을 보고 1차 senior_relevance 힌트를 만든다."""
    if not life_str:
        return "unknown", None
    stages = [s.strip() for s in life_str.split(",") if s.strip()]
    stage_set = set(stages)
    if "노년" in stage_set:
        return "likely_senior_relevant", None
    if stage_set and stage_set.issubset(INFANT_CHILD_YOUTH_MATERNAL_ONLY):
        return "likely_not_senior", f"lifeArray가 {life_str} 로만 구성되어 고령자 대상이 아닐 가능성"
    return "unknown", None


def process_central():
    tree = ET.parse(RAW_DIR / "central_welfare_all.xml")
    root = tree.getroot()
    rows = []
    for item in root.findall(".//servList"):
        serv_id = item.findtext("servId")
        serv_nm = item.findtext("servNm") or ""
        serv_dgst = item.findtext("servDgst") or ""
        life_arr = item.findtext("lifeArray") or ""

        matched = {}
        for field_name, text in (("servNm", serv_nm), ("servDgst", serv_dgst)):
            kws = find_keyword_matches(text, KEYWORDS)
            for kw in kws:
                matched.setdefault(kw, set()).add(field_name)

        if not matched:
            continue

        senior_relevance, exclusion_reason = classify_life_stage(life_arr)

        for kw, fields in matched.items():
            rows.append({
                "service_id": serv_id,
                "source_api": "central",
                "service_name": serv_nm,
                "sido": "",
                "sigungu": "",
                "servDgst": serv_dgst,
                "lifeArray": life_arr,
                "matched_keyword": kw,
                "matched_field": "+".join(sorted(fields)),
                "senior_relevance": senior_relevance,
                "exclusion_reason": exclusion_reason or "",
            })
    return rows


def process_local():
    tree = ET.parse(RAW_DIR / "local_welfare_all.xml")
    root = tree.getroot()
    rows = []
    for item in root.findall(".//servList"):
        serv_id = item.findtext("servId")
        serv_nm = item.findtext("servNm") or ""
        serv_dgst = item.findtext("servDgst") or ""
        life_arr = item.findtext("lifeNmArray") or ""
        ctpv_nm = item.findtext("ctpvNm") or ""
        sgg_nm = item.findtext("sggNm") or ""

        matched = {}
        for field_name, text in (("servNm", serv_nm), ("servDgst", serv_dgst)):
            kws = find_keyword_matches(text, KEYWORDS)
            for kw in kws:
                matched.setdefault(kw, set()).add(field_name)

        if not matched:
            continue

        senior_relevance, exclusion_reason = classify_life_stage(life_arr)

        for kw, fields in matched.items():
            rows.append({
                "service_id": serv_id,
                "source_api": "local",
                "service_name": serv_nm,
                "sido": ctpv_nm,
                "sigungu": sgg_nm,
                "servDgst": serv_dgst,
                "lifeArray": life_arr,
                "matched_keyword": kw,
                "matched_field": "+".join(sorted(fields)),
                "senior_relevance": senior_relevance,
                "exclusion_reason": exclusion_reason or "",
            })
    return rows


def main():
    central_rows = process_central()
    local_rows = process_local()
    all_rows = central_rows + local_rows

    # service_id 기준으로 dedup해서 "고유 후보 서비스" 통계도 함께 낸다
    central_unique = {r["service_id"] for r in central_rows}
    local_unique = {r["service_id"] for r in local_rows}

    print(f"[중앙부처] 키워드 매치(행 기준, 중복 키워드 포함): {len(central_rows)}건 / 고유 서비스: {len(central_unique)}건")
    print(f"[지자체]   키워드 매치(행 기준, 중복 키워드 포함): {len(local_rows)}건 / 고유 서비스: {len(local_unique)}건")

    likely_senior = sum(1 for r in all_rows if r["senior_relevance"] == "likely_senior_relevant")
    likely_not_senior = sum(1 for r in all_rows if r["senior_relevance"] == "likely_not_senior")
    unknown = sum(1 for r in all_rows if r["senior_relevance"] == "unknown")
    print(f"\nsenior_relevance 1차 분류(행 기준): likely_senior_relevant={likely_senior}, "
          f"likely_not_senior={likely_not_senior}, unknown={unknown}")

    out_path = PROCESSED_DIR / "candidates_stage1_raw.csv"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()) if all_rows else [])
        w.writeheader()
        w.writerows(all_rows)
    print(f"\n[저장] {out_path} ({len(all_rows)}행, service_id당 매치 키워드별로 여러 행일 수 있음)")


if __name__ == "__main__":
    main()
