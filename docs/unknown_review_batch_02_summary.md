# UNKNOWN 후보 2차 배치(30건) 검토 요약

작성일: 2026-08-21
대상: `senior_relevance=unknown` 142건 중 batch01(30건)을 **service_id 기준**으로 제외한 나머지
112건 중, 파일 순서상 다음 30건.
기준: `docs/classification_criteria.md` v2.1(2축 판단), batch01과 동일 기준 그대로 적용, 새 기준을
만들지 않았다.
방법: `welfare_candidates_reviewed.csv`에 이미 저장된 원문만 사용, 새 API 호출 없음.
`welfare_candidates_reviewed.csv`와 `unknown_review_batch_01.csv`는 수정하지 않았다.
결과는 `data/processed/unknown_review_batch_02.csv`에 별도 저장했다.

## 1. 검토 건수: 30건

## 2~4. 판정 결과

| review_status | 건수 |
|---|---|
| INCLUDE | 2 |
| EXCLUDE | 27 |
| NEEDS_REVIEW | 1 |

## 5. senior_relation_v2 분포

| 값 | 건수 |
|---|---|
| SENIOR_DIRECT | 0 |
| SENIOR_CONDITIONAL | 7 |
| NOT_SENIOR_RELEVANT | 23 |

## 6. nutrition_relevance 분포

| 값 | 건수 |
|---|---|
| DIRECT_NUTRITION | 3 |
| SUPPORTIVE_NUTRITION | 5 |
| NOT_NUTRITION_RELEVANT | 22 |

## 7. INCLUDE 서비스 전체 목록 (2건)

| service_id | 서비스명 | 지역 | senior_relation_v2 | service_type | verification_level |
|---|---|---|---|---|---|
| WLF00005598 | 제주가치 통합돌봄 | 제주특별자치도 | SENIOR_CONDITIONAL | community_care\|meal_support | A |
| WLF00001291 | 장애인 급식소 운영 | 경기도 하남시 | SENIOR_CONDITIONAL | meal_support | B |

제주가치 통합돌봄은 "돌봄이 필요한 도민 누구나"가 대상이고 5대 9종 서비스 중 "식사지원: 도시락,
반찬 및 죽 배달"이 명시돼 있다. 장애인 급식소 운영은 "일반인"까지 포함하는 대상 범위에 중·간식·
중식 제공이 명시돼 있다.

## 8. 대표적인 EXCLUDE 사례 5건

| service_id | 서비스명 | 제외 이유 |
|---|---|---|
| WLF00000236 | 산모신생아건강관리사 인력양성지원 | 선정기준에 "만18세 이상~64세 이하"로 연령 상한이 명시돼 65세 이상 배제(NOT_SENIOR_RELEVANT) |
| WLF00006696 | 저소득장애인 의료비 지원 | 장애인 대상(SENIOR_CONDITIONAL)이나 입원 의료비 본인부담금 지원뿐, 식사·영양 없음 |
| WLF00005779 | 읍면동 찾아가는 보건복지서비스 사업비 | 지역주민 전체 대상(SENIOR_CONDITIONAL)이나 의료비·생활지원비·자활교육비뿐, 식사·영양 없음 |
| WLF00003098 | 고등학교생 무상급식(조,석식) 지원 | 무상급식(DIRECT_NUTRITION)이지만 대상이 고등학교 재학생으로 명시 |
| WLF00002361 | 임산부·영유아 영양제 지원 | 영양제 지원(SUPPORTIVE_NUTRITION)이지만 대상이 임산부·영유아(3~36개월)로 명시 |

## 9. NEEDS_REVIEW 전체 목록 (1건)

| service_id | 서비스명 | 지역 | 판단 보류 사유 |
|---|---|---|---|
| WLF00001309 | 행려자 귀향여비 및 급식비(안중출장소) | 경기도 평택시 | 대상 "행려자"(귀향 희망 무숙식 여행자)는 연령 제한이 없어 고령자도 해당 가능(SENIOR_CONDITIONAL). 지원내용에 급식비(8천원)가 있으나 여비·장제비·의료비와 묶인 일회성 긴급구호라, 이 프로젝트가 다루는 "지속적 영양돌봄 서비스"에 해당하는지 원문만으로 확정하기 어려움 |

## 10. 데이터 품질 문제

- **WLF00005779(읍면동 찾아가는 보건복지서비스 사업비)**: `target_original`, `criteria_original`,
  `application_original` **세 필드가 완전히 동일한 문장**(사업 설명문)을 반복하고 있어 실질적인
  자격조건·신청방법 정보가 없다.
- **WLF00001291(장애인 급식소 운영)**: `target_original`과 `criteria_original`이 완전히 동일한
  문장이다(batch01의 여러 사례에서도 반복 관찰된 패턴).
- **WLF00000236(산모신생아건강관리사 인력양성지원)**: 연령 상한(64세)이라는 핵심 자격조건이
  `target_original`에는 없고 `criteria_original`에만 있어, 필드 간 정보가 불균등하게 분산돼
  있었다 — `target_original`만 보고 판단하면 놓칠 뻔한 사례.

