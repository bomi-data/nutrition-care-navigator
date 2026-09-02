# 추천 엔진 입력 데이터 준비 문서 (Recommendation Data Readiness)

> 이 문서는 `data/processed/welfare_services_final.csv`(85건)를 원문 근거에 한해 보강하여
> `data/processed/welfare_services_recommendation_ready.csv`를 생성한 과정과 검증 결과를 기록합니다.
> **추측으로 값을 생성한 항목은 없습니다.** 원문(target_original/criteria_original/support_original/
> application_original/service_name/contact/sido/sigungu)과 기존 검증된 구조화 필드만 근거로 사용했습니다.

---

## 1. 보강 목적

`docs/recommendation_system_design.md`에서 확정한 추천 엔진 설계를 실제로 구현하기 전에,
85건의 서비스가 그 설계가 요구하는 핵심 조건 필드(지역/연령/장애/소득/독거/거동불편/서비스유형)를
얼마나 갖추고 있는지 원문 근거로 보강하고, 그 결과를 검증하여 **추천 엔진이 그대로 읽을 수 있는
최종 입력 파일**을 확정하는 것이 목적입니다. 이번 작업 이후 데이터 전처리/보강은 종료하고
규칙 기반 추천 엔진 구현 단계로 넘어갑니다.

## 2. 사용한 원문 필드

- `target_original` (지원대상 원문)
- `criteria_original` (선정기준 원문)
- `support_original` (지원내용 원문)
- `service_name` (서비스명 — 예: "거동불편 재가노인 식사배달"처럼 조건이 서비스명에만 명시된 경우)
- `contact` (문의처 — 시군구 추정 근거로 사용)
- `sido` / `sigungu` (기존 지역 필드)
- 기존에 이미 검증된 구조화 필드(`service_type`, `senior_relation`, `service_type_primary` 등, 10건/31건 그룹)

`application_original`은 신청방법 관련 필드라 이번 조건 보강(연령/장애/소득/독거/거동불편)에는
직접적인 근거로 쓰이지 않았습니다. 외부 웹 검색이나 신규 API 호출은 전혀 사용하지 않았습니다.

## 3. 보강 규칙

### 3.1 절대 원칙
- 원문에 명시되지 않은 값은 생성하지 않습니다. "노인"/"어르신"만 있고 숫자가 없으면 `min_age`는
  `unknown`으로 남깁니다.
- 조건이 "언급되지 않음"과 "명시적으로 불필요함"을 구분합니다. 예: "노인, 장애인 등 시민 누구나"처럼
  장애 여부와 무관하게 이용 가능함이 명시된 경우에만 `disability_required=false`로 판정하고,
  단순히 장애 언급이 없는 경우는 `unknown`으로 둡니다.
- **이미 검증된 값(10건/31건 그룹)은 절대 덮어쓰지 않았습니다.** 이번 보강은 기존에 비어 있던
  셀에만 적용됩니다.

### 3.2 필드별 판정 규칙

| 필드 | TRUE 판정 | FALSE 판정 | UNKNOWN 유지 |
|---|---|---|---|
| `disability_required` | "등록장애인", "장애인" 등이 자격조건으로 명시되고, 대체 자격군(노인 단독 등)이 없는 경우 | "노인, 장애인 등"처럼 장애 여부와 무관하게 이용 가능함이 명시된 경우 | 장애 언급이 없거나, 여러 대상군 중 하나로만 병렬 열거되어 필수조건인지 불명확한 경우 |
| `low_income_required` | "기초생활수급자", "차상위계층", "저소득" 등이 명시된 경우 | "소득수준과 상관없이" 등 명시적 무관 표현 | 소득 관련 언급이 전혀 없거나, 소득이 자격요건이 아니라 본인부담률만 좌우하는 구조(예: SOS센터형 사업)인 경우 |
| `single_household_required` | "독거노인", "홀로 사는 어르신" 등이 유일한 가구유형 설명으로 등장하는 경우 | (원문에 명시적 반례 없음 — 이번 데이터셋에서 발생하지 않음) | 독거가 "노인가구", "노인부부세대" 등 다른 가구유형과 병렬 열거된 경우 (배타적 필수조건 아님) |
| `homebound_or_mobility_condition` | "거동불편", "거동이 어려운" 등이 대상 설명에 명시된 경우 (서비스명 포함) | (명시적 반례 없음) | 거동 관련 언급이 전혀 없는 경우 |
| `min_age` / `age_condition_type` | "NN세 이상" 단일 기준 → `SIMPLE_MIN` | — | 숫자 언급이 없으면 `min_age=unknown`, `age_condition_type=NONE` |

