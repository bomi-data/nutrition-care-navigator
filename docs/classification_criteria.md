# 후보 서비스 분류 기준 (v2, 2026-08-21 개정)

이 문서는 `welfare_candidates_reviewed.csv`를 만들 때 적용하는 판정 기준의 단일 출처(source of
truth)다. 앞으로 `unknown`(142건) 등 나머지 후보를 검토할 때도 이 기준을 그대로 적용한다.

## 개정 이유

1차 검토(98건)에서 "고령자 전용 서비스인가?"를 기준으로 판단한 결과, 지원대상이 "저소득 재가장애인"
처럼 **연령 제한이 없는 서비스**가 부당하게 NEEDS_REVIEW/EXCLUDE로 밀리는 문제가 있었다. 이 프로젝트의
목적은 "고령자 전용 서비스만 찾기"가 아니라 "고령자가 조건을 충족하면 신청 후보가 될 수 있는 서비스를
찾기"이므로, 판단축을 아래와 같이 분리한다.

## 1. 대상관계(senior_relation) — "누가 받을 수 있는가"

| 값 | 정의 |
|---|---|
| `SENIOR_DIRECT` | 65세 이상/노인/어르신이 지원대상으로 명시됨 |
| `SENIOR_CONDITIONAL` | 고령자 전용은 아니지만, 연령 상한이나 고령자를 배제하는 조건이 없고, 장애·저소득·재가·독거 등 다른 조건을 고령자도 동시에 충족할 수 있는 서비스 |
| `NOT_SENIOR_RELEVANT` | 고령자가 이용 대상이 될 수 없거나(예: 연령 상한이 명시적으로 65세 미만), 대상은 고령자이지만 2절의 영양돌봄 관련성 기준을 충족하지 못하는 서비스 |

**"연령 조건이 없다"는 이유만으로 `SENIOR_CONDITIONAL`을 `NOT_SENIOR_RELEVANT`로 내리지 않는다.**
반대로 이 판정은 "고령자가 확실히 받을 수 있다"를 의미하지 않는다 — 최종 자격은 사용자가 직접
확인해야 한다는 전제를 유지한다(7절 참고).

## 2. 영양돌봄 관련성 기준 — "이 서비스가 영양돌봄과 관련 있는가"

**적극 포함 검토**: 식사 제공, 무료급식, 도시락 배달, 밑반찬/반찬 배달, 식재료 지원, 식품 지원,
식비 지원, 식품/식재료 구매 바우처, 영양상담, 영양교육, 영양관리, 재택 영양관리, 퇴원 후 영양지원

**단순 키워드만으로 포함 금지**: 단순 병원동행, 교통지원, 이미용, 일반적인 복지상담, 주거지원,
취업지원, 단순 건강검진, 영양과 무관한 방문서비스. "통합돌봄"/"재가"/"건강"이라는 단어가 있다는
이유만으로 포함하지 않는다 — 지원내용(support_original)에 식사·영양 관련 내용이 실제로 있는지를
확인한다.

**대상관계와 영양돌봄 관련성은 별개의 두 축이다.** `SENIOR_DIRECT`이더라도 영양돌봄 관련성이 없으면
`NOT_SENIOR_RELEVANT`로 최종 분류하고 EXCLUDE한다(예: 담양군 병원동행서비스, 8절 참고).

## 3. service_type 체계 (v2)

| service_type | 정의 |
|---|---|
| `meal_support` | 식사/급식/도시락/반찬 등을 **직접 제공** |
| `food_cost_support` (신설) | 식비 또는 식재료 구매에 쓸 수 있는 **바우처·금전 지원**(직접 조리·배달이 아님) |
| `nutrition_counseling` | 영양상담 |
| `nutrition_education` | 영양교육 |
| `community_care` | 영양 또는 식생활 유지와 직접 연결되는 지역사회 통합돌봄 |
| `home_visit` | 영양/식사/건강관리와 관련된 방문서비스 |
| `discharge_support` | 퇴원 후 지역사회 연계 및 영양돌봄 |

`meal_support`와 `food_cost_support`를 구분하는 이유: 전자는 조리된 음식이나 식재료를 직접
배달·제공하고, 후자는 사용처가 정해진 예산(바우처·카드)을 지급해 수급자가 스스로 식품을
구매하게 한다. 추천 문구("도시락이 배달됩니다" vs "식비로 쓸 수 있는 카드가 지급됩니다")가
달라지므로 구분이 필요하다.

**primary/secondary 태그**: `service_type` 컬럼은 기존처럼 파이프(`|`)로 여러 태그를 담을 수 있다.
여기에 더해 `service_type_primary` 컬럼을 추가해 **가장 핵심적인 태그 하나**를 별도로 표시한다
(예: `service_type=community_care|meal_support|home_visit`, `service_type_primary=community_care`).
기존 파이프 목록 구조를 깨지 않는 범위에서 추가한 것이라 이전 데이터와 호환된다.

**연계 서비스 표시**: 식사/영양을 직접 제공하지 않지만 통합돌봄 체계 안에서 영양 서비스와 함께
연계될 수 있는 서비스(예: 장기요양 방문요양·방문간호처럼 식사 내용이 명시되지 않은 경우)는
`service_type`에 `meal_support`/`nutrition_*`를 넣지 않고 `home_visit`/`community_care`만
부여한 뒤, `review_note`에 "식사/영양 직접 지원 아님, 연계 서비스로만 고려"라고 명시한다.

## 4. 확장 필드 스키마

