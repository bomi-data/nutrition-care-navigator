# 천안시 공식 데이터 Production 병합 보고서

> 이전 단계(`docs/cheonan_official_enrichment_report.md`)에서 검증된 천안시 신규 서비스
> 2건을 실제 production 데이터셋(`data/processed/welfare_services_recommendation_ready.csv`)에
> 병합하고, 87건 기준으로 recommender/RAG를 재검증한 결과를 기록한다.

---

## 0. Merge audit (병합 전 최종 감사)

병합 스크립트 `src/data_collection/merge_verified_enrichment.py`의 `audit()` 함수로
아래 7개 항목을 자동/수동으로 재확인했다(전체 결과는
`data/processed/welfare_services_enrichment_cheonan_verified.csv` 기준 재검증).

| # | 확인 항목 | 결과 |
|---|---|---|
| 1 | service_id 충돌 | 없음 (`base 85개 ∩ new 2개 = ∅`) |
| 1 | normalized name / semantic duplicate | 없음 (부분 문자열 포함 비교로도 겹치는 서비스명 없음) |
| 1 | 지역 중복(기존 85건 중 천안시 소재 서비스) | 0건 → 병합 후보와 지역 충돌 불가능 |
| 2 | 필수 컬럼(REQUIRED_COLUMNS 28개) 호환성 | 전부 존재, 누락 0 |
| 3 | 빈 값/UNKNOWN으로 인한 부당 HIGH_MATCH 가능성 | `ENR-CHEONAN-02`는 `special_eligibility_required=true`로 `open_count`가 항상 ≥1이 되어 **구조적으로 HIGH_MATCH 도달 불가**(recommender.py `_determine_match_level` 규칙 6). `ENR-CHEONAN-01`은 특수자격요건 없음(`false`)이지만 `low_income_required=true`가 실제 하드 게이트로 작동해 무조건적 매치를 방지 |
| 4 | 공식 원문과의 재대조(age/low_income/disability/recent_discharge/nutrition/community_care/special_eligibility/application) | 원문(사용자 제공 verbatim 텍스트, 이전 턴에서 파싱)과 CSV 필드값 일치 재확인 완료 — 변경 없음(이전 보고서 §5와 동일) |
| 5 | 공식 근거 없는 필드의 임의 True 여부 | `ENR-CHEONAN-01`은 `low_income_required=true` 1개만 True(원문의 필수조건과 일치), `ENR-CHEONAN-02`는 `special_eligibility_required=true` 1개만 True(원문의 통합판정 절차와 일치) — 그 외 모든 필드는 `unknown`/`false`이며 임의 True 없음 |
| 6 | 의료·요양 통합돌봄의 disability/recent_discharge 단독 확정 자격 방지 | `disability_required=unknown`(병렬 대상 규칙), `special_eligibility_required=true`로 확정 자격 불가 — Scenario D(§5)에서 실측 재확인 |
| 7 | 노인맞춤돌봄서비스의 meal_support 오분류 여부 | `service_type={'community_care'}` — `meal_support` 미포함 확인 |

**Merge audit: PASS.** 문제 발견 없음 → 병합 진행.

---

## 1. Merge audit

**PASS** (위 §0, 7개 항목 전부 통과)

## 2. 기존 서비스 수

**85건**

## 3. 신규 서비스 수

**2건**

## 4. 최종 서비스 수

**87건**

## 5. 기존 85건 변경 여부

**변경 없음.** 병합 스크립트가 production CSV를 덮어쓰기 전
`data/processed/backups/welfare_services_recommendation_ready_backup_20260824_210559.csv`에
원본을 자동 백업했고, 병합 후 87건 중 첫 85행을 백업본과 컬럼별로 전부 비교한 결과
**변경된 셀 0개**였다(pandas 셀 단위 diff). `service_id` 87개 전부 고유, 완전 중복 행 0건.

## 6. 신규 서비스 classification

| 필드 | ENR-CHEONAN-01 (노인맞춤돌봄서비스) | ENR-CHEONAN-02 (의료·요양 통합돌봄) |
|---|---|---|
| `service_type` | `community_care` | `community_care`, `discharge_support`, `home_visit` |
| `disability_required` | `unknown` | `unknown`(병렬 대상 규칙 — WLF00006261 선례) |
| `low_income_required` | `true`(원문 필수조건) | `unknown`(원문에 소득기준 없음) |
| `nutrition_relevance` | (blank) | `SUPPORTIVE_NUTRITION`(meal_support와 구분) |
| `special_eligibility_required` | `false` | `true`(통합판정+통합지원회의, WLF00003248 선례) |
| `meal_support` 태그 | 미부여 | 미부여 |

이전 단계 대비 classification 로직/규칙 변경 없음(기존 classification v2 구조 그대로 재사용).