### 3.3 복합 연령조건 처리
"65세 이상 노인 및 노인성 질병을 가진 65세 미만 국민"(장기요양보험), "60세 이상(저소득) 또는
75세 이상(독거) 또는 80세 이상(노인부부)"처럼 하나의 서비스에 여러 연령 경로가 섞인 경우,
`min_age`를 가장 낮은/일반적인 문턱값으로 채우고 `age_condition_type=COMPOUND`,
`age_condition_note`에 복합 조건의 내용을 그대로 보존했습니다. **단순 `min_age` 하나로 조건을
왜곡하지 않기 위한 조치**입니다. 이번 데이터셋에서 깔끔한 "NN세 이상 MM세 미만" 단일 범위
(`SIMPLE_RANGE`)는 발견되지 않았습니다 — 모두 하위 대상군이 다른 COMPOUND 형태였습니다.

### 3.4 지역 구조화 (`region_scope`)
- `NATIONAL`: `sido`/`sigungu`가 모두 없고 전국 단위 중앙부처 사업인 경우 (2건)
- `SIGUNGU`: `sigungu`가 있거나(기존 68건), 서비스명·문의처로 특정 시군구가 명확히 특정되는 경우(신규 3건)
- `SIDO`: `sido`만 있고 문의처가 여러 시군구 부서를 나열하거나 광역 단위 부서인 경우(12건) —
  이 경우 `sigungu`를 억지로 채우지 않았습니다.

## 4. 변경된 필드

| 필드 | 변경 내용 |
|---|---|
| `sigungu` | 3건 보강 (근거: 서비스명+문의처) — 아래 4.1 참조 |
| `min_age` | 비어 있던 75건 모두 채움 (숫자 29건, `unknown` 46건) |
| `disability_required` / `low_income_required` / `single_household_required` / `homebound_or_mobility_condition` | 비어 있던 75건 모두 `true`/`false`/`unknown` 3상태로 채움 |
| `service_type_primary` / `meal_support_flag` / `food_cost_support_flag` | 비어 있던 54건을 기존 100% 필드인 `service_type`에서 직접 파생하여 채움 (신규 조사 없음) |
| `data_quality_note` | 판정이 애매하거나 복합조건인 경우 근거를 추가 기록(기존 내용은 보존, `\|\|`로 구분하여 추가) |
| **(신규 컬럼)** `region_scope` | 전 85건에 `NATIONAL`/`SIDO`/`SIGUNGU` 부여 |
| **(신규 컬럼)** `max_age` | 이번 데이터셋에는 해당 사례 없어 전 건 공란 |
| **(신규 컬럼)** `age_condition_type` | `SIMPLE_MIN`(28) / `COMPOUND`(12) / `NONE`(45) |
| **(신규 컬럼)** `age_condition_note` | COMPOUND인 경우 복합조건 설명 |
| **(신규 컬럼)** `structured_from_original` | 이번 보강으로 구체적 값이 하나라도 추가되었으면 `true`(75건), 아니면 `false`(10건 — 기존 완전 구조화 그룹) |
| **(신규 컬럼)** `structured_fields_added` | 이번에 채운 필드명 목록(`\|` 구분, provenance) |

`senior_relation`, `nutrition_relevance`, `eligibility_summary`, `support_summary`,
`nutritionist_involvement`는 **의도적으로 이번 보강 대상에서 제외**했습니다. 추천 설계
(`recommendation_system_design.md` §3~§9)상 실제 매칭에 쓰이는 필드는 `service_type`,
`sido`/`sigungu`, `min_age`, `disability_required`, `low_income_required`,
`single_household_required`, `homebound_or_mobility_condition`이며, 위 4개 필드는 보조
지표에 그쳐 우선순위가 낮다고 판단했습니다. `nutritionist_involvement`는 원문에 "영양사"라는
단어가 명시된 경우(기존 1건)만 `direct`로 판정하는 엄격한 규칙을 유지했고, 85건 전체를
재검토했지만 추가로 발견된 명시적 사례는 없었습니다(§9 참조).

### 4.1 sigungu 보강 3건 (근거 명시)

| service_id | 서비스명 | 근거 | 보강값 |
|---|---|---|---|
| WLF00005718 | 수원형 통합돌봄 수원새빛돌봄(누구나) 사업 | 서비스명 "수원형" + 문의처 "수원시 돌봄정책과" | `수원시` (기존 `data_quality_note`에 이미 결측이 지적되어 있던 건) |
| WLF00006261 | 함양군 통합돌봄사업 | 서비스명 "함양군" + 문의처 "함양군청 노인복지과" | `함양군` |
| WLF00004015 | 어르신 급식사업 지원 | 문의처가 "부산광역시 동구 복지정책과" 단일 부서로 한정 | `동구` |

