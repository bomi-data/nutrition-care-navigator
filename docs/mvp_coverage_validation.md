# MVP Coverage & v1.2 검증 보고서

> 이 단계는 **MEASURE → ANALYZE → DECIDE**까지만 수행했습니다. 코드/CSV/RAG/UI 질문을
> 수정하지 않았고, score 조정이나 새 eligibility rule을 추가하지 않았습니다. 아래 모든 수치는
> 실제 85개 서비스 데이터와 실제 `recommend()` 파이프라인 실행 결과입니다.

---

## 1. Executive Summary

- v1.2에서 수정한 3개 로직 버그(시군구 세부구 fallback, 특수자격 게이트, meal_preparation
  배선)가 **Streamlit 실제 사용자 흐름에서도 정상 작동**함을 6개 시나리오로 확인했습니다.
- 대표 profile 8종 × 지역 8곳(64개 조합) 실측 결과, **Top-5 미달 원인의 78.6%는
  REGION_DATA_COVERAGE(지역 데이터 부족), 21.4%는 SUPPORT_TYPE_COVERAGE(해당 지역에 원하는
  서비스 유형 자체가 없음)였고, 로직 결함(FILTER_LOGIC)으로 분류된 사례는 0건**이었습니다.
- 85개 서비스는 **17개 광역자치단체 중 14개**에만 존재하며, **세종특별자치시·울산광역시는
  SIGUNGU/SIDO 서비스가 0건**입니다(NATIONAL 2건만 항상 노출).
- `recent_discharge`(퇴원 후 지원) 입력은 대응 서비스가 85건 중 **1건**뿐이라 사실상
  정보가치가 낮습니다. `single_household`(독거)도 9건(10.6%)뿐입니다.
- **최종 판정: `DATA_ENRICHMENT_RECOMMENDED`** — MVP 시연 자체는 가능하지만, "우리동네"라는
  제품명이 약속하는 지역 커버리지를 실질적으로 채우려면 데이터 보강이 다음 우선순위입니다.

---

## 2. Streamlit Scenario 검증 결과

`app/streamlit_app.py`가 실제로 호출하는 것과 동일한 `recommend()` + `HardFilterResult` 조합으로
검증했습니다(§9의 기존 `tests/test_streamlit_app_ui.py`도 재실행해 UI 위젯 조작 경로 자체가
v1.2 이후에도 무사함을 재확인 — 11 passed).

### Scenario A — 화성시 고령 저소득 식사지원

| 항목 | 값 |
|---|---|
| 전체 서비스 | 85 |
| HARD FILTER 이후 후보 | 3 |
| 최종 추천 수 | 3 |

| 순위 | service_id | 서비스명 | score | level | 지역 scope | confirmation_needed |
|---|---|---|---:|---|---|---|
| 1 | WLF00004001 | 저소득 재가노인 식사배달 | 73.7 | **HIGH_MATCH** | SIDO(경기도) | 없음 |
| 2 | WLF00000098 | 국가유공자재가복지지원 | 15.8 | NEEDS_CONFIRMATION | NATIONAL | 특수 자격요건(보훈) |
| 3 | WLF00003248 | 재가급여 | 15.8 | NEEDS_CONFIRMATION | NATIONAL | 특수 자격요건(장기요양등급) |

1위의 `matched_conditions`: 거주 시/도 일치, 연령 조건(60세 이상) 충족, 저소득 해당, 거동불편
해당, 원하시는 도움(meal_support)과 일치 — 5개 전부 확정 MATCH, `confirmation_needed=[]`.

### Scenario B — 장애 여부만 변경 (아니오 → 예)

**결과: 완전히 동일** (3개 서비스, score/순위 모두 무변화).

- 새로 등장/사라진 서비스: 없음
- 원인 분류: **DATA_COVERAGE_LIMITATION** — 화성시 후보 3건 중 `disability_required`가
  구조화된 서비스가 0건이라(WLF00004001=unknown, 나머지 2건도 unknown), disability 입력이
  영향을 줄 수 있는 대상 자체가 없습니다. (참고: 서울 성동구처럼 disability 구조화 서비스가
  실제로 있는 지역에서는 동일 입력이 후보 2→4건, 1위 서비스 교체까지 일으킴 —
  `docs/recommendation_engine_v1_2_validation.md` §3/§4에 이미 검증됨.)

### Scenario C — desired_support 변경 (meal_support → community_care)

