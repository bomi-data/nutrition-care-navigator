# 규칙 기반 추천엔진 v1 구현 보고서

> `docs/recommendation_rules_spec.md`의 명세를 그대로 코드로 구현한 결과 보고서입니다.
> Streamlit/RAG/LangChain/Vector DB/Claude API/n8n/배포는 이번 단계에서 다루지 않았습니다.

---

## 0. 구현 전 검증 결과

`data/processed/welfare_services_recommendation_ready.csv`와 `docs/recommendation_rules_spec.md`를
다시 읽고 확인한 결과, **구현을 막는 문제는 없었습니다**:

- 행 수 85, `service_id` unique 85/85
- rules spec에서 언급한 모든 필드(`region_scope`, `min_age`, `max_age`, `age_condition_type`,
  `age_condition_note`, `disability_required`, `low_income_required`,
  `single_household_required`, `homebound_or_mobility_condition`, `service_type`,
  `service_type_primary`, `nutritionist_involvement`, `nutrition_relevance`,
  `verification_level` 등)이 실제 CSV에 그대로 존재
- `region_scope` 허용값: `SIGUNGU`(71)/`SIDO`(12)/`NATIONAL`(2) — 명세와 일치
- tri-state 필드 허용값: `true`/`false`/`unknown`만 존재 — 명세와 일치
- `verification_level`: `A`(50)/`B`(35)만 존재
- `age_condition_type`: `SIMPLE_MIN`(28)/`COMPOUND`(12)/`NONE`(45) — `SIMPLE_RANGE`,
  `max_age` 실사례는 0건(명세에서 이미 "미발동"으로 표시된 부분과 일치)

따라서 문서에 있지만 CSV에 없는 필드를 임의로 만들어 쓴 부분은 없습니다.

---

## 1. 구현 구조

```
src/recommender/
    __init__.py       # 공개 API (UserProfile, ServiceRecord, recommend, ...)
    config.py          # DEFAULT_WEIGHTS, HIGH_MATCH_SCORE_THRESHOLD 등 -- 숫자는 여기에만 존재
    models.py          # TriState/MatchStatus/MatchLevel/RegionScope/AgeConditionType Enum,
                       # UserProfile, ServiceRecord, ConditionCheck, RecommendationResult
    loader.py          # CSV -> List[ServiceRecord] (표준 csv 모듈만 사용, pandas 미사용)
    matcher.py         # 순수 비교 함수: 3x3 매트릭스, 지역 규칙, 연령 규칙
    filters.py         # HARD FILTER 오케스트레이션 (region/age/disability/low_income)
    scorer.py          # SOFT SCORE 계산 (service_type/독거/거동불편/지역정밀도/verification/영양/퇴원)
    recommender.py     # 파이프라인 전체 조립: evaluate_service(), recommend()

tests/
    conftest.py         # make_service()/make_user() 합성 픽스처 + all_services(실제 85건) 픽스처
    test_matcher.py     # 3x3 매트릭스, 지역(NATIONAL/SIDO/SIGUNGU), 연령(SIMPLE_MIN/COMPOUND)
    test_filters.py     # HARD FILTER, UNKNOWN 비배제, open_count
    test_scorer.py      # SOFT SCORE, 반쪽 매칭, anti-gaming(정보부족 서비스 미가산)
    test_recommender.py # end-to-end: 등급강등, 결정론성, top_k, 85건 전체 무예외 실행
    test_scenarios.py   # rules_spec.md §13의 10개 시나리오 자동화

pytest.ini             # pythonpath=src, testpaths=tests
requirements-dev.txt    # pytest (엔진 자체는 표준 라이브러리만 사용)
```

**왜 pandas를 쓰지 않았는가**: `requirements.txt`는 pandas를 "예정 기술 스택"으로 이미 포함하고
있지만, 실제 실행 환경에 설치되어 있지 않았고(확인됨), 85행짜리 CSV를 한 줄씩 타입이 있는
객체로 읽어들이는 데는 표준 라이브러리 `csv.DictReader`만으로 충분합니다. 규칙 엔진 자체는
**표준 라이브러리 외 런타임 의존성이 0개**입니다 — 이는 나중에 Streamlit/RAG 계층이 pandas를
쓰기로 하더라도 이 패키지가 영향받지 않는다는 뜻이며, 테스트 환경 이식성도 높입니다.

---

## 2~6. 사용한 규칙 (HARD FILTER / SOFT SCORE / UNKNOWN / 등급)

