# UNKNOWN 후보 3차 배치(40건) 검토 요약

작성일: 2026-08-21
기준: `docs/classification_criteria.md` v2.1 — batch01·02와 동일 기준, 완화·강화 없음.
방법: `welfare_candidates_reviewed.csv`에 이미 저장된 원문만 사용, 새 API 호출 없음.
`welfare_candidates_reviewed.csv`, `unknown_review_batch_01.csv`, `unknown_review_batch_02.csv`는
수정하지 않았다. 결과는 `data/processed/unknown_review_batch_03.csv`에 저장했다.

## 1. 남은 UNKNOWN이 정확히 82건인지

**검증 완료.** `senior_relevance=unknown` 142건에서 batch01(30건)·batch02(30건)를 service_id
기준으로 제외한 결과 정확히 **82건**이 남았다(중복 0건, 두 배치 파일 모두 unknown 142건의 부분집합임을
확인). 스크립트 내 assert 문으로 이 조건을 검증한 뒤에만 다음 단계를 진행했다.

## 2. 남은 82건의 서비스 유형 분포 (임시 그룹, service_name/target_original 키워드 기반)

| 임시 그룹 | 건수 | 비율 |
|---|---|---|
| 산모·신생아 | 50 | 61% |
| 장애인 | 9 | 11% |
| 노인·고령자 | 7 | 9% |
| 지역사회 돌봄 | 4 | 5% |
| 기타 | 3 | 4% |
| 식사·급식·영양 | 3 | 4% |
| 아동·청소년 | 3 | 4% |
| 저소득층(기타) | 2 | 2% |
| 기관·운영지원 | 1 | 1% |

**산모·신생아 편중이 batch01(37%)·batch02(63%)에 이어 82건 전체에서도 61%로 압도적임을 확인했다.**

## 3. batch 03 선정 방식

단순 앞 40행을 선택하지 않고 다음과 같이 층화 표집했다.

1. **비(非) 산모·신생아 32건 전부 포함** — 장애인 9, 노인·고령자 7, 지역사회 돌봄 4, 기타 3,
   식사·급식·영양 3, 아동·청소년 3, 저소득층(기타) 2, 기관·운영지원 1
2. **산모·신생아 50건 중 8건을 체계적 표집** — 목록 순서 index 0, 7, 14, 21, 28, 35, 42, 49
   (매 7번째, 목록 전체에 고르게 분산되도록 함). 내용을 보고 유망한 것만 고르지 않았다.

32 + 8 = **40건**. 이 방식은 "영양 관련 가능성이 높은 것만 의도적으로 고르지 않는다"는 원칙을
지키기 위해, 산모·신생아 표본 선택은 순서 기반 기계적 표집으로만 했고, 나머지 8개 유형은 전수
포함(선별하지 않음)했다.

## 4. 검토 40건

`data/processed/unknown_review_batch_03.csv`에 전체 원문과 함께 기록했다. service_id 목록은
5·7·9절 표에 있다.

## 5. INCLUDE 건수 및 전체 목록: 15건

| service_id | 서비스명 | 지역 | senior_relation_v2 | service_type | verification_level |
|---|---|---|---|---|---|
| WLF00004268 | 저소득 재가장애인 식사배달사업 | 충북 옥천군 | SENIOR_CONDITIONAL | meal_support | A |
| WLF00006240 | 안동시 식사배달 | 경북 안동시 | SENIOR_CONDITIONAL | meal_support\|community_care | A |
| WLF00001842 | 저소득 장애인 무료급식 지원 사업 | 서울 동대문구 | SENIOR_CONDITIONAL | meal_support | B |
| WLF00002047 | 저소득 거동불편 장애인도시락배달 | 전북 전주시 | SENIOR_CONDITIONAL | meal_support | B |
| WLF00002076 | 저소득 취약세대 밑반찬 지원사업 | 전북 군산시 | SENIOR_CONDITIONAL | meal_support | A |
| WLF00001509 | 재가복지 서비스 | 충남 서산시 | SENIOR_CONDITIONAL | meal_support\|home_visit | A |
| WLF00003300 | 거동불편 저소득노인 식사배달 사업 | 경남 합천군 | **SENIOR_DIRECT** | meal_support | A |
| WLF00004743 | 소외계층 지원 | 전남광주통합 함평군 | SENIOR_CONDITIONAL | meal_support | A |
| WLF00006231 | 장수군 도시락 배달 사업 | 전북 장수군 | SENIOR_CONDITIONAL | meal_support\|community_care | A |
| WLF00000115 | 저소득층 도시락 지원사업 | 강원 평창군 | SENIOR_CONDITIONAL | meal_support | B |
| WLF00005857 | 부산, 함께돌봄(부산형 통합돌봄) | 부산 | SENIOR_CONDITIONAL | community_care\|meal_support | A |
| WLF00005102 | 광주다움 통합돌봄 | 전남광주통합 | SENIOR_CONDITIONAL | community_care\|meal_support | A |
| WLF00005718 | 수원형 통합돌봄 수원새빛돌봄(누구나) | 경기 (수원시 추정) | SENIOR_CONDITIONAL | community_care\|meal_support | A |
| WLF00002345 | 고독사 등 고위험가구 반찬지원 및 안부확인 사업 | 전북 임실군 | SENIOR_CONDITIONAL | meal_support | B |
| WLF00002523 | 늘해랑푸드마켓 | 대구 남구 | SENIOR_CONDITIONAL | meal_support | A |

