# 우리동네 영양돌봄 내비게이터 — 추천 시스템 설계 문서

> 이 문서는 **설계 문서**입니다. 추천 로직/RAG/LangChain/Vector DB/Streamlit 구현 코드는
> 포함하지 않습니다. 목적은 "무엇을 묻고, 무엇과 비교하고, 무엇을 모른다고 인정할지"를
> 확정하는 것입니다.

데이터 소스: `data/processed/welfare_services_final.csv` (85건, 28개 컬럼)

---

## 0. 데이터 실측 결과 (설계의 전제)

실제 CSV를 읽어 컬럼별 결측률과 값 분포를 확인했습니다. **아래는 가정이 아니라 실측치**입니다.

### 0.1 전체 컬럼 목록과 결측률

| # | 컬럼 | 의미 | 채움 비율 | 비고 |
|---|---|---|---|---|
| 1 | `service_id` | 서비스 고유 ID | 85/85 (100%) | 중복 0건 |
| 2 | `service_name` | 서비스명 | 85/85 (100%) | 고유값 77개 (동명이인성 서비스 존재) |
| 3 | `source_api` | 데이터 출처 | 85/85 (100%) | `local` 83건, `central` 2건 |
| 4 | `sido` | 광역시도 | 83/85 (97.6%) | 2건 결측 (중앙부처 사업으로 추정) |
| 5 | `sigungu` | 시군구 | 68/85 (80.0%) | 17건 결측 |
| 6 | `target_original` | 지원대상 원문 | 85/85 (100%) | 자연어 |
| 7 | `criteria_original` | 선정기준 원문 | 85/85 (100%) | 자연어 |
| 8 | `support_original` | 지원내용 원문 | 85/85 (100%) | 자연어 |
| 9 | `application_original` | 신청방법 원문 | 85/85 (100%) | **실질 정보 없음(`[]`) 29건 포함** |
| 10 | `contact` | 문의처 | 85/85 (100%) | 자연어, 기관명+전화번호 |
| 11 | `senior_relation` | 고령자 직접/조건부 관련 태그 | **31/85 (36.5%)** | `SENIOR_DIRECT` 4 / `SENIOR_CONDITIONAL` 27 |
| 12 | `nutrition_relevance` | 영양 직접 관련 태그 | **21/85 (24.7%)** | 값은 `DIRECT_NUTRITION` 뿐 (없음=미태깅, 부정 아님) |
| 13 | `service_type` | 서비스 유형(다중, `\|` 구분) | 85/85 (100%) | **가장 신뢰도 높은 구조화 필드** |
| 14 | `service_type_primary` | 주 서비스 유형 | **31/85 (36.5%)** | `service_type`과 동일 31건에서만 채움 |
| 15 | `service_type_secondary` | 부 서비스 유형 | 8/85 (9.4%) | |
| 16 | `min_age` | 최소 연령 | **10/85 (11.8%)** | `65` 2건, 문자열 `"unknown"` 8건 |
| 17 | `disability_required` | 장애 필수 여부 | **10/85 (11.8%)** | true 8 / false 2 |
| 18 | `low_income_required` | 저소득 필수 여부 | **10/85 (11.8%)** | true 7 / false 1 / `"unknown"` 2 |
| 19 | `single_household_required` | 독거 필수 여부 | **10/85 (11.8%)** | `"unknown"` 9 / true 1 (false 사례 없음) |
| 20 | `homebound_or_mobility_condition` | 거동불편 조건 | **10/85 (11.8%)** | true 2 / `"unknown"` 8 |
| 21 | `eligibility_summary` | 선정기준 요약(자연어) | **10/85 (11.8%)** | |
| 22 | `meal_support_flag` | 식사지원 여부 | **31/85 (36.5%)** | true 29 / false 2 |
| 23 | `food_cost_support_flag` | 식비지원 여부 | **10/85 (11.8%)** | false 9 / true 1 |
| 24 | `support_summary` | 지원내용 요약(자연어) | **10/85 (11.8%)** | |
| 25 | `nutritionist_involvement` | 영양사 개입 여부 | 85/85 (100%) | `not_specified` 84 / `direct` 1 |
| 26 | `verification_level` | 검증 등급 | 85/85 (100%) | A 50 / B 35 |
| 27 | `review_note` | 내부 검토 메모(자연어) | 85/85 (100%) | 내부용, 사용자 노출 부적합 |
| 28 | `data_quality_note` | 데이터 품질 이슈 메모 | 3/85 (3.5%) | 내부용 |

> **주의**: 사용자가 요청서에서 언급한 `region`, `senior_relation_v2` 컬럼은 **존재하지 않습니다**.
> 실제로는 `sido`/`sigungu` (지역), `senior_relation` (버전 접미사 없음)이 존재합니다. 없는 필드를
> 있다고 가정하지 않기 위해 이 문서 전체에서 실제 컬럼명만 사용합니다.