## 7. Scenario A~E 결과 (production 87건 기준)

| Scenario | Top-5 개수 | 1위 | 2위 | 신규 서비스 순위/match_level |
|---|---|---|---|---|
| **A** (75세/저소득예/독거예/거동불편예/식사준비어려움예/disability아니오/meal_support) | 4 | `ENR-CHEONAN-01`(15.8, NEEDS_CONFIRMATION) | `ENR-CHEONAN-02`(15.8, NEEDS_CONFIRMATION) | 둘 다 상위권이나 낮은 절대점수 — meal_support 요청에 두 서비스 모두 서비스타입 불일치라 보너스 없음(과장 없음) |
| **B** (A와 동일 + disability=예) | 4 | A와 **완전 동일**(15.8/15.8) | 동일 | disability 응답이 두 신규 서비스 점수에 전혀 영향 없음 — `disability_required=unknown`이므로 채점 요소 아님(정상 동작) |
| **C** (70세/recent_discharge=예/community_care 요청) | 4 | `ENR-CHEONAN-02`(**77.8**, POSSIBLE_MATCH) | `ENR-CHEONAN-01`(72.2, POSSIBLE_MATCH) | B가 discharge 보너스로 A보다 5.6점 높음. **둘 다 HIGH_MATCH 아님**(B는 special_eligibility로 상한 고정) |
| **D** (60세/disability=예/community_care 요청) | 3 | `ENR-CHEONAN-02`(76.5, **NEEDS_CONFIRMATION**) | WLF00000098(5.9) | `ENR-CHEONAN-01`은 Top-3 밖(60세가 `min_age=65` 하드 미달, 대체 경로 없어 정당하게 배제). B는 1위지만 연령 COMPOUND 미확정 + special_eligibility 미확정으로 **POSSIBLE_MATCH도 아닌 NEEDS_CONFIRMATION**에 머묾 — disability 단독으로 확정 자격 아님 재확인 |
| **E** (70세/disability아니오/discharge아니오/저소득아니오/특별조건없음) | 3 | `ENR-CHEONAN-02`(42.9, NEEDS_CONFIRMATION) | WLF00000098(14.3) | `ENR-CHEONAN-01`은 저소득=아니오가 `low_income_required=true`와 정면 MISMATCH로 정당하게 하드 배제. B는 순수 지역정밀도만으로 1위지만 연령미입력+특수자격 미확정 2개 open으로 NEEDS_CONFIRMATION 유지(과신 없음) |

**결론(사용자 요청 핵심 확인사항)**: 신규 서비스가 추가됐다는 이유만으로 무조건 Top-1이
되지 않는다 — Scenario A/B에서는 절대점수가 낮게(15.8점) 유지되고, Scenario D/E에서
자격 미달 서비스(`ENR-CHEONAN-01`)는 정당하게 배제되며, `ENR-CHEONAN-02`가 상위에
오르는 경우도 match_level이 POSSIBLE_MATCH 이하로 항상 제한된다.

## 8. 기존 UX 문제 개선 여부

| # | 문제 | 상태 | 분류 | 근거 |
|---|---|---|---|---|
| 1 | 지역 선택 시 Top 2~3만 나옴 | **천안시에 한해 부분 개선**(Top-2 → Top-3~4) | `DATA_LIMITATION` | 다른 미보강 지역은 이번 작업 범위 밖이라 그대로 남음. 2건 추가만으로 전국 문제는 해결 안 됨 |
| 2 | disability 변경에도 순위 거의 안 변함 | **미해결**(Scenario A/B 완전 동일 결과) | `DATA_LIMITATION` | 로직은 정상(기존 disability_required=true 12건에는 정상 반응, v1.2 검증 완료). 천안 신규 2건 모두 disability_required가 병렬대상이라 unknown이라 이 지역에서는 영향 없음 — 데이터 부족이지 로직 결함 아님 |
| 3 | desired_support 변경에도 순위 거의 안 변함 | **천안시에 한해 개선**(A: 15.8 vs C: 77.8, 4.9배 차이) | 개선(부분) | community_care 후보가 생기며 desired_support 변경이 실제 점수를 크게 움직임을 확인. 타 지역은 여전히 `DATA_LIMITATION` |
| 4 | 특별자격 서비스가 일반사용자에게 과도한 순위 | **match_level 기준으로는 해결 유지**(HIGH_MATCH 도달 0건), 목록 최상단 노출 자체는 여전히 발생(순위=score 기준) | 절반은 `LOGIC 픽스로 이미 해결`(v1.2), 나머지 절반(랭킹 위치)은 설계상 트레이드오프이지 버그 아님 | Scenario E에서 `ENR-CHEONAN-02`가 1위지만 NEEDS_CONFIRMATION으로 명확히 표시됨(UI가 match_level을 신뢰도 표시에 사용하므로 사용자에게 과신을 주지 않음) |
| 5 | UNKNOWN 입력이 과도한 HIGH_MATCH를 만듦 | **해결 유지**(5개 시나리오 전체에서 HIGH_MATCH 0건) | 기존 v1.2 구조적 픽스 유지 확인 | — |

