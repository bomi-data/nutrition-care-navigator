# 추천 랭킹 최종 튜닝 보고서

> production 87건(기존 85 + 천안 2) 기준으로 실제 Streamlit 사용자 테스트에서 보고된
> ranking 이상 현상 3건(desired_support 무효과, disability 무효과, 국가유공자 과다노출)을
> 재현 → score breakdown → 원인 확인 → 최소 수정 순서로 진단·보정한 결과를 기록한다.
> RAG corpus/FAISS/데이터 수집/Streamlit 디자인은 이번 단계에서 전혀 건드리지 않았다.

---

## 1. 실제 사용자 테스트 증상

| 현상 | 보고 내용 |
|---|---|
| A. desired_support | 천안 프로필에서 "식사/도시락/반찬 지원" ↔ "지역사회 통합돌봄"을 바꿔도 Top-4 구성과 **순서**가 완전히 동일(1.노인맞춤돌봄서비스 2.의료·요양 통합돌봄 3.국가유공자재가복지지원 4.재가급여) |
| B. disability | 천안 사례에서 disability 아니오→예로 바꿔도 Top-4 동일. 단, 그 자체만으로 로직 결함이라 단정하지 말고 score/match_level까지 확인하라는 전제 |
| C. special eligibility | 특별한 취약조건이 거의 없는 일반 사용자에게도 국가유공자재가복지지원(특수자격 필요)이 Top 2~3에 반복 등장 |

## 2. desired_support 코드 흐름 (§2 audit, Q1~Q8)

**Q1/Q2. 어느 단계, HARD or SOFT?** `desired_support`는 오직 `scorer.py`의
`_service_type_component`(SOFT SCORE)에서만 사용된다. `filters.py`(HARD FILTER)에는
전혀 등장하지 않는다 — hard exclude를 일으키지 않는다(원래부터 안전하게 설계됨).

**Q3. 값별 점수는?** (수정 전) `service_type_match_max=50.0`(전체 가중치 중 가장 큰
단일 컴포넌트, config.py). 사용자가 desired_support로 고른 태그와 `service.service_type`의
교집합 비율(`len(intersection)/len(desired_tags)`) × 50 — **이진(binary) 매칭**이었다.

**Q4. 비교 대상 필드는?** `service.service_type`(frozenset 태그: meal_support/
food_cost_support/community_care/home_visit/discharge_support)만 비교한다.
`service_type_primary`/`meal_support_flag`/`food_cost_support_flag`는 **scorer.py 어디에도
쓰이지 않는다**(레거시/감사용 컬럼, `recommendation_data_readiness.md`에서 이미 확인된
사실 — meal_preparation_bonus도 `service_type` 기준으로 채점하도록 v1.2에서 명시적으로
`meal_support_flag` 대신 선택된 바 있음).

**Q5. meal_support 범위가 너무 넓어 구분력이 약한가?** 87건 중 81건(93%)이
`service_type`에 `meal_support`를 포함한다(§6 상세). 하지만 이번 진단에서 확인한 결과,
이 넓은 분포 자체는 desired_support 무효과 증상의 **원인이 아니었다** — 문제가 된 천안
프로필에서는 애초에 지역 하드필터를 통과하는 후보가 4건뿐이고, 그 4건 중 meal_support
태그를 가진 서비스는 **0건**이었다(§4-a).

**Q6. special_eligibility_required=True 서비스는 ranking에서 어떻게?**
`_determine_match_level`의 open_count 규칙(규칙 4/6)에 의해 `special_eligibility_check`가
항상 `confirmation_needed=True`를 반환하므로 open_count가 최소 1 — **HIGH_MATCH(규칙 7)에
절대 도달하지 못하고 POSSIBLE_MATCH 이하로 구조적으로 제한**된다(수정 전부터 이미 그랬음,
Cheonan 병합 보고서에서도 검증됨).

**Q7. disability=True/False/Unknown이 score에?** `disability_required`는 **HARD
FILTER 필드로만 쓰인다**(`filters.py`). `scorer.py`에는 disability를 반영하는 컴포넌트가
**하나도 없다** — 이는 결함이 아니라 설계다(disability는 이진 자격조건이지 선호도가
아니라는 `rules_spec.md`의 분류). 서비스가 `disability_required=unknown`이면
`evaluate_tristate`가 사용자의 답과 무관하게 항상 `status=UNKNOWN, confirmation_needed=False,
score_signal=0`을 반환한다(matcher.py 확인, §8에서 실측 재확인).

