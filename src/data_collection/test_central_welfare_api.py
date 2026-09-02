"""
한국사회보장정보원_중앙부처복지서비스 API 연결/구조 테스트.

공식 명세 (공공데이터포털 15090532 상세페이지에 내장된 Swagger 2.0 문서를 직접 파싱하여 확인, 2026-08-21):
  Base URL : https://apis.data.go.kr/B554287/NationalWelfareInformationsV001
  목록조회 : GET /NationalWelfarelistV001
             필수 파라미터: serviceKey, callTp(L=목록), pageNo, numOfRows, srchKeyCode
  상세조회 : GET /NationalWelfaredetailedV001
             필수 파라미터: serviceKey, callTp(D=상세), servId
  응답형식 : application/xml (Swagger 'produces'에 application/xml만 명시됨. JSON 미지원)

이 스크립트는 목록 5건 + 그중 1건 상세조회만 호출한다. 전체 데이터 수집은 하지 않는다.
API 인증키는 .env의 CENTRAL_WELFARE_API_KEY에서만 읽으며, 코드에 직접 작성하지 않는다.
"""
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

BASE_URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001"
LIST_ENDPOINT = f"{BASE_URL}/NationalWelfarelistV001"
DETAIL_ENDPOINT = f"{BASE_URL}/NationalWelfaredetailedV001"

RAW_DIR = ROOT_DIR / "data" / "raw"
SAMPLE_COUNT = 5


def get_api_key() -> str:
    key = os.getenv("CENTRAL_WELFARE_API_KEY", "").strip()
    if not key:
        print("[중단] .env 파일의 CENTRAL_WELFARE_API_KEY 값이 비어 있습니다.")
        print("       공공데이터포털(data.go.kr)에서 발급받은 인증키를 .env에 직접 입력한 뒤 다시 실행하세요.")
        sys.exit(1)
    return key


def check_service_error(root: ET.Element) -> bool:
    """공공데이터포털 표준 오류 응답(OpenAPI_ServiceResponse)인지 확인하고, 오류면 내용을 출력한다."""
    if root.tag == "OpenAPI_ServiceResponse":
        print("[오류] 공공데이터포털 표준 오류 응답(OpenAPI_ServiceResponse)을 받았습니다.")
        print(f"       errMsg          : {root.findtext('.//errMsg')}")
        print(f"       returnAuthMsg   : {root.findtext('.//returnAuthMsg')}")
        print(f"       returnReasonCode: {root.findtext('.//returnReasonCode')}")
        return True
    return False


def call(endpoint: str, params: dict, label: str) -> Optional[str]:
    print(f"\n--- {label} ---")
    print(f"URL   : {endpoint}")
    safe_params = {k: v for k, v in params.items() if k != "serviceKey"}
    print(f"params: {safe_params}  (serviceKey는 로그에 출력하지 않음)")

    try:
        resp = requests.get(endpoint, params=params, timeout=10)
    except requests.RequestException as e:
        print(f"[오류] 요청 자체가 실패했습니다: {e}")
        return None

    print(f"HTTP status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"[오류] HTTP 상태코드가 200이 아닙니다. 응답 본문 앞부분:\n{resp.text[:500]}")
        return None

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        print(f"[오류] XML 파싱 실패: {e}")
        print(f"응답 본문 앞부분:\n{resp.text[:500]}")
        return None

    if check_service_error(root):
        return None

    print(f"resultCode   : {root.findtext('.//resultCode')}")
    print(f"resultMessage: {root.findtext('.//resultMessage')}")
    return resp.text


def main():
    service_key = get_api_key()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # 1) 목록조회 (5건, 검색어 미지정 — 구조 확인 목적)
    list_params = {
        "serviceKey": service_key,
        "callTp": "L",
        "pageNo": "1",
        "numOfRows": str(SAMPLE_COUNT),
        "srchKeyCode": "003",  # 001 제목 / 002 내용 / 003 제목+내용 (필수 파라미터)
    }
    list_xml = call(LIST_ENDPOINT, list_params, "중앙부처복지서비스 목록조회")
    if list_xml is None:
        print("\n목록조회에 실패하여 상세조회로 진행하지 않습니다.")
        sys.exit(1)

    list_path = RAW_DIR / "central_welfare_sample.xml"
    list_path.write_text(list_xml, encoding="utf-8")
    print(f"[저장] {list_path}")

    root = ET.fromstring(list_xml)
    items = root.findall(".//servList")
    print(f"totalCount    : {root.findtext('.//totalCount')}")
    print(f"이번 응답 건수 : {len(items)}")
    for item in items:
        print(f"  - servId={item.findtext('servId')} servNm={item.findtext('servNm')}")

    if not items:
        print("\n목록에 항목이 없어 상세조회로 진행하지 않습니다.")
        return

    # 2) 상세조회 (목록의 첫 번째 servId 사용)
    first_serv_id = items[0].findtext("servId")
    detail_params = {
        "serviceKey": service_key,
        "callTp": "D",
        "servId": first_serv_id,
    }
    detail_xml = call(
        DETAIL_ENDPOINT, detail_params, f"중앙부처복지서비스 상세조회 (servId={first_serv_id})"
    )
    if detail_xml is None:
        return

    detail_path = RAW_DIR / "central_welfare_detail_sample.xml"
    detail_path.write_text(detail_xml, encoding="utf-8")
    print(f"[저장] {detail_path}")


if __name__ == "__main__":
    main()