## 11. 특정 서비스 유형 편중 여부

**매우 심하게 편중돼 있다.** 30건 중 **19건(서비스명 기준)이 산모·신생아·임신·출산·산후조리
관련 서비스**였다 — batch01(30건 중 11건, 37%)보다도 훨씬 높은 비율(63%)이다. 이 30건 중
산모/신생아 계열이 아닌 것은 제주가치 통합돌봄, 장애인 급식소 운영, 장애인 의료비/신문구독/
활동지원, 찾아가는 보건복지서비스, 고등학생 무상급식, 행려자 급식비, 신혼부부 영양제 정도뿐이다.

## 12. batch 01과 batch 02 비교 — 분류 기준의 일관성 평가

| 항목 | batch 01 | batch 02 |
|---|---|---|
| INCLUDE | 4 | 2 |
| EXCLUDE | 26 | 27 |
| NEEDS_REVIEW | 0 | 1 |
| SENIOR_DIRECT | 1 | 0 |
| SENIOR_CONDITIONAL | 6 | 7 |
| NOT_SENIOR_RELEVANT | 23 | 23 |
| DIRECT_NUTRITION | 5 | 3 |
| SUPPORTIVE_NUTRITION | 2 | 5 |
| NOT_NUTRITION_RELEVANT | 23 | 22 |
| 산모/신생아 등 모자보건 서비스 비율 | 37%(11/30) | 63%(19/30) |

**기준 자체는 두 배치에서 일관되게 작동했다고 판단한다.** "SENIOR_DIRECT/CONDITIONAL이라도
영양돌봄 관련성이 없으면 EXCLUDE", "영양 관련 내용이 있어도 대상관계가 NOT_SENIOR_RELEVANT면
EXCLUDE"라는 두 원칙이 이번에도 동일하게 여러 건에 적용됐다(예: 저소득장애인 의료비 지원, 임산부·
영유아 영양제 지원). 다만 **INCLUDE 비율(수확률)이 batch01의 13%(4/30)에서 batch02는 7%(2/30)로
낮아졌는데, 이는 기준이 바뀌어서가 아니라 batch02에 모자보건 서비스(구조적으로 NOT_SENIOR_RELEVANT일
수밖에 없음)가 훨씬 더 많이 몰려 있었기 때문**으로 보인다. NEEDS_REVIEW가 batch01의 0건에서
batch02는 1건으로 늘었는데, 이는 "행려자 급식비"처럼 batch01에는 없던 새로운 유형(일회성 긴급구호성
급식비)이 처음 등장했기 때문이지 기준이 흔들려서가 아니다.

## 13. 남은 UNKNOWN 82건을 동일 기준으로 한 번에 처리해도 되는가

**권장하지 않는다.** 이유는 다음과 같다.

1. batch01(37%) → batch02(63%)로 모자보건(산모/신생아) 서비스 비중이 오히려 더 높아졌다. 이는
   `senior_relevance=unknown` 142건 안에 모자보건 서비스가 큰 덩어리로 연속 배치돼 있을 가능성을
   시사하며, 남은 82건에도 비슷하거나 더 심한 편중이 있을 수 있다.
2. NEEDS_REVIEW 사례(행려자 급식비)처럼 두 배치 모두 "예상 못 한 새 유형"이 매 배치 1~2건씩
   나타났다 — 82건을 한 번에 처리하면 이런 애매한 사례를 사람이 확인하기 전에 대량으로 지나칠
   위험이 있다.
3. 지금까지 60건 검토에서 INCLUDE는 6건(10%)뿐이었다. 82건을 한 번에 처리해도 결과 자체는
   기준대로 나오겠지만, "한 번에 다 처리하지 말고 배치 단위로 검토"하라는 원래 지침의 취지
   (사람이 각 배치 결과를 확인하고 다음 배치로 넘어갈지 판단)를 지키는 것이 안전하다.

**따라서 지금처럼 30건 안팎 단위로 나눠서(예: batch03, batch04, batch05로 82건을 3회 분할)
계속 진행하는 것을 권장하며, 이번에도 batch02까지만 하고 멈춘다.**

## 요약 표 (사람이 한눈에 보기용)

| 항목 | 결과 |
|---|---|
| INCLUDE | 2건 |
| EXCLUDE | 27건 |
| NEEDS_REVIEW | 1건 |
| 데이터 품질 문제 | 3건 발견(동일문장 반복 2건, 정보 필드 간 불균등 분산 1건) — 원문은 수정하지 않음 |
| batch01과의 일관성 | 기준은 동일하게 작동함, INCLUDE 비율 차이는 배치 구성(모자보건 편중도) 차이 때문 |
| 남은 82건 일괄 처리 권장 여부 | **권장하지 않음** — 배치 단위(30건씩)로 계속 진행 권장 |
