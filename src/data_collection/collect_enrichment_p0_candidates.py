"""
P0 데이터 보강 1차 수집 (docs/data_enrichment_plan.md, 이번 단계 지시사항 기준).

기존 collect_local_welfare_full.py/collect_candidate_details.py와 같은
지자체복지서비스 API(LcgvWelfarelist/LcgvWelfaredetailed)를 재사용한다. 새 API를 찾지
않는다. 이번 단계 목적은 오직 "수집 + 후보 저장"이며, 다음은 하지 않는다:

  - data/processed/welfare_services_recommendation_ready.csv 수정/병합
  - senior_relation/nutrition_relevance/service_type_primary 최종 판정
  - classification_criteria.md v2 최종 적용
  - INCLUDE/EXCLUDE 확정

두 갈래로 수집한다:
  A) P0 지역 목록조회(ctpvNm/sggNm) -- 화성시/천안시/세종/울산 전체 목록을 가져와
     로컬에서 후보 keyword로 1차 screening만 한다(최종 판정 아님).
  B) community_care 관련 searchWrd 전국 검색 -- 지역 무관하게 신규 후보를 찾는다.

산출물:
  data/raw/enrichment/*.xml          -- API 원문 응답 보존(기존 raw 파일은 건드리지 않음)
  data/processed/welfare_services_enrichment_candidates.csv -- 검토 전 후보(COLLECTED만)
"""

from __future__ import annotations

import csv
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

BASE_URL = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations"
LIST_ENDPOINT = f"{BASE_URL}/LcgvWelfarelist"
DETAIL_ENDPOINT = f"{BASE_URL}/LcgvWelfaredetailed"

RAW_DIR = ROOT_DIR / "data" / "raw" / "enrichment"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
EXISTING_CSV = PROCESSED_DIR / "welfare_services_recommendation_ready.csv"
OUT_CSV = PROCESSED_DIR / "welfare_services_enrichment_candidates.csv"

SLEEP_BETWEEN_CALLS = 0.4

# 지침 §3의 후보 발굴용 keyword(최종 판정 기준 아님, 1차 screening만)
CANDIDATE_KEYWORDS = [
    "도시락", "식사", "식사지원", "반찬", "밑반찬", "급식", "무료급식", "재가", "방문",
    "돌봄", "통합돌봄", "지역돌봄", "식생활", "영양", "식품", "식재료", "바우처",
    "장애인", "노인", "어르신",
]

# 오탐이 특히 많다고 이미 검증된(recommendation_engine_v1_2_validation.md §8,
# data_enrichment_plan.md §7) 범용 keyword -- 제거하지 않고 낮은 신뢰도로만 표시
LOW_CONFIDENCE_KEYWORDS = {"재가", "건강", "통합지원", "식품", "바우처", "돌봄", "노인", "어르신", "장애인"}

# 실제 음식/영양 핵심어(있으면 preliminary_relevance를 끌어올림)
CORE_FOOD_KEYWORDS = {"도시락", "식사", "식사지원", "반찬", "밑반찬", "급식", "무료급식", "식생활", "영양", "식재료"}

P0_REGIONS = [
    ("경기도", "화성시"),
    ("충청남도", "천안시"),
    ("세종특별자치시", None),
    ("울산광역시", None),
]

COMMUNITY_CARE_SEARCH_TERMS = [
    "통합돌봄", "재가돌봄", "방문돌봄", "지역사회 통합지원", "퇴원연계", "식사연계",
    "일상생활지원", "돌봄SOS",
]

ENDED_SIGNALS = ["폐지", "신청기간 종료", "한시사업", "종료되었", "사업 종료", "신규신청 불가"]

LOG_LINES: list[str] = []


def log(msg: str) -> None:
    print(msg)
    LOG_LINES.append(msg)


def get_key() -> str:
    key = os.getenv("LOCAL_WELFARE_API_KEY", "").strip()
    if not key:
        print("[중단] LOCAL_WELFARE_API_KEY가 비어 있습니다.")
        sys.exit(1)
    return key


def call_list(service_key: str, params_no_key: dict, raw_filename: str) -> list[ET.Element]:
    """목록조회 1페이지(numOfRows<=100이면 대부분 1페이지로 충분한 소규모 쿼리 전용).
    호출 로그(엔드포인트/파라미터/상태/건수)를 남기고, API key는 로그에 남기지 않는다."""
    params = {"serviceKey": service_key, "pageNo": "1", "numOfRows": "200", **params_no_key}
    log(f"[API 호출] {LIST_ENDPOINT} params={params_no_key}")
    try:
        resp = requests.get(LIST_ENDPOINT, params=params, timeout=30)
    except requests.RequestException as e:
        log(f"  -> 요청 예외: {e}")
        return []
    log(f"  -> HTTP {resp.status_code}")
    if resp.status_code != 200:
        return []

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / raw_filename).write_text(resp.text, encoding="utf-8")

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        log(f"  -> XML 파싱 실패: {e}")
        return []
    if root.tag == "OpenAPI_ServiceResponse":
        log(f"  -> 서비스 오류: {root.findtext('.//returnAuthMsg')}")
        return []
    result_code = root.findtext(".//resultCode")
    total_count = root.findtext(".//totalCount")
    items = root.findall(".//servList")
    log(f"  -> resultCode={result_code} totalCount={total_count} 반환건수={len(items)}")
    return items