## 9. RAG retrieval 결과

`python -m rag.build_index`(기존 방식 그대로, `src/rag/build_index.py` 무수정)로
production `data/vectorstore/`를 87건 기준 재빌드(문서 334개: target 90/criteria 89/
support 92/application 63, 빈 섹션 제외 25건 — 병합 전과 동일한 제외 수, 신규 2건은
4섹션 모두 비어있지 않음).

**5개 질의 — service_id-scoped 방식(Phase 1 원 평가 방법론과 동일: 정답 service_id로
스코프를 건 뒤 기대 section이 top-1/top-3인지 측정)**:

| 질의 | 스코프 | 기대 section | Hit@1 | Hit@3 |
|---|---|---|---|---|
| "천안 노인맞춤돌봄서비스" | ENR-CHEONAN-01 | target | True | True |
| "천안 퇴원 후 돌봄" | ENR-CHEONAN-02 | target | True | True |
| "천안 장애인 통합돌봄" | ENR-CHEONAN-02 | target | True | True |
| "천안 영양지원" | ENR-CHEONAN-02 | support | True | True |
| "천안 노인 돌봄 신청 방법" | ENR-CHEONAN-01 | application | True | True |

**Hit@1 = 5/5 (100%), Hit@3 = 5/5 (100%)** — Phase 1 원 평가(90.0%/96.7%)와 동일한
방법론 기준으로 신규 서비스도 정상 검색됨.

**Contamination**: 신규 2개 서비스 각각에 스코프를 걸고 5개 질의 전부 재실행(10개 조합) →
누출 0건. 기존 서비스(`WLF00003248`)에 스코프를 걸고 동일 5개 질의 재실행 → 신규 서비스
콘텐츠 누출 0건. **cross-service contamination 없음.**

**추가로 발견한 사실(참고용, 버그 아님)**: service_id 스코프를 걸지 않고 87건 전체를
대상으로 자유 검색하면, "천안 퇴원 후 돌봄"/"천안 장애인 통합돌봄"/"천안 영양지원" 3개
질의에서 신규 천안 서비스가 top-1으로 나오지 않고(다른 지역의 의미상 유사한 "통합돌봄"
서비스가 상위에 옴) — 이는 **오염이 아니라, 이 RAG 시스템이 애초에 "지역명 키워드로
전체 서비스 중 검색"하도록 설계되지 않고 항상 recommender가 먼저 service_id를 좁혀준
뒤에만 검색하도록 설계되었기 때문**이다(§retriever.py 문서화, Phase 1부터 유지). 실제
Streamlit 플로우(추천 결과 카드 클릭 → 그 서비스만 설명)에서는 문제가 되지 않지만,
"지역명 키워드로 전체 검색"이라는 사용 패턴을 어딘가에서 지원하게 된다면 이 한계가
드러날 것 — §13 한계에 기록.

## 10. Coverage Before/After

| 지표 | BEFORE(85) | AFTER(87) | 증감 |
|---|---|---|---|
| 전체 서비스 수 | 85 | 87 | +2 |
| 천안시 서비스 수 | 0 | 2 | **+2** |
| SIGUNGU coverage | 71 | 73 | +2 |
| community_care coverage | 12 | 14 | +2 |
| disability_required=true coverage | 12 | 12 | +0 |
| discharge_support 태그 coverage | 1 | 2 | +1 |
| nutrition_relevance=DIRECT_NUTRITION | 21 | 21 | +0 |
| nutrition_relevance=SUPPORTIVE_NUTRITION | 0 | 1 | **+1**(신규 사용) |
| meal_support 태그 coverage | 81 | 81 | +0(의도대로 미부여) |

**단순 개수 증가를 넘어선 실질 개선**: 천안시는 Phase 5/7/8에서 반복 확인된
"SIGUNGU coverage 0" 지역 중 하나였다. 이번 병합으로 천안시는 (a) community_care
성격의 요청(Scenario C/D)에서 최대 77.8점까지 오르는 실질적 후보를 갖게 됐고, (b)
`SUPPORTIVE_NUTRITION`이라는 기존에 정의만 되어 있고 실사용 사례가 없던 분류값이
처음으로 실제 데이터에 쓰이며 "meal_support가 아닌 영양 관련 지원"을 구분해서 보여줄 수
있게 됐다. 다만 disability_required=true coverage는 그대로다 — 천안 신규 2건 모두
disability를 유일 조건으로 명시하지 않았기 때문에 당연한 결과다(§8 문제 2 참고).

