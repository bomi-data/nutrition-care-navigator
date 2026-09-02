# 규칙 기반 추천 로직 명세 (Rule Specification)

> 이 문서는 **명세 문서**입니다. Python 코드, Streamlit, RAG, LangChain, Vector DB는 포함하지
> 않습니다. 목적은 추천 결과가 어떤 논리로 만들어졌는지 사람이 설명하고 재현할 수 있도록
> 규칙을 문서로 확정하는 것입니다.

데이터 소스: `data/processed/welfare_services_recommendation_ready.csv` (85건, 34개 컬럼)
선행 문서: `docs/recommendation_system_design.md`, `docs/recommendation_data_readiness.md`,
`docs/classification_criteria.md`

---

## 0. 실제 데이터 재확인 및 문서 간 차이

이번 단계 시작 전에 CSV를 다시 직접 읽고 확인했습니다. 실측치는 다음과 같습니다.

| 필드 | 값 분포 |
|---|---|
| `region_scope` | SIGUNGU 71 / SIDO 12 / NATIONAL 2 |
| `age_condition_type` | NONE 45 / SIMPLE_MIN 28 / COMPOUND 12 |
| `min_age` (숫자 확정) | 65(23건) / 60(16건) — 39건, 나머지 46건은 `unknown` |
| `disability_required` | unknown 67 / true 12 / false 6 |
| `low_income_required` | true 64 / unknown 13 / false 8 |
| `single_household_required` | unknown 76 / true 9 / **false 0건** |
| `homebound_or_mobility_condition` | unknown 48 / true 37 / **false 0건** |
| `service_type` 내 태그 보유 건수 | meal_support 81 / community_care 12 / home_visit 6 / food_cost_support 1 / discharge_support 1 |
| `service_type_primary` | meal_support 72 / community_care 10 / home_visit 2 / food_cost_support 1 |
| `nutritionist_involvement=direct` | 1건 (WLF00005102) |
| `senior_relation` | SENIOR_CONDITIONAL 27 / SENIOR_DIRECT 4 / 공란 54 |
| `nutrition_relevance` | DIRECT_NUTRITION 21 / 공란 64 |
| `verification_level` | A 50 / B 35 |

**문서와 실제 CSV 간 차이 (보고)**:
- `docs/classification_criteria.md`는 `senior_relation_v2`, `nutrition_relevance`의 3값 체계
  (`SENIOR_DIRECT/SENIOR_CONDITIONAL/NOT_SENIOR_RELEVANT`, `DIRECT_NUTRITION/SUPPORTIVE_NUTRITION/
  NOT_NUTRITION_RELEVANT`)를 정의하지만, 실제 CSV 컬럼명은 `senior_relation`(접미사 `_v2` 없음)이고
  값은 `SENIOR_DIRECT`/`SENIOR_CONDITIONAL` 두 가지만 존재합니다(`NOT_SENIOR_RELEVANT`는 최종
  INCLUDE 대상에서 이미 제외되어 존재하지 않음 — 정상). `nutrition_relevance`도 `DIRECT_NUTRITION`
  값만 존재하고 `SUPPORTIVE_NUTRITION`/`NOT_NUTRITION_RELEVANT`는 없습니다.
- `classification_criteria.md` §3의 `service_type` 체계에는 `nutrition_counseling`,
  `nutrition_education` 태그가 정의되어 있지만, **실제 85건 중 이 두 태그를 가진 서비스는
  0건입니다.** `service_type`에 실제로 존재하는 값은 `meal_support` / `food_cost_support` /
  `community_care` / `home_visit` / `discharge_support` 다섯 가지뿐입니다. 이는 §9(서비스 유형
  매핑)에서 "영양상담/교육"을 사용자가 선택해도 구조화된 매칭 대상이 사실상 없다는 것을 의미하며,
  아래 규칙은 이 실측 결과를 그대로 반영합니다.
- `max_age`는 전 85건 공란입니다(해당 사례 없음). 규칙은 정의하되 현재 데이터에서는 발동하지 않습니다.
- 이하 모든 규칙은 이 실측치를 전제로 설계되었습니다. 새 API 호출이나 웹 검색은 하지 않았습니다.

---

## 1. 시스템 목적

사용자의 상황과 입력 정보를 바탕으로 **관련 가능성이 높은** 영양돌봄/복지서비스를 찾아
우선순위를 제공합니다. 이 시스템은 수급자격을 확정하지 않습니다. 다음과 같은 확정적 표현은
어떤 결과 화면에서도 사용하지 않습니다: "신청 가능합니다", "대상자입니다", "수급 가능합니다",
"자격이 확정되었습니다". 모든 결과는 `HIGH_MATCH` / `POSSIBLE_MATCH` / `NEEDS_CONFIRMATION`
3단계 가능성 표현으로만 제시합니다(등급 체계 확정 이유는 §10 참조).

---

## 2. 사용자 입력 schema

`docs/recommendation_system_design.md` §3의 `user_profile` 스키마를 그대로 채택합니다
(3상태 `true`/`false`/`unknown` 문자열 표기를 CSV와 동일하게 사용).