먼저 화성시 후보 풀의 실제 service_type 다양성을 확인: **`{'meal_support', 'home_visit'}` 2종뿐,
`community_care`는 0건**입니다.

| 순위 | service_id | Before(meal_support) | After(community_care) |
|---|---|---|---|
| WLF00004001 | score/level | 73.7 / HIGH_MATCH | **21.1 / NEEDS_CONFIRMATION** |
| WLF00000098 | score/level | 15.8 / NEEDS_CONFIRMATION | 15.8 / NEEDS_CONFIRMATION(변화없음) |
| WLF00003248 | score/level | 15.8 / NEEDS_CONFIRMATION | 15.8 / NEEDS_CONFIRMATION(변화없음) |

desired_support 변경은 **확실히 큰 영향**을 줍니다(1위가 HIGH_MATCH→NEEDS_CONFIRMATION으로
강등). 다만 화성시에는 애초에 `community_care` 서비스가 없어 "이걸로 바꾸면 더 나은 서비스가
나온다"는 의미는 아니고, "요청과 안 맞으니 등급이 낮아진다"는 올바른 방향의 변화입니다.

### Scenario D — meal_preparation_difficulty 변경 (예 → 아니오)

v1.2에서 새로 연결된 조건이 실제로 작동하는지 확인:

| service_id | Before(예=TRUE) | After(아니오=FALSE) | 차이 |
|---|---:|---:|---|
| WLF00004001(meal_support) | 73.68 | 70.59 | **-3.09** (보너스 소멸) |
| WLF00000098(home_visit) | 15.79 | 17.65 | +1.86 (분모 축소로 상대적 상승) |
| WLF00003248(home_visit) | 15.79 | 17.65 | +1.86 (동일 이유) |

**정상 작동 확인.** meal_support 서비스는 확실히 낮아지고, 무관한 서비스는 분모 효과로 소폭
상대 상승합니다(기존 discharge_bonus와 동일한 이미 검증된 패턴).

### Scenario E — 전주시 덕진구 (v1.1→v1.2 지역 fallback 검증)

정보가 부족한 일반 고령자 profile로 확인:

| 순위 | service_id | 서비스명 | score | level | 지역 scope |
|---|---|---|---:|---|---|
| 1 | **WLF00002047** | 저소득 거동불편 장애인도시락배달 | 70.6 | NEEDS_CONFIRMATION | **SIGUNGU(전주시)** |
| 2 | WLF00000098 | 국가유공자재가복지지원 | 5.9 | NEEDS_CONFIRMATION | NATIONAL |
| 3 | WLF00003248 | 재가급여 | 5.9 | NEEDS_CONFIRMATION | NATIONAL |

**전주시 단위 서비스(WLF00002047)가 전주시 덕진구 사용자에게 정상적으로 후보에 포함됩니다**
(`matched_conditions`에 "거주 시군구까지 일치해요(같은 시/군 내 세부 구 단위 차이)." 문구로
fallback 경로임을 명시). v1.1에서는 이 서비스가 완전히 탈락했던 사례입니다
(`recommendation_engine_v1_2_validation.md` §region 참고). NEEDS_CONFIRMATION인 이유는 이
서비스가 장애/저소득을 모두 요구하는데 사용자가 둘 다 UNKNOWN이라 `open_count=2`가 되었기
때문이며, 지역 매칭 자체와는 무관합니다.

### Scenario F — 특수 자격 서비스 (일반 고령자, 특수자격 UNKNOWN)

춘천시(서비스 유형이 다양해 home_visit도 실제로 일치 가능한 지역) 기준:

| service_id | score | level | HIGH_MATCH 여부 |
|---|---:|---|---|
| WLF00000098(국가유공자재가복지지원) | 64.7 | **POSSIBLE_MATCH** | 아니오 |
| WLF00003248(재가급여) | 64.7 | **POSSIBLE_MATCH** | 아니오 |
| (참고) WLF00005308(춘천형 노인통합돌봄, 실제 지역 서비스) | 76.5 | HIGH_MATCH | — |

**확인됨: 특수자격 미확인 일반 사용자는 두 서비스 모두 HIGH_MATCH를 받지 않습니다**
(`confirmation_needed`에 "특수 자격요건이 필요해요(국가유공자·보훈.../장기요양등급...)" 문구가
포함되어 목록에서 삭제되지 않고 안내됨).