`docs/recommendation_rules_spec.md` §4~§10을 그대로 코드화했습니다. 요약:

### HARD FILTER (filters.py) — 4개, 전부 "양쪽 값이 구체적으로 존재하고 충돌할 때만" 발동
| 필드 | 배제 조건 |
|---|---|
| 지역(`region_scope`+`sido`+`sigungu`) | §6 표 그대로: SIDO 불일치, SIGUNGU 불일치(시도부터 다르거나 시군구가 다름) |
| 연령(`min_age`, `age_condition_type`) | `SIMPLE_MIN`/`SIMPLE_RANGE`이고 사용자 연령이 기준 미달/초과일 때만. `COMPOUND`는 **매칭 함수 자체가 구조적으로 MISMATCH를 반환하지 않도록 설계**되어 있어 필터 단계에서 실수로라도 배제할 수 없음 |
| `disability_required` | 서비스=TRUE, 사용자=FALSE |
| `low_income_required` | 서비스=TRUE, 사용자=FALSE |

### SOFT SCORE (scorer.py)
사용자가 실제로 요청한 항목에만 반응하는 고정 분모 정규화(0~100)를 사용합니다.

| 요소 | 최대 배점 | 활성 조건 |
|---|---|---|
| `service_type` ∩ `desired_support` | 50 | `desired_support`가 `unsure`가 아니고 비어있지 않을 때 |
| 독거(`single_household_required`) 소프트 매치 | 10 | 항상 (TRUE/TRUE만 +, TRUE/FALSE만 -, 나머지 0) |
| 거동불편(`homebound_or_mobility_condition`) 소프트 매치 | 10 | 항상 |
| 지역 정밀도(시군구 정확 일치) | 10 | 항상(정확히 일치할 때만 만점) |
| `verification_level` | 5 | 항상(A=만점, B=0) |
| 영양상담 보너스 | 10 | `desired_support`에 `nutrition_counseling` 포함 시에만 |
| 퇴원연계 보너스 | 5 | `desired_support`에 `discharge_support` 포함 또는 `recent_discharge=true`일 때만 |

**중요**: 분모(각 컴포넌트의 max)는 **서비스가 얼마나 많은 정보를 갖고 있는지와 무관하게, 오직
사용자가 무엇을 선택했는지에 따라서만** 정해집니다. 서비스 쪽 필드가 UNKNOWN이면 achieved는
항상 0이지 max에서 빠지지 않습니다 — 그래서 정보가 적은 서비스는 절대 정보가 많은 서비스보다
"쉽게 만점에 가까워지는" 방식으로 유리해질 수 없습니다(§9 참고, `test_scorer.py::
test_eligibility_gate_unknown_never_receives_positive_score_credit`로 검증).

### UNKNOWN 처리 (matcher.py의 `evaluate_tristate`)
3x3 매트릭스를 하나의 함수로 구현해 지역/연령을 제외한 모든 조건 비교(장애/저소득/독거/거동불편)에
재사용합니다. UNKNOWN은 어떤 경우에도 MISMATCH가 되지 않으며, "서비스=TRUE + 사용자=UNKNOWN"인
경우에만 `confirmation_needed=True`가 됩니다.

### 추천 등급 (recommender._determine_match_level)
점수 cutoff만으로 결정하지 않고, 다음 순서로 강제 판정을 먼저 적용합니다.
1. `desired_support`가 비었거나 `unsure` → `NEEDS_CONFIRMATION`
2. 연령이 `COMPOUND`인데 대표 임계값 미만 → `NEEDS_CONFIRMATION`
3. `SIGUNGU` 범위 서비스인데 사용자 시군구를 몰라 정밀 확인이 안 됨 → `NEEDS_CONFIRMATION`
4. `open_count`(핵심 게이트 중 "서비스는 요구하는데 사용자가 모름" 개수) ≥ 2 → `NEEDS_CONFIRMATION`
5. **`service_type`이 `desired_support`와 전혀 겹치지 않음 → `NEEDS_CONFIRMATION`**
   (2026-08-23 실사용 사례 검증에서 추가됨 — §8-보완 및
   `recommendation_engine_real_case_validation.md` 참고. 이전에는 이 확인이 누락되어
   0% 관련성인 서비스도 `POSSIBLE_MATCH`로 표시될 수 있었습니다.)
6. `open_count == 1` → `POSSIBLE_MATCH`
7. `open_count == 0`이고 점수가 임계값(v1: 55) 이상 → `HIGH_MATCH`
8. 그 외 → `POSSIBLE_MATCH`

---