def call_detail(service_key: str, serv_id: str) -> Optional[dict]:
    params = {"serviceKey": service_key, "servId": serv_id}
    try:
        resp = requests.get(DETAIL_ENDPOINT, params=params, timeout=30)
    except requests.RequestException as e:
        log(f"  [상세조회 실패] {serv_id}: 요청 예외 {e}")
        return None
    if resp.status_code != 200:
        log(f"  [상세조회 실패] {serv_id}: HTTP {resp.status_code}")
        return None

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"detail_{serv_id}.xml").write_text(resp.text, encoding="utf-8")

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        log(f"  [상세조회 실패] {serv_id}: XML 파싱 실패 {e}")
        return None
    if root.tag == "OpenAPI_ServiceResponse":
        log(f"  [상세조회 실패] {serv_id}: 서비스 오류 {root.findtext('.//returnAuthMsg')}")
        return None
    if root.findtext(".//resultCode") != "0":
        log(f"  [상세조회 실패] {serv_id}: resultCode={root.findtext('.//resultCode')}")
        return None

    target = root.findtext(".//sprtTrgtCn") or ""
    criteria = root.findtext(".//slctCritCn") or ""
    support = root.findtext(".//alwServCn") or ""
    apply_nm = root.findtext(".//aplyMtdNm") or ""
    apply_cn = root.findtext(".//aplyMtdCn") or ""
    application = f"[{apply_nm}] {apply_cn}".strip()

    contact_parts = []
    for node in root.findall(".//inqplCtadrList"):
        nm = node.findtext("wlfareInfoReldNm") or ""
        cn = node.findtext("wlfareInfoReldCn") or ""
        if nm or cn:
            contact_parts.append(f"{nm}: {cn}".strip())
    contact = " | ".join(contact_parts)

    return {
        "target_original": target,
        "criteria_original": criteria,
        "support_original": support,
        "application_original": application,
        "contact": contact,
    }


def find_matched_keywords(text: str) -> list[str]:
    if not text:
        return []
    return [kw for kw in CANDIDATE_KEYWORDS if kw in text]


def preliminary_relevance(matched: list[str], text: str) -> str:
    if not matched:
        return "UNKNOWN"
    core_hits = [k for k in matched if k in CORE_FOOD_KEYWORDS]
    senior_signal = ("노인" in text) or ("어르신" in text) or ("고령" in text)
    if core_hits and senior_signal:
        return "HIGH"
    if core_hits or (senior_signal and any(k in matched for k in ("재가", "방문", "돌봄"))):
        return "MEDIUM"
    return "LOW"


def guess_active_status(text: str) -> str:
    if any(sig in text for sig in ENDED_SIGNALS):
        return "ENDED"
    if not text.strip():
        return "UNKNOWN"
    return "ACTIVE"