## 11. 전체 테스트 결과

- 시작 baseline(이전 단계 종료 시점): 235 passed / 4 skipped
- 병합 직후 1차 실행: **2건 실패** — `test_document_builder.py::test_builds_one_document_per_nonempty_section`(하드코딩된 `85` 카운트), `test_special_eligibility.py::test_only_two_real_services_are_flagged`(하드코딩된 "2건만 flagged" 리스트). 둘 다 로직 결함이 아니라 **데이터가 85→87로, special_eligibility flagged가 2→3건으로 의도적으로 변경된 것을 반영하지 못한 stale 카운트 테스트**였다.
- 두 테스트를 실제 값(87/3건)에 맞게 최소 수정(로직 변경 없음, 기대값만 갱신) 후 재실행 → **전부 통과**
- 신규 병합 검증 테스트 3건 추가(`tests/test_merge_verified_enrichment.py`) — merge audit의 충돌 차단 로직 자체를 검증
- **최종: 238 passed / 4 skipped, 실패 0.** 기존 235건 baseline 대비 회귀 0건(2건은 값 갱신, 로직 변경 아님), 신규 3건 추가.

## 12. 남은 DATA_LIMITATION

1. disability_required=true 구조화 서비스가 천안 지역에는 여전히 0건 (§8 문제 2)
2. 화성/세종/울산에서 발견된 OWEB 후보 7건이 아직 review/병합 대기 상태
3. 전국적 REGION_DATA_COVERAGE(78.6%)/SUPPORT_TYPE_COVERAGE(21.4%) 갭은 이번 작업(천안
   2건) 범위 밖 — 그대로 남아있음
4. `ENR-CHEONAN-01`/`ENR-CHEONAN-02` 모두 담당부서 연락처(`contact`)가 원문에 없어
   공란 — 실사용 전 보완 필요
5. `official_url`이 최상위 도메인만 기록되어 정확한 하위 경로 재확인 필요

## 13. 남은 LOGIC_LIMITATION

1. **RAG가 service_id 스코프 없이 지역명 키워드만으로 전체 코퍼스를 검색하면 신규
   천안 서비스가 항상 top-1으로 나오지는 않음**(§9 "추가로 발견한 사실" 참고) — 이는
   버그가 아니라 애초 설계(항상 scoped 검색)의 특성이지만, 향후 "지역 기반 자유 검색"
   기능을 추가한다면 재설계가 필요할 수 있음
2. "유사 중복사업 제외"/"지자체장 예외 인정" 조건이 구조적으로 강제되지 않고 텍스트로만
   보존됨(기존부터 알려진 한계, §0.3 이전 보고서)
3. 특별자격 서비스가 match_level은 낮게 유지되지만 raw score 기준으로는 여전히 목록
   최상단에 노출될 수 있음(§8 문제 4) — 버그는 아니나 UX 설계상 참고할 트레이드오프

## 14. 아직 추가 데이터 수집이 필요한 영역

- 천안시 disability 특화 서비스(§12-1)
- 화성/세종/울산 OWEB 후보 7건의 review/병합 결정
- 그 외 REGION_DATA_COVERAGE가 낮은 지역 전반(Phase 5/6에서 식별된 P1/P2 우선순위 지역)

## 15. 다음 개발 단계 권장사항

1. 화성/세종/울산 OWEB 후보 7건에 대해 이번과 동일한 절차(audit → merge script →
   integrity → classification → scenario → RAG rebuild → regression)를 반복 적용
2. `contact`/`official_url` 하위경로 등 §12에서 식별된 필드 공백을 사용자 재확인으로 보완
3. (이번 범위 밖, 장기 과제) RAG를 "지역명 기반 자유 검색"까지 지원하려면 §13-1의 설계
   특성을 먼저 재검토

---

## 최종 판정

**`PRODUCTION_ENRICHMENT_READY_WITH_LIMITATIONS`**

근거: merge audit 7개 항목 전부 PASS, 기존 85건 셀 단위 변경 0건(백업 대조 확인),
service_id/이름 중복 없음, classification이 기존 규칙만으로 정확히 반영됨, 5개 시나리오
모두 "신규 서비스=무조건 1위"가 아님을 실측으로 반증, RAG Hit@1/Hit@3 100%(기존 평가
방법론과 동일 기준) + contamination 0건, 회귀 테스트 0건(하드코딩 카운트 2건만 값
갱신) — **production 반영 자체는 안전하게 완료됐다.** 다만 §12-13의 실질적 DATA/LOGIC
LIMITATION이 남아 있어(특히 disability coverage가 천안에서 여전히 0이고, RAG의
scoped-only 설계 특성이 이번에 처음 드러남) `_WITH_LIMITATIONS`로 판정한다.