---

## 3. 화성시 Before/After 분석

| 항목 | v1.1(수정 전, 참고) | v1.2(수정 후) |
|---|---|---|
| 화성시 **동탄구** 선택 시 후보 | 3건 (SIDO 1 + NATIONAL 2, 세부구 자체는 원래도 영향 없음 — 화성시는 시 단위로도 0건) | 3건 (동일 — 데이터 자체가 없어 변화 없음) |
| 화성시 **(시 단위)** 선택 시 후보 | 3건 | 3건 |
| 1위 서비스 | WLF00004001 | WLF00004001 (동일) |
| 1위 match_level | HIGH_MATCH | HIGH_MATCH (동일) |

**화성시는 v1.2 수정으로 후보 수가 늘지 않습니다** — 이는 실패가 아니라 정확한 진단입니다.
화성시 문제의 원인은 세부구 granularity(그건 전주시 사례처럼 실제로 존재하는 시 단위 서비스가
있을 때만 발동)가 아니라, **애초에 화성시 소재 서비스 자체가 85건 중 0건**이기 때문입니다
(§4에서 정량 확인). v1.2가 고친 것은 "전주시 덕진구처럼 실제로 존재하는데 잘못 탈락하던 사례"이지,
"애초에 존재하지 않는 사례"가 아닙니다 — 이 구분이 정확히 지켜졌음을 재확인합니다.

---

## 4. 지역 Coverage (정량)

### 4.1 시/도별 서비스 수

| 시/도 | 전체 | SIGUNGU | SIDO | meal_support(SIGUNGU) | disability=true(SIGUNGU) | low_income=true(SIGUNGU) |
|---|---:|---:|---:|---:|---:|---:|
| 강원특별자치도 | 18 | 18 | 0 | 18 | 0 | 16 |
| 경상남도 | 16 | 15 | 1 | 15 | 0 | 13 |
| 서울특별시 | 7 | 7 | 0 | 6 | **4** | 6 |
| 전남광주통합특별시 | 8 | 5 | 3 | 4 | 0 | 3 |
| 전북특별자치도 | 7 | 7 | 0 | 7 | 1 | 5 |
| 경기도 | 6 | 5 | 1 | 5 | 1 | 2 |
| 부산광역시 | 5 | 2 | 3 | 2 | 0 | 1 |
| 충청남도 | 4 | 4 | 0 | 4 | 2 | 4 |
| 충청북도 | 4 | 4 | 0 | 4 | 2 | 4 |
| 대구광역시 | 3 | 2 | 1 | 2 | 0 | 2 |
| 경상북도 | 2 | 2 | 0 | 2 | 1 | 1 |
| 대전광역시 | 1 | 0 | 1 | — | — | — |
| 인천광역시 | 1 | 0 | 1 | — | — | — |
| 제주특별자치도 | 1 | 0 | 1 | — | — | — |
| **세종특별자치시** | **0** | 0 | 0 | — | — | — |
| **울산광역시** | **0** | 0 | 0 | — | — | — |
| (NATIONAL, 지역무관) | 2 | — | — | — | — | — |

**핵심 발견**: 17개 광역자치단체 중 **세종특별자치시·울산광역시는 0건**입니다(NATIONAL 2건만
항상 노출). `region_codes.csv`에는 두 지역 모두 선택지로 존재하므로, 사용자가 이 지역을
선택하면 **항상 NATIONAL 2건만** 받게 됩니다.

### 4.2 특정 지역 4곳 상세 (지침 §2-1 지정)

| 지역 | 정확 SIGUNGU | SIDO 전역 | NATIONAL | 합계 |
|---|---:|---:|---:|---:|
| 경기도 화성시 | 0 | 1 | 2 | **3** |
| 서울특별시 성동구 | 2 | 0 | 2 | **4** |
| 충청남도 천안시 | 0 | 0 | 2 | **2** |
| 전북특별자치도 전주시 | 1 | 0 | 2 | **3** |
| 전주시 덕진구 (v1.2 fallback 적용) | 1(fallback) | 0 | 2 | **3** |

**천안시가 화성시보다 더 적습니다(2건)** — 충청남도는 SIGUNGU-scope 4건이 있지만(§4.1) 전부
다른 시/군 소재입니다.

---

## 5. 지원유형(service_type) Coverage

