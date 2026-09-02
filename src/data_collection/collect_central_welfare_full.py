"""
한국사회보장정보원_중앙부처복지서비스 API 목록조회 전체 수집.

- 목록조회(callTp=L)만 수집한다. 상세조회(자격조건 원문)는 이후 후보 추출 단계에서
  필요한 서비스에 한해 별도로 호출한다(여기서는 전체 상세조회를 수행하지 않는다).
- numOfRows 최대값 500이 공식 Swagger 명세에 명시되어 있고, 이전 검증에서
  totalCount=461로 확인되어 1페이지로 전체 수집이 가능하다. 다만 이 스크립트는
  totalCount가 numOfRows를 넘는 경우에도 안전하게 동작하도록 페이지네이션 루프로 작성한다.
- API 원문 응답(<wantedList> 전체)을 페이지 단위로 그대로 보존해 저장한다. 개별
  <servList> 항목의 내용은 전혀 가공하지 않는다.
"""
import json
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

BASE_URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001"
LIST_ENDPOINT = f"{BASE_URL}/NationalWelfarelistV001"

RAW_DIR = ROOT_DIR / "data" / "raw"
NUM_OF_ROWS = 500
MAX_RETRY = 2
SLEEP_BETWEEN_CALLS = 0.4


def get_api_key() -> str:
    key = os.getenv("CENTRAL_WELFARE_API_KEY", "").strip()
    if not key:
        print("[중단] .env 파일의 CENTRAL_WELFARE_API_KEY 값이 비어 있습니다.")
        sys.exit(1)
    return key


def fetch_page(service_key: str, page_no: int) -> Optional[tuple]:
    """(root, raw_text) 반환. 실패 시 None."""
    params = {
        "serviceKey": service_key,
        "callTp": "L",
        "pageNo": str(page_no),
        "numOfRows": str(NUM_OF_ROWS),
        "srchKeyCode": "003",
    }
    for attempt in range(1, MAX_RETRY + 2):
        try:
            resp = requests.get(LIST_ENDPOINT, params=params, timeout=30)
        except requests.RequestException as e:
            print(f"  [page {page_no}] 요청 예외 (시도 {attempt}): {e}")
            continue
        if resp.status_code != 200:
            print(f"  [page {page_no}] HTTP {resp.status_code} (시도 {attempt})")
            continue
        try:
            root = ET.fromstring(resp.text)
        except ET.ParseError as e:
            print(f"  [page {page_no}] XML 파싱 실패 (시도 {attempt}): {e}")
            continue
        if root.tag == "OpenAPI_ServiceResponse":
            print(f"  [page {page_no}] 서비스 오류 응답 (시도 {attempt}): "
                  f"{root.findtext('.//returnAuthMsg')}")
            continue
        result_code = root.findtext(".//resultCode")
        if result_code != "0":
            print(f"  [page {page_no}] resultCode={result_code} "
                  f"resultMessage={root.findtext('.//resultMessage')} (시도 {attempt})")
            continue
        return root, resp.text
    return None


def main():
    service_key = get_api_key()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    collected_at = datetime.now(timezone.utc).astimezone().isoformat()

    call_count = 0
    failed_pages = []
    page_raw_texts = []
    all_serv_ids = []
    total_count_reported = None

    page_no = 1
    while True:
        print(f"중앙부처복지서비스 목록조회 - page {page_no} (numOfRows={NUM_OF_ROWS}) 호출 중...")
        result = fetch_page(service_key, page_no)
        call_count += 1
        if result is None:
            print(f"  [page {page_no}] 최종 실패. 실패 페이지로 기록하고 중단합니다.")
            failed_pages.append(page_no)
            break

        root, raw_text = result
        page_raw_texts.append((page_no, raw_text))
        total_count_reported = root.findtext(".//totalCount")
        items = root.findall(".//servList")
        for item in items:
            all_serv_ids.append(item.findtext("servId"))

        print(f"  [page {page_no}] 성공. 이번 페이지 {len(items)}건, totalCount={total_count_reported}")

        if not items:
            break
        if total_count_reported and len(all_serv_ids) >= int(total_count_reported):
            break

        page_no += 1
        time.sleep(SLEEP_BETWEEN_CALLS)

    # 원문 페이지들을 하나의 파일로 보존 저장 (각 <wantedList> 내부는 원문 그대로)
    out_path = RAW_DIR / "central_welfare_all.xml"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(
            f'<collected_pages source="central_welfare" endpoint="{LIST_ENDPOINT}" '
            f'collected_at="{collected_at}" total_pages="{len(page_raw_texts)}">\n'
        )
        for page_no_written, raw_text in page_raw_texts:
            # XML 선언부를 제거하고 본문만 그대로 삽입 (내용은 무가공)
            body = raw_text.split("?>", 1)[-1].strip() if raw_text.strip().startswith("<?xml") else raw_text.strip()
            f.write(f"<!-- page {page_no_written} -->\n")
            f.write(body + "\n")
        f.write("</collected_pages>\n")
    print(f"[저장] {out_path}")

    duplicate_ids = sorted({sid for sid in all_serv_ids if all_serv_ids.count(sid) > 1})
    unique_count = len(set(all_serv_ids))

    log = {
        "source": "central_welfare",
        "endpoint": LIST_ENDPOINT,
        "collected_at": collected_at,
        "call_count": call_count,
        "num_of_rows_per_call": NUM_OF_ROWS,
        "total_count_reported_by_api": int(total_count_reported) if total_count_reported else None,
        "total_items_collected": len(all_serv_ids),
        "unique_serv_id_count": unique_count,
        "duplicate_serv_ids": duplicate_ids,
        "failed_pages": failed_pages,
        "missing_count": (
            int(total_count_reported) - unique_count if total_count_reported else None
        ),
    }
    log_path = RAW_DIR / "central_welfare_collection_log.json"
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[저장] {log_path}")

    print("\n=== 수집 요약 ===")
    print(json.dumps(log, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