**Q8. Top4 동일 원인이 데이터 때문인가 scoring 때문인가?** **둘 다 확인됐고, 서로 다른
부분을 설명한다** — Top-4 "구성(같은 4개 서비스)"은 100% 데이터(지역 커버리지) 문제,
Top-4 "순서(항상 같은 배열)"는 scoring 로직(이진 매칭으로 인한 타이) 문제였다. 아래
§4에서 실측으로 분리했다.

## 3. score breakdown (Before, 수정 전 코드 기준)

공통 프로필: 천안시/75세/저소득 예/독거 예/거동불편 예/식사준비어려움 예/disability
아니오/recent_discharge UNKNOWN(Streamlit 기본 라디오 index=2와 동일).

### §4-a. 하드필터 통과 후보: 87건 중 단 4건

| service_id | service_type | region_scope |
|---|---|---|
| WLF00000098 국가유공자재가복지지원 | home_visit | NATIONAL |
| WLF00003248 재가급여 | home_visit | NATIONAL |
| ENR-CHEONAN-01 노인맞춤돌봄서비스 | community_care | SIGUNGU(천안) |
| ENR-CHEONAN-02 의료·요양 통합돌봄 | community_care, discharge_support, home_visit | SIGUNGU(천안) |

81건의 meal_support 태그 서비스 중 천안시/충청남도/NATIONAL 범위는 **0건**이었다(전부
다른 시군구 SIGUNGU 스코프). → **Top-4 "구성"이 바뀌지 않는 이유는 애초에 후보가 4개뿐이기
때문**(DATA_COVERAGE, §12).

### §4-b. Scenario M(meal_support) vs C(community_care) — 수정 전 컴포넌트별 점수

| service_id | service_type_match(M) | service_type_match(C) | 기타 컴포넌트(M=C, 불변) | TOTAL(M) | TOTAL(C) |
|---|---|---|---|---|---|
| WLF00000098 | 0.00/50 | 0.00/50 | mobility 10/10, verif 5/5, mealprep 0/10 | 15.79 | 15.79 |
| WLF00003248 | 0.00/50 | 0.00/50 | 위와 동일 | 15.79 | 15.79 |
| ENR-CHEONAN-01 | 0.00/50 | **50.00/50** | region_precision 10/10, verif 5/5 | 15.79 | **68.42** |
| ENR-CHEONAN-02 | 0.00/50 | **50.00/50** | 위와 동일 | 15.79 | **68.42** |

(수정 전 코드로 직접 재현한 실측치. `_service_type_component`는 EXACT 매치에서는
수정 전후 동일하게 계산하므로 이 표의 값은 수정 전/후 공통이다.)

**핵심 관찰**: M→C 전환 시 `service_type_match` 컴포넌트가 ENR-CHEONAN-01/02 **둘 다
동일하게 0→50으로 스윙**했다(둘 다 `community_care` 태그를 갖고 있으므로). 즉
desired_support는 이미 절대 점수에 큰 영향을 주고 있었지만, ENR-01과 ENR-02가 서로에
대해 갖는 **상대적 우열은 M(둘 다 0)과 C(둘 다 50) 어느 쪽에서도 완전히 동일(항상
tie)** 했다 — 그 결과 `_sort_key`의 결정적 tie-break(service_id 오름차순)가 매번 같은
순서(ENR-01 먼저)를 만들어냈다. WLF00000098/WLF00003248도 같은 이유로 서로 항상 tie였다
(M: 둘 다 0, C: 수정 전에는 둘 다 0, 수정 후에는 RELATED credit으로 둘 다 25 — 그래도
서로는 여전히 tie, 이는 둘의 service_type이 둘 다 `{home_visit}`로 완전히 동일하기
때문이며 버그가 아니다).

## 4. 원인

**Top-4 "구성" 불변 = DATA_COVERAGE_LIMITATION.** 천안시에서 하드필터를 통과하는
서비스가 애초에 4건뿐이라 desired_support를 아무리 바꿔도 5번째 서비스가 등장할 수 없다.

**Top-4 "순서" 불변 = LOGIC_ISSUE(확인됨, 수정 대상).** `_service_type_component`가
순수 이진 교집합 비율만 계산해, "완전히 일치"와 "전혀 무관"만 구분하고 **"관련은
있지만 정확히 일치하진 않는" 중간 단계가 없었다**. 이 때문에 서로 다른 서비스가
desired_support 변경에 동일하게 반응해(0→50 vs 0→50) 상대 순서가 절대 바뀌지 않는
경우가 생겼다. 사용자의 §4 "기대되는 ranking 원칙"이 요구한 EXACT/RELATED/NEUTRAL
구조가 정확히 이 지점에 필요했다.