**주목할 만한 발견 — WLF00005102(광주다움 통합돌봄)**: 지원내용에 "맞춤형 영양설계(**전문 영양사
진단**)/무료, 영양음식 조리·배달"이라고 명시돼 있다. batch01·02와 이전의 98건·11건 재검토를
통틀어 **원문에 "영양사"가 직접 명시된 최초 사례**다. `nutritionist_involvement=direct`로 반영했다.

## 6. EXCLUDE 건수: 23건

## 7. NEEDS_REVIEW 건수 및 전체 목록: 2건

| service_id | 서비스명 | 지역 | 판단 보류 사유 |
|---|---|---|---|
| WLF00003721 | 행려자 관리 | 강원 횡성군 | 급식비 포함된 일회성 긴급구호(숙박비·교통비·급식비). batch02의 WLF00001309와 동일 유형 — 일관성을 위해 동일하게 보류 |
| WLF00000783 | 행려자 귀향여비 및 급식비(송탄출장소) | 경기 평택시 | batch02의 WLF00001309(안중출장소)와 **사실상 동일 사업이 평택시 내 출장소별로 별도 service_id 등록**된 것으로 보임. 같은 이유로 보류 |

## 8. senior_relation_v2 분포

| 값 | 건수 |
|---|---|
| SENIOR_DIRECT | 2 |
| SENIOR_CONDITIONAL | 24 |
| NOT_SENIOR_RELEVANT | 14 |

## 9. nutrition_relevance 분포

| 값 | 건수 |
|---|---|
| DIRECT_NUTRITION | 16 |
| SUPPORTIVE_NUTRITION | 3 |
| NOT_NUTRITION_RELEVANT | 21 |

## 10. 발견한 데이터 품질 문제

- **WLF00006413(황금도시락)**: `target_original`과 `criteria_original`이 완전히 동일한 문장(전체
  블록)을 반복.
- **WLF00000115(저소득층 도시락 지원사업)**: `target_original`의 "(노인,아동,장애인 급식 대상이
  아닌 자)"라는 문구가 연령 배제인지 단순 중복지원 방지 조항인지 문면만으로 다소 모호함 —
  중복지원 방지로 해석해 INCLUDE했으나 재확인이 필요할 수 있음.
- **WLF00006232(퇴원환자 지역사회 연계사업)**: 사업명과 달리 `support_original`에 "**급여서비스
  없음**"이라고 명시돼 있어, 이름만 보고 discharge_support로 추측 부여하지 않고 EXCLUDE했다.
- **WLF00005718(수원형 통합돌봄)**: `region`의 시군구 필드가 비어 있음(시도만 "경기도") — 서비스명·
  문의처로 보아 명백히 수원시 한정 사업인데 지역 필드가 누락돼 있다.
- **WLF00000783 / (batch02) WLF00001309**: "행려자 귀향여비 및 급식비"가 평택시 내 서로 다른
  출장소(안중출장소/송탄출장소) 이름으로 **사실상 같은 사업이 별도 service_id로 중복 등록**돼
  있는 것으로 보인다.

## 11. batch 01~03 사이 분류 기준의 일관성

| 항목 | batch01 | batch02 | batch03 |
|---|---|---|---|
| 검토 건수 | 30 | 30 | 40 |
| INCLUDE | 4 (13%) | 2 (7%) | 15 (**38%**) |
| EXCLUDE | 26 | 27 | 23 |
| NEEDS_REVIEW | 0 | 1 | 2 |
| SENIOR_DIRECT | 1 | 0 | 2 |
| SENIOR_CONDITIONAL | 6 | 7 | 24 |
| NOT_SENIOR_RELEVANT | 23 | 23 | 14 |
| DIRECT_NUTRITION | 5 | 3 | 16 |
| SUPPORTIVE_NUTRITION | 2 | 5 | 3 |
| NOT_NUTRITION_RELEVANT | 23 | 22 | 21 |