실제 taxonomy(`SERVICE_TYPE_TAGS`, `recommender/models.py`, 무수정 확인) 5종 + 미사용 1종:

| service_type | 건수 | 비율 | NATIONAL | SIDO | SIGUNGU |
|---|---:|---:|---:|---:|---:|
| `meal_support` | 81 | 95.3% | 0 | 12 | 69 |
| `community_care` | 12 | 14.1% | 0 | 4 | 8 |
| `home_visit` | 6 | 7.1% | 2 | 1 | 3 |
| `food_cost_support` | 1 | 1.2% | 0 | 0 | 1 |
| `discharge_support` | 1 | 1.2% | 0 | 0 | 1 |
| `nutrition_counseling`/`nutrition_education` | 0 | 0% | — | — | — |

(`nutrition_counseling`은 classification_criteria.md/rules_spec.md §0이 이미 "실제 태그 0건"으로
문서화한 내용을 재확인함 — 새로운 발견 아님.)

`service_type_primary`: `meal_support` 72 / `community_care` 10 / `home_visit` 2 /
`food_cost_support` 1 (85건 전부 채워짐, 무수정 확인).

---

## 6. 사용자 조건 Coverage

| 필드 | TRUE/required | FALSE/not required | UNKNOWN |
|---|---:|---:|---:|
| `disability_required` | 12 (14.1%) | 6 (7.1%) | 67 (78.8%) |
| `low_income_required` | 64 (75.3%) | 8 (9.4%) | 13 (15.3%) |
| `single_household_required` | 9 (10.6%) | 0 (0%) | 76 (89.4%) |
| `homebound_or_mobility_condition` | 37 (43.5%) | 0 (0%) | 48 (56.5%) |
| `special_eligibility_required`(v1.2 신규) | 2 (2.4%) | 0 | 83 (97.6%) |
| `min_age`(숫자 확정) | 39 (45.9%) | — | 46 (54.1%, `age_condition_type=NONE`) |
| `discharge_support` 태그 보유(=`recent_discharge` 관련성 proxy) | 1 (1.2%) | — | — |

**"UI에서 질문은 하지만 데이터에서 거의 안 쓰이는 변수" 후보**:
- `recent_discharge` — 대응 서비스 1/85건(1.2%)뿐. **가장 낮음.**
- `single_household_required` — 9/85건(10.6%). 두 번째로 낮음.
- `disability_required` — 12/85건(14.1%)로 낮지만, §2 Scenario B(성동구 대비)에서 확인했듯
  **있을 때는 영향력이 매우 큽니다** — "빈도가 낮다"와 "가치가 없다"는 다릅니다(§7에서 구분).

---

## 7. UI 질문 정보가치 분석

| 질문 | 데이터 등장 빈도 | 필터 영향 | 랭킹 영향 | 정보가치 | 제안 |
|---|---|---|---|---|---|
| 지역(시/도+시/군/구) | SIGUNGU 71/85(83.5%) 대상 | **최상**(HARD, §2/§10 Top-K 분석에서 부족 원인의 78.6% 차지) | 중(정밀도 보너스 10점) | **HIGH** | **KEEP** (필수) |
| 원하는 도움(desired_support) | service_type 85/85(100%) | 없음(SOFT지만 사실상 등급 좌우, rule 5) | **최상**(50점 만점, Scenario C에서 -52.6점 확인) | **HIGH** | **KEEP** (필수) |
| 저소득(low_income) | 72/85(84.7%, true+false) | **높음**(HARD, Scenario 3에서 HARD EXCLUDE 실증) | 없음(게이트 전용) | **HIGH** | **KEEP** (필수) |
| 연령(age) | 39/85(45.9%) 숫자 확정 | 중(HARD, SIMPLE_MIN만) | 없음(게이트 전용) | **MEDIUM** | **KEEP** (필수) |
| 거동불편(mobility) | 37/85(43.5%) | 없음(SOFT) | 중(10점, Scenario B 유사 사례서 실증) | **MEDIUM** | **KEEP** |
| 장애(disability) | 18/85(21.2%, true+false) | 낮은 빈도지만 **HARD**(있으면 강한 영향, 성동구 사례 2→4건+1위 교체) | 없음(게이트 전용) | **MEDIUM**(빈도 낮음 + 영향力 큼의 조합) | **KEEP** |
| 식사준비 어려움(meal_preparation) | service_type 경유 81/85(95.3%) | 없음(SOFT) | 중(v1.2 신규, ±3점대 실증) | **MEDIUM** | **KEEP** |
| 독거(single_household) | 9/85(10.6%) | 없음(SOFT) | 낮음(대부분 UNKNOWN이라 0) | **LOW** | **KEEP**(사회적 의미 + 향후 데이터 확장 가치, 삭제 비권장) |
| 최근 퇴원(recent_discharge) | 1/85(1.2%) | 없음(SOFT) | 매우 낮음(discharge_bonus 5점, 사실상 항상 0) | **LOW** | **OPTIONAL**(design doc §2가 이미 "선택" 입력으로 설계 — 현재도 필수처럼 안 보이면 정상. 삭제는 비권장 — "영양돌봄" 제품 정체성상 퇴원 후 영양연계는 향후 데이터 보강 시 핵심 후보) |