| 필드 | 필수/선택 | 매칭 대상 CSV 필드 |
|---|---|---|
| `sido` | 필수 | `sido`, `region_scope` |
| `sigungu` | 선택 | `sigungu`, `region_scope` |
| `age` | 필수 | `min_age`, `age_condition_type` |
| `has_disability` | 필수(3상태) | `disability_required` |
| `low_income_status` | 필수(3상태) | `low_income_required` |
| `lives_alone` | 필수(3상태) | `single_household_required` |
| `mobility_difficulty` | 필수(3상태) | `homebound_or_mobility_condition` |
| `meal_preparation_difficulty` | 필수(3상태) | `meal_support_flag`, `service_type` |
| `recent_discharge` | 선택(3상태) | `service_type`(discharge_support 태그, 1건뿐) |
| `desired_support` | 필수(다중선택) | `service_type`, `nutritionist_involvement` |
| `respondent_type` | 선택 | 매칭 미사용(문구 톤 전용) |

---

## 3. 추천 처리 순서 (파이프라인)

사용자가 제시한 STEP1~10 구조를 실제 데이터로 검증한 결과, **큰 틀은 유효하지만 두 가지를
명확히 합니다.**

1. **STEP3("명백한 자격 불일치 HARD FILTER")는 지역을 제외한 나머지 하드 조건(연령/장애/소득)만
   다룹니다.** 지역 불일치는 STEP2에서 이미 하드 배제로 처리되므로, STEP3에서 지역을 다시 검사하면
   로직이 중복됩니다.
2. **STEP7("UNKNOWN 조건 처리")은 별도로 실행되는 독립된 패스가 아니라, STEP2~6 각 단계 내부에
   반드시 내장되어야 하는 교차 규칙(cross-cutting policy)입니다.** 문서 가독성을 위해 사용자가
   요청한 대로 번호를 유지하되, 실제 구현에서는 "UNKNOWN을 만나면 이렇게 처리한다"는 규칙이
   STEP2~6 각각에 이미 적용되어 있어야 한다는 점을 명시합니다.

| STEP | 내용 | 종류 |
|---|---|---|
| 1 | 사용자 입력 정규화 (문자열 trim, tri-state 정규화, `desired_support` 집합화) | 전처리 |
| 2 | 지역 조건 비교 (`region_scope` 기준, §6) — 여기서 지역 HARD EXCLUDE 발생 가능 | HARD |
| 3 | 연령·장애·소득 HARD FILTER (§7, §4) | HARD |
| 4 | 서비스 유형 ↔ `desired_support` 일치도 계산 (§9) | SOFT (최고 가중치) |
| 5 | 생활조건 일치도 계산 (독거·거동불편, §4) | SOFT |
| 6 | 데이터 신뢰도(`verification_level`) 및 `nutrition_relevance`/`nutritionist_involvement` 반영 | SOFT (보조/타이브레이커) |
| 7 | UNKNOWN 처리 원칙 적용 — STEP2~6에 내장된 교차규칙(§5) | 교차규칙, 별도 패스 아님 |
| 8 | 최종 점수 계산 (게이트 통과 서비스에 한해 SOFT 점수 합산) | 집계 |
| 9 | 추천 등급 결정 (§10 — 점수 cutoff만이 아니라 게이트 확정도(certainty) 반영) | 판정 |
| 10 | 추천 이유 / 확인 필요 조건 생성 (§11) | 설명 생성 |

---

## 4. HARD FILTER / SOFT SCORE / INFORMATION_ONLY 분류

**가장 중요한 결정입니다.** 실제 CSV 필드별로 분류하고 근거를 명시합니다.

| CSV 필드 | 분류 | 근거 |
|---|---|---|
| `region_scope` + `sido` + `sigungu` | **HARD** | 지역이 명백히 다르면 물리적으로 이용 불가능한 서비스가 대부분 (§6) |
| `min_age` (단, `age_condition_type=SIMPLE_MIN`일 때만) | **HARD** | 단순 "NN세 이상" 기준은 명확하고 예외 조항이 없음 (§7) |
| `min_age` (`age_condition_type=COMPOUND`일 때) | **SOFT/INFO** | 복합조건(예: 65세 이상 또는 65세 미만 노인성질환자)은 min_age 하나로 배제하면 예외 대상자를 부당하게 걸러낼 위험 (§7) |
| `disability_required` | **HARD** | 서비스=TRUE이고 사용자=FALSE로 명확히 답한 경우, 장애 유무는 비교적 검증 가능한 이진 조건 |
| `low_income_required` | **HARD** | 다수 서비스(64/85)가 기초생활수급자/차상위를 명시적 요건으로 규정 — 단, 서비스=TRUE + 사용자=FALSE(명확히 저소득이 아님)일 때만 배제 |
| `single_household_required` | **SOFT** | 현재 데이터에 `false` 값이 전혀 없고(76건 unknown/9건 true), 판정 자체도 "독거 또는 노인부부세대" 같은 원문의 해석적 여지가 있어(`recommendation_data_readiness.md` §7) 하드 배제에 쓰기엔 근거가 약함. 대신 랭킹 가점으로 사용 |
| `homebound_or_mobility_condition` | **SOFT** | 위와 동일 이유(`false` 값 0건, 거동상태는 변동 가능하고 최종적으로 담당자가 재확인하는 사항) — 랭킹 가점으로 사용 |
| `service_type` / `service_type_primary` ↔ `desired_support` | **SOFT (최고 가중치)** | 자격조건이 아니라 사용자의 필요/선호이므로 게이트가 아닌 점수 요소 (§9) |
| `verification_level` | **SOFT (낮은 가중치)** | 데이터 신뢰도이지 사용자 자격과 무관 — 타이브레이커로만 사용 |
| `nutrition_relevance` / `nutritionist_involvement` | **SOFT (낮은 가중치, 조건부)** | 데이터가 극히 희소(각 21/85, 1/85)하여 일반 가중치로 쓰면 왜곡 위험 — `desired_support`에 영양상담이 포함될 때만 소폭 가점 |
| `eligibility_summary` / `support_summary` | **INFORMATION_ONLY** | 자연어 요약, 매칭 로직 입력 아님 — 결과 설명 문구 생성 시 원문 보조자료로만 사용 |
| `application_original` / `contact` | **INFORMATION_ONLY** | 결과 화면의 "신청방법"/"문의처" 표시용, 점수·필터에 미사용 |
| `review_note` / `data_quality_note` | **INFORMATION_ONLY (내부용)** | 사용자에게 직접 노출하지 않음, 개발/감사 목적 |
| `structured_from_original` / `structured_fields_added` | **INFORMATION_ONLY** | 데이터 보강 이력(provenance) — 점수/필터에 사용 금지 |
| `max_age` | **HARD (미발동)** | 규칙은 정의하되 현재 85건 전부 공란이라 실제 효과 없음 |
| `recent_discharge` 대응 (`discharge_support` 태그) | **SOFT (매우 낮은 가중치)** | 태그 보유 서비스가 1/85건뿐이라 사실상 항상 UNKNOWN에 가까움 |