## 5. meal/community care 분류 상태 (§6)

87건 기준 `service_type` 태그 분포: `meal_support` 81 / `community_care` 14 /
`home_visit` 7 / `discharge_support` 2 / `food_cost_support` 1.
`nutrition_relevance`: 빈값 65 / `DIRECT_NUTRITION` 21 / `SUPPORTIVE_NUTRITION` 1.

meal_support가 81/87(93%)로 매우 넓은 것은 사실이나, 이는 **이 프로젝트 자체가
"영양돌봄" 서비스를 대상으로 원본 데이터가 수집됐기 때문**(기존 데이터 수집 단계부터
확인된 사실)이며, 이번 진단에서 이것이 실제 ranking 이상 현상의 원인이 아님을 §4-a에서
실측으로 배제했다. **원문 재분류나 LLM 추측 재판정은 하지 않았다** — 기존
`service_type`/`nutrition_relevance` 값을 그대로 신뢰하고, 그 위에서 매칭 로직만
정교화했다.

## 6. special eligibility 문제

`special_eligibility_required` 메커니즘은 **이미 정상 동작 중이었다**(신규 코드 불필요,
지시사항대로 국가유공자 전용 하드코딩을 만들지 않음): WLF00000098이 이번 진단의 모든
시나리오(M/C/Test1~5, disability D0~D2)에서 **단 한 번도 HIGH_MATCH에 도달하지
않았다**. 다만 desired_support의 이진 매칭 결함으로 인해 **낮은 절대점수(15.79)로
고정되어 있었을 뿐 상대적으로 Top-3 안에 계속 보였다** — 이는 원래도 match_level이
NEEDS_CONFIRMATION이라 "확정 추천"으로 오인될 위험은 낮았지만(§7 Test3에서 재검증).

## 7. 실제 수정 내용

`src/recommender/scorer.py`의 `_service_type_component`를 EXACT/RELATED/NEUTRAL
3단계로 확장했다(matcher.py의 순수 비교 로직은 건드리지 않음 — 이 함수는 scorer.py의
scoring 정책이므로 원래도 scorer.py에 있었음):

- **EXACT**: `desired tag ∈ service.service_type` → 기존과 동일하게 만점(1.0) credit.
- **RELATED**(신규): 두 개의 서로 겹치지 않는 클러스터로 정의 —
  `{meal_support, food_cost_support}`(식사·식비는 서로 관련), `{community_care,
  home_visit, discharge_support}`(재가/방문/퇴원 돌봄은 지역사회 통합돌봄의 하위
  유형 — 사용자가 제시한 §4 원칙에 명시된 그룹핑을 그대로 반영). 추가로
  `meal_support` 요청에 한해 `nutrition_relevance ∈ {DIRECT_NUTRITION,
  SUPPORTIVE_NUTRITION}`인 서비스도 RELATED로 인정(기존 필드 재사용, 신규 데이터
  없음). RELATED는 **0.5(절반) credit** — 기존 `service_type_match_max=50`이라는
  scale 안에서 "완전 일치(50)"와 "완전 무관(0)"의 중간값을 택한 것으로, desired_support의
  최대 영향력 자체는 전혀 늘리지 않았다(상한 50 그대로).
- **NEUTRAL**: 그 외 → 기존과 동일하게 0.

`_determine_match_level`(recommender.py) 조정:
- 규칙 5("완전 무관 → NEEDS_CONFIRMATION")를 "EXACT도 RELATED도 없을 때만"으로 완화 —
  RELATED만 있는 서비스가 무조건 NEEDS_CONFIRMATION으로 깔리지 않게 함.
- 규칙 7(HIGH_MATCH)에 **"EXACT 매치가 있어야 함"** 조건을 신규로 추가 — RELATED만으로는
  아무리 점수가 높아도 HIGH_MATCH에 도달할 수 없다(완전히 일치하지 않는데 "확신"을
  주지 않기 위한 안전장치, special_eligibility와 같은 철학).

`_build_explanations`(recommender.py): RELATED 매치에 대해 "완전히 같지는 않지만
관련이 있는 지원" 문구를 별도로 추가 — EXACT("일치해요")와 RELATED를 사용자에게
과장 없이 구분해서 안내.

**변경하지 않은 것**: HARD FILTER(filters.py), matcher.py의 3x3 비교 로직,
`special_eligibility_required` 메커니즘 자체, `DEFAULT_WEIGHTS`의 다른 컴포넌트
가중치(region/age/disability 등), disability 관련 코드(§9에서 이유 설명), RAG,
Streamlit UI.