**REMOVE_CANDIDATE로 분류한 항목: 없음.** 지침이 요청한 대로 LOW라고 즉시 삭제를 제안하지
않았습니다 — `recent_discharge`/`single_household` 모두 사회복지 기획 의미가 있고, §13의
데이터 보강이 이루어지면 정보가치가 즉시 올라갈 수 있는 항목입니다.

---

## 8. Top-K 부족 원인 정량 분석

**Profile 8종 × 지역 8곳 = 64개 조합**을 실행했습니다(대표성 있는 profile matrix, 무작위 생성
아님 — 지침 §5가 예시한 8종 그대로 사용).

지역: 강원 속초시(밀집), 경남 고성군(밀집), 서울 성동구(장애 데이터 有), 경기 화성시(희소),
충남 천안시(희소), 전북 전주시 덕진구(v1.2 fallback 사례), 제주(SIDO만 존재), 인천 부평구(SIDO만
존재).

### 결과 수 분포

| 결과 수 | 조합 수 | 비율 |
|---:|---:|---:|
| 5 | 8 | 12.5% |
| 4 | 16 | 25.0% |
| 3 | 32 | 50.0% |
| 2 | 8 | 12.5% |
| 1 | 0 | 0% |
| **0** | **0** | **0%** |

**0건 발생 사례가 없었습니다** — NATIONAL 2건이 사실상 모든 지역/조건에서 최소한의 fallback을
보장합니다(HARD gate가 NATIONAL 서비스를 배제하려면 나이/장애/소득이 명확히 충돌해야 하는데,
NATIONAL 2건은 그 조건들이 대부분 unknown/false라 충돌이 거의 발생하지 않음).

### 원인 분류 (Top-5 미달 56개 조합 기준)

| 원인 | 건수 | 비율 |
|---|---:|---:|
| REGION_DATA_COVERAGE | 44 | 78.6% |
| SUPPORT_TYPE_COVERAGE | 12 | 21.4% |
| REAL_ELIGIBILITY_LIMIT | 0 | 0% |
| SPECIAL_ELIGIBILITY | 0 | 0% |
| FILTER_LOGIC | 0 | 0% |
| UNKNOWN/OTHER | 0 | 0% |

**REGION_DATA_COVERAGE가 압도적 1위(78.6%)** — 지역 자체에 존재하는 서비스 수가 5건에 못
미치는 경우가 원인의 대부분입니다. SUPPORT_TYPE_COVERAGE(21.4%)는 전부 `7_discharge+mobility`
profile(desired_support=community_care)이 `community_care` 서비스가 없는 지역에 배정된
경우였습니다. **로직 문제(FILTER_LOGIC)로 분류된 사례는 0건** — v1.2 수정 이후 대표 profile
matrix에서 새로운 로직 결함은 발견되지 않았습니다.

---

## 9. 특수자격 처리 검증