---

## 5. UNKNOWN 처리 Matrix

서비스 조건과 사용자 답변의 3×3 조합 각각에 대해 정의합니다. **HARD-class 필드**
(`disability_required`, `low_income_required`, `min_age`-SIMPLE_MIN)와
**SOFT-class 필드**(`single_household_required`, `homebound_or_mobility_condition`)는
"제외 여부" 칸만 다르고 나머지 원칙은 동일합니다.

| # | 서비스 조건 | 사용자 답변 | 판정 | HARD 필드 제외여부 | SOFT 필드 점수영향 | confirmation_needed | 사용자 설명 |
|---|---|---|---|---|---|---|---|
| 1 | TRUE | TRUE | MATCH | 유지(통과) | **+ (양의 가점)** | 아니오 | "이 조건에 해당하는 것으로 보여요" |
| 2 | TRUE | FALSE | MISMATCH | **HARD EXCLUDE** | **− (감점, 배제 아님)** | 아니오(제외됨/HARD는 목록에서 빠짐, SOFT는 낮은 순위로 유지) | "이 조건이 맞지 않을 수 있어요"(HARD는 목록 미노출) |
| 3 | TRUE | UNKNOWN | UNKNOWN | 유지, **제외 안 함** | 0 (중립) | **예 — 핵심 확인 대상** | "이 조건은 확인이 필요해요" |
| 4 | FALSE | TRUE | MATCH(해당없음 조건 통과) | 유지(통과) | 0 또는 소폭+ | 아니오 | "이 조건은 이 서비스와 상관없어요" |
| 5 | FALSE | FALSE | MATCH | 유지(통과) | 0 또는 소폭+ | 아니오 | 동일 |
| 6 | FALSE | UNKNOWN | 사실상 무관 | 유지(통과) | 0 | 아니오 | 설명 생략 가능(서비스가 애초에 요구하지 않는 조건) |
| 7 | UNKNOWN | TRUE | UNKNOWN | 유지, **제외 안 함** | 0 | 아니오(서비스가 이 조건을 명시하지 않아 사용자에게 확인을 요구할 필요 없음) | "이 서비스는 해당 조건을 별도로 명시하지 않았어요" |
| 8 | UNKNOWN | FALSE | UNKNOWN | 유지, 제외 안 함 | 0 | 아니오 | 동일 |
| 9 | UNKNOWN | UNKNOWN | 완전 무정보 | 유지, 제외 안 함 | 0 | 아니오(정보 자체가 없어 확인을 요구할 대상이 불명확) | 설명 생략 가능 |

**핵심 원칙**: UNKNOWN을 FALSE로 간주하지 않습니다. 표의 #3(서비스가 조건을 명시했는데 사용자가
모른다고 답한 경우)만 `confirmation_needed`에 오르는 이유는, 이때만 사용자가 실제로 확인해야
할 구체적 정보(서비스가 요구하는 조건)가 존재하기 때문입니다. #7~#9는 서비스 쪽 정보 자체가
없어 "무엇을 확인해야 하는지"조차 특정할 수 없으므로 확인 요청 대상에서 제외합니다.

---

## 6. 지역 규칙

`region_scope` 값 4가지(`NATIONAL`/`SIDO`/`SIGUNGU`/`UNKNOWN` — 현재 데이터엔 `UNKNOWN` 없음,
미래 데이터 대비 정의)에 따라 다르게 처리합니다.