### 0.2 핵심 발견 — 구조화 필드는 "계층적으로" 비어 있다

컬럼별로 독립적으로 비어 있는 게 아니라, **정확히 동일한 행 집합**에서만 채워져 있습니다 (집합 비교로 확인).

```
전체 85건
 └─ service_type: 100% (85건) — 항상 존재, 신뢰 가능
 └─ sido/sigungu: 97.6%/80% — 지역, 대체로 신뢰 가능
 └─ nutritionist_involvement/verification_level: 100% — 존재하지만 값이 편중(대부분 not_specified/A,B)
 └─ 31건 그룹 { senior_relation, service_type_primary, meal_support_flag } ← 완전히 동일한 31개 행
     └─ 그 안의 10건 그룹 { min_age, disability_required, low_income_required,
                            single_household_required, homebound_or_mobility_condition,
                            eligibility_summary, support_summary, food_cost_support_flag }
                            ← 완전히 동일한 10개 행 (31건의 부분집합)
 └─ nutrition_relevance 21건 — 위 31건과 겹치지만 10건 그룹과는 전혀 겹치지 않음
 └─ 나머지 54건(63.5%)은 위 어떤 세부 구조화 필드도 전혀 없음
    (단, service_type/sido/sigungu/원문 3종은 여전히 100%에 가깝게 존재)
```

**의미**: 85건 중 54건(63.5%)은 "연령/장애/소득/독거/거동불편"을 판정할 구조화 필드가
**하나도 없고**, 오직 원문(`target_original`/`criteria_original`/`support_original`)과
`service_type`, `sido`/`sigungu`만 가지고 있습니다. 이 설계 전체(특히 §5, §6, §12)는
이 사실을 전제로 합니다.

### 0.3 구조화 필드로 바로 쓸 수 있는 것 / 어려운 것

| 구분 | 필드 | 이유 |
|---|---|---|
| **바로 사용 가능** | `service_id`, `service_name`, `sido`, `service_type`, `contact`, `verification_level` | 결측 거의 없음, 형식 일관 |
| **바로 사용 가능(주의 필요)** | `sigungu` | 20% 결측 — 없을 때 "지역불일치"로 오판하면 안 됨 |
| **바로 사용 가능(희소)** | `nutritionist_involvement` | 100% 채워져 있으나 사실상 1건만 `direct` — 변별력 낮음 |
| **제한적 사용 (10~31건만)** | `senior_relation`, `service_type_primary`, `meal_support_flag`, `nutrition_relevance` | 있으면 신뢰, 없으면 UNKNOWN 처리 |
| **매우 제한적 사용 (10건만)** | `min_age`, `disability_required`, `low_income_required`, `single_household_required`, `homebound_or_mobility_condition`, `food_cost_support_flag` | 85건 중 11.8%에서만 판정 가능 |
| **구조화 필드지만 사실상 자연어** | `eligibility_summary`, `support_summary` | 사람이 읽는 요약문, 규칙 매칭 입력으로는 부적합 |
| **완전 자연어(구조화 안 됨)** | `target_original`, `criteria_original`, `support_original`, `application_original`, `contact`, `review_note`, `data_quality_note` | 2차 fallback 소스로만 사용 |

---

## 1. 시스템 목적

- 고령자 본인 또는 보호자가 몇 가지 질문에 답하면, 85건의 영양돌봄 관련 복지서비스 중
  **관련성이 높은 서비스를 좁혀서 보여주는 것**이 목적입니다.
- **자격을 확정하거나 보장하지 않습니다.** 최종 자격 판정은 항상 소관 기관(주민센터,
  국민건강보험공단, 보훈청 등)의 몫이며, 이 시스템은 "확인해볼 만한 서비스 후보 + 확인이
  필요한 조건"을 정리해 보여주는 역할만 합니다.
- 데이터가 부족한 조건(§0.2)에 대해 **거짓 확신을 주지 않는 것**이 이 설계의 최우선 원칙입니다.

---

## 2. 사용자 입력 설계

### 2.1 사용자 유형
- 고령자 본인
- 고령자를 돌보는 보호자/가족 (대리 응답 — 매칭 로직에는 영향 없음, 문구 톤에만 영향)

### 2.2 입력 항목 평가