§2 Scenario F에서 실측 확인한 대로, 특수자격이 필요한 2개 서비스(WLF00000098/WLF00003248)는
일반 사용자에게 **POSSIBLE_MATCH 상한**을 유지하며(HIGH_MATCH 0건), 목록에서 삭제되지 않고
`confirmation_needed`에 구체적 문구("국가유공자·보훈보상대상자 등...", "장기요양보험
등급판정...")로 안내됩니다. 64개 profile×region 조합 전체에서 이 두 서비스가 HIGH_MATCH로
노출된 사례는 **0건**이었습니다.

---

## 10. 데이터 한계

1. 세종특별자치시·울산광역시: **완전 공백**(0건).
2. 전남광주통합특별시라는 표기가 실제로 광주광역시를 포함하는지 여부는 `region_codes.csv`와
   서비스 CSV가 서로 일치(둘 다 "전남광주통합특별시" 사용)하므로 **매칭 버그는 아님** —
   다만 사용자가 "광주광역시"라는 익숙한 이름을 찾다가 혼란을 겪을 수 있는 **명칭 인지 문제**로
   기록해 둡니다(코드 변경 없이 확인만 함).
3. `recent_discharge`(1건), `single_household_required`(9건), `disability_required`(12건)
   구조화 데이터가 희소합니다.
4. `food_cost_support`/`discharge_support` service_type 자체가 각 1건뿐입니다.

## 11. 추천엔진 로직 한계

- 이번 64개 조합 분석에서 **새로운 로직 결함은 발견되지 않았습니다**(§8, FILTER_LOGIC 0건).
- `recommendation_engine_v1_2_validation.md`가 이미 남긴 한계(NATIONAL tie-break 아티팩트,
  `single_household`/`mobility` 낮은 구조화율)는 이번 분석에서도 동일하게 재확인되었을 뿐,
  악화되거나 새로 발견되지는 않았습니다.

## 12. 데이터 보강 필요성 판단 (Q1~Q9)

**Q1. 85개 서비스가 MVP 시연에 충분한가?**
부분적으로 그렇습니다. 로직 자체는 건강하고(§8), 데이터가 있는 지역(강원/경남/서울 등)에서는
민감도 있는 추천이 실제로 나옵니다. 다만 "우리동네"라는 제품 컨셉을 17개 광역자치단체 전역에서
동일한 신뢰도로 시연하기에는 **부족**합니다.

**Q2. 화성시 결과 부족이 정량 분석에서도 데이터 문제로 유지되는가?**
**예.** §3/§4에서 화성시는 v1.2 수정 전후 완전히 동일한 3건이며, 이는 SIGUNGU-scope 서비스가
0건이라는 사실 하나로 전부 설명됩니다.

**Q3. 특정 지역에서 서비스가 지나치게 적은가?**
**예.** 세종/울산 0건, 화성시/천안시 등 다수 대도시가 SIGUNGU 기준 0건입니다(§4.1).

**Q4. meal_support 서비스 자체가 부족한가?**
**아니오.** 81/85(95.3%)로 오히려 가장 풍부합니다. 문제는 총량이 아니라 **지역 분포**입니다
(강원·경남에 집중, 세종/울산/화성시/천안시 등에는 0건).

**Q5. disability 관련 서비스가 부족한가?**
**예.** 12/85(14.1%)이며, 그마저 서울/경기/충남/충북/경북 5개 시도에만 존재합니다(§4.1).

**Q6. recent_discharge 관련 서비스가 부족한가?**
**예, 가장 부족합니다.** 1/85(1.2%)뿐입니다.

**Q7. UI에서 받지만 데이터가 거의 활용 못하는 항목이 있는가?**
**예.** `recent_discharge`(1건)와 `single_household_required`(9건)가 해당합니다(§6-7).

**Q8. 추천엔진을 더 튜닝해야 하는가, 데이터를 보강해야 하는가?**
**데이터 보강이 우선입니다.** §8에서 확인했듯 Top-K 부족의 78.6%+21.4%=100%가
데이터/서비스유형 커버리지 문제이고 로직 문제는 0%였습니다. 로직을 더 튜닝해도 존재하지 않는
서비스를 만들어낼 수는 없습니다.

**Q9. 데이터 보강이 필요하다면 어떤 데이터를 우선해야 하는가?**
§13 참고.

## 13. 데이터 보강 우선순위 제안

**P0 — MVP 신뢰성에 직접 영향**

| 항목 | 필요한 데이터 | 왜 필요한가 | 해결하는 gap | 연결되는 입력 | 예상 개선 | 원천 형태 |
|---|---|---|---|---|---|---|
| 지역 커버리지 확장 | 세종/울산 포함, 현재 SIGUNGU 0건 지역(화성시·천안시 등 대도시) 위주 신규 서비스 | §8에서 Top-K 부족의 78.6%가 이 문제 | REGION_DATA_COVERAGE | 시/도, 시/군/구 | 대부분 지역에서 Top-5 정상 도달 | **CSV/OPEN_API** — `data_source_plan.md` A장의 한국사회보장정보원_지자체복지서비스 API(data.go.kr/data/15108347) — 이미 이 85건의 원 출처이며, 추가 수집 범위만 넓히면 됨 |

**P1 — 있으면 추천 품질이 크게 좋아짐**

| 항목 | 필요한 데이터 | 왜 필요한가 | 해결하는 gap | 연결되는 입력 | 예상 개선 | 원천 형태 |
|---|---|---|---|---|---|---|
| disability_required 구조화 확대 | 이미 수집된 원문에서 장애 관련 서비스 추가 태깅 또는 신규 지자체 장애인 대상 서비스 수집 | §2 Scenario B에서 있을 때 영향력이 매우 큼을 실증 | disability 정보가치 향상 | 장애 여부 | 장애인 사용자의 순위 변별력 확대 지역 증가 | 기존 CSV 재검토(`data_source_plan.md` A장 API 재수집) |
| community_care 지역 다양성 확대 | §8에서 SUPPORT_TYPE_COVERAGE(21.4%) 원인이 된 지역 위주 통합돌봄형 서비스 수집 | community_care가 12/85로 상대적으로 적음 | SUPPORT_TYPE_COVERAGE | 원하는 도움 | desired_support=community_care 사용자의 결과 개선 | CSV/OPEN_API(동일 출처) |

**P2 — 향후 확장 단계**

| 항목 | 필요한 데이터 | 왜 필요한가 | 해결하는 gap | 연결되는 입력 | 예상 개선 | 원천 형태 |
|---|---|---|---|---|---|---|
| recent_discharge 관련 서비스 | 퇴원환자 연계 서비스 추가 수집 | 1/85건뿐, "영양돌봄" 제품 정체성과 직접 관련 | recent_discharge 정보가치 향상 | 최근 퇴원 여부 | 현재 사실상 0에 가까운 discharge_bonus가 의미를 갖게 됨 | PDF — `data_source_plan.md` B장의 "급성기 환자 퇴원지원 및 지역사회 연계활동 시범사업 지침"(hira.or.kr), 병원 단위 서비스라 신청정보 보완 필요 |
| single_household_required 구조화 확대 | 독거 조건이 명시된 서비스 재검토 | 9/85건뿐 | single_household 정보가치 향상 | 독거 여부 | 독거 사용자 변별력 확대 | 기존 원문 재검토(신규 수집 불요, SEMI_AUTO) |
| food_cost_support 다양성 | 식비/바우처형 서비스 추가 | 1/85건뿐 | 지원유형 다양성 | 원하는 도움(식비지원) | 해당 옵션 선택 시 결과 개선 | CSV/OPEN_API(동일 출처) |

실제 존재하지 않는 데이터셋/기관명은 만들지 않았습니다 — 위 원천은 모두
`docs/data_source_plan.md`(기존 조사 문서, 무수정)에 이미 존재를 확인해 둔 항목만
인용했습니다.

## 14. 다음 개발 단계 추천

1. **(P0)** `data_source_plan.md` A장의 지자체복지서비스 API로 세종/울산 포함 지역 커버리지
   확장 수집 — 별도 승인 후 진행.
2. **(P1)** disability/community_care 구조화 확대.
3. 데이터 보강 이후, 확장된 데이터로 §8의 64개 profile×region 분석을 재실행해 개선 폭을
   정량적으로 재검증.
4. 이번 단계에서 발견한 "전남광주통합특별시" 명칭 인지 문제는 코드 문제가 아니므로, UI
   문구(예: 안내 caption)로 보완할지는 별도 논의.
5. 추천엔진 자체의 추가 튜닝은 **데이터 보강 이후** 재평가 — 현재는 로직이 병목이 아닙니다(§8).

---

## 최종 판정

**DATA_ENRICHMENT_RECOMMENDED**

(로직은 건강하고 v1.2 수정 사항 전부가 Streamlit 실사용 흐름에서 정상 동작함을 확인했습니다.
Top-K 부족의 100%가 데이터/서비스유형 커버리지 문제로 설명되며 로직 문제는 0건이었으므로,
다음 단계는 추천엔진 추가 튜닝이 아니라 §13의 우선순위에 따른 데이터 보강입니다. "필수"가
아니라 "권장"으로 판정한 이유는 현재 데이터만으로도 로직 검증·시연 자체는 정상적으로 가능하기
때문입니다.)