| region_scope | 사용자 `sido` | 사용자 `sigungu` | 판정 규칙 |
|---|---|---|---|
| `NATIONAL` | 무관 | 무관 | 지역으로 절대 제외하지 않음 (전국 대상) |
| `SIDO` | 제공됨, 서비스 `sido`와 일치 | (비교 안 함) | 통과 |
| `SIDO` | 제공됨, 서비스 `sido`와 불일치 | — | **HARD EXCLUDE** |
| `SIDO` | 미제공(unknown) | — | UNKNOWN, 제외 안 함, `confirmation_needed`에 "거주 시도 확인 필요" |
| `SIGUNGU` | 일치 | 제공됨, 서비스 `sigungu`와 일치 | 통과 (지역 소프트 가점 최대) |
| `SIGUNGU` | 일치 | 제공됨, 서비스 `sigungu`와 불일치 | **HARD EXCLUDE** |
| `SIGUNGU` | 일치 | 미제공(unknown) | 통과하되 UNKNOWN 처리(시군구까지는 확인 안 됨) — 제외하지 않음, 소프트 가점 없음 |
| `SIGUNGU` | 불일치 | — | **HARD EXCLUDE** (시군구 비교 불필요, 시도부터 다름) |
| `SIGUNGU` | 미제공(unknown) | — | UNKNOWN, 제외 안 함, "거주 지역 확인 필요" |
| `UNKNOWN`(미래 대비) | 무관 | 무관 | 지역으로 제외하지 않음, `confirmation_needed`에 등재 |

서비스 쪽 `sido`/`sigungu`가 `region_scope`와 논리적으로 안 맞는 경우(예: `SIGUNGU`인데
`sigungu`가 비어있음 — 정합성 검사에서 이미 0건 확인됨, `recommendation_data_readiness.md` §9)는
방어적으로 `SIDO` 규칙으로 강등 처리하고 이상 로그를 남깁니다.

---

## 7. 연령 규칙

실제 존재하는 필드: `min_age`(숫자 또는 `unknown`), `max_age`(현재 전부 공란),
`age_condition_type`(`SIMPLE_MIN`/`COMPOUND`/`NONE`), `age_condition_note`(자유텍스트).

| age_condition_type | 규칙 |
|---|---|
| `SIMPLE_MIN` | `min_age`가 숫자로 존재. 사용자 `age`가 숫자로 존재하고 `age < min_age`이면 **HARD EXCLUDE**. `age >= min_age`면 통과(게이트 확정 MATCH). 사용자 `age` 미제공 시 UNKNOWN, 제외 안 함 |
| `COMPOUND` | "65세 이상 또는 노인성질환 65세 미만"처럼 복합조건. **`min_age` 하나만으로 HARD EXCLUDE 하지 않음.** `age >= min_age`(대표 임계값)이면 소프트 가점 + 통과. `age < min_age`여도 예외 경로가 있을 수 있으므로 배제하지 않고 `confirmation_needed`에 `age_condition_note` 원문과 함께 "연령 조건이 복합적이니 확인 필요" 등재 |
| `NONE` | `min_age`가 `unknown`. 연령으로 제외/가점 모두 하지 않음 (완전 중립) |
| (미래 대비) `SIMPLE_RANGE` | `min_age`~`max_age` 단일 범위. `age`가 범위를 벗어나면 HARD EXCLUDE. 현재 데이터엔 사례 없음 |

`max_age`가 존재하는데(현재는 없음) 사용자 `age`가 그보다 큰 경우도 `SIMPLE_MIN`/`SIMPLE_RANGE`
한정으로만 HARD EXCLUDE 규칙을 적용하고, `COMPOUND`에는 적용하지 않습니다.

---

## 8. service_type 매핑 (실제 데이터 기준)

실제 `service_type` 태그 5종과 보유 건수(중복 태그 포함 집계):

| 태그 | 보유 건수 |
|---|---|
| `meal_support` | 81건 |
| `community_care` | 12건 |
| `home_visit` | 6건 |
| `food_cost_support` | 1건 |
| `discharge_support` | 1건 |

`desired_support` ↔ 실제 매핑표:

| 사용자 desired_support | 매핑 대상 | 실측 매칭 가능 건수 | 비고 |
|---|---|---|---|
| 식사/반찬 지원 (`meal_support`) | `service_type`에 `meal_support` 포함 | 81건 | 가장 신뢰도 높은 매칭, 그러나 표본이 커서(§14 위험4) 이것만으로는 변별력 낮음 |
| 식품비/바우처 (`food_cost_support`) | `service_type`에 `food_cost_support` 포함 | **1건뿐** | 매칭되는 서비스가 극히 적음 — 나머지는 자연스럽게 POSSIBLE_MATCH/NEEDS_CONFIRMATION 낮은 순위 |
| 영양상담/교육 (`nutrition_counseling`) | **`service_type`에 대응 태그 없음.** `nutritionist_involvement=='direct'`(1건)만 구조화 근거 | 1건 | `classification_criteria.md`가 언급한 `nutrition_counseling`/`nutrition_education` 태그는 실제 85건에 존재하지 않음 — 이 옵션을 선택한 사용자에게는 "현재 데이터셋에 전문 영양상담 서비스가 매우 적습니다"를 명시적으로 안내해야 함 |
| 방문형 지원 (`home_visit`) | `service_type`에 `home_visit` 포함 | 6건 | |
| 통합돌봄 (`community_care`) | `service_type`에 `community_care` 포함 | 12건 | |
| 퇴원 후 연계 (`discharge_support`) | `service_type`에 `discharge_support` 포함 | **1건뿐** | 사실상 항상 매칭 실패, "데이터 부족" 안내 필수 |
| 잘 모르겠음 (`unsure`) | 전체 노출, 가점 없음(중립) | — | 하드 배제 없이 지역/연령 게이트만 적용된 전체 목록 노출 |

**다중 필요 처리**: 사용자가 `desired_support`를 복수 선택하면(예: `[meal_support, community_care]`),
서비스의 `service_type` 태그 집합과의 **교집합 크기**를 점수 요소로 사용합니다(교집합이 클수록
가점 증가, 0이면 이 항목 가점 없음 — 단, 하드 배제는 아님).