## 5. 필드별 Coverage (Before → After)

| 필드 | 보강 전 값 있음 | 보강 후 값 있음 | 비고 |
|---|---:|---:|---|
| `sido` | 83/85 (97.6%) | 83/85 (97.6%) | 변경 없음 (2건은 NATIONAL로 분류) |
| `sigungu` | 68/85 (80.0%) | 71/85 (83.5%) | 3건 근거기반 보강 |
| `region_scope` (신규) | 0/85 | 85/85 (100%) | NATIONAL 2 / SIDO 12 / SIGUNGU 71 |
| `min_age` (셀 채움) | 10/85 (11.8%) | 85/85 (100%) | 단, 숫자로 확정된 것은 39/85 (45.9%), 나머지는 `unknown` |
| `disability_required` (셀 채움) | 10/85 (11.8%) | 85/85 (100%) | 확정(true/false) 18/85 (21.2%) — true 12 / false 6 |
| `low_income_required` (셀 채움) | 10/85 (11.8%) | 85/85 (100%) | 확정 72/85 (84.7%) — true 64 / false 8 |
| `single_household_required` (셀 채움) | 10/85 (11.8%) | 85/85 (100%) | 확정 9/85 (10.6%) — true 9 / false 0 |
| `homebound_or_mobility_condition` (셀 채움) | 10/85 (11.8%) | 85/85 (100%) | 확정 37/85 (43.5%) — true 37 / false 0 |
| `service_type` | 85/85 (100%) | 85/85 (100%) | 변경 없음(원래 완전) |
| `service_type_primary` | 31/85 (36.5%) | 85/85 (100%) | `service_type`에서 직접 파생 |
| `meal_support_flag` | 31/85 (36.5%) | 85/85 (100%) | true 81 / false 4 |
| `food_cost_support_flag` | 10/85 (11.8%) | 85/85 (100%) | true 1 / false 84 |

**"셀이 채워졌다"(100%)는 것과 "조건이 확정 판정되었다"는 것은 다릅니다.** 위 표의 "확정" 수치가
실제 하드필터/랭킹에 쓸 수 있는 정보량입니다. UNKNOWN으로 남은 나머지는 데이터가 부족해서가
아니라, **원문 자체가 그 조건을 명시하지 않아서**이며 이는 오류가 아니라 정직한 표시입니다.

## 6. UNKNOWN 처리 원칙

- 서비스 원문에 조건이 언급되지 않으면 `unknown`을 유지합니다(임의로 `false`를 넣지 않음).
- 여러 대상군이 OR로 열거되어("독거노인, 노인가구" 등) 어느 하나가 배타적 필수조건인지 불명확한
  경우도 `unknown`으로 유지하고 `data_quality_note`에 근거를 남겼습니다.
- 소득 조건이 "본인부담률 차등"(예: SOS센터형 통합돌봄 사업 — 저소득이면 전액지원, 초과분은
  자부담)으로 쓰인 경우는 "자격요건"이 아니라 "비용 차등 기준"이므로 `low_income_required=false`로
  판정하고 근거를 남겼습니다. 이는 "언급 없음=unknown"과 "명시적 무관=false"를 구분하는
  원칙(§3.1)의 실제 적용 사례입니다.
- 연령이 다층적으로 섞인 경우(§3.3) `min_age`를 강제로 단순화하지 않고 `age_condition_type=
  COMPOUND` + `age_condition_note`로 원본 복잡성을 보존했습니다.

## 7. 데이터 품질 이슈 (이번 보강 과정에서 발견/기록)

- **국가유공자재가복지지원(WLF00000098)**: 국가유공자 대상 특수 자격체계로, 장애인복지법상
  "장애" 개념이나 일반 소득기준과 다른 별도 판정 체계를 가짐 — 일반 사용자 질문(장애/소득 여부)과
  1:1로 매칭하기 어려움.
- **복합 하위서비스 레코드** (예: WLF00004588 저소득 어르신 무료급식사업, WLF00002209,
  WLF00004322, WLF00004015, WLF00002352, WLF00006261 등): 경로식당/식사배달/밑반찬배달처럼
  연령·독거·장애 조건이 서로 다른 하위서비스가 **한 레코드**에 묶여 있어, 대표값으로 단순화하는
  과정에서 일부 하위조건의 정밀도가 낮아짐. 각 레코드의 `age_condition_note`/`data_quality_note`에
  상세 근거를 남김.