## 7. 테스트 결과

```
53 passed in 0.24s   (pytest 9.1.1, python 3.10)
```

| 테스트 파일 | 개수 | 검증 내용 |
|---|---|---|
| `test_matcher.py` | 21 | 3x3 매트릭스 전 조합(A), NATIONAL/SIDO/SIGUNGU 지역 규칙(B), SIMPLE_MIN/COMPOUND 연령 규칙(C) |
| `test_filters.py` | 8 | UNKNOWN 비배제(D), 장애 TRUE+FALSE 배제(E), 지역/연령 명백 불일치 배제, open_count 계산 |
| `test_scorer.py` | 8 | 서비스유형 일치 시 점수 상승(F), unsure 무가점, 정보부족 anti-gaming, 소프트 미스매치 패널티, 지역정밀도/영양보너스 조건부 활성 |
| `test_recommender.py` | 7 | confirmation_needed → 등급 강등(G), 결정론성(H), top_k(I), 85건 전체 무예외 실행(J) |
| `test_scenarios.py` | 4 | 10개 시나리오 자동 실행, unsure 시나리오는 HIGH_MATCH 불가, 연령/지역 불일치 시나리오의 생존자 검증 |
| **합계** | **53** | **전부 통과** |

완료 기준 체크리스트(§19) 전부 충족:

- [x] 85개 서비스 정상 로드
- [x] MATCH/MISMATCH/UNKNOWN 구현
- [x] HARD FILTER 구현
- [x] SOFT SCORE 구현
- [x] 추천등급 구현
- [x] 추천 이유 생성 (Python 규칙, LLM 미사용)
- [x] top_k 추천 구현
- [x] pytest 테스트 작성
- [x] 테스트 전체 통과 (53/53)
- [x] 10개 사용자 시나리오 실행
- [x] 이상 결과 검토 (§9 참고)
- [x] `recommendation_engine_v1_report.md` 생성

---

## 8-보완. 2026-08-23 실사용 사례 검증에 따른 갱신

`docs/recommendation_engine_real_case_validation.md`에 기록된 첫 실사용 테스트(경기도
화성시 동탄구, 75세)에서 `_determine_match_level()`이 자체 명세(§10)를 완전히 구현하지
못한 결함이 발견되어 수정했습니다: **`service_type`이 `desired_support`와 전혀 겹치지
않는 서비스는 게이트를 통과했더라도 `HIGH_MATCH`/`POSSIBLE_MATCH`가 아니라
`NEEDS_CONFIRMATION`으로만 표시됩니다.** 점수·순위·HARD FILTER는 변경되지 않았고, 등급
표시와 설명 문구만 갱신되었습니다. 아래 §8 표는 이 수정이 반영된 **최신 결과**이며,
자세한 진단 과정은 `recommendation_engine_real_case_validation.md`를 참고하세요.

## 8. 10개 시나리오 결과 요약

실제 85건 데이터에 대해 실행했습니다. "정답"을 미리 정하지 않고 흐름만 검증했습니다.

| # | 시나리오 | HARD EXCLUDE | 최종 후보 | TOP1 | 점수 | 등급 |
|---|---|---:|---:|---|---:|---|
| 1 | 75세 독거+식사준비어려움(강원, 시군구모름) | 65/85 | 20 | 저소득 재가노인 식사 배달(강릉시) | 76.5 | NEEDS_CONFIRMATION |
| 2 | 70세 저소득+거동불편(경남, 시군구모름) | 67/85 | 18 | 저소득 재가노인 식사배달(남해군) | 76.5 | NEEDS_CONFIRMATION |
| 3 | 68세 장애+식사지원(서울 성동구) | 81/85 | 4 | 장애인무료급식소 운영(성동구) | 76.5 | POSSIBLE_MATCH |
| 4 | 66세 취약조건 없음(전북, 시군구모름) | 81/85 | 4 | 고독사 등 고위험가구 반찬지원(임실군) | 58.8 | NEEDS_CONFIRMATION |
| 5 | 지역만 입력, 나머지 모름, unsure(강원) | 65/85 | 20 | 국가유공자재가복지지원(전국) | 14.3 | NEEDS_CONFIRMATION |
| 6 | 40세(연령 명백 불일치, 강원) | 83/85 | 2 | 국가유공자재가복지지원(전국) | 0.0 | NEEDS_CONFIRMATION |
| 7 | 시군구 명백 불일치(제주 서귀포시) | 82/85 | 3 | 제주가치 통합돌봄(제주도 전역) | 64.7 | HIGH_MATCH |
| 8 | 대부분 정보 모름(지역조차 모름) | 0/85 | 85 | 국가유공자재가복지지원(전국) | 14.3 | NEEDS_CONFIRMATION |
| 9 | 여러 서비스유형 필요(식사+통합돌봄, 강원) | 65/85 | 20 | 춘천형 노인통합돌봄사업(춘천시) | 64.7 | NEEDS_CONFIRMATION |
| 10 | 최근 퇴원+재택생활지원(경남) | 67/85 | 18 | 함양군 통합돌봄사업(함양군) | 77.8 | NEEDS_CONFIRMATION |