**하나의 서비스가 여러 필요와 연결**: `service_type`이 파이프(`|`)로 다중 태그를 가진 레코드
(예: `community_care|meal_support|home_visit`, 12건 중 일부)는 사용자가 그 중 하나만 선택해도
교집합이 성립하므로 정상적으로 매칭됩니다. 별도 처리 불필요 — 이미 §8 교집합 계산에 포함됨.

---

## 9. Scoring 후보 분석 (가중치는 확정하지 않음)

**원칙: 자격조건(HARD gate)과 사용자 필요(SOFT ranking)를 분리합니다.** HARD gate 통과 여부는
이진(통과/배제)이며, 통과한 서비스들 사이에서만 아래 SOFT 요소로 순위를 매깁니다. HARD gate
필드(지역/연령-SIMPLE_MIN/장애/소득)는 게이트 통과 후 **점수에 다시 더하지 않습니다** (이중 집행 방지
— 단, "게이트가 UNKNOWN으로 남은 항목 수"는 §10의 등급 결정에 별도로 반영됩니다).

| 요소 | 점수화 여부 | 상대적 중요도 | 왜 필요한가 | 잠재적 부작용 |
|---|---|---|---|---|
| 서비스 유형 일치 (`service_type` ∩ `desired_support`) | SOFT, 점수화 | **최고** | 유일하게 100% 커버리지를 가진 신뢰 가능한 신호이며 사용자가 직접 밝힌 필요를 반영 | `meal_support`가 81/85건이라 이 요소만으로는 대부분의 서비스가 비슷하게 높은 점수를 받아 변별력이 낮아짐(§14 위험6) — 반드시 다른 요소와 결합 필요 |
| 생활상황 일치 (독거 `single_household_required`, 거동불편 `homebound_or_mobility_condition`) | SOFT, 점수화 | 중간~높음 | 실제 도움이 필요한 정도를 반영(예: 거동불편 사용자에게 배달형 서비스 우선) | 커버리지가 각각 10.6%/43.5%뿐이라 대부분 0점(중립) — "점수가 낮다"가 아니라 "정보가 없다"임을 등급 설명에서 구분해야 함 |
| 지역 적합성(시군구 정밀 일치 보너스) | SOFT, 점수화(소폭) | 낮음~중간 | 이미 게이트를 통과했지만, 정확히 내 동네 사업인지가 체감 관련성에 영향 | 과도한 가중 시 전국/광역 사업이 부당하게 밀림(§14 위험4) — 소폭 보너스로 제한 |
| 연령 적합성(임계값과의 근접도) | **점수화하지 않음(게이트 전용)** | — | SIMPLE_MIN은 이미 게이트에서 통과/배제가 갈리므로 통과자 사이에서는 추가 정보가 거의 없음 | 게이트와 점수에 중복 반영하면 나이가 젊을수록/많을수록 부당 가중되는 왜곡 발생 |
| 저소득 조건 일치 | **점수화하지 않음(게이트 전용)** | — | 이미 HARD gate | 이중 집행 방지. 단, UNKNOWN(서비스 요구+사용자 모름)은 §10 등급 결정에서 확정도로 반영 |
| 장애 조건 일치 | **점수화하지 않음(게이트 전용)** | — | 이미 HARD gate | 동일 |
| `verification_level` | SOFT, 점수화(매우 소폭) | 낮음 | 데이터 신뢰도 반영, A/B 동률일 때 타이브레이커 | 과도한 가중 시 "데이터가 잘 정리된 서비스"가 "실제로 더 관련 있는 서비스"보다 우선시됨(§14 위험5) |
| `nutrition_relevance` / `nutritionist_involvement` | SOFT, 점수화(조건부, 매우 소폭) | 낮음 | 사용자가 영양상담을 원할 때만 의미 있는 신호 | 표본이 1~21건뿐이라 일반 가중치로 쓰면 거의 항상 0이거나 특정 1건에만 과도하게 작용 — `desired_support`에 영양상담이 포함될 때만 활성화 |
| `source_api`(central/local) | **점수화하지 않음, 참고 정보만** | — | 중앙부처/지자체 구분은 자격과 무관 | — |

**결론**: 점수 = `w1 × 서비스유형_교집합비율 + w2 × 생활상황_소프트매치 + w3 × 지역정밀도 +
w4 × verification_level + w5 × 영양관련(조건부)`. 정확한 `w1~w5` 수치는 이번 단계에서 확정하지
않고, 다음 구현 단계에서 §14 위험 분석을 반영해 조정합니다. 단, **`w1`이 다른 항목들의 합보다
커야 한다는 상대적 순서만** 이번 단계에서 못박습니다(서비스 유형 일치가 가장 중요한 신호).

---

## 10. 추천 등급 기준

3단계 체계를 유지합니다(사용자가 대안 제안 여지를 열어두었으나, 검토 결과 **3단계면 충분**하다고
판단했습니다 — 이유: 85건이라는 작은 데이터셋에서 4단계 이상으로 세분화하면 각 등급의 표본이
너무 작아져 등급 자체의 의미가 희석됩니다. 대신 "점수"와 "확정도(certainty)"라는 두 축을 결합해
3단계 안에서 필요한 구분을 모두 표현할 수 있습니다).

**등급은 단순 점수 cutoff가 아니라 "점수 + 게이트 확정도"로 결정합니다.**