| 항목 | 필수/선택 | 추천 품질 중요도 | 현재 CSV 매칭 가능성 | 채택 여부 |
|---|---|---|---|---|
| 거주 시도 (sido) | **필수** | 높음 (하드필터) | 높음 (`sido` 97.6%) | ✅ 채택 |
| 거주 시군구 (sigungu) | 선택 | 중간 (정밀 랭킹) | 중간 (`sigungu` 80%) | ✅ 채택(선택) |
| 연령 | **필수** | 높음 (하드필터 후보) | 낮음 (`min_age` 11.8%만 명시, 나머지는 원문 fallback) | ✅ 채택하되 기대치 낮게 안내 |
| 장애 여부 | **필수(3상태)** | 높음 | 낮음 (`disability_required` 11.8%) | ✅ 채택 |
| 기초생활수급자 여부 | **필수(3상태)** | 높음 | 낮음 (`low_income_required` 11.8%) | ✅ "저소득층 여부"로 **통합** |
| 차상위 여부 | — | — | CSV가 수급자/차상위를 구분하지 않고 단일 `low_income_required`만 가짐 | ❌ 별도 질문 제거, 위 항목에 통합 |
| 기초연금 여부 | — | 낮음 | CSV에 대응 필드 없음 (딱 1건의 원문에서만 "건강권/일반권" 구분으로 언급) | ❌ MVP 제외 |
| 독거 여부 | **필수(3상태)** | 중간 | 낮음 (`single_household_required` 11.8%, false 값 자체가 없음) | ✅ 채택 |
| 거동 불편 여부 | **필수(3상태)** | 높음 | 낮음 (`homebound_or_mobility_condition` 11.8%) | ✅ 채택 |
| 식사 준비 어려움 여부 | **필수(3상태)** | 매우 높음 | 중간 (`meal_support_flag` 36.5%, `service_type` 100%로 보강 가능) | ✅ 채택 (실질 핵심 필드) |
| 최근 퇴원 여부 | 선택 | 낮음 (현재) | 매우 낮음 (`discharge_support` 태그 1/85건뿐) | ✅ 채택하되 "데이터 부족" 명시 |
| 원하는 도움 (desired_support) | **필수(다중선택)** | **가장 높음** | **높음** (`service_type` 100% 필드로 직접 매칭) | ✅ 채택 — 최우선 입력 |
| (신규) 응답자 유형 (본인/보호자) | 선택 | UX 톤 조정용, 매칭에는 미사용 | 해당 없음 | ✅ 추가 제안 |

**제외 결정 — 의료 정보**: 질환명, 검사수치, 약물정보는 CSV의 어떤 필드와도 대응되지 않고,
민감정보 처리 부담과 의료적 오판 리스크가 크므로 **MVP에서는 받지 않습니다.**
"거동불편 여부", "식사 준비 어려움 여부"처럼 생활기능 관점의 질문만으로 충분히 대체됩니다.

**부담 검토**: 필수 항목 7개(지역, 연령, 장애, 저소득, 독거, 거동불편, 식사준비어려움) +
다중선택 1개(원하는 도움)로 구성. 각 항목에 "모름"을 항상 허용하므로 응답 부담이 낮습니다.
시군구/최근퇴원/응답자유형은 선택 입력으로 남겨 진입장벽을 낮춥니다.

---

## 3. User Profile Schema

CSV 자체가 `true`/`false`/`unknown` 문자열 3상태 값을 이미 사용하고 있으므로(`low_income_required`,
`single_household_required`, `homebound_or_mobility_condition`, `min_age`), user_profile도
동일한 3상태 표기를 그대로 채택해 **비교 로직에서 별도 매핑이 필요 없도록** 설계합니다.

```python
from typing import Literal, Optional

TriState = Literal["true", "false", "unknown"]

user_profile = {
    # 지역 — 필수 / 선택
    "sido": Optional[str],              # 필수 입력, CSV `sido`와 문자열 직접 비교
    "sigungu": Optional[str],            # 선택 입력, CSV `sigungu`와 직접 비교, 없으면 None

    # 연령 — 필수 (숫자, 응답 거부 시 None)
    "age": Optional[int],

    # 3상태 조건들 — 모두 "모름" 허용
    "has_disability": TriState,
    "low_income_status": TriState,       # 수급자/차상위 통합
    "lives_alone": TriState,
    "mobility_difficulty": TriState,
    "meal_preparation_difficulty": TriState,
    "recent_discharge": TriState,

    # 원하는 도움 — 필수, 다중 선택
    # CSV service_type 태그값과 동일한 어휘 사용 (변환 테이블 불필요)
    "desired_support": list[
        Literal[
            "meal_support",        # 식사/도시락/반찬 지원
            "food_cost_support",    # 식비/식재료 지원
            "nutrition_counseling", # 영양상담 (CSV엔 nutritionist_involvement로 대응)
            "home_visit",           # 방문관리
            "community_care",       # 지역사회 돌봄
            "discharge_support",    # 퇴원 후 돌봄
            "unsure",               # 어떤 도움이 필요한지 모르겠음
        ]
    ],

    # 매칭에는 미사용, 결과 문구 톤 조정용
    "respondent_type": Literal["self", "caregiver"],
}
```

