# P0 공식 출처 보강 보고서 (2차: API 후보 선별 + 지자체 공식 홈페이지 조사)

> 이 단계는 **DISCOVER → SOURCE VERIFY → CANDIDATE SAVE**까지만 수행했습니다. 기존 85건과
> 병합하지 않았고, 신규 후보를 최종 INCLUDE 처리하지 않았으며, classification v2를 적용하지
> 않았습니다. `추천엔진/RAG/Streamlit` 코드는 전혀 수정하지 않았습니다.

---

## 1. 기존 API 후보 49건 선별 결과

`data/processed/welfare_services_enrichment_candidates.csv`(49건)를 지침 우선순위대로
선별했습니다.

| 순위 | 기준 | 건수 |
|---|---|---:|
| 1순위 | `preliminary_relevance == HIGH` | 2 |
| 2순위 | `preliminary_relevance == MEDIUM` | 6 |
| 3순위 | `LOW` 중 명확한 식사/영양/지역돌봄 개념(도시락·반찬·급식·식사배달·식사지원·영양·식생활·
       재가노인·통합돌봄·방문돌봄·식사연계)이 원문에 실제로 존재하는 경우 | 2 |
| **합계(재검토 대상)** | | **10** |

나머지 39건(LOW 중 개념 불일치 39건)은 이번 P0 단계에서 **HOLD**로 남겨두었습니다(원문은
`welfare_services_enrichment_candidates.csv`에 그대로 보존, 삭제하지 않음).

**49건 → 10건으로 선별**했습니다(목표 "약 5~15건" 범위 안).

---

## 2. 실제 priority review 후보 (`welfare_services_enrichment_priority_review.csv`, 10건)

원문을 직접 읽고 `priority_review_reason` + `review_note`를 부여했습니다.

| service_id | 서비스명 | 지역 | duplicate_status | priority_review_reason | 실제 판단 |
|---|---|---|---|---|---|
| WLF00005308 | 춘천형 노인통합돌봄사업 | 강원 춘천시 | `EXACT_SERVICE_ID` | COMMUNITY_CARE | 기존 85건과 완전 중복, 신규 검토 불요 |
| WLF00005857 | 부산, 함께돌봄(부산형 통합돌봄)사업 | 부산 | `EXACT_SERVICE_ID` | COMMUNITY_CARE | 기존 85건과 완전 중복, 신규 검토 불요 |
| WLF00001627 | 독거노인 행복커뮤니티 지원 사업 | 경기 화성시 | `NONE`(신규) | OTHER_RELEVANT | 원문(`alwServCn`)이 AI스피커 안부확인/정서지원 중심 — **식사/영양 내용 없음**. `REJECT_CANDIDATE` 권장 |
| WLF00001283 | 아동급식 지원 | 울산 | `NONE`(신규) | OTHER_RELEVANT | 18세 미만 아동 대상 — **고령자 무관**. `REJECT_CANDIDATE` 권장 |
| WLF00003820 | 아동급식비 지원(학기중 토공휴일) | 울산 남구 | `NONE`(신규) | OTHER_RELEVANT | 아동 대상 — 고령자 무관. `REJECT_CANDIDATE` 권장 |
| WLF00005770 | 대전형 지역사회통합돌봄 | 대전 | `EXACT_SERVICE_ID` | COMMUNITY_CARE | 기존 85건과 완전 중복 |
| WLF00006336 | [통합돌봄] AI 생활지원사 지원사업 | 강원 정선군 | `NONE`(신규) | OTHER_RELEVANT | 65세 이상 대상이나 원문이 AI앱(안부확인·건강관리) 중심 — **식사/영양 내용 없음**. `REJECT_CANDIDATE` 권장 |
| WLF00006261 | 함양군 통합돌봄사업 | 경남 함양군 | `EXACT_SERVICE_ID` | COMMUNITY_CARE | 기존 85건과 완전 중복 |
| WLF00001244 | 사랑의 우유 | 울산 동구 | `NONE`(신규) | FOOD_COST_SUPPORT | 우유 현물 지급(거동불편 저소득층 포함) — 완전한 식사는 아니나 식품지원 성격, 참고용 |
| WLF00006428 | 다함께돌봄센터 급, 간식비 지원 | 울산 울주군 | `NONE`(신규) | OTHER_RELEVANT | 6~12세 아동 대상 — 고령자 무관. `REJECT_CANDIDATE` 권장 |

