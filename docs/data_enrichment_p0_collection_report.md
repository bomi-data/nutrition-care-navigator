# P0 데이터 보강 1차 수집 보고서

> 이 단계는 **수집 전용**입니다. 기존 85건(`welfare_services_recommendation_ready.csv`)을
> 병합/수정하지 않았고, 추천엔진/RAG/Streamlit 코드도 전혀 수정하지 않았습니다. 신규 후보는
> 전부 `review_status=COLLECTED` 상태로만 저장했습니다 — `COLLECTED ≠ VERIFIED ≠ INCLUDE`
> 원칙을 그대로 지켰습니다.

---

## 1. 수집 목적

`docs/data_enrichment_plan.md`가 제안한 P0 우선순위(화성시/천안시/세종/울산 지역 coverage +
community_care 전국 확대)에 대해, 실제 공식 API로 후보를 수집해 **검토 전 별도 파일**에
저장하는 것이 목적입니다. 최종 INCLUDE/EXCLUDE 판정, classification v2 적용, 기존 85건과의
병합은 다음 단계로 남겨둡니다.

---

## 2. 사용한 API

**새 API를 찾지 않고 기존 지자체복지서비스 API를 재사용했습니다**
(`src/data_collection/collect_local_welfare_full.py`/`collect_candidate_details.py`와 동일한
엔드포인트).

| 항목 | 값 |
|---|---|
| Base URL | `https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations` |
| 목록조회 | `GET /LcgvWelfarelist` (파라미터: `serviceKey`, `pageNo`, `numOfRows`, **`ctpvNm`**, **`sggNm`**, **`searchWrd`** — 전부 기존 `test_local_welfare_api.py` 문서 주석에 이미 확인되어 있던 실제 파라미터만 사용, 추측 없음) |
| 상세조회 | `GET /LcgvWelfaredetailed` (파라미터: `serviceKey`, `servId`) |
| 인증키 | `.env`의 `LOCAL_WELFARE_API_KEY`(기존과 동일 변수명, 로그에 출력하지 않음) |

신규 스크립트: `src/data_collection/collect_enrichment_p0_candidates.py`(신규 작성, 기존
collector들의 재시도/로그/CSV 저장 패턴을 그대로 재사용).

---

## 3. 사용한 keyword

지침 §3이 제시한 20개를 그대로 사용했습니다(1차 screening 전용, 최종 판정 기준 아님):
도시락·식사·식사지원·반찬·밑반찬·급식·무료급식·재가·방문·돌봄·통합돌봄·지역돌봄·식생활·영양·
식품·식재료·바우처·장애인·노인·어르신.

**community_care 전국 검색은 `searchWrd`로 8개 어구를 시험**했습니다: 통합돌봄, 재가돌봄,
방문돌봄, 지역사회 통합지원, 퇴원연계, 식사연계, 일상생활지원, 돌봄SOS.

**실제로 확인한 것(추측 아님)**: `searchWrd`는 서비스명(`servNm`) 문자열에 대한 **정확한
부분일치**로 동작합니다. 8개 중 "통합돌봄"(8건)과 "돌봄SOS"(1건)만 결과가 있었고, 나머지
6개("재가돌봄", "방문돌봄", "지역사회 통합지원", "퇴원연계", "식사연계", "일상생활지원")는
API가 `resultCode=40, resultMessage="NO DATA FOUND"`를 반환했습니다 — **이는 오류가 아니라
"해당 문구를 서비스명에 포함한 서비스가 전국에 0건"이라는 명확한 응답**임을 원문(raw XML)으로
직접 확인했습니다(`data/raw/enrichment/search_재가돌봄.xml` 등).

---

## 4. 지역별 검색 결과

`ctpvNm`/`sggNm`으로 지역 전체 목록을 가져온 뒤 로컬에서 20개 keyword로 screening했습니다.

| 지역 | API 응답(`totalCount`) | keyword 매치 후보 | 그중 기존 85건과 겹침(`EXACT_SERVICE_ID`) | 신규(`NONE`) |
|---|---:|---:|---:|---:|
| 경기도 화성시 | 23 | 6 | 0 | 6 |
| 충청남도 천안시 | 25 | 8 | 0 | 8 |
| 세종특별자치시 | **0**(`resultCode=40, NO DATA FOUND`) | 0 | 0 | 0 |
| 울산광역시 | 101 | 26 | 0 | 26 |

**세종특별자치시는 `ctpvNm=세종특별자치시` 쿼리 자체가 "NO DATA FOUND"를 반환**했습니다 —
`data_enrichment_plan.md` §5.2가 정적 raw XML로 확인했던 것과 동일하게, **라이브 API
호출로도 재확인**되었습니다. 이 API에 세종시가 사업을 등록하지 않았을 가능성이 높습니다.

화성시/천안시의 `totalCount`(23/25)는 `data_enrichment_plan.md`가 정적 XML에서 확인했던
수치와 **정확히 일치**합니다 — 원 수집 시점 이후 두 지역에 새로 등록된 사업은 없는 것으로
보입니다.