- `has_disability` 등 조건 필드에 `"unknown"`을 문자열로 쓰는 이유: CSV의 `low_income_required`,
  `single_household_required`, `homebound_or_mobility_condition`, `min_age`가 이미 빈 값이 아니라
  **명시적으로 `"unknown"` 문자열을 쓰는 경우가 있음**을 확인했습니다(§0.1). 사용자 쪽과
  서비스 쪽이 같은 어휘를 쓰면 비교 함수가 단순해집니다.
- `age`는 CSV `min_age`가 숫자(`"65"`)이거나 문자열 `"unknown"`이므로, 비교 시 서비스 쪽
  `min_age`가 숫자로 파싱되지 않으면 무조건 UNKNOWN 처리합니다.

---

## 4. 사용자 입력 ↔ 서비스 데이터 매핑

| user_profile 필드 | 1순위 (구조화 필드) | 2순위 (원문 fallback) | 3순위 | 비고 |
|---|---|---|---|---|
| `sido` | `sido` | `contact` 텍스트에서 지역명 추출 | RAG (원문 검색) | 2건은 중앙부처 사업(sido 결측) → 지역 무관으로 처리, 제외하지 않음 |
| `sigungu` | `sigungu` | `contact`, `target_original`/`criteria_original` 텍스트 | RAG | 17건 결측. `data_quality_note`에 실제로 "sigungu 누락, contact으로 추정 가능" 사례 확인됨 |
| `age` | `min_age` (숫자인 경우만) | `criteria_original`/`target_original` 내 "OO세 이상" 패턴 | RAG | `min_age`가 10건뿐이라 대부분 2순위 필요 |
| `has_disability` | `disability_required` | 원문 내 "장애인" 키워드 | RAG | 10건만 구조화됨 |
| `low_income_status` | `low_income_required` | 원문 내 "수급자"/"차상위" 키워드 | RAG | 10건만 구조화됨 |
| `lives_alone` | `single_household_required` | 원문 내 "독거" 키워드 | RAG | 10건뿐이지만 원문에는 "독거"가 매우 자주 등장(샘플 확인) |
| `mobility_difficulty` | `homebound_or_mobility_condition` | 원문 내 "거동불편"/`service_type`에 `home_visit` 포함 여부 | RAG | 10건만 구조화됨 |
| `meal_preparation_difficulty` / `desired_support`(meal) | `meal_support_flag`, **`service_type`에 `meal_support` 포함** | `support_original` 텍스트 | — | `service_type`이 100% 채워져 있어 사실상 1순위만으로 충분 |
| `desired_support`(food_cost) | `food_cost_support_flag`, `service_type`에 `food_cost_support` 포함 | `support_original` | — | |
| `desired_support`(nutrition_counseling) | `nutritionist_involvement` | `support_original` 내 "영양사"/"영양상담" 키워드 | RAG | `nutritionist_involvement`가 100%지만 사실상 1건만 `direct`라 2순위 비중이 큼 |
| `desired_support`(home_visit/community_care) | `service_type`에 해당 태그 포함 | — | — | 신뢰도 높음 (100% 필드) |
| `desired_support`(discharge_support) | `service_type`에 `discharge_support` 포함 | 원문 내 "퇴원" 키워드 | RAG | 태그 보유 서비스 1/85건뿐 — 대부분 UNKNOWN 예상 |
| `recent_discharge` | (대응 구조화 필드 없음) | `service_type`의 `discharge_support`, 원문 "퇴원" 키워드 | RAG | 신호 매우 약함, 랭킹 가중치 낮게 |

**Fallback 우선순위 원칙 (전 필드 공통)**:

1. **구조화 필드**가 존재하면 그대로 사용 (신뢰도 최상)
2. 없으면 **원문 텍스트의 규칙기반 키워드/정규식 매칭** (LLM 아님, 결정적 규칙)
3. 그래도 판정 불가하면 **UNKNOWN 유지** — RAG/LLM은 이 시점부터 "설명"만 담당하고,
   **최종 MATCH/MISMATCH 판정을 LLM이 내리지 않습니다.**

---

## 5. 하드 필터 (HARD_EXCLUDE) 설계

원칙: **조건 정보가 없거나 사용자가 "모름"으로 답하면 절대 자동 제외하지 않습니다.**
값이 양쪽 다 명확하게 존재하고 명백히 충돌할 때만 제외합니다.

| # | 조건 | HARD_EXCLUDE 발동 조건 | 비고 |
|---|---|---|---|
| 1 | 지역 불일치 | 서비스 `sido`가 존재하고, `source_api=local`이며, 사용자 `sido`와 다름 | `source_api=central`(2건)은 지역 무관 처리, 제외 안 함. `sido` 결측 시 UNKNOWN, 제외 안 함 |
| 2 | 연령 불일치 | `min_age`가 숫자로 파싱되고, 사용자 `age`가 그보다 명확히 낮음 | `min_age`가 `"unknown"`이거나 결측이면 제외 안 함 |
| 3 | 장애 조건 불일치 | `disability_required="true"`이고 사용자 `has_disability="false"` | 반대(서비스 disability_required=false, 사용자=장애인)는 제외 사유 아님 — "장애 무관"으로 해석 |