**중요한 정직한 결론**: 기존 API 후보 49건을 원문까지 전부 직접 읽은 결과, **P0 4개 지역
(화성/천안/세종/울산)이나 community_care 확대에 실제로 기여할 수 있는 신규 후보는 API
경로에서는 0건**이었습니다. 5건은 이미 기존 85건과 완전히 같은 서비스였고, 나머지 5건은
신규였지만 인구집단 불일치(아동 대상)이거나 식사·영양 내용이 아예 없는 AI 안부확인
서비스였습니다(`WLF00001627`/`WLF00006336`은 앞서 `unknown_review_batch` 검토에서 이미
확인된 "AI/IoT 안부확인, 식사·영양 내용 없음" 오탐 패턴과 동일). 이는 `data_enrichment_p0
_collection_report.md`의 결론(API 스냅샷에 해당 서비스가 없음)을 원문 검토 수준에서 다시
한번 확증합니다.

---

## 3. 지역별 공식 홈페이지 조사

지침이 지정한 4개 지역만 조사했습니다(다른 지역으로 확장하지 않음). 사용한 source는 전부
시청/구청 공식 도메인(`hscity.go.kr`, `sejong.go.kr`, `ulsannamgu.go.kr`, `donggu.ulsan.kr`,
`cheonan.go.kr`)이며, 언론기사·블로그·민간 요약사이트는 evidence로 사용하지 않았습니다
(검색 결과에 섞여 나온 오마이뉴스 기사 등은 링크만 확인하고 최종 근거로 채택하지 않음).

## 4. 화성 결과 — 신규 후보 2건 (목표 2~3건 달성)