**신규 후보 40건(화성 6 + 천안 8 + 울산 26)을 실제로 열람한 결과, 식사/영양/급식 서비스는
단 한 건도 없었습니다.** 대부분 장애 관련 활동지원·보조기기·바우처, 경로효친 기념품/장수수당,
건강보험료 지원, 아동급식(아동 대상, 고령자 무관) 등이었습니다. 유일하게 확인 가치가 있던
후보는 **`WLF00005011`(노인복지관 운영, 화성시)**이었으나, 상세조회 원문(`sprtTrgtCn`=
"화성시에 주소지를 둔 만60세 이상 노인", `alwServCn`=**"노인복지관 운영"**)에 식사/급식에
대한 구체적 언급이 전혀 없어 `preliminary_relevance=LOW`로 저장했습니다 — **원문에 없는
내용(예: "경로식당 운영 포함일 것")을 추정해 넣지 않았습니다.**

---

## 5. community_care 검색 결과

| searchWrd | 결과 | 신규(기존 85건 아님) |
|---|---:|---:|
| 통합돌봄 | 8건 | 0건(전부 기존 85건과 `EXACT_SERVICE_ID`) |
| 재가돌봄 | 0건(NO DATA FOUND) | — |
| 방문돌봄 | 0건(NO DATA FOUND) | — |
| 지역사회 통합지원 | 0건(NO DATA FOUND) | — |
| 퇴원연계 | 0건(NO DATA FOUND) | — |
| 식사연계 | 0건(NO DATA FOUND) | — |
| 일상생활지원 | 0건(NO DATA FOUND) | — |
| 돌봄SOS | 1건 | 0건(기존 85건과 `EXACT_SERVICE_ID`) |

**community_care 전국 검색에서는 신규 후보를 발견하지 못했습니다.** 서비스명에 "통합돌봄"이
들어간 사업은 전국에 8건뿐이며(§3에서 이미 확인) 이미 전부 기존 85건에 포함되어 있습니다.
`data_enrichment_plan.md` §3이 제안한 +8건 목표는 이번 1차 수집(searchWrd 기반)만으로는
달성하지 못했습니다 — §12에서 원인과 대안을 정리합니다.

---

## 6. API 후보 수

총 **49건**(중복 제거 전, 화성 6 + 천안 8 + 울산 26 + 통합돌봄 검색 8 + 돌봄SOS 검색 1 =
49 — 지역 검색과 keyword 검색 간 겹침 없음 확인됨).

## 7. 공식 웹페이지 후보 수