- 그 외 "지원대상이 명확히 다른 집단"(예: 국가유공자 전용) 같은 조건은 구조화 필드가 없어
  **자동 HARD_EXCLUDE로 넣지 않습니다.** 오탐 위험이 크기 때문에, 이번 단계에서는 원문을
  보여주고 "확인 필요"로 남기는 쪽을 선택합니다 (향후 태깅 보강 대상).
- "서비스 종료 여부"는 현재 CSV에 대응 필드가 없어 하드필터 불가 — 향후 필드 추가 필요.

**하드필터 개수: 3개**, 모두 "값이 있을 때만 조건부로 작동"하는 조건입니다.

---

## 6. MATCH / MISMATCH / UNKNOWN 규칙

전 조건에 공통으로 적용하는 원칙:

> **서비스 쪽 필드가 비어 있거나 `"unknown"`이면 → 무조건 UNKNOWN**
> **사용자가 "모름"으로 답했으면 → 무조건 UNKNOWN**
> 양쪽 모두 구체적인 값이 있고 서로 충돌할 때만 MISMATCH.
> 양쪽 모두 구체적인 값이 있고 일치할 때만 MATCH.

| 조건 | MATCH | MISMATCH | UNKNOWN |
|---|---|---|---|
| 연령 | `min_age` 숫자 ≤ 사용자 `age` | `min_age` 숫자 > 사용자 `age` | `min_age` 결측/`"unknown"` 또는 사용자 `age` 미입력 |
| 지역 | `sido`/`sigungu` 일치 (또는 central 서비스) | `sido` 다름(§5의 하드필터로 이미 걸러짐 — 랭킹 단계에서는 `sigungu` 세부 일치만 비교) | `sigungu` 결측 |
| 장애 | 둘 다 `true` 또는 둘 다 "무관" | `disability_required=true` & `has_disability=false` (하드필터로 이미 제거됨) | `disability_required` 결측 또는 `has_disability="unknown"` |
| 소득 | `low_income_required`와 `low_income_status` 값 일치 | 값이 명확히 반대 | `low_income_required` 결측/`"unknown"` 또는 사용자 `"unknown"` — 예: "저소득층 대상" 서비스인데 사용자가 소득상태 모름 → **MISMATCH 아니라 UNKNOWN**, 결과에는 "소득 조건 추가 확인 필요"로 표시 |
| 독거 | 둘 다 `true` | 이론상 가능하나 현재 데이터에 `single_household_required=false` 사례가 없어 사실상 발생 안 함 | 둘 중 하나라도 결측/`"unknown"` |
| 거동불편 | 둘 다 `true` | 현재 데이터에 false 사례 없음, 사실상 미발생 | 둘 중 하나라도 결측/`"unknown"` |
| 기타 정성 조건 (원하는 도움) | `desired_support`와 `service_type` 교집합 존재 | 원칙적으로 MISMATCH 개념 적용 안 함(제외 사유 아니므로) — 교집합 없음은 랭킹 감점일 뿐 | `desired_support=["unsure"]`인 경우 전체 UNKNOWN 취급, 감점 없이 전체 노출 |

---

## 7. 추천 Ranking 설계

하드필터(§5) 통과 후, 소프트 점수 요소만 나열합니다. **숫자 가중치는 여기서 확정하지 않고,
구성요소와 처리 방식만 정의합니다.**

| 요소 | 중요도 | 하드필터 vs 소프트 | UNKNOWN 처리 |
|---|---|---|---|
| 원하는 도움(`desired_support`) ↔ `service_type` 교집합 | **최상** | 소프트 (핵심 랭킹 동력) | `desired_support=["unsure"]`면 가점 0, 전체 노출 |
| 식사 준비 어려움 ↔ `meal_support_flag`/`service_type` | 최상 | 소프트 | 사용자 "모름"이면 가점 0 |
| 거동불편 ↔ `home_visit`/배달형 `service_type` | 높음 | 소프트 | UNKNOWN → 가점 0 |
| 독거 ↔ `single_household_required` | 중간 | 소프트 | UNKNOWN → 가점 0 |
| 지역 세부 일치 (`sigungu`) | 중간 | 소프트 (시도 일치는 이미 하드필터에서 처리됨 — 중복 방지) | `sigungu` 결측 → 가점 0 |
| 연령 근접도 | 중간 | 소프트 (명백한 불일치는 이미 하드필터에서 제거됨) | UNKNOWN → 가점 0 |
| 장애 조건 일치 | 중간 | 소프트 (명백한 불일치는 하드필터에서 제거됨) | UNKNOWN → 가점 0 |
| 저소득 조건 일치 | 중간 | 소프트 | UNKNOWN → 가점 0 |
| 최근 퇴원 ↔ `discharge_support`/`community_care` | **낮음 (데이터 희소, 1/85건)** | 소프트 | 대부분 UNKNOWN → 가점 0. 현재 데이터에서는 사실상 랭킹에 거의 기여하지 못함 |
| `verification_level` | 낮음~중간 | 소프트 (사용자 조건과 무관, 데이터 신뢰도 가점) | 결측 없음(100%) — UNKNOWN 없음 |
| `nutritionist_involvement` | **낮음 (1/85건만 `direct`)** | 소프트 | 대부분 `not_specified` → 가점 0. 향후 데이터 보강 시 가중치 상향 검토 |