`welfare_candidates_reviewed.csv`에 다음 컬럼을 추가한다(기존 컬럼은 그대로 유지):

| 컬럼 | 값 | 비고 |
|---|---|---|
| `senior_relation` | SENIOR_DIRECT / SENIOR_CONDITIONAL / NOT_SENIOR_RELEVANT / (빈값=미판정) | |
| `service_type_primary` | service_type 중 1개 | |
| `min_age` | 숫자 또는 `unknown` | |
| `disability_required` | true/false/unknown | |
| `low_income_required` | true/false/unknown | |
| `single_household_required` | true/false/unknown | |
| `homebound_or_mobility_condition` | true/false/unknown | |
| `meal_support_flag` | true/false | service_type에 meal_support 포함 여부(파생값) |
| `food_cost_support_flag` | true/false | service_type에 food_cost_support 포함 여부(파생값) |
| `eligibility_summary` | 원문 기반 1~2문장 요약 | 추측 금지, 원문에 없는 조건은 언급하지 않음 |
| `support_summary` | 원문 기반 1~2문장 요약 | |

**원문에서 확인되지 않는 조건은 반드시 `unknown`으로 남긴다.** 예를 들어 "저소득 장애인"이라고만
되어 있고 연령이 언급되지 않으면 `min_age=unknown`이며, 이것이 "고령자도 이용 가능함이 확정됨"을
뜻하지 않는다. `senior_relation=SENIOR_CONDITIONAL`은 "연령 상한/배제 조건이 없어 후보로 검토할
가치가 있다"는 뜻이지 "고령자가 확정적으로 받을 수 있다"는 뜻이 아니다.

## v2.1 추가 — UNKNOWN(senior_relevance=unknown) 142건 검토용 2축 판단 (2026-08-21)

`senior_relevance=unknown`은 `lifeArray`/`lifeNmArray` 등 생애주기 정보가 애초에 없어서 1차
자동판정을 못 한 것일 뿐, "판단하기 어려운 서비스"라는 뜻이 아니다. 이 142건은 v2의
`senior_relation`(SENIOR_DIRECT/SENIOR_CONDITIONAL/NOT_SENIOR_RELEVANT) 개념을 그대로 쓰되,
**대상관계 축과 영양돌봄 관련성 축을 명시적으로 분리**해 `senior_relation_v2` +
`nutrition_relevance`라는 두 컬럼으로 각각 기록한다(기존 `senior_relation` 컬럼은 1차 98건
검토분에 이미 쓰였으므로 보존하고, `_v2` 컬럼을 새로 둔다).

### 축 A: `senior_relation_v2`
`SENIOR_DIRECT` / `SENIOR_CONDITIONAL` / `NOT_SENIOR_RELEVANT` — 정의는 v2(위 1절)와 동일하다.
추가로 `NOT_SENIOR_RELEVANT`에는 "수혜자가 개인 고령자가 아니라 기관/종사자/양성대상자인 경우"도
포함한다(예: 상담센터 운영비 지원, 돌봄인력 양성 교육비).

### 축 B: `nutrition_relevance`
`DIRECT_NUTRITION`(식사·급식·도시락·반찬·식품/식재료·영양상담·영양교육 직접 제공) /
`SUPPORTIVE_NUTRITION`(식비·식재료 바우처, 또는 통합돌봄의 명시적 일부로 포함된 식사·영양지원) /
`NOT_NUTRITION_RELEVANT`(병원동행·취업·장학금·상담·주거·이미용·교통·일반 의료검사·단순 기관운영비 등)

**두 축은 독립적으로 판정한다.** `senior_relation_v2=SENIOR_DIRECT`여도
`nutrition_relevance=NOT_NUTRITION_RELEVANT`면 최종 `review_status=EXCLUDE`다. 반대로
`nutrition_relevance=DIRECT_NUTRITION`이어도 `senior_relation_v2=NOT_SENIOR_RELEVANT`면 역시
EXCLUDE다(예: 임신부 가사돌봄 서비스는 식사 준비를 지원하지만 대상이 임신부라 EXCLUDE).

### 최종 판정 규칙
- `SENIOR_DIRECT` 또는 `SENIOR_CONDITIONAL` **AND** `DIRECT_NUTRITION` 또는 `SUPPORTIVE_NUTRITION`
  → `INCLUDE`
- 두 축 중 하나라도 `NOT_SENIOR_RELEVANT` / `NOT_NUTRITION_RELEVANT` → `EXCLUDE`
- 원문만으로 어느 한 축이라도 확정하기 어려우면 → `NEEDS_REVIEW` (애매하면 INCLUDE보다 우선)

## 5. 추천 표시 단계(향후 UI 설계 참고용, 이번 단계에서 구현하지 않음)

이 프로젝트는 최종 수급자격을 판정하지 않는다. 데이터 구조는 다음과 같은 단계적 안내가 가능하도록
설계한다(실제 점수 계산 로직은 이번 단계에서 만들지 않음):

- 높은 가능성: `senior_relation=SENIOR_DIRECT` + 사용자가 입력한 조건과 eligibility_summary가
  직접 일치
- 추가 조건 확인 필요: `senior_relation=SENIOR_CONDITIONAL`이거나 일부 조건이 `unknown`
- 관련 서비스: `service_type`은 맞지만 지역/대상 조건이 불일치
- 대상 가능성 낮음: `senior_relation=NOT_SENIOR_RELEVANT`(추천 목록에서 기본 제외)
