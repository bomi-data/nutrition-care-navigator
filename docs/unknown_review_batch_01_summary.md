# UNKNOWN 후보 1차 배치(30건) 검토 요약

작성일: 2026-08-21
대상: `senior_relevance=unknown` 142건 중 **파일 순서상 첫 30건**
기준: `docs/classification_criteria.md` v2.1(2축 판단: `senior_relation_v2` × `nutrition_relevance`)
방법: `welfare_candidates_reviewed.csv`에 이미 저장된 원문(target/criteria/support/application_original)만
사용했다. 새 API 호출은 하지 않았으며, `welfare_candidates_reviewed.csv` 원본은 수정하지 않았다.
결과는 `data/processed/unknown_review_batch_01.csv`에 별도 저장했다.

## 1. 검토한 건수
**30건**

## 2~4. 판정 결과

| review_status | 건수 |
|---|---|
| INCLUDE | 4 |
| EXCLUDE | 26 |
| NEEDS_REVIEW | 0 |

## 5~7. 대상관계(senior_relation_v2)

| 값 | 건수 |
|---|---|
| SENIOR_DIRECT | 1 |
| SENIOR_CONDITIONAL | 6 |
| NOT_SENIOR_RELEVANT | 23 |

## 8~10. 영양돌봄 관련성(nutrition_relevance)

| 값 | 건수 |
|---|---|
| DIRECT_NUTRITION | 5 |
| SUPPORTIVE_NUTRITION | 2 |
| NOT_NUTRITION_RELEVANT | 23 |

두 축이 모두 충족된 경우만 INCLUDE(4건)가 됐고, DIRECT/SUPPORTIVE_NUTRITION인데도 대상관계가
`NOT_SENIOR_RELEVANT`라서 최종 EXCLUDE된 경우가 2건(임신부 가사돌봄, 임신 전·산후 영양제) 있었다 —
2축을 분리한 이번 기준이 실제로 작동했음을 보여주는 사례다.

## 11. 대표적인 INCLUDE 사례 (이번 배치에서는 4건 전부)

| service_id | 서비스명 | senior_relation_v2 | 근거 |
|---|---|---|---|
| WLF00005239 | 누구나 돌봄! 시흥돌봄SOS센터 운영 | SENIOR_CONDITIONAL | 대상이 "돌봄이 필요한 시민 누구나"(연령 무관, 기능조건 기반)이고, 13대 돌봄서비스 중 "식사지원: 식생활 유지를 위한 식사 배달"이 명시됨 |
| WLF00004595 | 저소득노인 무료급식(식사배달사업, 밀양시) | SENIOR_DIRECT | "결식우려 거동불편 저소득노인" 명시, 도시락 제조·배달 |
| WLF00004507 | 사회복지센터 재가복지 봉사(김장서비스, 거창군) | SENIOR_CONDITIONAL | 여러 취약계층 중 "독거노인"(거동불편 독거노인 우선)이 명시적으로 포함, 반찬·김장김치 지원 |
| WLF00005583 | 장애인복지관 무료급식 지원사업(부산) | SENIOR_CONDITIONAL | 연령 제한 없는 저소득 장애인 대상, 복지관 점심 무료제공+식사/밑반찬 배달 |

**요청하신 "대표적인 INCLUDE 5건"에는 못 미친다** — 이번 30건에서 실제로 INCLUDE로 확정된 건이
4건뿐이라 과장 없이 있는 그대로 4건만 보고한다.

## 12. 대표적인 EXCLUDE 사례