- 하드필터에서 이미 제거된 명백한 불일치가 소프트 점수에서 다시 감점되는 **이중 처리를
  하지 않습니다.** 소프트 점수는 "근접도/부분일치/신뢰도" 가산에만 사용합니다.
- 점수는 **설명 가능한 가중합**이어야 하며, LLM이 임의로 최종 순위를 재조정하지 않습니다.
- 모든 소프트 요소가 UNKNOWN이어도 `desired_support` 교집합만으로 최소 노출 우선순위를
  가지도록 하여, 데이터 희소성 때문에 서비스가 완전히 묻히지 않게 합니다.

---

## 8. 추천 등급 설계

| 등급 | 한국어 라벨 | 조건 |
|---|---|---|
| `HIGH_MATCH` | 높은 관련성 | 하드필터 통과 + `desired_support` 직접 일치 + 핵심 조건(장애/소득/독거/거동/연령) 중 MISMATCH 없음 + UNKNOWN보다 확인된 MATCH가 많음 |
| `POSSIBLE_MATCH` | 관련 서비스로 보여요 | 하드필터 통과 + `desired_support` 일치는 있으나, 나머지 핵심 조건 대부분이 UNKNOWN (현재 데이터 상태에서 **대다수 서비스가 이 등급**에 해당할 것으로 예상) |
| `NEEDS_CONFIRMATION` | 조건 확인이 필요해요 | 하드필터는 통과했지만 `desired_support` 자체가 모호(`unsure`)하거나, 핵심 조건 전반이 UNKNOWN이라 판단 근거가 부족한 경우. 또는 근거가 낮은 텍스트 fallback(2순위)에만 의존해 MATCH가 나온 경우 |

**금지 표현**: "이용 가능", "자격 충족", "지원 대상입니다" 등 확정적 표현은 사용하지 않습니다.
대신 "조건에 부합할 가능성이 있어요", "~조건 확인이 필요해요"와 같은 완곡 표현을 사용합니다.

---

## 9. 최종 추천 결과 Schema

```json
{
  "service_id": "WLF00003248",
  "service_name": "저소득 재가노인 식사배달",
  "region": { "sido": "강원특별자치도", "sigungu": "속초시" },

  "match_level": "HIGH_MATCH",
  "match_score": 78,

  "matched_conditions": [
    "desired_support:meal_support",
    "region:sido",
    "region:sigungu",
    "mobility_difficulty"
  ],
  "unmatched_conditions": [],
  "unknown_conditions": [
    "low_income_status",
    "lives_alone",
    "age"
  ],

  "recommendation_reason": "식사배달 서비스를 찾고 계셔서, 거주 지역의 식사배달형 서비스를 우선 안내해드려요. 소득 조건과 독거 여부는 원문에서 확인되지 않아 추가 확인이 필요해요.",

  "support_summary": "1. 업무협약 식사배달사업 기관: 2개소 ... 식자재비 1식(5,000원), 유류비 지원",
  "eligibility_summary": "거동불편·저소득 재가노인 대상 도시락 배달(주5회) ...",

  "application_method": "읍면 방문신청",
  "contact": "속초시 사회복지과: 033-xxx-xxxx",

  "nutritionist_involvement": "not_specified",
  "verification_level": "A",

  "source": {
    "source_api": "local",
    "official_evidence": {
      "target_original": "...",
      "criteria_original": "...",
      "support_original": "..."
    }
  }
}
```

**현재 데이터에 없는 필드는 어떻게 채우나**:

| 필드 | 상태 | 채우는 방법 |
|---|---|---|
| `support_summary` / `eligibility_summary` | 85건 중 10건만 존재 | 없으면 `support_original`/`criteria_original` 원문을 그대로 노출 (LLM이 사실과 다른 요약을 새로 만들지 않음). 후속 작업으로 나머지 75건에 대한 요약을 **사람이 검수한 배치 작업**으로 채우는 것을 권장 |
| `application_method` | 29건이 `[]`(정보 없음) | "신청 방법 정보가 없어요. 문의처에 직접 확인해주세요"로 표시 |
| `region.sigungu` | 17건 결측 | `null`로 두고 UI에서 "시군구 정보 없음"으로 표시, 지역 하드필터에는 영향 없음(§5) |
| `match_score` 숫자 | 신규 계산값 | §7 가중합으로 런타임에 계산 (구현 단계에서 확정) |