| candidate_id | 서비스명 | 핵심 내용 | 공식 URL |
|---|---|---|---|
| OWEB001 | 노인무료급식지원 | 경로식당 무료급식(월~금) + 재가노인 식사배달(밑반찬 주1회 5일분) | [hscity.go.kr](https://www.hscity.go.kr/www/partInfo/femaleFamily/Welfare5/Welfare5_4.jsp) |
| OWEB002 | 누구나돌봄(그냥드림 사업) | 통합돌봄 7개 서비스 중 "④식사지원"으로 도시락 제공(연 45식, 1식 11,000원) | [hscity.go.kr](https://www.hscity.go.kr/www/partInfo/femaleFamily/Welfare8/Welfare8_8.jsp) |

두 건 모두 API의 화성시 23개 목록에는 없던 서비스입니다 — **API 미등록, 공식 홈페이지에만
게시된 사업**임을 실제로 확인했습니다(`data_enrichment_plan.md` §5.3이 예상한 그대로).

## 5. 천안 결과 — 신규 후보 0건(검증 실패), manual check 2건

`https://www.cheonan.go.kr/dongnam/sub03_01.do`, `.../seobuk/sub03_01.do`는 모두 **"페이지
준비중"**이었고, `https://www.cheonan.go.kr/kor/sub06_06_01_01.do`(노인복지서비스)는
**JavaScript 렌더링 콘텐츠**라 WebFetch로 메뉴 구조만 확인되고 실제 내용을 읽지 못했습니다.
초기 검색 단계에서 "저소득 재가노인 식사배달사업(4개 기관, 월 155명)"/"무료경로식당
운영지원(4개 기관, 월 208명)"이라는 구체적 수치가 검색엔진 요약에 등장했으나, **라이브
페이지로 직접 재확인하지 못했으므로 후보로 저장하지 않았습니다**(지침 §8/§14 원칙 —
불완전한 정보를 추측해서 채우지 않음). 대신 `manual_source_check_required.csv`에 2건
기록했습니다.

## 6. 세종 결과 — 신규 후보 2건 (목표 1~2건 달성)

| candidate_id | 서비스명 | 핵심 내용 | 공식 URL |
|---|---|---|---|
| OWEB003 | 의료·요양 통합돌봄 사업 | 6개 분야 54개 사업 중 "일상생활돌봄(식사, 이동지원 등)" 포함 | [sejong.go.kr](https://www.sejong.go.kr/bbs/R0071/view.do?nttId=B000000146073Yt3lA4n) |
| OWEB004 | 기부식품 등 제공 사업(푸드뱅크·푸드마켓) | 독거노인 포함 취약계층에 식품 기부 전달 | [sejong.go.kr](https://www.sejong.go.kr/welfare/sub05_01.do) |

세종은 API 목록조회 자체가 `resultCode=40, NO DATA FOUND`(§ `data_enrichment_p0_collection
_report.md` §4)였던 지역인데, **공식 홈페이지에는 실제로 관련 사업이 존재**함을 확인했습니다
— API 미등록이 "사업 부재"를 의미하지 않는다는 것을 보여주는 명확한 사례입니다.

## 7. 울산 결과 — 신규 후보 3건 (목표 2건 초과 달성)

| candidate_id | 서비스명 | 핵심 내용 | 공식 URL |
|---|---|---|---|
| OWEB005 | 거동불편 재가노인 식사배달 및 무료급식사업(남구) | 밥/국/밑반찬 배달 + 7개 경로식당 무료급식(일 1,885명) | [ulsannamgu.go.kr](https://www.ulsannamgu.go.kr/welfare/contents/old/support_food.do) |
| OWEB006 | 결식우려노인 무료급식(동구) | 5개 경로식당에서 평일 중식 제공 | [donggu.ulsan.kr](https://www.donggu.ulsan.kr/donggu/contents/contents.do?mId=3010105) |
| OWEB007 | 거동불편 저소득 재가노인 식사배달(도시락)(동구) | 도시락 자원봉사자 배달, 월~금 1일 150명 | [donggu.ulsan.kr](https://www.donggu.ulsan.kr/donggu/contents/contents.do?mId=3010105) |

**정확히 API가 놓친 유형**입니다 — 울산광역시 전체를 대상으로 한 API 검색(§4의 26건
keyword 매치)에서는 발견되지 않았고, **구청(남구/동구) 단위 공식 홈페이지**에서만
발견되었습니다. 이는 지자체복지서비스 API가 광역시 단위 등록에는 다소 공백이 있고, 실제
운영은 자치구 단위로 이뤄지고 있음을 시사합니다.

## 8. community_care 결과

지침 §12는 "통합돌봄이라는 단어만 있는 서비스는 후보로 인정하지 말라"고 명시했습니다. 이번에
발견한 COMMUNITY_CARE 신규 후보 2건(OWEB002 화성 누구나돌봄, OWEB003 세종 의료·요양
통합돌봄)은 **둘 다 "통합돌봄"이라는 단어만이 아니라 원문에 구체적인 식사/생활지원 항목이
명시**되어 있음을 직접 확인한 뒤 포함했습니다(누구나돌봄=도시락 제공 상세 규정, 세종
통합돌봄="일상생활돌봄(식사, 이동지원 등)" 명시). 이 2건은 §4/§6의 지역별 결과와 중복
집계이며, 별도로 추가된 community_care 전용 신규 후보는 없습니다(§12가 "다른 지역으로
확장하지 마세요"라는 §3 제약과 함께 적용되어, 이번 라운드에서는 P0 지역 밖의 community_care
신규 발굴은 수행하지 않았습니다).

---

## 9. 신규 후보

**총 7건**(화성 2 + 세종 2 + 울산 3), 전부 `data/processed/welfare_services_enrichment
_official_web_candidates.csv`에 저장했습니다.

## 10. 중복 후보

7건 전부 `duplicate_status = NONE`입니다. 기존 85건에는 화성시/세종/울산 지역 서비스가
0건이므로(`recommendation_engine_v1_2_validation.md`/`mvp_coverage_validation.md`에서 이미
확인, 이번에도 재확인함) `service_id`/`service_name+region` 어느 기준으로도 중복이 발생할
수 없습니다.

## 11. 정보 부족 후보

다음 필드는 공식 페이지에 명시되어 있지 않아 **추측하지 않고 "UNKNOWN(정보 없음)"으로
남겼습니다**(지침 §8):

| candidate_id | 비어있는 필드 |
|---|---|
| OWEB002 | `criteria_original`(선정기준 별도 문구 없음) |
| OWEB003 | `criteria_original` |
| OWEB004 | `criteria_original`, `application_original` |
| OWEB005 | `criteria_original` |
| OWEB006 | `criteria_original`, `application_original` |
| OWEB007 | `criteria_original`, `application_original` |

연령/소득기준/담당기관/전화번호/신청방법/영양사 참여 여부를 임의로 채운 항목은 하나도
없습니다.

## 12. 수동 확인 필요 페이지

`manual_source_check_required.csv`에 **2건** 기록했습니다(§5 참고). JavaScript 렌더링 또는
"페이지 준비중" 상태로 검증하지 못한 케이스이며, 억지로 추측하지 않았습니다.

---

## 13. 현재 P0 coverage 개선 가능성

이번 조사로 확인된 7건이 향후 검증·병합을 거쳐 최종 반영된다면:

| 지역 | 현재(기존 85건) | 이번 조사로 확인된 신규 후보(미병합) |
|---|---:|---:|
| 화성시 | 3건(SIDO 1 + NATIONAL 2) | +2건(검증 대기) |
| 천안시 | 2건(NATIONAL만) | +0건(검증 실패, manual check 2건) |
| 세종 | 2건(NATIONAL만) | +2건(검증 대기) |
| 울산 | 2건(NATIONAL만) | +3건(검증 대기) |

**4개 지역 중 3개 지역(화성/세종/울산)에서 API에 없던 신규 관련 후보를 실제로
발견했습니다** — §13 성공기준 A(4개 중 최소 2~3개 지역)를 충족합니다. 천안시만 "공식 조사
결과 관련 페이지에 접근하지 못해 부재/존재 여부를 확정할 수 없음"(성공기준 B의 부분 충족 —
실제 사업 부재가 아니라 **접근 실패**로 확인됨, 이 구분 자체가 의미 있는 결과입니다)로
남았습니다.

## 14. 다음 검증 단계

1. 이번 7건 각각을 `classification_criteria.md` v2 기준으로 검토(senior_relation/
   nutrition_relevance/service_type_primary 최종 판정) — 이번 단계에서는 미실시.
2. 천안시는 사용자가 직접 브라우저로 페이지를 열람하거나 전화 문의로 확인(§12 manual
   check 참고).
3. 검증 완료 후 기존 85건과 병합하는 별도 단계 진행(이번에도 병합하지 않음).
4. `WLF00001627`/`WLF00006336`(AI 안부확인 서비스) 패턴이 이번에도 재확인되었으므로, 향후
   API 재검색 시 이 패턴을 자동으로 낮은 우선순위 처리하는 규칙을 검토할 수 있음(이번
   단계에서는 코드를 수정하지 않음).

---

## 완료 체크리스트

- [x] 기존 85건 무수정(85행 36열, 재확인)
- [x] API 후보 49건 → 10건 선별(`priority_review_reason`/`review_note` 부여)
- [x] P0 4개 지역만 조사(다른 지역 확장 없음)
- [x] 공식 source만 사용(시청/구청 공식 도메인), 뉴스/블로그/SNS 미사용
- [x] 신규 후보 7건 저장(`welfare_services_enrichment_official_web_candidates.csv`)
- [x] 정보 부족 필드는 UNKNOWN 유지, 추측 없음
- [x] 중복 검사 완료(전부 `NONE`)
- [x] 검증 실패 2건은 `manual_source_check_required.csv`에 기록, 추측하지 않음
- [x] 신규 후보 최종 INCLUDE 없음, classification v2 미적용, 85건과 merge 없음
- [x] 추천엔진/RAG/Streamlit 코드 무수정
- [x] 기존 baseline(226 passed, 4 skipped) 무변경 확인