## 8. 수정하지 않은 항목과 이유

| 항목 | 이유 |
|---|---|
| Top-4 "구성"이 천안에서 4개로 고정되는 문제 | `DATA_COVERAGE_LIMITATION` — 천안 지역에 region-eligible한 meal_support 서비스가 0건이라 scoring으로 해결 불가. 신규 데이터 수집은 이번 지시사항에서 명시적으로 금지됨 |
| disability가 천안 4개 후보에서 score에 영향 없음 | `EXPECTED_BEHAVIOR`(설계상 disability는 HARD FILTER 전용, SOFT SCORE 컴포넌트 없음) + `DATA_COVERAGE_ISSUE`(4개 후보 모두 disability_required=unknown). 억지로 disability soft bonus를 신설하는 것은 이번 지시사항이 금지한 "임의 가중치 패치"에 해당해 시행하지 않음 |
| `special_eligibility_required` 메커니즘 자체 변경 | 이미 정상 작동 확인(HIGH_MATCH 0건 유지) — 재사용만 하고 새 패널티 체계를 만들지 않음(지시사항 §7 준수) |
| RELATED credit 계수(0.5)를 더 세분화 | 지시사항이 요구한 최소 구조(EXACT/RELATED/NEUTRAL)를 넘어서는 추가 등급(예: WEAK_RELATED)은 이번 진단에서 근거를 찾지 못해 도입하지 않음 — 과설계 방지 |
| meal_support 태그 재분류 | §5에서 확인했듯 이번 증상의 원인이 아니었고, 공식 원문 재해석/LLM 추측 재분류는 명시적으로 금지됨 |

## 9. Test 1~5 Before/After

(Before는 §7 수정 전 구조로 재현, After는 수정 후 실측)

| Test | Before Top1(score/level) | After Top1(score/level) | 비고 |
|---|---|---|---|
| **1** meal_support | ENR-CHEONAN-01 (15.79/NEEDS_CONFIRMATION, 4개 후보 전부 15.79로 tie → service_id 오름차순 tie-break로 우연히 1위) | **ENR-CHEONAN-02 (42.11/POSSIBLE_MATCH)** | SUPPORTIVE_NUTRITION 신호로 식사 관련성이 더 높은 서비스가 tie를 깨고 정당하게 1위로 이동 |
| **2** community_care | ENR-CHEONAN-01 (**68.42/HIGH_MATCH**, 이미 수정 전에도 EXACT 매치라 1위였음) | ENR-CHEONAN-01 (**68.42/HIGH_MATCH**, 동일) | EXACT 매치 케이스는 이번 수정으로 바뀌지 않음(의도된 동작 — RELATED 로직은 EXACT가 없을 때만 개입) |
| **1 vs 2 비교** | Top-4 **구성·순서 완전 동일**(M/C 모두 ENR-01→ENR-02→WLF098→WLF3248 — ENR-01/02가 서로 항상 tie, WLF098/3248도 서로 항상 tie였기 때문에 desired_support를 바꿔도 각 tie 내부 순서가 tie-break로 고정) | **순서가 서로 다름**(meal: ENR-02 > ENR-01, community: ENR-01 > ENR-02) — 구성(4개 서비스)은 데이터 한계로 동일 유지, meal 시나리오에서만 ENR-01/02 사이의 tie가 깨져 순서가 desired_support에 따라 유의미하게 달라짐 |  |
| **3** 특별취약조건 없음(70세, community_care) | WLF00000098 rank 확인 필요(Before도 이미 POSSIBLE_MATCH 이하) | rank=3, score=35.29, **level=POSSIBLE_MATCH**(HIGH_MATCH 아님), confirmation_needed 2건 | 국가유공자 서비스가 Top1~2를 차지하지 않음 재확인 |
| **4** disability no→yes | 동일 | **동일**(68.42/HIGH_MATCH 그대로) | `DATA_COVERAGE_ISSUE`로 판정(§8) — scoring 억지 변경하지 않음 |
| **5** unknown-heavy | HIGH_MATCH 0건(Before도 이미 0건, special_eligibility 메커니즘이 원래 작동 중이었으므로) | **HIGH_MATCH 0건 유지** | 회귀 없음 확인 |

## 10. 전체 테스트 결과