---

## 10. RAG / LLM 역할 경계

| 구성요소 | 역할 |
|---|---|
| **규칙 기반 엔진** | 지역 필터, 연령조건 비교, 장애조건 비교, 소득조건 비교, 서비스 유형 매칭, `match_level`/`match_score` 산출, MATCH/MISMATCH/UNKNOWN 판정 (§4~§8 전체) |
| **RAG** | `target_original`/`criteria_original`/`support_original`/`application_original` 원문에서 근거 구절 검색, 선정기준 설명 구절 검색, 신청방법 근거 구절 검색, "추가 확인이 필요한 조건" 후보 텍스트 검색 |
| **LLM** | RAG가 찾아온 원문 근거를 이해하기 쉬운 문장으로 재서술, `recommendation_reason` 문장 생성(반드시 matched/unmatched/unknown 리스트에 근거), "확인해야 할 조건" 정리 문구 생성 |

**LLM이 절대 하지 않는 일**:
- 수급자격을 확정하거나 보장하는 표현 생성
- 원문에 없는 조건/숫자/기준을 새로 만들어내는 것
- 의료진/영양사 상담을 대체하는 조언 제공
- 원문과 다른 내용을 생성하거나 원문을 왜곡
- 규칙 엔진이 산출한 `match_level`/`match_score`를 자체 판단으로 바꾸는 것

---

## 11. 사용자 시나리오 검증 (5건)

실제 CSV에 존재하는 서비스명만 사용합니다: "저소득 재가노인 식사배달", "경로식당 무료급식사업",
"노인맞춤돌봄지원 강화 사업", "재가급여", "국가유공자재가복지지원".

### A. 75세 / 독거 / 거동불편 / 저소득 / 식사 준비 어려움
- **하드필터**: 사용자 거주 `sido` 일치 서비스만 통과. 연령 75는 `min_age`가 있는 서비스(65)도 통과.
- **랭킹 상승**: `desired_support=meal_support` → "저소득 재가노인 식사배달"류 최상위. 거동불편 → 방문/배달형 가점.
- **UNKNOWN**: 독거·저소득 조건은 대부분 서비스에서 구조화 필드가 없어(§0.2) UNKNOWN 처리, "독거/소득 조건 확인 필요"로 표시.
- **결과 형식**: 식사배달류는 `HIGH_MATCH`, 나머지 지역사회돌봄류는 `POSSIBLE_MATCH`.

### B. 68세 / 장애 있음 / 저소득 / 식사지원 희망
- **하드필터**: `disability_required=true`인 서비스도 사용자가 장애인이므로 제외되지 않음(통과). `disability_required=false`(장애 무관) 서비스도 당연히 통과.
- **랭킹 상승**: 장애조건 일치 시 가점 + `desired_support=meal_support` 가점.
- **UNKNOWN**: 지역/독거/거동은 사용자가 답하지 않았다고 가정 시 UNKNOWN.
- **결과 형식**: 장애 관련 태그가 있는 급식 서비스 → `HIGH_MATCH`, 그 외 → `POSSIBLE_MATCH`.

### C. 72세 / 최근 퇴원 / 식사보다 지역사회 돌봄 희망
- **하드필터**: 연령/지역만 적용.
- **랭킹 상승**: `service_type`에 `community_care` 포함된 서비스(약 9~10건) 가점. `discharge_support` 태그는 85건 중 1건뿐이라 사실상 거의 안 나옴.
- **UNKNOWN**: `recent_discharge` 대응 구조화 필드가 없어 항상 UNKNOWN.
- **결과 형식**: 대부분 `POSSIBLE_MATCH`/`NEEDS_CONFIRMATION`. "퇴원 후 돌봄에 특화된 서비스는 현재 데이터가 많지 않습니다" 안내 문구 포함.

### D. 80세, 보호자가 대신 검색 / 소득상태 모름
- **하드필터**: 지역/연령만 적용 (`respondent_type=caregiver`는 문구 톤에만 영향).
- **소득 조건**: 사용자가 "모름" → `low_income_required=true`인 서비스도 자동 배제 **안 함**, UNKNOWN 처리.
- **결과 형식**: 소득이 핵심 조건인 서비스는 `NEEDS_CONFIRMATION`으로 강등 권장, `unknown_conditions`에 "저소득 여부" 명시, "읍면동 주민센터에서 소득 조건 확인이 필요해요" 안내.

