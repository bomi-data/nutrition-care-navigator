# 데이터 수집 및 1차 후보 추출 결과 (2026-08-21)

이번 단계는 지역 표준 데이터 준비, 두 API 전체 원본 수집, 키워드 기반 1차 후보 추출까지만
수행했다. 최종 추천점수 계산, LLM 자격조건 판정, 영양사 참여 여부 추측, RAG/Vector DB/Streamlit은
진행하지 않았다.

## 1. 행정구역 표준 데이터

- **방법**: 공공데이터포털 API를 새로 신청하지 않고, 행정안전부 행정표준코드관리시스템(code.go.kr)의
  공개 조회 기능(로그인/인증키 불필요)을 직접 호출해 확보했다.
- **중요 발견**: 실제 데이터 조사 중 2026-07-01자로 **광주광역시+전라남도가 "전남광주통합특별시"로
  통합**되었고, 인천광역시는 중구/동구 개편과 함께 제물포구·영종구·검단구·서해구가 반영된 것을
  code.go.kr 원본 데이터로 확인했다. 이는 제 지식 기준일(2026-01) 이후의 매우 최근 변경이라
  기존에 알고 있던 정보로 판단하지 않고 실제 소스에서 확인했다.
- **산출물**:
  - `data/processed/region_codes.csv` — 16개 현재 시도, 273행(세종 자체 포함), `sido_code/sido_name/sigungu_code/sigungu_name`
  - `data/processed/region_aliases.csv` — 약칭·구칭 → 표준명 매핑(예: 서울→서울특별시, 광주광역시/전라남도→전남광주통합특별시)
- 읍면동 단위는 수집하지 않았다(MVP 범위 외, 요청대로 시도/시군구까지만).

## 2. 복지서비스 전체 원본 수집

| API | 호출 건수 | API가 보고한 총 건수 | 실제 수집 건수 | 실패 페이지 | 중복 ID | 누락 |
|---|---|---|---|---|---|---|
| 중앙부처복지서비스 | 1 | 461 | 461 | 없음 | 없음 | 0 |
| 지자체복지서비스 | 5 (numOfRows=1000 × 5페이지) | 4,770 | 4,770 | 없음 | 없음 | 0 |

- 수집일: 2026-08-21
- 응답 형식: XML (공식 명세상 JSON 미지원 확인되어 XML 그대로 사용)
- 저장 위치(원문 그대로, 페이지 단위로 감싸기만 함): `data/raw/central_welfare_all.xml`, `data/raw/local_welfare_all.xml`
- 수집 로그(JSON): `data/raw/central_welfare_collection_log.json`, `data/raw/local_welfare_collection_log.json`
- 목록조회만 전체 수집했다. 지원대상/선정기준/지원내용/신청방법 원문은 목록조회에 없으므로,
  1차 키워드 후보로 좁힌 서비스에 한해서만 상세조회를 추가로 호출했다(아래 3절).

## 3. 영양돌봄 관련 후보 1차 추출

### 방법
- 목록조회 데이터에서 실제로 존재하는 자연어 필드(`서비스명`, `서비스요약`)를 대상으로
  16개 키워드를 부분 문자열 매칭했다. **지원대상/선정기준/지원내용/신청방법 원문은
  목록조회에 없어 이 1차 스크리닝 단계에서는 검색 대상에 포함하지 못했다** — 대신
  키워드에 걸린 서비스에 한해 상세조회를 별도로 호출해 이 필드들을 채웠다(`target_original`
  `criteria_original` `support_original` `application_original` `contact`).
- 매치 1건마다 `matched_keyword`/`matched_field`를 기록했고, 같은 서비스가 여러 키워드에
  매치되면 최종 산출물에서 쉼표로 합쳤다.
- `lifeArray`(중앙)/`lifeNmArray`(지자체) 값만으로 1차 `senior_relevance`를 판단했다
  (`likely_senior_relevant` / `likely_not_senior` / `unknown`). 이는 최종 판정이 아니라
  사람이 검토할 실마리일 뿐이다. 값이 영유아/아동/청소년/임신·출산으로만 구성된 경우
  `exclusion_reason`을 남겼다.

### 산출물
`data/processed/welfare_candidates.csv` (357행, 서비스 1건당 1행)

필드: `service_id, source_api, service_name, sido, sigungu, target_original, criteria_original, support_original, application_original, contact, matched_keyword, matched_field, senior_relevance, exclusion_reason`

### 명백한 오탐(false positive) 예시 — 실제 데이터에서 확인
| service_id | 서비스명 | matched_keyword | 실제 내용 | 오탐 이유 |
|---|---|---|---|---|
| WLF00006236 | 고교 취업연계 장려금 | 재가 | 고졸 기술·기능"인재가" 사회초기 정착 지원 | "인재가"라는 단어 안의 부분 문자열이 "재가"와 우연히 일치 |
| WLF00006342 | 성남시민 건강진단결과서 무료 발급 | 식품 | "식품위생 분야 종사자"의 건강진단결과서 발급 수수료 관련 | 식품업 종사자 행정처리이지 영양돌봄과 무관 |
| WLF00001139 | 성매매 피해아동청소년 통합지원 | 통합지원 | 성매매 피해 아동·청소년 보호·자립 지원 | "통합지원"이라는 일반적 단어가 전혀 다른 분야(청소년 보호)에도 쓰임 |

`건강관리`(162건) `재가`(56건) 키워드가 매치 건수의 큰 비중을 차지했는데, 두 키워드 모두
일반적인 단어라 장애인 건강주치의, 국가유공자 재가복지처럼 영양돌봄과 무관한 서비스가
다수 섞여 있다.