게이트 확정도 정의: HARD gate 대상 4개 차원(지역/연령/장애/소득) 중 "서비스가 조건을 명시했는데
사용자 답변이 UNKNOWN인" 항목의 개수를 `open_count`라 합니다.

| 등급 | 조건 |
|---|---|
| `HIGH_MATCH` | 모든 HARD gate 통과 **AND** `open_count == 0` **AND** `desired_support`가 `unsure`가 아니고 `service_type`과 직접 교집합 존재 **AND** 소프트 점수가 상대적으로 높음(같은 게이트 확정도를 가진 서비스들 중 상위) |
| `POSSIBLE_MATCH` | 모든 HARD gate 통과 **AND** `open_count == 1` (핵심 조건 하나만 확인 필요) **AND** `desired_support` 교집합 존재 |
| `NEEDS_CONFIRMATION` | 다음 중 하나라도 해당: `open_count >= 2`(핵심 조건 다수 미확인) **OR** `desired_support == unsure` **OR** `age_condition_type == COMPOUND`로 인해 연령 게이트 자체가 불확실 **OR** 지역이 `SIGUNGU` 필요 매칭인데 사용자 `sigungu` 미제공(시도만 일치) |

**점수가 높아도 등급이 낮아지는 예시**: 서비스가 `disability_required=true`,
`low_income_required=true`를 명시했는데 사용자가 둘 다 `unknown`으로 답했다면, 서비스 유형이
완벽히 일치해 소프트 점수가 최고여도 `open_count=2`이므로 `HIGH_MATCH`가 아니라
`NEEDS_CONFIRMATION`이 됩니다. 이것이 이번 등급 체계의 핵심 안전장치입니다.

---

## 11. 추천 결과 Explanation Schema

```json
{
  "service_id": "WLF00003375",
  "service_name": "저소득 재가노인 식사배달(지방이양)",
  "region": {"sido": "강원특별자치도", "sigungu": "속초시", "region_scope": "SIGUNGU"},
  "service_type": ["meal_support"],

  "match_score": 74,
  "match_level": "POSSIBLE_MATCH",

  "matched_reasons": [
    "원하시는 '식사/반찬 지원'과 이 서비스의 제공 내용이 일치해요",
    "거주 지역(속초시)이 일치해요",
    "거동불편 조건이 일치하는 것으로 보여요"
  ],
  "unmatched_reasons": [],
  "confirmation_needed": [
    "소득 조건(기초생활수급자/차상위 등)은 이 서비스가 요구하지만, 입력하신 정보로는 확인되지 않아요"
  ],
  "eligibility_warnings": [
    "이 항목은 참고용 안내이며 실제 자격은 읍/면/동 주민센터 확인이 필요합니다"
  ],

  "verification_level": "B",
  "source": {
    "official_evidence": {
      "target_original": "...", "criteria_original": "...", "support_original": "..."
    }
  }
}
```

- **`matched_reasons`**(추천 이유)와 **`confirmation_needed`**(신청 전 확인할 조건)는 명확히
  분리된 배열입니다. UI에서도 "왜 추천됐는지"와 "가서 무엇을 확인해야 하는지"를 서로 다른
  섹션에 표시해야 합니다.
- `unmatched_reasons`는 HARD EXCLUDE되어 아예 결과에 없는 서비스의 사유가 아니라, **게이트를
  통과했지만 SOFT 차원에서 명확히 MISMATCH가 난 항목**(예: 독거 조건 불일치)을 담습니다.
- `eligibility_warnings`는 모든 결과에 공통으로 포함되는 고정 문구("참고용 안내이며...")와,
  §0에서 확인된 데이터 특이사항(예: 국가유공자 특수 자격체계, 복합 연령조건)이 있는 서비스에는
  해당 내용을 추가로 포함합니다.

---

## 12. 안전 규칙 (절대 금지 사항)

1. **원문에 없는 자격조건을 생성하지 않습니다.** 구조화 필드나 `age_condition_note` 등에
   근거가 없는 조건을 추론해 넣지 않습니다.
2. **UNKNOWN을 FALSE로 간주하지 않습니다.** §5 매트릭스를 항상 그대로 적용합니다.
3. **수급 가능 여부를 확정하지 않습니다.** 모든 결과 문구는 가능성 표현(§1)만 사용합니다.
4. **질환을 추정해서 자격을 부여하지 않습니다.** 사용자로부터 질환명·검사수치·약물정보를
   받지 않으므로(설계 문서 §2), 애초에 추정할 근거도 없습니다.
5. **단순 키워드 하나로 추천을 확정하지 않습니다.** 모든 판정은 §4~§10의 구조화된 규칙을
   통과해야 하며, 텍스트 키워드 매칭은 어디까지나 `recommendation_data_readiness.md`에서 이미
   완료된 2차 fallback 판정 결과(구조화 필드)를 사용하는 것이지, 런타임에 즉석 키워드 매칭으로
   자격을 결정하지 않습니다.
6. **LLM이 규칙 엔진 결과를 임의로 변경하지 않습니다.** `match_score`/`match_level`/
   `matched_reasons`/`confirmation_needed`는 전적으로 규칙 엔진이 산출하며, LLM(도입 시)은
   이를 자연어로 재서술하는 역할만 합니다(설계 문서 §10 RAG/LLM 역할 경계와 동일).