### E. 66세 / 특별한 취약조건 없음 / 영양 관련 도움을 찾음
- **하드필터**: 연령/지역만.
- **랭킹 상승**: `nutritionist_involvement=direct`인 유일 1건이 있으면 최상위, 그 외엔 `support_original` 텍스트 내 "영양" 키워드 매칭으로 부분 가점(2순위 fallback).
- **결과 형식**: 대부분 `POSSIBLE_MATCH`. "영양 상담을 전문으로 제공하는 서비스는 현재 데이터셋에 많지 않습니다" 같은 한계 안내 필요.

---

## 12. 현재 85건 데이터의 한계 평가

**판정: B — 일부 핵심 필드만 추가 보강하면 가능** (전면 재전처리는 불필요)

**판정 이유**:
- 추천에 가장 중요한 두 축인 **"지원 유형 매칭"**(`service_type`, 100% 채움)과 **"지역 하드필터"**(`sido`, 97.6% 채움)는 이미 거의 완전하게 구조화되어 있어, 핵심 사용자 경험("내 지역의, 내가 원하는 유형의 서비스")은 현재 데이터만으로도 동작합니다.
- 반면 연령/장애/소득/독거/거동불편처럼 세밀한 조건은 85건 중 **10건(11.8%)에만** 구조화되어 있고, 54건(63.5%)은 이 축에서 아무 구조화 신호가 없습니다.
- 하지만 이 54건도 **원문(`target_original`/`criteria_original`/`support_original`)은 100% 존재**하며, 샘플 검토 결과 "장애인", "수급자", "차상위", "독거", "거동불편", "65세 이상" 같은 키워드가 원문에 실제로 등장합니다. 즉 **새로 조사할 필요 없이, 기존 원문에서 규칙기반으로 추출만 하면 되는** 작업이라 전면 재전처리가 아닙니다.
- §6의 UNKNOWN 우선 설계 덕분에, 필드가 없는 상태에서도 시스템이 "틀린 확답"을 주지 않고 안전하게 동작합니다. 다만 `HIGH_MATCH` 비율은 낮고 `POSSIBLE_MATCH`/`NEEDS_CONFIRMATION` 비중이 커질 것으로 예상됩니다 — 이는 데이터 부족의 자연스러운 결과이며 설계 결함이 아닙니다.

**우선순위별 최소 보강 제안**:

| 우선순위 | 대상 필드 | 작업 방식 | 예상 작업량 |
|---|---|---|---|
| 0 (즉시, 작업 불요) | `service_type_primary` 대체 | 이미 100% 채워진 `service_type`을 그대로 다중태그로 사용 — 별도 보강 불필요 | 없음 |
| 1 | `low_income_required`, `disability_required` (75건) | `criteria_original`/`target_original` 내 "수급자"/"차상위"/"장애인" 키워드 규칙 추출 | 소규모 (원문 존재, 정규식+표본 검수) |
| 2 | `single_household_required`, `homebound_or_mobility_condition` (75건) | "독거"/"거동불편" 키워드 규칙 추출 | 소규모 |
| 3 | `sigungu` (17건 결측) | `contact` 필드에서 시군구명 정규식 추출 (`data_quality_note`에 실제 사례 확인됨) | 매우 소규모 |
| 4 (신중히) | `min_age` (75건) | "OO세 이상" 패턴 추출 — 하드필터 임계값이므로 **자동 추출 후 사람 검수 필수** (잘못 추출 시 부당 배제 위험) | 중간 (검수 비중 큼) |
| 5 (낮은 ROI, 보류) | `nutritionist_involvement`, `food_cost_support_flag` 세분화 | 데이터 자체가 희소(각 1건/10건)해 지금 보강해도 개선 폭이 작음 — 추후 신규 서비스 추가 시 재검토 | 보류 |

---

## 13. 구현 전에 필요한 최소 보강 작업 (요약)

1. §12 우선순위 1~3 (저소득/장애/독거/거동불편 키워드 추출 + 시군구 보강) — 규칙기반 스크립트, 결과는 검증등급 B로 표시.
2. `min_age` 추출은 사람 검수를 거친 뒤 반영.
3. `application_original="[]"` 29건에 대한 UI 문구("신청방법 정보 없음") 확정.
4. 텍스트 fallback용 키워드 사전(예: "독거"→lives_alone, "장애인"→has_disability 등) 정의 — 이번 문서 범위 밖, 별도 작업으로 분리.

---

## 14. 구현 순서 (제안)

1. 규칙 기반 매칭 함수 구현 (§4~§8) — 순수 함수, LLM/RAG 미포함
2. §12 우선순위 1~3 텍스트 fallback 키워드 추출 스크립트 작성 및 검수
3. 5개 시나리오(§11)를 테스트 케이스로 고정, 회귀 테스트화
4. 추천 결과 schema(§9) 확정 및 목데이터로 UI 프로토타입 검토
5. RAG/LLM 계층(§10)은 규칙 엔진이 안정된 이후 추가 — 근거 검색과 문장 생성 역할로 한정

---