- **"고독사 위험가구"(WLF00002345)**: 개념적으로 독거를 강하게 시사하나 원문에 "독거"라는 단어가
  명시되지 않아 `single_household_required=unknown`으로 보수적으로 처리.
- **저소득층 도시락 지원사업(WLF00000115)**: 기존 `data_quality_note`에 이미 "노인/아동/장애인
  급식 대상이 아닌 자" 문구의 모호성이 기록되어 있었음 — 이번 보강에서도 추가 확정 없이
  `disability_required=unknown`으로 유지, 기존 노트 보존.
- **부부세대 예외**: 일부 서비스(WLF00003294, WLF00000414)는 "독거노인" 우선이지만 "노인부부가구"도
  명시적으로 포함되어 있어 `single_household_required`를 `true`로 단정하지 않고 `unknown` 처리.

## 8. 추천 엔진에서 주의할 점

1. **`min_age`가 `unknown`인 서비스를 나이 조건으로 자동 제외하지 마세요.** (§5 하드필터 설계 원칙과 동일)
2. **`age_condition_type=COMPOUND`인 서비스는 `min_age` 하나만으로 하드필터에 사용하지 말고,
   `age_condition_note`를 함께 노출해 "조건 확인 필요"로 표시하는 것을 권장합니다.**
3. **`disability_required=false`는 "비장애인만 가능"이 아니라 "장애 여부와 무관하게 이용 가능"이라는
   뜻입니다.** 반대로 해석하지 않도록 주의하세요.
4. **`low_income_required=false`로 표시된 SOS센터형 통합돌봄 사업들은 실제로는 소득에 따라
   본인부담률이 달라지는 구조입니다.** "무료"라는 뜻이 아니라 "소득이 자격 자체를 막지는 않는다"는
   뜻이므로, 추천 이유 문구 생성 시 이 뉘앙스를 살려야 합니다.
5. **`region_scope=SIDO`인 12건은 `sigungu`가 없다고 해서 지역 불일치로 처리하면 안 됩니다.**
   province/시 전역 사업이므로 사용자의 `sido`만 일치하면 지역 조건은 통과해야 합니다.
6. **`structured_fields_added`가 비어 있는 10건(기존 완전 구조화 그룹)과, 이번에 채운 75건은
   신뢰도가 다를 수 있습니다.** 전자는 이전 라운드에서 verification_level A/B로 개별 검수된
   값이고, 후자는 이번 라운드에서 규칙 기반으로 판정한 값입니다. 필요 시 두 그룹을 구분해
   추천 신뢰도 표시에 반영할 수 있습니다(`structured_from_original` 컬럼으로 구분 가능).

## 9. 최종 무결성 검사 결과

| # | 검사 항목 | 결과 |
|---|---|---|
| 1 | 행 수 = 85 | ✅ PASS |
| 2 | service_id unique = 85 | ✅ PASS |
| 3 | 기존 85개 service_id와 정확히 동일 | ✅ PASS |
| 4 | 원문 필드(target/criteria/support/application_original 등 17개 원본 컬럼) 손상 = 0 | ✅ PASS |
| 5 | 신규 행 = 0 | ✅ PASS |
| 6 | 누락 행 = 0 | ✅ PASS |
| 7 | service_type ↔ meal_support_flag/food_cost_support_flag/service_type_primary 논리 충돌 = 0건 | ✅ PASS |
| 8 | region_scope 허용값 및 논리(NATIONAL↔sido 없음, SIGUNGU↔sigungu 있음, SIDO↔sido 있음) | ✅ PASS |
| 9 | age_condition_type 허용값 및 min_age와의 논리 정합성 | ✅ PASS |
| 10 | 조건 필드(disability/low_income/single_household/homebound) 허용값이 `true`/`false`/`unknown`/빈값 뿐인지 | ✅ PASS |
| 11 | 구조화 값 vs 원문 키워드 교차검증 | 3건에서 키워드 불일치 감지, 전부 검토 결과 **정상**(서비스명 근거 사용 2건, "어려운세대"류 의미 해석 1건 — 모두 `data_quality_note`에 근거 명시됨) |

## 부록: 보강 사례 (Dry Run 표본)

### A. 명확한 보강 사례