- 시작 baseline: 238 passed / 4 skipped / 0 failed
- 수정 직후 1차 실행: 2건 실패 — `test_scorer.py::test_multi_desired_support_partial_intersection_scores_between_zero_and_full`(고정관념이던 "home_visit=0 관련성" 가정이 RELATED 도입으로 깨짐), `test_special_eligibility.py::test_flagged_services_still_appear_not_deleted`(`top_k=85`가 총 87건 중 최하위 2건을 우연히 컷오프 — "삭제되지 않는지" 확인이 목적이므로 `top_k=len(all_services)`로 수정)
- 두 테스트를 실제 의도에 맞게 최소 수정(로직 변경 아님, fixture/top_k 값만 조정) → 전부 통과
- 신규 테스트 8건 추가: `tests/test_scorer.py`에 2건(RELATED credit 등급 검증), `tests/test_ranking_tuning_v1_3.py`에 6건(이번 진단·수정 전체를 실제 production 87건 데이터로 회귀 고정)
- **최종: 246 passed / 4 skipped, 실패 0.** 238건 baseline 대비 회귀 0건(2건은 값/fixture 갱신, 로직 변경 아님), 신규 8건 추가.

## 11. 남은 DATA_COVERAGE_LIMITATION

1. 천안시에서 하드필터를 통과하는 meal_support 직접 서비스가 0건 — Top-4 "구성"이
   desired_support와 무관하게 고정되는 근본 원인. 신규 데이터 수집 전까지 해결 불가
   (이번 단계에서 수집 금지).
2. 천안시 disability_required=true 서비스 0건(Cheonan 병합 보고서에서 이미 식별된
   한계, 재확인됨) — disability 응답이 4개 후보 중 어느 것의 점수에도 영향을 주지 못함.
3. 화성/세종/울산 OWEB 후보 7건 미병합 — 다른 지역에서도 유사한 "Top-K 구성 고정"
   현상이 있을 가능성이 있으나 이번 단계 범위 밖.

## 12. 남은 LOGIC_LIMITATION

1. RELATED credit 계수(0.5)는 "현재 scale 대비 합리적인 중간값"으로 결정한 것이지,
   실사용자 피드백으로 보정된 값은 아니다 — 향후 실사용 데이터가 쌓이면 재검토 필요.
2. RELATED 관계 매핑(`RELATED_SERVICE_TYPE_TAGS`)은 5개 태그 내에서 2개 클러스터로
   수동 정의한 것으로, 새로운 `service_type` 태그가 추가되면 이 매핑도 함께 검토해야
   한다(자동으로 일반화되지 않음).
3. `nutrition_counseling` desired_support는 여전히 `service_type`에 대응 태그가 없어
   `_nutrition_component`(기존 별도 컴포넌트)에만 의존한다 — 이번 수정 범위 밖.

## 13. Streamlit 재검증이 필요한 항목

이번 단계는 recommender 코드만 수정했고 Streamlit UI/adapter는 건드리지 않았지만,
`recommend()` 반환값(특히 `match_level`이 이제 RELATED-only 경우 POSSIBLE_MATCH까지
오를 수 있게 됨)을 실제 화면에서 사람이 다시 확인할 필요가 있다:

1. 서비스 카드에 "완전히 같지는 않지만 관련이 있는 지원이에요" 신규 문구가 자연스럽게
   표시되는지(레이아웃/줄바꿈 포함)
2. Test 2(community_care)에서 `ENR-CHEONAN-01`이 실제로 HIGH_MATCH 배지로 표시되는지
3. 기존에 저장된 세션/캐시된 추천 결과가 있다면 재실행 후 결과가 달라짐을 사용자가
   혼란스러워하지 않도록 안내가 필요한지

---

## 최종 판정

**`RANKING_TUNING_VALIDATED_WITH_DATA_LIMITATIONS`**

근거: 재현→score breakdown→원인 확인→최소 수정의 순서를 지켰고, 확인된 LOGIC_ISSUE
(이진 매칭으로 인한 desired_support 순서 고정)만 최소 범위로 수정했다. desired_support는
이제 하드필터가 아닌 소프트스코어를 유지한 채 EXACT/RELATED/NEUTRAL로 세분화되어 실제
순서를 바꾸고, 국가유공자재가복지지원은 모든 시나리오에서 HIGH_MATCH에 도달하지 않으며,
disability 무효과는 데이터 부족으로 명확히 판정되어 억지로 손대지 않았다. 회귀 테스트
0건(246 passed/4 skipped), RAG/데이터/Streamlit UI 변경 없음. 다만 Top-4 "구성" 자체가
고정되는 근본 원인(§11)은 데이터 부족이라 이번 단계로 해결되지 않아 `_WITH_DATA_LIMITATIONS`로
판정한다.