**0건.** 지침 §10("API 재검색 후 화성/천안/세종/울산에서 관련 후보가 여전히 부족한 경우에만
지자체 홈페이지 조사")에 따라, API 재검색을 먼저 완료했습니다. §4/§6 결과가 보여주듯 4개
지역 모두 **여전히 부족**하지만, 이번 세션에서는 시간·안정성 제약으로 **지자체 홈페이지
직접 조사는 다음 단계로 넘겼습니다**(§13 참고) — 무리하게 브라우저 자동화나 불완전한 정보로
`manual_review_needed` 후보를 만들어내지 않았습니다(지침 §10/§11의 "불완전하면 추측해서
채우지 마세요" 원칙 준수).

---

## 8. 중복 결과

| duplicate_status | 건수 |
|---|---:|
| `NONE`(신규) | 41 |
| `EXACT_SERVICE_ID`(기존 85건과 동일) | 8 |
| `POSSIBLE_NAME_REGION_DUPLICATE` | 0 |

`EXACT_SERVICE_ID` 8건은 전부 community_care `searchWrd` 검색에서 나온, 이미 기존 85건에
포함된 서비스입니다(춘천형/부산형/대전형/함양군 통합돌봄 등) — **삭제하지 않고 후보 CSV에
그대로 남겨 감사 추적이 가능하도록 했습니다**(지침이 예시한 스키마 그대로).

---

## 9. 종료/불명확 사업

| active_status | 건수 |
|---|---:|
| ACTIVE | 49 |
| POSSIBLY_ACTIVE / ENDED / UNKNOWN | 0 |

이번 49건의 원문(`target_original`/`criteria_original`/`support_original`)에서 "폐지",
"신청기간 종료", "한시사업", "신규신청 불가" 등 명시적 종료 신호는 발견되지 않아 전부
`ACTIVE`로 기록했습니다. 연도 표기만으로 종료를 단정하지 않았습니다(지침 §9 원칙 준수).

---

## 10. 데이터 품질 문제

1. **울산 26건 중 다수가 `sigungu` 필드 공백(`nan`)**입니다 — 원본 API 응답의 `sggNm`이
   비어 있는 경우(광역시 단위로만 등록된 사업)를 그대로 반영한 것이며, 임의로 채우지
   않았습니다.
2. **아동급식(`WLF00001283`/`WLF00003820`) 같은 명백한 오탐이 keyword 매치에 포함**되어
   있습니다 — "급식"/"영양" 키워드가 아동 대상 서비스에도 매치되는 것은 이미
   `candidate_review_summary.md`가 문서화한 기존 패턴과 동일합니다. `preliminary_relevance`
   로만 표시했고 자동으로 제외하지 않았습니다(지침이 최종 판정을 금지함).
3. **`WLF00005011`(노인복지관 운영)처럼 원문이 매우 짧고 구체성이 낮은 후보**가 있습니다 —
   `data_preprocessing`/`candidate_review_summary.md`가 이미 지적한 "실무정보 부족" 패턴이
   신규 후보에서도 재현됩니다.

---

## 11. 기존 85개와의 차이

- 기존 85건에는 화성시/천안시/세종의 SIGUNGU-scope 서비스가 **0건**이며, 이번 수집도 그
  공백을 메우지 못했습니다(§4).
- 기존 85건의 울산 서비스도 0건이며, 이번에 발견한 울산 26건 후보 역시 전부 이 프로젝트의
  핵심 taxonomy(`meal_support`/`food_cost_support`/`community_care`/`home_visit`/
  `discharge_support`)와 거리가 있는 유형(장애 보조기기, 경로 기념품, 아동급식 등)입니다.
- community_care 유형은 기존 85건에 12건이 있고, 이번 수집으로 **추가 확보된 신규 건수는
  0건**입니다(§5).

**즉 이번 1차 API 재수집만으로는 `data_enrichment_plan.md`의 P0 목표(화성 +2~3, 천안 +2,
세종 +1~2, 울산 +2, community_care +8)를 달성하지 못했습니다.** 이는 API 사용 방식의 문제가
아니라(§3에서 `searchWrd`/`ctpvNm`/`sggNm`이 정상 동작함을 확인) **이 API의 현재 스냅샷에
해당 지역·유형의 영양돌봄 서비스가 실제로 등록되어 있지 않다는, 이전 정적 분석(§5.2)을
재확인하는 결과**입니다.

---

## 12. 다음 검증 단계 후보 수

| 항목 | 건수 |
|---|---:|
| 사람이 원문 대조로 검토해야 할 후보(`review_status=COLLECTED`) | 49 |
| 그중 `preliminary_relevance=HIGH`(빠른 확인용) | 2(둘 다 기존 85건과 중복 확인됨, 신규 검토 대상 아님) |
| 그중 `preliminary_relevance=MEDIUM`(우선 검토 권장) | 6 |
| 그중 `preliminary_relevance=LOW`(낮은 우선순위) | 41 |
| `manual_review_required=TRUE`(LOW/UNKNOWN) | 47 |

## 13. 수동 확인 필요 항목

1. **지자체 홈페이지 직접 확인(§7에서 보류한 항목)** — 화성시청/천안시청/세종시청/
   울산광역시청 복지 게시판을 API로 찾지 못한 사업이 있는지 별도로 확인해야 합니다
   (`data_source_plan.md` C장이 이미 "전국 통합 소스 없음, MANUAL 필요"로 명시한 영역).
2. **`WLF00005011`(노인복지관 운영, 화성시)** — 원문이 너무 간략해 실제 급식/식사 프로그램
   포함 여부를 시청 홈페이지나 전화 문의로 재확인해야 합니다.
3. **community_care +8 목표 재검토** — `searchWrd` 방식으로는 신규 후보를 찾지 못했으므로,
   서비스명이 아니라 **설명문(`servDgst`)까지 검색하는 방식**이나 지역별 목록 전수조사
   (§4 방식을 화성/천안/세종/울산 외 지역으로 확장)가 필요할 수 있습니다.
4. 세종특별자치시는 이 API 자체에 데이터가 없는 것이 재확인되었으므로, **API 재시도보다
   세종시 공식 홈페이지 확인이 유일한 다음 경로**입니다.

---

## 완료 체크리스트

- [x] 기존 85건 무수정(85행 36열, 재확인)
- [x] 기존 API(지자체복지서비스) 재사용, 새 API 탐색 없음
- [x] 실제 존재하는 파라미터(`ctpvNm`/`sggNm`/`searchWrd`/`servId`)만 사용, 추측 없음
- [x] 원문(target/criteria/support/application) 그대로 저장, LLM 재작성 없음
- [x] `data/processed/welfare_services_enrichment_candidates.csv` 생성(49행,
      `review_status=COLLECTED` 고정)
- [x] `data/raw/enrichment/`에 API 원문(raw XML) 보존, 기존 raw 파일 무수정
- [x] 호출 로그 기록(`data/raw/enrichment/collection_log.txt`), API key 미노출
- [x] 중복(`duplicate_status`)/종료여부(`active_status`) 플래그만 부여, 자동 제외 없음
- [x] senior_relation/nutrition_relevance/service_type_primary 최종 판정 없음
- [x] INCLUDE/EXCLUDE 확정 없음
- [x] 추천엔진/RAG/Streamlit 코드 무수정
- [x] 기존 baseline(226 passed, 4 skipped) 무변경 확인