| service_id | service_name | field | before → after | evidence (원문) | reason |
|---|---|---|---|---|---|
| WLF00000664 | 노인맞춤돌봄지원 강화 사업 | min_age | `''` → `65` | criteria_original: "저소득 가구중 65세 이상 노인맞춤돌봄 대상" | "65세 이상" 단일 기준 명시 → SIMPLE_MIN |
| WLF00002028 | 저소득 재가노인 식사배달 | homebound_or_mobility_condition | `''` → `true` | target_original: "거동불편 및 경제적 어려움이 있는 재가노인" | "거동불편" 명시 |
| WLF00004462 | 저소득재가노인 밑반찬배달사업(추가) | single_household_required | `''` → `true` | target_original: "만60세 이상 저소득(기초수급 및 차상위) 독거노인" | 독거노인이 유일한 가구유형 설명 (타 가구유형 병기 없음) |
| WLF00005718 | 수원형 통합돌봄 수원새빛돌봄(누구나) 사업 | sigungu | `''` → `수원시` | service_name "수원형" + contact "수원시 돌봄정책과" | 서비스명·문의처로 단일 시군구 명확히 특정됨 |
| WLF00003294 | 저소득재가노인 식사배달 | age_condition_type | `''` → `COMPOUND` | target_original: "1)65세이상 독거노인 2)65세이상 노인 3)부부세대로 중증장애 노인" | 3개 하위 대상군이 혼재 — 단일 min_age로 왜곡 방지 |
| WLF00005239 | 누구나 돌봄! 시흥돌봄SOS센터 운영 | low_income_required | `''` → `false` | criteria_original: "기초수급자·차상위·120%이하 전액지원, 120%초과~150%이하 50%지원, 150%초과 자부담" | 소득이 자격요건이 아니라 본인부담률만 좌우 → 명시적 무관으로 판정 |
| WLF00001291 | 장애인 급식소 운영 | disability_required | `''` → `false` | target_original: "다목적복지회관 이용 장애인 및 일반인" | "장애인 및 일반인" 병기 → 장애 여부 무관 명시 |
| WLF00006032 | 거동불편노인 식사배달 지원사업 | low_income_required | `''` → `true` | target_original: "65세 이상 전국가구 월평균소득 160%이하 거동불편 노인" | 소득기준 수치 명시 |
| WLF00006261 | 함양군 통합돌봄사업 | sigungu | `''` → `함양군` | service_name "함양군" + contact "함양군청 노인복지과" | 단일 시군구 명확 |
| WLF00004015 | 어르신 급식사업 지원 | sigungu | `''` → `동구` | contact "부산광역시 동구 복지정책과" (단일 부서) | 여러 구를 나열하는 다른 광역 사례와 달리 단일 구만 언급 |

### B. 추론이 애매하여 UNKNOWN으로 보수적으로 남긴 사례

| service_id | service_name | field | 판정 | 이유 |
|---|---|---|---|---|
| WLF00003375 | 저소득 재가노인 식사배달(지방이양) | single_household_required | `unknown` | criteria_original에 "거동불편 노인가구, 독거노인"이 병기되어 독거가 배타적 필수조건인지 불명확 |
| WLF00000414 | 재가노인 식사배달사업 | single_household_required | `unknown` | "1순위: 독거노인가구, 2순위: 노인부부가구"로 부부세대도 명시적으로 포함되어 있어 독거를 필수조건으로 단정 불가 |
| WLF00002345 | 고독사 등 고위험가구 반찬지원 및 안부확인 사업 | single_household_required | `unknown` | "고독사 위험가구"가 독거를 강하게 암시하나 원문에 "독거"라는 단어가 없어 단정하지 않음 |
| WLF00000098 | 국가유공자재가복지지원 | disability_required, low_income_required | `unknown` | 국가유공자 특수 자격체계(상이처/보훈보상 등)로 일반 장애·소득 개념과 판정체계가 달라 단순 매핑 어려움 |

## 10. 최종 데이터 사용 방법

- 추천 엔진은 `data/processed/welfare_services_recommendation_ready.csv`를 입력으로 사용합니다.
  **`welfare_services_final.csv`는 그대로 보존되며 수정되지 않았습니다.**
- 하드필터/랭킹 로직은 `disability_required`/`low_income_required`/`single_household_required`/
  `homebound_or_mobility_condition`/`min_age`가 `unknown`인 경우 반드시 UNKNOWN으로 처리하고,
  `true`/`false`인 경우에만 MATCH/MISMATCH 판정에 사용해야 합니다(`recommendation_system_design.md`
  §6 규칙 그대로 적용).
- `region_scope`를 지역 하드필터의 1차 기준으로 사용하고, `SIDO`/`NATIONAL`인 경우 `sigungu` 결측을
  불일치로 오판하지 않아야 합니다.
- `structured_fields_added`/`structured_from_original`은 디버깅·감사(audit) 용도로만 사용하고,
  추천 로직 자체의 입력으로 사용하지 않습니다.

---