7. **데이터가 부족하다는 이유로 서비스를 인위적으로 상위에 올리지 않습니다.** UNKNOWN은
   중립(0점)이어야 하며, "조건이 적어서(=UNKNOWN이 많아서) MISMATCH가 없는 것처럼 보이는"
   서비스가 부당하게 유리해지지 않도록 §10의 게이트 확정도(open_count) 규칙으로 방지합니다.
8. **취약조건(장애/저소득/독거/거동불편)을 차별적으로 사용하지 않습니다.** 이 조건들은 오직
   "더 적합한 서비스를 찾기 위한" 매칭 신호로만 쓰이며, 어떤 경우에도 사용자의 순위를 낮추거나
   낙인적 문구를 생성하는 데 사용하지 않습니다.
9. **HARD EXCLUDE된 서비스도 삭제하지 않습니다.** 점수 계산 대상에서는 제외하되, 시스템
   내부적으로는 "왜 제외되었는지" 로그를 남겨 추후 감사(audit)가 가능해야 합니다(사용자 화면
   노출 여부는 UI 설계에서 별도 결정).

---

## 13. 테스트 시나리오 (최소 10개)

**주의**: 아래 시나리오의 "예상 동작"은 로직의 동작 방식(어떤 게이트가 걸리는지, 어떤 등급이
나올지의 경향)을 설명하는 것이며, 특정 `service_id`가 반드시 1위로 나와야 한다고 데이터 확인 없이
단정하지 않습니다. 실제 순위는 사용자가 입력하는 정확한 `sido` 값 등에 따라 달라집니다.