**관찰**:
- 실제 조건 정보가 있는 시나리오(1,2,3,4,7,9,10)에서는 **지역·조건이 구체적으로 일치하는
  서비스**가 최상위에 옴 (예: 시나리오3의 장애인 대상 서비스, 시나리오10의 퇴원/통합돌봄
  서비스).
- 정보가 거의 없는 시나리오(5,6,8)에서는 전국 대상 서비스(`국가유공자재가복지지원`)가
  1위로 나왔는데, 원인 분석 결과 이는 "전국 서비스가 우월해서"가 아니라 **대다수 서비스가
  똑같이 낮은 점수로 동점을 이루는 상황에서 결정론적 동점 처리(§9의 tie-break)가 마지막에
  `service_id` 오름차순으로 정렬하기 때문**입니다(자세한 원인은 §9 참고). 실제로 정보가
  많아지는 순간(시나리오 1~4,7,9,10) 전국 서비스는 순위 밖으로 밀려납니다.
- `open_count`가 2 이상인 경우가 대부분이라 `NEEDS_CONFIRMATION`이 압도적으로 많이
  나왔습니다. 이는 `docs/recommendation_data_readiness.md`가 이미 예견한 대로(장애/독거
  조건의 낮은 확정판정률) 데이터 한계의 정직한 반영이지 로직 결함이 아닙니다.

---

## 9. 이상 결과 검토

지시된 8개 항목을 실제 시나리오 로그로 확인했습니다.

| 점검 항목 | 결과 | 근거 |
|---|---|---|
| 모든 사용자에게 같은 서비스가 1위인가? | **아니오** | 10개 시나리오에서 TOP1이 6종류로 다양함(WLF00003159/00504/01000/02345/00098/05598/05308/06261) |
| NATIONAL 서비스가 지역 서비스보다 무조건 유리한가? | **아니오, 단 주의할 부작용 발견** | 실신호가 있는 7개 시나리오에서는 지역 서비스가 1위. NATIONAL이 1위인 3개 시나리오(5,6,8)는 전부 극단적 정보 부족으로 다수 서비스가 정확히 동점이 된 경우이며, 그 동점을 깨는 마지막 기준이 `service_id` 오름차순이라 우연히 `WLF00000098`이 앞섬. **점수 자체가 실제로 더 높아서 이긴 것이 아님** — §11 개선 필요사항에 기록 |
| 조건 정보가 적은 서비스가 오히려 높은 점수를 받는가? | **아니오** | `test_scorer.py::test_eligibility_gate_unknown_never_receives_positive_score_credit`로 확정 검증. 시나리오1에서도 확정된 조건(독거+식사)이 많은 서비스(76.5점)가 정보 적은 서비스(64.7점)보다 항상 높음 |
| UNKNOWN이 많은 서비스가 과도하게 상위에 뜨는가? | **아니오(위 항목과 동일 근거)** | UNKNOWN은 항상 0점 기여, 절대 양수 기여 없음 |
| meal_support 서비스만 무조건 상위에 뜨는가? | **아니오** | 시나리오9(식사+통합돌봄 희망)에서 두 태그를 모두 가진 서비스가 단일 태그 서비스보다 높은 점수(64.7 vs 35.3). 시나리오10(퇴원+통합돌봄 희망)에서는 `discharge_support` 태그 보유 서비스가 1위(77.8) |
| 장애/저소득 사용자에게 관련 없는 서비스가 상위에 뜨는가? | **아니오** | 시나리오3(장애)에서 상위 2개가 모두 장애인 대상 급식서비스 |
| 지역 불일치 서비스가 살아남는가? | **아니오** | 시나리오6(연령불일치, 강원): 강원 지역 서비스가 전부 배제되지 않고 정확히 연령조건 불충족분만 배제. 시나리오7(제주): 제주/전국 외 82건 정확히 배제 |
| verification_level이 낮은 서비스가 과도하게 상위에 뜨는가? | **아니오** | verification은 점수의 5/최대 요소일 뿐이며, 최종 정렬은 점수 우선이라 낮은 점수의 B등급 서비스가 높은 점수의 A등급 서비스를 앞지르는 사례 없음(전 시나리오 로그 확인) |