**기준 자체는 세 배치에서 완전히 동일하게 작동했다.** "SENIOR_DIRECT라도 영양 관련성이 없으면
EXCLUDE"(WLF00005698, 65세 이상 명시됐지만 가사·건강 돌봄에 식사 언급 없어 EXCLUDE), "영양
관련 내용이 있어도 대상관계가 NOT_SENIOR_RELEVANT면 EXCLUDE"(WLF00005721, "영양식이관리"
언급되지만 대상이 산모라 EXCLUDE), "사업명만으로 service_type을 추측하지 않음"(WLF00006232,
"퇴원환자 지역사회 연계사업"이라는 이름에도 불구하고 실제 지원내용이 없어 EXCLUDE) 원칙이 이번에도
동일하게 적용됐다. 행려자 급식비 유형(batch02 1건, batch03 2건)에는 batch02에서 세운 선례를
그대로 따라 일관되게 NEEDS_REVIEW로 유지했다.

**다만 INCLUDE 비율이 batch01·02(7~13%)에서 batch03(38%)으로 크게 뛰었는데, 이는 기준이 느슨해진
것이 아니라 batch03이 산모·신생아 편중을 의도적으로 낮춘 층화 표본이기 때문이다.** 이는 오히려
batch01·02의 낮은 INCLUDE 비율이 "기준이 엄격해서"가 아니라 "표본 구성이 산모·신생아에 치우쳐
있었기 때문"이라는 가설을 뒷받침한다.

## 12. 마지막 42건을 동일 기준으로 전부 처리해도 되는가

**남은 42건의 구성을 먼저 확인하는 것을 권장한다.** 이번 82건 분포 확인 결과, batch03에서 이미
비(非) 산모·신생아 32건을 전부 소진했으므로, **남은 42건은 산모·신생아 50건 중 batch03에서
표집되지 않은 42건(50-8=42)으로 전부 채워져 있다.** 즉 남은 42건은 사실상 단일 유형(산모·신생아)
으로만 구성돼 있다.

- 이는 좋은 소식이기도 하다 — 이번 batch03에서 검증했듯 산모·신생아 유형은 예외 없이
  `NOT_SENIOR_RELEVANT`로 판정되는 매우 일관된 패턴을 보였다(50건 표본 중 8건 전부 EXCLUDE,
  batch01의 11건 중 11건 EXCLUDE, batch02의 19건 중 19건 EXCLUDE — 지금까지 산모·신생아
  유형에서 INCLUDE나 NEEDS_REVIEW가 단 한 건도 나오지 않았다).
- 따라서 남은 42건을 **한 번에 처리하는 것 자체는 위험이 낮다고 판단한다** — 유형이 단일하고
  판정 패턴이 지금까지 100% 일관됐기 때문이다. 다만 "새로운 기준을 만들지 않는다"는 원칙과
  "애매하면 NEEDS_REVIEW"라는 원칙은 42건에도 예외 없이 적용해야 하며, 혹시라도 이례적으로
  고령자를 포함하거나(예: "모든 연령" 산모신생아 지원처럼 보이지만 실제로는 다른 대상이 섞인
  경우) 영양사가 명시된 경우가 있는지는 42건 전부를 실제로 열어봐야 확인 가능하다.
- **결론: 남은 42건은 "산모·신생아 단일 유형 42건"이라는 것을 사람이 확인한 뒤, 원한다면 한
  번에 처리해도 되지만, 그 전에 이 사실(단일 유형 집중)을 사용자가 인지하고 진행 여부를
  결정하는 것을 권장한다.** 이번 단계에서는 42건을 처리하지 않고 여기서 멈춘다.

## 요약 표 (사람이 한눈에 보기용)

| 항목 | 결과 |
|---|---|
| 남은 UNKNOWN 82건 검증 | 정확히 82건 확인(중복·누락 없음) |
| INCLUDE | 15건 |
| EXCLUDE | 23건 |
| NEEDS_REVIEW | 2건 |
| 데이터 품질 문제 | 5건 발견(동일문장 반복 1건, 모호한 제외문구 1건, 사업명-내용 불일치 1건, 지역필드 누락 1건, 사업 중복등록 의심 1건) |
| batch01~03 일관성 | 기준은 완전히 동일하게 작동, INCLUDE 비율 차이는 표본 구성(산모·신생아 편중도) 차이 때문 |
| 남은 42건 처리 권장 여부 | 42건은 전부 산모·신생아 단일 유형으로 확인됨 — 지금까지 이 유형은 100% EXCLUDE 패턴을 보였으므로 한 번에 처리해도 위험은 낮으나, **이 사실을 인지한 뒤 진행 여부를 사용자가 결정**하는 것을 권장 |
