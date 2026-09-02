# 추천엔진 v1.2 검증 및 최소 수정 보고서

> 원칙: **DATA → RULE → RESULT**. 특정 사례의 순위를 맞추기 위한 `DESIRED RESULT → RULE PATCH`는
> 하지 않았습니다. 아래 모든 수정은 (1) 실제 코드 추적으로 원인을 확인하고, (2) 실제 85개
> 서비스 원문으로 재현하고, (3) 기존 패턴(3x3 UNKNOWN matrix, `open_count`, 조건부 SOFT 보너스)을
> 재사용하는 최소 변경만 적용한 뒤, (4) 기존 202개 테스트 전부가 그대로 통과함을 확인한
> 순서로 진행했습니다.

---

## 1. 발견한 문제 요약

| # | 문제 | 분류 | 재현 | 수정 |
|---|---|---|---|---|
| 1 | `전주시 덕진구` 등 39개 "구" 세부 시군구 선택 시 실제로 이용 가능한 시 단위 서비스가 통째로 배제됨 | **로직 버그** (데이터 결합 불일치) | 예 (WLF00002047) | 예 |
| 2 | `국가유공자재가복지지원`(WLF00000098)/`재가급여`(WLF00003248)가 특수 자격요건(보훈 등록/장기요양등급)을 구조화된 필드로 표현할 방법이 없어 일반 사용자에게 HIGH_MATCH까지 도달 가능 | **로직 버그** (게이트 누락) | 예 | 예 |
| 3 | `meal_preparation_difficulty`(식사 준비 어려움) 필수 입력값이 matcher/filters/scorer 어디에서도 전혀 읽히지 않음 | **로직 버그** (미배선) | 예 (`grep` 0건) | 예 |
| 4 | 화성시 동탄구 등 특정 지역에서 후보가 2~3건만 나오는데 UI에 "왜 적은지" 설명이 없어 오류로 오인될 위험 | **UI 문제** | 예 | 예 |
| 5 | 화성시 동탄구는 장애/독거/거동불편 등 입력을 바꿔도 결과가 거의 안 바뀜 | **데이터 한계** (재현했으나 로직 결함 아님) | 예 | 미수정(한계로 명시) |
| 6 | `desired_support`를 바꿔도 결과가 크게 안 바뀌는 것처럼 보임 | **데이터 한계로 판명** (지역별 service_type 다양성 부족) | 부분 재현 | 미수정 |
| 7 | 나머지 특수 자격 후보(4건: 시흥돌봄SOS, 김장서비스, 수원새빛돌봄, 함양군 통합돌봄) | 원문 재검토 결과 **문제 없음**(포함형 목록) | — | 미수정 |
| 8 | Top-K가 5보다 적게 나오는 현상 자체 | **대부분 정상** (CASE A/D), 일부는 CASE B(위 #1) | — | #1로 해결된 부분만 |

---

## 2. 지역 후보 생성 Funnel (§2)

기존 `apply_hard_filters()`/`evaluate_region()`를 그대로 재사용해 funnel을 추적했습니다(새 시스템을
만들지 않음).

### 화성시 동탄구 (경기도) — 수정 전/후 동일 (진짜 데이터 부족)

```
전체 서비스: 85
↓ region 조건
exact SIGUNGU("화성시" 또는 "화성시 OO구") 후보: 0   ← 경기도 SIGUNGU-scope 5건 중 화성시는 0건
SIDO(경기도 전역) 후보: 1  (WLF00004001)
NATIONAL 후보: 2  (WLF00000098, WLF00003248)
────────────────────────────────
region 생존 합계: 3
```

**원인 판정: CASE A + CASE E (데이터 자체가 부족함).** 경기도는 인구가 가장 많은 광역자치단체
중 하나지만, 현재 85건 데이터셋에는 경기도 SIGUNGU-scope 서비스가 **5건뿐**(시흥시 2, 이천시,
하남시, 수원시 각 1건)이고 화성시는 그중 하나도 없습니다. 이것은 SIGUNGU HARD FILTER가 지나치게
강해서가 아니라(§3에서 실증), 애초에 원본 공공데이터 수집 단계에서 화성시 소재 서비스가 85건
표본에 포함되지 못한 **수집 커버리지 문제**입니다. §6.4에서 만든 4번 문제(UI 미안내)는
수정했지만, 데이터 자체를 새로 수집하지는 않았습니다(이번 단계 범위 밖, §17).

### 전주시 덕진구 (전북특별자치도) — 수정 전후 비교

**수정 전**:
```
exact SIGUNGU 후보: 0   ← "전주시 덕진구" 문자열과 정확히 일치하는 행 없음
SIDO 후보: 0             ← 전북특별자치도 SIDO-scope 서비스 자체가 0건
NATIONAL 후보: 2
region 생존 합계: 2
```

**수정 후**(§7의 sigungu 세부구 fallback 적용):
```
exact/같은 시 SIGUNGU 후보: 1   ← WLF00002047(저소득 거동불편 장애인도시락배달, 전주시) 포함
NATIONAL 후보: 2
region 생존 합계: 3
```

**원인 판정: CASE B(진짜 로직 문제) + CASE A(그래도 여전히 적음, 데이터 한계)가 함께 작용.**
전북특별자치도 자체는 SIGUNGU-scope 서비스가 7건 있지만(남원시/고창군/군산시×2/임실군/장수군/
전주시 각 1건), 그중 전주시 소재가 1건뿐이라 수정 후에도 "많다"고 보기는 어렵습니다 — 이는
정직하게 데이터 한계로 남습니다.

### 정확한 시군구 > 같은 시도 > 전국 정책이 실제로 작동하는가?

**예, 셋 다 정상 작동합니다** (`matcher.evaluate_region`, `filters.apply_hard_filters` 무변경
확인). §2 지시사항이 우려한 "SIDO/NATIONAL이 후보로 안 들어오는 구조 문제"(가설 C)는
**기각**되었습니다 — 화성시 사례에서 이미 WLF00004001(SIDO)과 WLF00000098/WLF00003248(NATIONAL)
이 정상적으로 후보에 포함되어 있었습니다. 실제 문제는 가설 B("SIGUNGU 필터가 너무 강함")도
아니었고, 가설 A/D(데이터 부족)와 새로 발견한 세부구 granularity 불일치(§region 참고) 두 가지
였습니다.

---

## 3. One-variable-at-a-time 민감도 테스트 결과 (§3)

실제 85건 데이터로 서울 성동구(장애인 대상 식사 서비스가 실제로 존재하는 지역)와 강원 춘천시
(서비스 유형이 다양한 지역)를 기준 삼아 검증했습니다. 전체 결과는
`tests/test_v1_2_scenarios.py`, `tests/test_meal_preparation_sensitivity.py`,
`tests/test_special_eligibility.py`에 회귀 테스트로 고정했습니다.

| # | 입력 | 판정 | 근거 |
|---|---|---|---|
| 1 | disability 아니오→예 | **정상적인 영향** (지역에 실제 데이터가 있을 때) | 서울 성동구: 후보 2건→4건, 1위 서비스가 국가유공자 서비스(5.9점)에서 장애인 대상 급식 서비스(76.5점)로 완전히 교체됨 |
| 1' | (같은 조건, 화성시) | **사실상 영향 없음 — 데이터 부족으로 판단** | 화성시 후보 3건 중 disability_required가 구조화된 서비스가 0건이라 원천적으로 차이가 날 수 없음(§4에서 상세 확인) |
| 2 | low_income 아니오→예 | **정상적인 영향(HARD gate)** | 화성시: `low_income_required=true`인 WLF00004001이 사용자=예일 때만 통과, 아니오면 HARD EXCLUDE (Scenario 3, 실측) |
| 3 | single_household 아니오→예 | **영향은 있으나 지역에 따라 약함** | 서울 성동구 4건 후보 사례에서는 두 후보 모두 `single_household_required=unknown`이라 무변화(데이터 부족). rules_spec.md §14가 이미 "10.6%만 구조화"로 예견한 한계 |
| 4 | mobility 아니오→예 | **정상적인 영향** | 서울 성동구: WLF00001001 70.6→82.3점으로 상승, 순위 역전(#2→#1) |
| 5 | meal_preparation_difficulty 아니오→예 | **v1에서는 "사실상 영향 없음"(버그) → v1.2에서 수정 후 정상 작동** | §meal_prep 참고. 수정 전: `grep` 결과 코드 어디에서도 참조되지 않음. 수정 후: 속초시 실측 70.59→73.68점 |
| 6 | recent_discharge 아니오→예 | **정상적이나 매우 약함(설계상 의도됨)** | `discharge_support` 태그 보유 서비스가 85건 중 1건뿐이라 rules_spec.md §0/§8/§15가 이미 "데이터 희소, 거의 항상 UNKNOWN"이라고 명시한 대로 동작 |
| 7 | desired_support 잘모르겠음→meal_support | **정상적인 영향** | `_determine_match_level` rule 1이 unsure를 무조건 NEEDS_CONFIRMATION으로 강등하므로, meal_support 선택 시 등급 자체가 열림 |
| 8 | desired_support meal_support→다른 유형 | **정상적인 영향(지역에 다양성이 있을 때)** | 춘천시: home_visit 선택 시 WLF00000098/WLF00003248이 NEEDS_CONFIRMATION(5.9점)→POSSIBLE_MATCH(64.7점, v1.2 특수자격 게이트 반영값)로 상승 |
| 9 | sigungu 정확→UNKNOWN | **정상적인 영향** | 서울: region 생존 4건→9건으로 확대(계층적 fallback이 실제로 작동) |
| 10 | age 경계값 전/후 | **정상적인 HARD gate 영향** | 속초시(min_age=60 서비스 실존): 59세는 2건, 60세는 4건 — 정확히 그 경계에서만 갈림 |

**핵심 결론**: 사용자가 관찰한 "입력을 바꿔도 결과가 잘 안 바뀐다"는 현상은 **거의 전부 같은
근본 원인**(테스트 지역의 SIGUNGU 데이터가 얇아 해당 차원의 구조화 필드 자체가 없음)으로
설명되며, **같은 입력을 데이터가 풍부한 지역에서 테스트하면 정상적으로 큰 폭의 순위 변화가
나타납니다.** 즉 로직은 대체로 건강하고, 체감 문제의 대부분은 §2에서 확인한 지역 데이터 밀도
문제의 파생 증상이었습니다. 유일한 진짜 예외가 §meal_prep(수정 완료)입니다.

---

## 4. 장애(disability) 조건 집중 검증 (§4)

- 원문 확인 결과 `disability_required=true` 12건, `false` 6건, `unknown` 67건(rules_spec.md §0
  실측과 일치, 재확인함).
- 대표 서비스 `WLF00001000`(장애인무료급식소 운영, 서울 성동구)로 파이프라인을 직접 추적:
  region MATCH → age UNKNOWN(중립) → **disability**: 사용자=아니오일 때 HARD EXCLUDE, 사용자=예일
  때 MATCH+가점 → 최종 76.5점/POSSIBLE_MATCH(같은 지역의 `low_income_required=true`가 미확인이라
  `open_count=1`로 강등).
- **결론: 장애 조건은 disability_required가 구조화된 서비스가 후보 풀에 있을 때 정상적으로,
  그리고 상당히 크게(순위 재배열 수준으로) 반영됩니다.** "변화가 작았다"는 관찰은
  scoring bug가 아니라, 사용자가 테스트한 지역(화성시로 추정)에 장애 관련 구조화 서비스가
  0건이었기 때문(§3의 시나리오 1'과 동일 원인) — **DATA_LIMITATION으로 보고합니다.**

---

## 5. desired_support 검증 (§5)

`scorer._service_type_component()`(무수정)를 그대로 추적했습니다.

- direct match(교집합 크기/사용자가 고른 태그 수): 최대 50점 만점을 비율로 배분.
- related match: 한 서비스가 여러 태그(`community_care|meal_support|home_visit`)를 가지면
  사용자가 그중 하나만 선택해도 교집합 1로 정상 매칭(이미 존재하는 §8 다중태그 처리, 재확인).
- mismatch(교집합 0): `_determine_match_level` rule 5가 **NEEDS_CONFIRMATION으로 강제 강등**
  (2026-08-23 실사용 사례 검증에서 이미 추가된 로직, 이번에 재확인만 함, 수정 없음).

춘천시 실측(§3 표 8행)에서 A(직접 일치, WLF00005308)가 B/C(부분 일치, 65점대)보다, 그리고
D(무관, NEEDS_CONFIRMATION 강제)보다 항상 높다는 방향성이 실제로 성립함을 확인했습니다. **이
순서를 하드코딩하지 않았습니다** — 기존 `service_type ∩ desired_support` 비율 계산과 rule 5의
조합만으로 자연스럽게 나오는 결과입니다.

**meal_support 데이터가 81/85건으로 압도적**이라는 지적(§5)에 대해서도, 점수는 "meal_support
보유"가 아니라 "사용자가 고른 유형과의 교집합"에만 반응하므로(§9 anti-gaming 규칙, 무수정),
이 자체가 문제를 일으키지 않음을 재확인했습니다. **anti-gaming 규칙을 깨는 수정은 하지
않았습니다.**

**결론**: desired_support는 실제로 의미 있게 반영되지만, 그 효과가 "보이려면" 해당 지역
후보 풀에 서비스 유형 다양성이 있어야 합니다(§3과 동일한 메타 원인).

---

## 6. "어떤 도움이 필요한지 모르겠어요" UI 문제 (§6)

`src/streamlit_ui/adapter.py`의 `desired_support_labels()`/`labels_to_desired_support()`를
확인했습니다. Streamlit `st.multiselect`는 항목 간 상호 배제를 자체 지원하지 않아, 현재는
"식사/도시락/반찬 지원"과 "어떤 도움이 필요한지 모르겠어요"를 동시에 선택할 수 있습니다.

**Backend는 이미 이 모순을 안전하게 처리하고 있습니다** — `UserProfile.effective_desired_support()`
가 `DesiredSupport.UNSURE`가 집합에 포함되어 있으면 **무조건** 빈 집합(중립)으로 취급합니다
(`models.py`, 무수정). 즉 두 옵션을 동시에 선택해도 엔진은 "잘 모르겠음"으로 안전하게 해석하며,
구체적 선택이 부당하게 가점을 받는 사고는 나지 않습니다. **이 부분은 이미 안전하므로 backend를
수정하지 않았습니다.**

다만 UI에서 두 옵션이 동시에 하이라이트된 상태로 보이는 것은 사용자에게 혼란을 줄 수 있어, 이번
단계에서는 **UI만** 상호 배제를 적용하는 대신, 지침이 우려한 "session_state 오류 위험"을
피하기 위해 **더 단순한 방식**을 택했습니다: 별도의 selectbox/checkbox 상호작용 로직을 추가하지
않고 이번 단계에서는 **보류**합니다. 이유: (1) backend가 이미 안전해 사용자에게 잘못된 결과가
나가지는 않고, (2) `st.multiselect`의 위젯 상태를 프로그래밍적으로 되돌리는 것은 Streamlit
rerun 모델과 상호작용이 복잡해(선택 즉시 위젯 자체 상태를 코드에서 덮어써야 함) 이번 "최소
수정" 범위를 벗어난다고 판단했습니다. **한계로 명시**하고 다음 단계 후보로 남깁니다(§16).

---

## 7. 국가유공자재가복지지원 원인 분석 (§7)

`WLF00000098` 원문 전체(`target_original`/`criteria_original`/`support_original`/
`application_original`/`data_quality_note`)를 직접 읽었습니다.

- `target_original`: "(본인) 독립유공자, 국가유공자, 보훈보상대상자, 5·18민주유공자,
  특수임무유공자, 참전유공자, 고엽제후유의증환자 / (유족) ..." — **닫힌 목록**으로, 일반
  고령자는 원천적으로 대상이 아닙니다.
- `data_quality_note`(이미 기존 데이터 처리 단계에서 남겨진 내부 메모): "국가유공자/보훈보상대상자
  대상 특수 자격체계(장애인복지법상 장애 개념과 다름)... 일괄 단정 어려움" — 문제 자체는 이미
  한 차례 감지되어 기록되어 있었지만, **어떤 구조화 필드로도 연결되지 않았습니다.**
- 구조화 상태: `disability_required=unknown`, `low_income_required=unknown`,
  `region_scope=NATIONAL`, `age_condition_type=COMPOUND`(65세 미만도 예외적으로 포함) —
  **4개 HARD gate 차원 중 어느 것도 이 서비스의 진짜 자격 조건(보훈 등록 여부)을 표현하지
  못합니다.**

가능성 조사 결과(§7 지시된 5가지):
1. **special eligibility가 구조화되어 있지 않음 — 맞음(주원인).**
2. UNKNOWN으로만 남아있음 — 맞음(그러나 "요구하지 않음"과 "확인 안 됨"을 구분할 필드조차
   없었다는 게 더 정확한 표현).
3. NATIONAL이라서 과도하게 올라옴 — **부분적으로만 맞음.** NATIONAL 자체가 가점을 주지는
   않지만(`_region_precision_component`는 NATIONAL에 score_signal을 주지 않음, 무수정 확인),
   지역 HARD EXCLUDE를 아예 겪지 않아 "생존은 보장됨"이라는 간접 효과가 있었습니다.
4. **user profile에 해당 질문 자체가 없음 — 맞음(구조적 원인).**
5. 기타 — 없음.

**진짜 원인**: 1번(구조화 부재)이 근본 원인이고, 3·4번은 그로 인한 결과입니다. 순수 "동점 시
`service_id` 정렬" 문제(v1 보고서가 이미 지적한 tie-break 아티팩트)와는 **다른, 별개의
문제**였습니다 — 이 사례는 정보가 부족한 극단적 상황이 아니라 desired_support가 실제로
일치하는 정상적인 상황(춘천시 home_visit 시나리오)에서도 HIGH_MATCH까지 도달했기 때문입니다.

### 적용한 일반화 가능한 구조

`special_eligibility_required`(TriState) / `special_eligibility_note`(자유텍스트) 두 컬럼을
CSV에 추가했습니다. **기존 데이터 구조에서 이미 표현 가능한 필드가 있는지 먼저 확인**했으나
없었습니다(`disability_required`는 장애인복지법상 장애와 다른 개념, `low_income_required`는
소득 기준과 무관, `age_condition_type`은 나이 조건 전용). 값은 실제 원문을 읽고 확인한 **정확히
2건**(WLF00000098, WLF00003248)에만 `true`를 부여했고, 나머지 83건은 빈 값(`UNKNOWN`)입니다 —
"국가유공자 서비스 = -50점" 같은 점수 패치가 아니라, **기존 3x3 UNKNOWN matrix와 `open_count`
메커니즘을 그대로 재사용**해 "확인 안 된 특수 자격 요구 1건"으로 `open_count`를 1 올리는
방식입니다. 이는 rules_spec.md §10 rule 6(`open_count==1` → `POSSIBLE_MATCH` 상한)을 그대로
적용받아 **HIGH_MATCH 도달을 원천적으로 막되, 목록에서 삭제하거나 감점하지는 않습니다.**

---

## 8. 특수 자격 서비스 전체 감사 (§8)

85건 전체를 다음 키워드 카테고리로 원문(`target_original`+`criteria_original`) 스캔한 뒤, **각
매치를 실제로 읽고 개별 판정**했습니다(키워드 매치 자체를 자동 판정 근거로 쓰지 않음 —
rules_spec.md §12 rule 5 "런타임에 즉석 키워드 매칭으로 자격을 결정하지 않는다"를 이번 감사
방법론에도 적용해, 스캔은 오프라인 1회성 검토 도구로만 사용하고 결과는 사람이 원문을 읽고
확정했습니다).

| service_id | 서비스명 | 매치 키워드 | 실제 판정 | 근거 |
|---|---|---|---|---|
| WLF00000098 | 국가유공자재가복지지원 | 국가유공자/보훈 등 | **필수 특수자격, 과대노출 위험 → 수정함** | 닫힌 대상자 목록, 다른 조건 없음 |
| WLF00003248 | 재가급여 | 장기요양등급 | **필수 특수자격, 과대노출 위험 → 수정함** | `<장기요양등급 판정기준>`으로 criteria_original 전체가 등급 요건 |
| WLF00005239 | 시흥돌봄SOS센터 | 국가유공자 | **문제 없음** | "국가유공자 본인은 **전액지원**"(비용 우대일 뿐, 자격 자체는 "돌봄이 필요한 시민" 전체) |
| WLF00004507 | 김장서비스(재가복지 봉사) | 국가유공자 | **문제 없음** | 차상위/장애인/독거노인/한부모/조손/만성질환/**무의탁 국가유공자** 등 포함형 OR-목록 중 하나일 뿐 |
| WLF00005718 | 수원새빛돌봄 | 국가유공자 | **문제 없음** | "중위소득 120% 이하, **국가유공자**"(소득기준 OR 국가유공자 — 대체 경로일 뿐, 배타적 아님) |
| WLF00006261 | 함양군 통합돌봄사업 | 장기요양등급, 노인성질환 | **문제 없음** | 장기요양 재가급여자는 "우선관리 대상자" 중 하나일 뿐, 기본 대상은 "돌봄이 필요한 노인/장애인" 전체 |
| WLF00004132 | 경로무료급식사업(담양) | 노인성질환 | **문제 없음** | "기타 군수가 필요하다고 인정되는 자"의 예시 중 하나일 뿐, 기본 대상은 수급자/차상위/독거노인 등 |
| WLF00000212 | 어려운 세대 밑반찬 지원 | 한부모/조손 | **문제 없음** | 독거노인/소년소녀가장/한부모 등 포괄적 취약계층 목록, 이미 `low_income_required`로 대체로 커버됨 |
| (기초생활수급/차상위 매치 다수, ~50건) | — | 기초생활수급/차상위 | **이미 안전하게 처리됨** | `low_income_required` 필드가 이 카테고리를 이미 정확히 구조화하고 있음(재확인) |
| (장애인 관련 매치 다수) | — | 장애인 | **이미 안전하게 처리됨** | `disability_required` 필드가 이미 구조화 |

**분류 요약**:
- 이미 구조화되어 안전하게 처리됨: 기초생활수급/차상위/장애인 카테고리 전체
- 구조화가 부족하지만 confirmation으로 처리 가능: (§8 카테고리 중 이번 감사로는 해당 없음 —
  전부 이미 처리되었거나 애초에 배타적 조건이 아니었음)
- **필수 특수자격인데 과대노출 위험: WLF00000098, WLF00003248 (2건, 수정함)**
- 원문 자체가 불명확: 없음
- 문제 없음(포함형 목록/비용 우대일 뿐): 6건

국가유공자 사례 하나만 고치라는 지시를 따르지 않고 85건 전체를 검토했으며, **동일한 근본
원인(NATIONAL scope + 구조화 게이트 0개)을 가진 재가급여(WLF00003248)를 추가로 발견해 함께
수정**했습니다.

---

## 9. UNKNOWN 처리 원칙 유지 확인 (§9)

- `special_eligibility_required`는 사용자 쪽 답변이 **항상 UNKNOWN**(해당 질문 자체가
  UserProfile에 없음)이므로, 기존 3x3 matrix 상 "서비스=TRUE + 사용자=UNKNOWN" 행 하나만
  발생합니다 — `confirmation_needed=True`, **HARD EXCLUDE 아님**(`tests/test_special_eligibility.py
  ::test_special_eligibility_never_hard_excludes`로 검증).
- "정보 부족 보상" 현상(정보가 적은 서비스가 부당하게 유리해지는지)을 실측으로 재확인했습니다:
  화성시 시나리오에서 완전히 정보가 없는 WLF00000098(5.9~14.3점)이 실제로 확정된 매치를 가진
  WLF00004001(58.8점)보다 항상 낮음을 `test_scenario_8_...`로 고정했습니다. 기존
  `test_scorer.py::test_eligibility_gate_unknown_never_receives_positive_score_credit`의
  단일 서비스 단위 검증을 `recommend()` 종단 테스트로 보강한 것입니다.

---

## 10. Top-K 정책 검증 (§10)

| CASE | 발생 여부 | 사례 |
|---|---|---|
| A. 실제로 적합 서비스가 적음 | **예, 다수 발생** | 화성시(3건), 대부분의 SIGUNGU 밀도 낮은 지역 |
| B. 지역 필터 과도 작동 | **예, 1건 발견 및 수정** | 전주시 덕진구 등 세부구 granularity 불일치 |
| C. special eligibility 불분명 서비스가 상위권 차지 | **예, 2건 발견 및 수정** | WLF00000098, WLF00003248 |
| D. desired_support 일치 후보가 점수 구조 때문에 밀림 | **재현 안 됨** | §5에서 확인 — 오히려 정상적으로 상위 이동 |
| E. 데이터 coverage 부족 | **예** | §2의 화성시 사례가 대표적 |

Top-K를 채우기 위해 낮은 품질의 후보를 억지로 추가하는 코드는 어디에도 추가하지 않았습니다
(`recommender.py`의 `recommend()` 자체는 무수정 — `results[:max(0, top_k)]`만 남는 구조 그대로).

---

## 11. 수정한 파일

| 파일 | 변경 내용 |
|---|---|
| `data/processed/welfare_services_recommendation_ready.csv` | `special_eligibility_required`/`special_eligibility_note` 2개 컬럼 추가(85행 중 2행만 값 있음, 나머지 원문은 무변경) |
| `src/recommender/models.py` | `ServiceRecord`에 위 2개 필드 추가 |
| `src/recommender/loader.py` | 위 2개 컬럼을 `REQUIRED_COLUMNS`에 추가, 파싱 로직 2줄 추가 |
| `src/recommender/matcher.py` | `_sigungu_base()` 헬퍼 + `evaluate_region()`의 SIGUNGU 비교에 세부구 fallback 분기 추가; `evaluate_special_eligibility()` 신규 함수 추가 |
| `src/recommender/filters.py` | `HardFilterResult`에 `special_eligibility_check` 필드 추가, `gate_checks()`에 포함 |
| `src/recommender/scorer.py` | `_meal_preparation_component()` 신규 함수 추가, `compute_score()`에서 호출 |
| `src/recommender/config.py` | `meal_preparation_bonus_max: 10.0` 추가 |
| `src/streamlit_ui/adapter.py` | `few_candidates_notice()` 신규 함수 추가 |
| `app/streamlit_app.py` | `TOP_K` 상수화, `few_candidates_notice()` 호출 1줄 추가 |
| `tests/conftest.py` | `make_service()` 기본값에 신규 필드 2개 추가(하위 호환) |

**가중치 변경 상세 (지침 §12 요구사항)**:

| 항목 | 왜 수정했는가 | 기존 값 | 변경 값 | 어떤 테스트에서 문제였는가 | 다른 서비스에 미치는 영향 |
|---|---|---|---|---|---|
| `meal_preparation_bonus_max` | `meal_preparation_difficulty`가 필수 입력인데 어떤 코드에도 연결되어 있지 않음(`grep` 0건) | (없음, 신규) | `10.0` | §3 시나리오 5, `tests/test_meal_preparation_sensitivity.py` | `meal_support` 태그가 있는 81/85건에서 사용자가 "예"라고 답했을 때만 소폭(+최대 10점) 가산, 그 외 4건은 분모만 커져 상대적으로 소폭 감점(discharge_bonus와 동일한 기존 패턴) |
| `HIGH_MATCH_SCORE_THRESHOLD`, `service_type_match_max` 등 기존 가중치 | **변경 없음** | — | — | — | 화성시 사례가 원하는 결과를 만들기 위해 기존 가중치를 조정하지 않았습니다 |

---

## 12. 수정하지 않은 부분과 이유

1. **화성시 자체의 낮은 후보 수** — 데이터 자체가 없어 로직으로 해결 불가. UI 안내만 개선(§6.4).
2. **§6의 Streamlit "모르겠어요" 동시선택 UI** — backend가 이미 안전하게 처리하므로 UI 자체
   수정은 위험 대비 이득이 낮다고 판단, 보류(§16 다음 단계 후보).
3. **WLF00005239/WLF00004507/WLF00005718/WLF00006261/WLF00004132/WLF00000212** — 원문을 직접
   읽은 결과 배타적 특수자격이 아닌 포함형 목록으로 확인되어 수정하지 않음(§8 표 참고).
4. **NATIONAL tie-break 아티팩트**(v1 보고서에서 이미 문서화된, 극단적 정보 부족 시
   `service_id` 오름차순으로 정렬되는 현상) — 이번 진단에서 재확인했으나, 이번 특수자격 수정과는
   별개의 현상이고 rules_spec.md §11이 이미 "v2 후보"로 남겨둔 항목이라 이번 범위에서는
   손대지 않음.
5. **`single_household_required`/`homebound_or_mobility_condition`의 낮은 구조화율(10.6%/43.5%)**
   — rules_spec.md §14/§15가 이미 알려진 한계로 문서화한 내용이며, 이번 진단으로 재확인만 함.

---

## 13. Sensitivity Test 결과

§3, §11 표에 통합 정리했습니다. 회귀 테스트: `tests/test_v1_2_scenarios.py`(8개),
`tests/test_meal_preparation_sensitivity.py`(4개), `tests/test_region_granularity.py`(5개),
`tests/test_special_eligibility.py`(7개) — 총 **24개 신규 테스트**.

## 14. 지역 후보 Funnel 결과

§2에 통합 정리했습니다.

## 15. Special Eligibility Audit 결과

§8에 통합 정리했습니다.

---

## 16. Before / After 비교 (핵심 사례)

| 사례 | Before | After |
|---|---|---|
| 전주시 덕진구 + meal_support | 후보 2건 (NATIONAL만) | 후보 3건 (+WLF00002047 전주시 소재 실제 서비스) |
| 춘천시 + home_visit, 특수자격 정보 없는 일반 사용자 | WLF00000098 64.7점 **HIGH_MATCH** | WLF00000098 64.7점 **POSSIBLE_MATCH** (open_count=1로 상한) |
| 춘천시 + home_visit (동일) | WLF00003248 64.7점 **HIGH_MATCH** | WLF00003248 64.7점 **POSSIBLE_MATCH** |
| 속초시(min_age=60) + 식사준비어려움=예 | WLF00003375 70.59점 (식사준비어려움 반영 안 됨) | WLF00003375 73.68점 (반영됨) |
| 화성시 동탄구, 후보 3건일 때 UI | 안내 없음 | "확인할 수 있는 서비스가 3건으로 많지 않아요. 시스템 오류가 아니라..." 안내 표시 |

---

## 17. 기존 테스트 결과

```
python -m pytest -q   (수정 직후, 신규 테스트 추가 전)
202 passed, 4 skipped
```

**기존 202개 전부 무변경 통과** — recommender 88, RAG retrieval 34, RAG generation 51(+1 skip),
Streamlit 통합 29(+3 skip). 하드코딩된 예상 순위에 맞춰 기존 테스트를 고친 것은 없습니다.

## 18. 신규 테스트 결과

```
python -m pytest -q   (신규 테스트 24개 추가 후, 최종)
226 passed, 4 skipped
```

| 파일 | 개수 |
|---|---:|
| `tests/test_region_granularity.py` | 5 |
| `tests/test_special_eligibility.py` | 7 |
| `tests/test_meal_preparation_sensitivity.py` | 4 |
| `tests/test_v1_2_scenarios.py` | 8 |
| **합계(신규)** | **24** |

## 19. RAG Regression 여부

`src/rag/*`(retriever/generator/guardrails/prompt_builder)는 **한 줄도 수정하지 않았습니다.**
`ServiceRecord`에 필드 2개가 추가되었지만 `rag.document_builder.build_documents()`는
`target_original`/`criteria_original`/`support_original`/`application_original` 4개 필드만
읽으므로 영향이 없습니다. 전체 스위트(226 passed, 4 skipped)에 RAG retrieval 34개 +
generation 51개(+1 skip) + Streamlit RAG 통합 29개(+3 skip)가 모두 포함되어 무변경 통과를
확인했습니다. **RAG/LLM이 `match_score`/`match_level`/추천 순위를 변경하는 코드 경로는 이번
수정으로도 전혀 생기지 않았습니다** — 이번 수정은 전부 `src/recommender/` 내부이며,
`special_eligibility_required` 같은 신규 필드도 RAG 계층은 참조하지 않습니다.

## 20. 남아 있는 한계

1. 화성시 등 SIGUNGU 데이터가 얇은 지역의 추천 품질은 로직 수정만으로 해결할 수 없는 **수집
   커버리지 문제**입니다.
2. Streamlit의 "모르겠어요" 동시선택 UI는 backend가 안전하므로 급하지 않지만 여전히 시각적
   혼란 소지가 있습니다.
3. `single_household_required`/`homebound_or_mobility_condition`의 낮은 구조화율은 여전합니다.
4. NATIONAL 서비스의 tie-break 아티팩트(v1 보고서 §11)는 이번에도 손대지 않았습니다 — 별도
   과제로 남습니다.
5. `special_eligibility_required`는 이번 감사에서 발견된 2건만 반영되어 있습니다 — 향후 새
   서비스가 추가되면 같은 방식(원문 직접 검토)으로 재감사가 필요합니다.

---

## 21. 질문 답변

### Q1. 현재 시/군/구 입력은 유지하는 것이 좋은가? 아니면 UX에서 optional로 만드는 것이 좋은가?

**유지하되, 이미 optional입니다(변경 불필요).** `sigungu`는 이미 필수가 아니라 선택
입력이며(design doc §2, 무수정), UNKNOWN이면 §2에서 확인했듯 후보가 오히려 넓어집니다(계층적
fallback이 정상 작동). 시군구가 실제로 자격에 영향을 미치는 SIGUNGU-scope 서비스가 71/85건
(83.5%)이므로, 입력 자체를 없애면 오히려 정밀도가 떨어집니다. 이번에 발견한 진짜 문제(세부구
granularity 불일치)는 입력을 없애는 게 아니라 **비교 로직을 고치는 것**으로 해결했습니다.

### Q2. 현재 지역 필터는 너무 강했는가?

**아니오, 필터 자체(정확한 시군구=하드 배제)는 설계상 타당했습니다.** 대신 필터 로직이 비교하는
**데이터의 세분화 수준이 서로 다른 두 소스(region_codes.csv vs 실제 서비스 CSV) 사이에서 어긋나
있었습니다.** 이를 세부구 base-name 비교로 고쳤고, 시군구 자체가 다른 경우(예: 화성시 vs
수원시)는 여전히 정상적으로 배제됩니다(`test_sigungu_service_still_excludes_a_genuinely
_different_city`로 검증).

### Q3. 장애 여부는 실제 추천 결과에 의미 있게 반영되고 있는가?

**예, 데이터가 있는 곳에서는 매우 의미 있게 반영됩니다.** 서울 성동구 사례에서 disability
아니오→예 변경만으로 후보 수가 2배(2→4)로 늘고 1위 서비스가 완전히 바뀌었습니다. 사용자가
관찰한 "변화가 작다"는 현상은 스코어링 결함이 아니라 **테스트한 지역에 disability_required가
구조화된 서비스가 아예 없었기 때문**(DATA_LIMITATION)입니다.

### Q4. desired_support는 실제 추천 결과에 의미 있게 반영되고 있는가?

**예.** 춘천시 사례에서 desired_support를 바꾸는 것만으로 두 서비스의 등급이
NEEDS_CONFIRMATION↔POSSIBLE_MATCH/HIGH_MATCH 사이를 오갔습니다. meal_support가 81/85건으로
많다는 사실 자체는 문제를 일으키지 않는데, 점수가 "meal_support 보유"가 아니라 "사용자가 실제로
고른 유형과의 교집합"에만 반응하도록 이미 설계되어 있기 때문입니다(무수정, 재확인).

### Q5. 국가유공자재가복지지원 반복 상위 노출의 정확한 원인은 무엇이었는가?

**region_scope=NATIONAL이라 지역 배제를 겪지 않고, 동시에 disability_required/
low_income_required가 둘 다 UNKNOWN이라 그 어떤 HARD gate도 `open_count`를 올리지 못해,
사실상 "아무것도 확인할 게 없는" 서비스처럼 취급되었기 때문입니다.** 진짜 자격 조건(보훈 등록)은
원문에만 있었고 어떤 구조화 필드로도 표현되지 않아 시스템이 이를 인지할 방법이 없었습니다. 단순
tie-break(동점 시 `service_id` 정렬) 문제와는 다른, desired_support가 실제로 일치하는 정상
시나리오에서도 발생하는 별개의 문제였습니다.

### Q6. 다른 special eligibility 서비스에도 같은 문제가 있었는가?

**같은 근본 구조(NATIONAL + 구조화 게이트 0개)를 가진 서비스는 재가급여(WLF00003248) 1건 더
있었고 함께 수정했습니다.** 키워드가 매치된 나머지 6건은 원문을 직접 읽은 결과 전부 "포함형
목록"이거나 "비용 우대 조건"일 뿐 배타적 자격 요건이 아니어서 수정하지 않았습니다(§8).

### Q7. Top 2~3만 나타나는 사례는 데이터 부족인가, 필터 문제인가, 정상 동작인가?

**셋 다 있었고, 사례별로 다릅니다.** 화성시는 순수 데이터 부족(CASE A/E, 정상 동작 — 로직
수정 불가/불필요). 전주시 덕진구는 필터 로직의 데이터 결합 버그(CASE B)가 섞여 있었고
수정했습니다 — 다만 수정 후에도 전북 지역 자체의 SIGUNGU 데이터가 얇아 여전히 후보가 많지는
않습니다(2건→3건, 여전히 데이터 한계가 남음).

### Q8. 현재 recommender를 실제 MVP 사용자 테스트에 다시 사용해도 되는 수준인가?

**예.** 발견된 로직 결함(세부구 granularity, 특수자격 게이트 누락, meal_preparation_difficulty
미배선) 3건을 모두 최소 변경으로 수정했고, 기존 202개 테스트가 전부 무변경 통과하며, 24개의
새 회귀 테스트로 이번 수정 사항 자체도 고정했습니다. 남은 한계(§20)는 전부 데이터
커버리지/UX 폴리시 성격이며 안전 원칙(UNKNOWN≠FALSE, HARD EXCLUDE 최소화, RAG 경계)을 위협하지
않습니다.

---

## 최종 판정

**RECOMMENDER_V1_2_READY_WITH_LIMITATIONS**

(로직 결함 3건 수정 완료, 데이터 커버리지 한계는 로직으로 해결 불가능하여 "한계"로 명시, 안전
원칙 및 RAG 경계 전부 유지)