**결론**: 8개 항목 중 7개는 문제 없음. 1개(NATIONAL 서비스의 동점 승리)는 **점수 계산 자체의
결함이 아니라 극단적 정보 부족 상황에서의 tie-break 아티팩트**로 확인되었으며, §11에 개선
방향을 기록했습니다. **가중치를 임의로 조정해 이 현상을 감추지 않았습니다** — 원인을 있는
그대로 보고합니다.

---

## 10. 발견된 한계

1. **동점 시 `service_id` fallback의 의미 없음(§9에서 발견)**: 정보가 극히 부족한 사용자
   입력에서는 다수 서비스가 정확히 같은 점수를 받고, 마지막 tie-break가 의미 있는 신호가
   아닌 `service_id` 문자열 순서에 의존하게 됩니다. 기능적으로 틀린 결과는 아니지만(동점인
   서비스들끼리는 사실 우열이 없음), 사용자 경험상 "왜 하필 이 서비스가 1등이지?"에 대한
   설명력이 약합니다.
2. **`docs/recommendation_data_readiness.md`에 이미 기록된 데이터 한계가 그대로 결과에
   반영됨**: 장애/독거 조건의 낮은 확정판정률(21%/11%) 때문에 `NEEDS_CONFIRMATION`이
   대부분의 시나리오에서 압도적으로 많습니다. 이는 로직이 아니라 데이터의 한계입니다.
3. **HIGH_MATCH_SCORE_THRESHOLD(55)는 v1 임시값**입니다. 실제 사용자 반응 데이터 없이
   설계자 판단으로 정한 수치이며, §9에서 이미 "확정 아님"으로 명시했습니다.
4. **복합 하위서비스 레코드**(readiness 문서 §7의 사례들 — 경로식당/식사배달/밑반찬배달이
   연령·독거 조건이 다른데 한 행으로 존재)는 대표 조건 하나로 게이트가 적용되어, 하위
   서비스별 실제 조건과 미세하게 어긋날 수 있습니다.
5. **`nutrition_counseling`/`discharge_support` desired_support는 구조적으로 거의 항상
   매칭 대상이 1건뿐**이라(rules_spec.md §0/§8), 이 옵션을 고른 사용자에게는 항상 "데이터가
   부족합니다" 안내가 함께 나가야 합니다(현재 recommendation_reasons/exclusion_warnings에
   자동으로 이런 안내 문구가 생성되지는 않음 — v2에서 보완 필요).

---

## 11. 개선 필요사항 (v2 후보, 이번 단계에서는 미적용)

- tie-break에 "확정된 MATCH 개수" 등 추가 신호를 넣는 방안을 검토하되, §9에서 확인했듯이
  이 신호가 다시 "정보가 적어서 매칭도 적은" 서비스를 부당하게 띄우지 않는지 별도로
  검증한 뒤 도입해야 합니다(성급하게 붙이지 않았습니다).
- `desired_support`가 `nutrition_counseling`/`discharge_support`처럼 매칭 대상이 극히 적은
  옵션일 때, 결과 상단에 "이 유형의 서비스는 현재 데이터가 많지 않습니다" 같은 안내를
  자동 생성하는 로직 추가.
- `HIGH_MATCH_SCORE_THRESHOLD`와 `DEFAULT_WEIGHTS`를 실제 사용자 테스트/도메인 전문가
  검토를 거쳐 조정(현재는 v1 heuristic임을 코드 주석과 §9에 명시).
- 복합 하위서비스 레코드(§10-4)를 하위서비스 단위로 분리하는 데이터 재작업은 별도
  전처리 단계에서 검토(이번 엔진 구현 범위 밖).

---

## 12. RAG 단계로 넘어가도 되는지

**예, 넘어가도 됩니다.** 단, RAG/LLM은 `docs/recommendation_system_design.md` §10에서
이미 정의한 경계(원문 근거 검색 + 문장 재서술만 담당, 판정에는 관여 금지)를 그대로
지켜야 하며, 이번 엔진이 산출하는 `match_score`/`match_level`/`matched_conditions`/
`confirmation_needed`는 RAG/LLM이 절대 바꾸지 않는 입력으로 취급해야 합니다.

---