| service_id | 서비스명 | 제외 이유 |
|---|---|---|
| WLF00003176 | 농식품바우처 | 신선농산물 바우처로 DIRECT_NUTRITION이지만, 대상이 임산부·영유아·아동·청년(34세 이하)으로 명시되고 노인 언급이 전혀 없어 NOT_SENIOR_RELEVANT |
| WLF00000896 | 중독관리통합지원센터 지원 | 수혜자가 개인 고령자가 아니라 센터(기관) 운영비이며, 내용도 중독자 상담·재활로 영양과 무관 |
| WLF00005034 | 장애인 건강주치의 시범사업 | 장애인 대상(SENIOR_CONDITIONAL)이나 지원내용이 만성질환·장애 건강관리 방문진료뿐, 식사·영양 내용 없음(NOT_NUTRITION_RELEVANT) |
| WLF00004850 | 임신부 가사돌봄 서비스 | 식사 준비 보조가 포함돼 SUPPORTIVE_NUTRITION이지만 대상이 임신부로 명시돼 NOT_SENIOR_RELEVANT |
| WLF00002930 | 임신 전, 산 후 영양제 지원 | 영양제 지원(SUPPORTIVE_NUTRITION)이지만 대상이 가임기 여성(19~49세)으로 명시돼 NOT_SENIOR_RELEVANT |

## 13. 판단하기 어려웠던 사례

이번 30건은 결과적으로 전부 EXCLUDE/INCLUDE로 확정됐고 NEEDS_REVIEW는 0건이었지만, 판단에
신중함이 필요했던 사례는 있었다.

- **WLF00005239(시흥돌봄SOS)**: 대상이 특정 연령대가 아니라 "돌봄이 필요한 시민 누구나"로,
  기능적 조건(거동·가족부재)만으로 선정된다. `SENIOR_DIRECT`도 `NOT_SENIOR_RELEVANT`도 아니라서
  `SENIOR_CONDITIONAL`로 분류했는데, 이런 "전 연령 대상 기능기반 서비스"를 어떻게 일관되게
  분류할지는 앞으로도 반복적으로 마주칠 문제로 보인다.
- **WLF00004507(거창 김장서비스)**: 대상군이 차상위·장애인·독거노인·조손가정·한부모·국가유공자 등
  여러 그룹을 나열하고 "독거노인"은 그중 하나(우선순위 항목)일 뿐 필수조건이 아니다. 포함하는 것이
  맞다고 판단했지만, 이런 "여러 취약계층을 나열한 사업"에서 고령자가 언급 순서상 몇 번째인지에 따라
  판단이 달라지면 안 되므로 기준을 더 명확히 할 필요가 있다.

## 14. 새 분류 기준에서 발견된 문제

1. **이번 30건은 산모·신생아 관련 서비스가 유난히 많이 몰려 있었다**(30건 중 11건). 이는
   `senior_relevance=unknown`인 서비스들이 원본 API 순서(중복 없는 service_id 등록 순서에 가까움)
   그대로 배치된 결과로 보이며, 다음 30건은 구성 비율이 다를 수 있다.
2. **`WLF00005842`(고창군 산후조리비)**: `target_original`/`criteria_original`/`support_original`/
   `application_original` 4개 필드가 전부 동일한 문장을 반복하고 있었다 — 원문 데이터 자체의 품질
   문제로, 판정에는 영향이 없었지만 향후 UI에 그대로 노출하면 어색할 수 있다.
3. `nutrition_relevance=SUPPORTIVE_NUTRITION`이지만 `senior_relation_v2=NOT_SENIOR_RELEVANT`라서
   EXCLUDE된 사례(2건)가 있었다는 것은, 2축 분리가 "영양 키워드만 보고 성급히 포함"하는 것을
   실제로 막아준다는 뜻이라 기준 자체는 의도대로 작동하는 것으로 보인다.

## 15. 다음 30건에도 같은 기준을 적용해도 되는가

**그렇다.** 이번 30건에서 2축 판단 기준이 일관되게 적용 가능했고, 사용자가 제시한 "명백한 자동
제외 기준"(연령 상한 명시, 청소년/아동/임산부 전용, 기관/종사자 대상, 영양무관 내용)만으로
26건의 EXCLUDE를 무리 없이 판정할 수 있었다. 다만 13절에서 언급한 "전 연령 대상 기능기반
서비스"와 "여러 취약계층을 나열한 사업에서 고령자가 일부로만 언급된 경우"는 다음 배치에서도
반복될 가능성이 높으므로, 이 두 유형에 대한 판단 원칙을 이번 사례들을 참고 삼아 계속 일관되게
적용할 것을 권장한다.
