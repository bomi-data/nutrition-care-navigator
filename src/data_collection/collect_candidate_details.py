"""
2단계: 1단계(extract_candidates_stage1.py)에서 나온 후보 service_id들에 대해서만
상세조회 API를 호출해 지원대상/선정기준/지원내용/신청방법/문의처 원문을 채운다.

중앙부처 API는 개발계정 기준 100건/일 제한이 있고, 지자체 API는 1,000건/일 제한이
있음을 이전 검증에서 확인했다. 이번 1차 후보(중앙 19건, 지자체 338건, 총 357건)는
두 한도 안에 충분히 들어오므로 전량 상세조회한다.

산출물: data/processed/welfare_candidates.csv
"""
import csv
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

PROCESSED_DIR = ROOT_DIR / "data" / "processed"
STAGE1_PATH = PROCESSED_DIR / "candidates_stage1_raw.csv"
OUT_PATH = PROCESSED_DIR / "welfare_candidates.csv"

CENTRAL_DETAIL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfaredetailedV001"
LOCAL_DETAIL = "https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations/LcgvWelfaredetailed"

CENTRAL_KEY = os.getenv("CENTRAL_WELFARE_API_KEY", "").strip()
LOCAL_KEY = os.getenv("LOCAL_WELFARE_API_KEY", "").strip()

SLEEP_BETWEEN_CALLS = 0.3
FIELDNAMES = [
    "service_id", "source_api", "service_name", "sido", "sigungu",
    "target_original", "criteria_original", "support_original",
    "application_original", "contact",
    "matched_keyword", "matched_field", "senior_relevance", "exclusion_reason",
]


def load_stage1():
    with open(STAGE1_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    grouped = {}
    for r in rows:
        key = (r["service_id"], r["source_api"])
        g = grouped.setdefault(key, {
            "service_id": r["service_id"],
            "source_api": r["source_api"],
            "service_name": r["service_name"],
            "sido": r["sido"],
            "sigungu": r["sigungu"],
            "matched_keywords": set(),
            "matched_fields": set(),
            "senior_relevance": r["senior_relevance"],
            "exclusion_reason": r["exclusion_reason"],
        })
        g["matched_keywords"].add(r["matched_keyword"])
        g["matched_fields"].add(r["matched_field"])
    return grouped


def fetch_central_detail(serv_id):
    params = {"serviceKey": CENTRAL_KEY, "callTp": "D", "servId": serv_id}
    try:
        resp = requests.get(CENTRAL_DETAIL, params=params, timeout=20)
    except requests.RequestException as e:
        return None, f"요청 예외: {e}"
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        return None, f"XML 파싱 실패: {e}"
    if root.tag == "OpenAPI_ServiceResponse":
        return None, f"서비스 오류: {root.findtext('.//returnAuthMsg')}"
    if root.findtext(".//resultCode") != "0":
        return None, f"resultCode={root.findtext('.//resultCode')}"

    target = root.findtext(".//tgtrDtlCn") or ""
    criteria = root.findtext(".//slctCritCn") or ""
    support = root.findtext(".//alwServCn") or ""

    apply_parts = []
    for node in root.findall(".//applmetList"):
        nm = node.findtext("servSeDetailNm") or ""
        link = node.findtext("servSeDetailLink") or ""
        if nm or link:
            apply_parts.append(f"[{nm}] {link}".strip())
    application = " | ".join(apply_parts)

    contact_parts = []
    for node in root.findall(".//inqplCtadrList"):
        nm = node.findtext("servSeDetailNm") or ""
        link = node.findtext("servSeDetailLink") or ""
        if nm or link:
            contact_parts.append(f"{nm}: {link}".strip())
    contact = " | ".join(contact_parts)

    return {
        "target_original": target,
        "criteria_original": criteria,
        "support_original": support,
        "application_original": application,
        "contact": contact,
    }, None


def fetch_local_detail(serv_id):
    params = {"serviceKey": LOCAL_KEY, "servId": serv_id}
    try:
        resp = requests.get(LOCAL_DETAIL, params=params, timeout=20)
    except requests.RequestException as e:
        return None, f"요청 예외: {e}"
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        return None, f"XML 파싱 실패: {e}"
    if root.tag == "OpenAPI_ServiceResponse":
        return None, f"서비스 오류: {root.findtext('.//returnAuthMsg')}"
    if root.findtext(".//resultCode") != "0":
        return None, f"resultCode={root.findtext('.//resultCode')}"

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
    }, None


def main():
    if not STAGE1_PATH.exists():
        print(f"[중단] {STAGE1_PATH} 가 없습니다. extract_candidates_stage1.py를 먼저 실행하세요.")
        sys.exit(1)
    if not CENTRAL_KEY or not LOCAL_KEY:
        print("[중단] .env의 CENTRAL_WELFARE_API_KEY / LOCAL_WELFARE_API_KEY 중 비어 있는 값이 있습니다.")
        sys.exit(1)

    grouped = load_stage1()
    central_ids = [k for k in grouped if k[1] == "central"]
    local_ids = [k for k in grouped if k[1] == "local"]
    print(f"상세조회 대상: 중앙부처 {len(central_ids)}건, 지자체 {len(local_ids)}건, 총 {len(grouped)}건")

    out_rows = []
    detail_fail_count = 0

    for i, (key, g) in enumerate(grouped.items(), start=1):
        serv_id, source = key
        if source == "central":
            detail, err = fetch_central_detail(serv_id)
        else:
            detail, err = fetch_local_detail(serv_id)

        if detail is None:
            detail_fail_count += 1
            print(f"  [{i}/{len(grouped)}] {source} {serv_id} 상세조회 실패: {err}")
            detail = {
                "target_original": "", "criteria_original": "", "support_original": "",
                "application_original": "", "contact": "",
            }
            exclusion_reason = (g["exclusion_reason"] + " | " if g["exclusion_reason"] else "") + f"상세조회 실패({err})"
        else:
            exclusion_reason = g["exclusion_reason"]

        out_rows.append({
            "service_id": g["service_id"],
            "source_api": g["source_api"],
            "service_name": g["service_name"],
            "sido": g["sido"],
            "sigungu": g["sigungu"],
            "target_original": detail["target_original"],
            "criteria_original": detail["criteria_original"],
            "support_original": detail["support_original"],
            "application_original": detail["application_original"],
            "contact": detail["contact"],
            "matched_keyword": ",".join(sorted(g["matched_keywords"])),
            "matched_field": ",".join(sorted(g["matched_fields"])),
            "senior_relevance": g["senior_relevance"],
            "exclusion_reason": exclusion_reason,
        })
        time.sleep(SLEEP_BETWEEN_CALLS)

    with open(OUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(out_rows)

    print(f"\n[저장] {OUT_PATH} ({len(out_rows)}행)")
    print(f"상세조회 실패: {detail_fail_count}건")


if __name__ == "__main__":
    main()