| # | 시나리오 | 예상 동작 |
|---|---|---|
| 1 | 75세, 강원 소재 시군구 거주, 독거=true, 식사준비어려움=true, 나머지 unknown | 지역 게이트 통과(강원 내 SIGUNGU/SIDO 서비스 다수), 연령 게이트 통과(min_age 65 이하 다수 통과), `meal_support` 교집합으로 다수가 POSSIBLE_MATCH~HIGH_MATCH. `single_household_required=true`인 9건 중 지역이 맞는 서비스는 소프트 가점으로 상위 |
| 2 | 70세, 저소득=true, 거동불편=true, desired_support=[meal_support] | 소득 게이트 통과(다수 서비스 low_income_required=true와 일치), 거동불편 소프트 가점 다수 적용, POSSIBLE_MATCH 다수, `open_count`가 낮아 일부 HIGH_MATCH 가능 |
| 3 | 68세, 장애=true, desired_support=[meal_support] | `disability_required=true`인 12건은 장애=true와 매치(가점), `disability_required=false`(6건)는 게이트 통과(무관), `unknown`(67건)은 게이트 통과하되 §10에서 `open_count` 미증가(서비스가 애초에 요구 안함, 매트릭스 #6/#9 성격과 유사하나 이 경우는 사용자TRUE+서비스UNKNOWN=매트릭스#7이므로 open_count에 안잡힘) |
| 4 | 66세, 취약조건 전부 false/평범, desired_support=[meal_support] | 장애/소득/독거/거동불편 전부 사용자=false → 서비스 조건이 true인 서비스와는 매트릭스#2(HARD 필드는 EXCLUDE), false/unknown인 서비스와는 매트릭스#4~9로 통과. 결과적으로 "저소득/장애 요건이 없는" 서비스 중심으로 좁혀짐 — 실제로 이런 서비스가 드물어(대부분 low_income_required=true) 후보 수가 적을 것으로 예상 |
| 5 | 지역(sido)만 입력, 나머지 전부 unknown, desired_support=unsure | 지역 게이트만 적용, 나머지 전부 UNKNOWN → 거의 모든 지역 내 서비스가 통과하되 등급은 대부분 `NEEDS_CONFIRMATION`(`desired_support=unsure`이므로 §10 규칙 즉시 적용) |
| 6 | 40세, 그 외 정상 입력 | `min_age`가 `SIMPLE_MIN`이고 65/60인 서비스(39건)는 전부 **HARD EXCLUDE**. `age_condition_type=NONE`(45건)/`COMPOUND`(12건)는 배제되지 않고 남음 — 즉 결과가 0건이 되지는 않지만 대상 서비스 성격이 바뀜(연령 무관 서비스 위주로 축소) |
| 7 | 사용자 sido가 서비스들이 속한 sido와 명백히 다름(예: 사용자=서울, 대상 서비스=경남 SIGUNGU) | 해당 서비스 **HARD EXCLUDE**. 단, `region_scope=NATIONAL`인 2건은 지역과 무관하게 계속 후보로 남음 |
| 8 | sido조차 미입력(unknown), 나머지도 전부 unknown | 지역 게이트가 UNKNOWN이 되어 배제 없이 전체 85건이 1차 후보 유지 → 그러나 실무적으로는 지역 없이 의미 있는 추천이 어려우므로, `confirmation_needed`에 "거주 지역 확인 필요"가 최우선으로 표시되고 등급은 대부분 `NEEDS_CONFIRMATION` 경향 |
| 9 | desired_support=[meal_support, community_care] (다중 선택) | 두 태그를 모두 가진 서비스(12건 `community_care` 태그 보유분 중 `meal_support`도 겸한 서비스, 실측 9건: `community_care|meal_support` 6 + `community_care|meal_support|home_visit` 2 + `meal_support|community_care` 2 등 조합)가 교집합 크기 2로 최고 가점, 단일 태그 서비스는 교집합 1로 그다음 |
| 10 | recent_discharge=true, desired_support=[discharge_support, community_care] | `discharge_support` 태그 보유 서비스가 **1건뿐**이므로 대부분 UNKNOWN/미매칭, `community_care`(12건)로 대체 매칭됨. 결과 상단에 "퇴원 후 연계에 특화된 서비스는 현재 데이터가 매우 적습니다" 안내 필수 |

---

## 14. 설계 검증 (위험 요소와 해결책)

| 위험 | 실제 발생 가능성(데이터 근거) | 해결책 |
|---|---|---|
| 과도한 HARD EXCLUDE | HARD gate를 지역/연령(SIMPLE_MIN)/장애/소득 4개로 제한하고, 전부 "양쪽 값이 구체적으로 존재하고 충돌할 때만" 발동하도록 설계(§5) | 이미 반영됨 — 독거/거동불편은 SOFT로 강등하여 과잉배제 방지 |
| UNKNOWN 때문에 좋은 서비스를 놓칠 위험 | UNKNOWN 비율이 매우 높음(장애 78.8%, 독거 89.4%, 거동불편 56.5%가 unknown) | UNKNOWN은 항상 중립(0점), 제외 없음(§5). §10에서 UNKNOWN이 많으면 등급만 낮추지 목록에서 빼지 않음 |
| 조건이 적은(=UNKNOWN이 많은) 서비스가 과도하게 상위에 뜰 위험 | 실제로 76건이 독거 unknown, 48건이 거동불편 unknown — "깨끗해 보이지만 사실 정보가 없는" 서비스가 많음 | §10의 `open_count` 규칙: 정보 부족은 `HIGH_MATCH` 승격을 막는 방향으로만 작동(가점 방향으로 작동하지 않음). UNKNOWN에 양의 점수를 절대 부여하지 않음(§5 #3,#7,#8,#9 모두 점수영향 0) |
| 지역 서비스 vs 전국 서비스 ranking 문제 | NATIONAL 2건, SIDO 12건, SIGUNGU 71건으로 불균형 | 시군구 정밀 일치는 "소폭" 보너스로 제한(§9), NATIONAL/SIDO 서비스가 관련성 낮다고 자동 간주하지 않음 |
| verification_level 낮은 서비스 과잉 상위 | B등급 35건(41%) — 상당수 | verification_level 가중치를 최저 수준(타이브레이커)으로 한정(§9) |
| meal_support만 과도하게 우대 | `meal_support` 태그가 81/85(95%)로 압도적 | 점수는 "meal_support 태그 보유"가 아니라 "사용자가 선택한 desired_support와의 교집합"에만 반응하도록 설계(§8, §9) — 사용자가 community_care/food_cost_support 등을 선택하면 그 신호만 가점, meal_support는 자동 가점되지 않음 |
| 장애/저소득/독거 조건의 차별적 사용 위험 | 해당 조건들이 그대로 노출되면 낙인 효과 우려 | §12 규칙 8: 매칭 신호로만 사용, 순위 하향이나 낙인적 문구 생성 금지. `matched_reasons` 문구는 항상 "~와 맞는 것으로 보여요" 톤 유지 |
| 데이터 결측이 점수에 유리하게 작용 | 위 "조건이 적은 서비스" 위험과 동일 근본 원인 | 동일 해결책(open_count 규칙 + UNKNOWN=0점 원칙)으로 대응 |

---

## 15. 알려진 한계

- 장애(21.2%)/독거(10.6%)/거동불편(43.5%) 조건의 **확정 판정률이 낮아**, 대다수 추천 결과가
  `POSSIBLE_MATCH`에 몰릴 것으로 예상됩니다. 이는 로직 결함이 아니라 원문 데이터의 한계이며,
  `docs/recommendation_data_readiness.md`에 이미 문서화되어 있습니다.
- `nutrition_counseling`(영양상담) 관련 `desired_support`는 구조화 매칭 대상이 사실상 1건뿐이라
  이 옵션을 선택하는 사용자에게는 항상 "데이터 부족" 안내가 함께 나가야 합니다.
- `discharge_support`(퇴원 후 연계)도 동일하게 1건뿐이라 유사한 한계가 있습니다.
- `max_age`/`SIMPLE_RANGE` 규칙은 정의만 되어 있고 현재 데이터로는 검증되지 않았습니다(사례 0건).
- 다중 하위서비스가 한 레코드에 묶인 경우(readiness 문서 §7에 정리된 사례들, 예: 경로식당+식사배달
  +밑반찬배달이 연령·독거 조건이 다른데 한 행으로 존재)는, 대표값 하나로 게이트를 적용하기 때문에
  일부 하위서비스에는 과도하게 관대하거나 엄격한 판정이 될 수 있습니다.

---

## 16. 다음 구현 단계

1. 이 명세를 그대로 따르는 순수 함수형 규칙 엔진 구현(§3 파이프라인, §4~§10 규칙) — 아직
   시작하지 않음.
2. §9에서 정의만 하고 확정하지 않은 가중치(`w1~w5`)를 실제 85건 + §13 시나리오로 시뮬레이션하며
   확정.
3. §13 테스트 시나리오를 회귀 테스트 케이스로 고정.
4. §11 explanation schema를 목데이터로 UI 프로토타입 검토.
5. RAG/LLM 계층은 규칙 엔진이 안정된 이후, `docs/recommendation_system_design.md` §10 역할
   경계 그대로 추가(근거 검색·문장 생성 역할로 한정, 판정에는 관여하지 않음).

---