def load_existing_ids_and_names() -> tuple[set, list[tuple]]:
    ids = set()
    name_region = []
    with open(EXISTING_CSV, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ids.add(row["service_id"])
            name_region.append((row["service_name"], row.get("sido") or "", row.get("sigungu") or ""))
    return ids, name_region


def duplicate_status(serv_id: str, serv_nm: str, sido: str, sigungu: str, existing_ids: set, existing_name_region: list) -> str:
    if serv_id in existing_ids:
        return "EXACT_SERVICE_ID"
    for nm, s_sido, s_sigungu in existing_name_region:
        if nm and serv_nm and (nm in serv_nm or serv_nm in nm) and (sido == s_sido):
            return "POSSIBLE_NAME_REGION_DUPLICATE"
    return "NONE"


def main():
    service_key = get_key()
    existing_ids, existing_name_region = load_existing_ids_and_names()
    log(f"기존 최종 데이터: {len(existing_ids)}건 (무수정, 읽기 전용)")

    collected_at = datetime.now(timezone.utc).astimezone().isoformat()

    # candidate accumulation: service_id -> record dict
    candidates: dict[str, dict] = {}

    # --- A) P0 지역 목록조회 ---
    for sido, sigungu in P0_REGIONS:
        params = {"ctpvNm": sido}
        if sigungu:
            params["sggNm"] = sigungu
        raw_name = f"list_{sido}_{sigungu or 'all'}.xml".replace("/", "_")
        items = call_list(service_key, params, raw_name)
        time.sleep(SLEEP_BETWEEN_CALLS)

        for item in items:
            serv_id = item.findtext("servId")
            serv_nm = item.findtext("servNm") or ""
            serv_dgst = item.findtext("servDgst") or ""
            ctpv = item.findtext("ctpvNm") or sido
            sgg = item.findtext("sggNm") or (sigungu or "")
            text = serv_nm + " " + serv_dgst
            matched = find_matched_keywords(text)
            if not matched:
                continue  # 후보 발굴 목적 -- 키워드 매치 없는 항목은 저장하지 않음(§3)

            candidates.setdefault(serv_id, {
                "source_api": "local_welfare_api",
                "collected_at": collected_at,
                "service_id": serv_id,
                "service_name": serv_nm,
                "sido": ctpv,
                "sigungu": sgg,
                "servDgst": serv_dgst,
                "matched_keywords": set(),
                "collection_reason": f"P0 지역 목록조회({sido}/{sigungu or '전역'})",
                "source_type": "API",
                "source_reference": LIST_ENDPOINT,
            })
            candidates[serv_id]["matched_keywords"] |= set(matched)

        region_hit = sum(1 for c in candidates.values() if c["collection_reason"].startswith(f"P0 지역 목록조회({sido}"))
        log(f"  [{sido}/{sigungu or '전역'}] 원본 {len(items)}건 중 keyword 매치 후보 {region_hit}건")

    # --- B) community_care 전국 searchWrd 검색 ---
    for term in COMMUNITY_CARE_SEARCH_TERMS:
        raw_name = f"search_{term}.xml".replace(" ", "_")
        items = call_list(service_key, {"searchWrd": term}, raw_name)
        time.sleep(SLEEP_BETWEEN_CALLS)

        new_count = 0
        for item in items:
            serv_id = item.findtext("servId")
            serv_nm = item.findtext("servNm") or ""
            serv_dgst = item.findtext("servDgst") or ""
            ctpv = item.findtext("ctpvNm") or ""
            sgg = item.findtext("sggNm") or ""
            text = serv_nm + " " + serv_dgst
            matched = find_matched_keywords(text) or [term]

            if serv_id not in candidates:
                new_count += 1
            candidates.setdefault(serv_id, {
                "source_api": "local_welfare_api",
                "collected_at": collected_at,
                "service_id": serv_id,
                "service_name": serv_nm,
                "sido": ctpv,
                "sigungu": sgg,
                "servDgst": serv_dgst,
                "matched_keywords": set(),
                "collection_reason": f"community_care 전국 검색(searchWrd={term})",
                "source_type": "API",
                "source_reference": LIST_ENDPOINT,
            })
            candidates[serv_id]["matched_keywords"] |= set(matched)
        log(f"  [searchWrd={term}] 반환 {len(items)}건 중 candidate 목록에 처음 추가된 service_id {new_count}건 (기존 85건 포함 여부는 duplicate_status로 별도 표시)")

    log(f"\n1차 후보(중복 제거 전, 기존 85건 겹침 포함) 총 {len(candidates)}건")

    # --- 상세조회(원문 확보) ---
    detail_fail = 0
    rows_out = []
    for i, (serv_id, cand) in enumerate(candidates.items(), start=1):
        detail = call_detail(service_key, serv_id)
        time.sleep(SLEEP_BETWEEN_CALLS)
        if detail is None:
            detail_fail += 1
            detail = {k: "" for k in ("target_original", "criteria_original", "support_original", "application_original", "contact")}

        full_text_for_status = " ".join([cand["servDgst"], detail["target_original"], detail["criteria_original"], detail["support_original"]])
        dup = duplicate_status(serv_id, cand["service_name"], cand["sido"], cand["sigungu"], existing_ids, existing_name_region)
        matched_list = sorted(cand["matched_keywords"])
        rel = preliminary_relevance(matched_list, full_text_for_status)

        rows_out.append({
            "source_api": cand["source_api"],
            "collected_at": cand["collected_at"],
            "service_id": serv_id,
            "service_name": cand["service_name"],
            "region": f"{cand['sido']} {cand['sigungu']}".strip(),
            "sido": cand["sido"],
            "sigungu": cand["sigungu"],
            "target_original": detail["target_original"],
            "criteria_original": detail["criteria_original"],
            "support_original": detail["support_original"],
            "application_original": detail["application_original"],
            "matched_keywords": "|".join(matched_list),
            "collection_reason": cand["collection_reason"],
            "source_type": cand["source_type"],
            "source_reference": cand["source_reference"],
            "preliminary_category": "meal_support/community_care 후보(미확정)",
            "preliminary_relevance": rel,
            "review_status": "COLLECTED",
            "duplicate_status": dup,
            "active_status": guess_active_status(full_text_for_status),
            "manual_review_required": "TRUE" if rel in ("LOW", "UNKNOWN") else "FALSE",
        })
        if i % 10 == 0:
            log(f"  상세조회 진행 {i}/{len(candidates)}")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows_out[0].keys()) if rows_out else []
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)
    log(f"\n[저장] {OUT_CSV} ({len(rows_out)}행)")
    log(f"상세조회 실패: {detail_fail}건")

    log_path = RAW_DIR / "collection_log.txt"
    log_path.write_text("\n".join(LOG_LINES), encoding="utf-8")
    log(f"[저장] {log_path}")


if __name__ == "__main__":
    main()
