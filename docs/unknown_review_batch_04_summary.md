# UNKNOWN 후보 4차 배치(42건, 마지막) 검토 요약 + 142건 전체 완결성 검사

작성일: 2026-08-21
기준: `docs/classification_criteria.md` v2.1 — batch01~03과 동일 기준, 완화·강화 없음.
방법: `welfare_candidates_reviewed.csv`에 이미 저장된 원문만 사용, 새 API 호출 없음.
기존 `welfare_candidates_reviewed.csv`, batch01~03 파일은 모두 수정하지 않았다.
결과는 `data/processed/unknown_review_batch_04.csv`에 저장했다.

## 0. 42건 재검증 — "산모·신생아 유형이므로 자동 EXCLUDE"를 하지 않은 근거

batch03에서 예상됐던 대로 남은 42건은 실제로 **전부** 임신·출산·산모·신생아를 직접적인 자격요건
으로 하는 서비스였다. 하지만 이는 "유형명만 보고" 내린 결론이 아니라, 42건 각각의
`target_original`을 실제로 읽고 다음을 확인한 결과다.

- "장애인가정 출산지원금" 계열(6건: 안양시·김제시·안산시·사상구·군산시·하남시)은 이름에
  "장애인가정"이 들어있어 자칫 SENIOR_CONDITIONAL(장애인 조건, 연령무관)로 오판할 수 있었으나,
  실제 자격요건을 확인하니 **트리거가 '신생아의 부 또는 모가 장애인'인 가정의 출산장려금**이었다
  — 즉 자격의 핵심 조건은 "출산"이며 장애 여부는 지원금액 차등 기준일 뿐, 대상 자체가 육아기
  부모(신생아의 부모)로 한정돼 고령자가 개입할 여지가 없음을 원문으로 확인했다.
- 42건 모두에서 "고령자도 이용 가능"하다고 해석될 수 있는 문구(예: 조부모 양육 포함, 연령
  무관 가구원 지원 등)는 **단 한 건도 발견되지 않았다.**
- 예외 서비스는 없었다.

## 1~2. 42건 판정 결과

| review_status | 건수 |
|---|---|
| INCLUDE | 0 |
| EXCLUDE | **42** |
| NEEDS_REVIEW | 0 |

| senior_relation_v2 | 건수 |
|---|---|
| SENIOR_DIRECT | 0 |
| SENIOR_CONDITIONAL | 0 |
| NOT_SENIOR_RELEVANT | **42** |

| nutrition_relevance | 건수 |
|---|---|
| DIRECT_NUTRITION | 0 |
| SUPPORTIVE_NUTRITION | 5 (엽산제·영양제·영양구입 사용처가 명시된 5건 — 대상관계 축에서 탈락해 최종 EXCLUDE) |
| NOT_NUTRITION_RELEVANT | 37 |

## 3. 데이터 품질 문제 (6건)

- **WLF00001849(산후 건강관리 지원, 강원)**: `contact`가 `033-000-0000`으로 **명백한 더미(placeholder)
  전화번호**임 — 실제 문의처 정보 없음.
- **WLF00003583(장애인가정 출산장려금, 김제시)**: `contact`에 같은 부서의 서로 다른 두 전화번호가
  나열돼 대표번호가 불명확.
- **WLF00003658(산모신생아 건강관리 지원사업 본인부담금 지원, 경북)**: `contact`에 '복지로:',
  '사회보장정보원: 1566-3232'가 각각 중복 나열.
- **WLF00006390(밀양시 임신지원금 지급)**: `application_original`에 "보거놋 방문"이라는 오탈자
  (보건소 오기).
- **WLF00003141(산후건강관리 지원사업, 전북)**: `contact`가 '지자체 사이트:'로만 돼 있고 실제
  값이 없음.
- **WLF00001381(산모신생아 건강관리서비스 본인부담금 지원, 인천)**: `contact`가 '거주지 보건소:
  군구별 상이'로 광역 단위 사업 특성상 구체적 연락처가 없음.

원문 필드는 수정하지 않았다.

---

## 7. UNKNOWN 142건 전체 완결성 검사

| 항목 | 값 |
|---|---|
| 원래 UNKNOWN service_id 수 | 142 |
| batch01 수 | 30 |
| batch02 수 | 30 |
| batch03 수 | 40 |
| batch04 수 | 42 |
| 네 batch 합집합 고유 service_id 수 | **142** |
| batch 간 중복 service_id 수 | **0** |
| 아직 검토되지 않은 service_id 수 | **0** |
| 원래 UNKNOWN에 없는데 batch에 들어간 service_id 수 | **0** |

**정상 조건(142/30/30/40/42, 고유 142, 중복 0, 미검토 0) 그대로 성립함을 확인했다.**

## 8. UNKNOWN 142건 전체 결과 요약

| review_status | 건수 |
|---|---|
| INCLUDE | **21** |
| EXCLUDE | **118** |
| NEEDS_REVIEW | **3** |

| senior_relation_v2 | 건수 |
|---|---|
| SENIOR_DIRECT | 3 |
| SENIOR_CONDITIONAL | 37 |
| NOT_SENIOR_RELEVANT | 102 |

| nutrition_relevance | 건수 |
|---|---|
| DIRECT_NUTRITION | 24 |
| SUPPORTIVE_NUTRITION | 15 |
| NOT_NUTRITION_RELEVANT | 103 |

### INCLUDE 21건 전체 목록

| service_id | 서비스명 | 지역 | senior_relation_v2 | nutrition_relevance | service_type_primary | verification_level |
|---|---|---|---|---|---|---|
| WLF00005239 | 누구나 돌봄! 시흥돌봄SOS센터 운영 | 경기도 시흥시 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | community_care | A |
| WLF00004595 | 저소득노인 무료급식(식사배달사업) | 경남 밀양시 | SENIOR_DIRECT | DIRECT_NUTRITION | meal_support | A |
| WLF00004507 | 사회복지센터 재가복지 봉사(김장서비스) | 경남 거창군 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | B |
| WLF00005583 | 장애인복지관 무료급식 지원사업 | 부산 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | A |
| WLF00005598 | 제주가치 통합돌봄 | 제주 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | community_care | A |
| WLF00001291 | 장애인 급식소 운영 | 경기 하남시 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | B |
| WLF00004268 | 저소득 재가장애인 식사배달사업 | 충북 옥천군 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | A |
| WLF00006240 | 안동시 식사배달 | 경북 안동시 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | A |
| WLF00001842 | 저소득 장애인 무료급식 지원 사업 | 서울 동대문구 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | B |
| WLF00002047 | 저소득 거동불편 장애인도시락배달 | 전북 전주시 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | B |
| WLF00002076 | 저소득 취약세대 밑반찬 지원사업 | 전북 군산시 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | A |
| WLF00001509 | 재가복지 서비스 | 충남 서산시 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | A |
| WLF00003300 | 거동불편 저소득노인 식사배달 사업 | 경남 합천군 | SENIOR_DIRECT | DIRECT_NUTRITION | meal_support | A |
| WLF00004743 | 소외계층 지원 | 전남광주통합 함평군 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | A |
| WLF00006231 | 장수군 도시락 배달 사업 | 전북 장수군 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | A |
| WLF00000115 | 저소득층 도시락 지원사업 | 강원 평창군 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | B |
| WLF00005857 | 부산, 함께돌봄(부산형 통합돌봄)사업 | 부산 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | community_care | A |
| WLF00005102 | 광주다움 통합돌봄 | 전남광주통합 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | community_care | A |
| WLF00005718 | 수원형 통합돌봄 수원새빛돌봄(누구나) 사업 | 경기(수원시 추정) | SENIOR_CONDITIONAL | DIRECT_NUTRITION | community_care | A |
| WLF00002345 | 고독사 등 고위험가구 반찬지원 및 안부확인 사업 | 전북 임실군 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | B |
| WLF00002523 | 늘해랑푸드마켓 | 대구 남구 | SENIOR_CONDITIONAL | DIRECT_NUTRITION | meal_support | A |

**21건 모두 `nutrition_relevance=DIRECT_NUTRITION`이다** — SUPPORTIVE_NUTRITION만으로 INCLUDE된
건은 UNKNOWN 142건 전체에서 단 한 건도 없었다(원문에 영양제·영양구입 언급이 있어도 전부 대상관계
축(임산부·산모 등)에서 탈락했기 때문).

**service_type_primary 분포**: meal_support **16건**, community_care **5건**(시흥돌봄SOS·제주가치
통합돌봄·부산 함께돌봄·광주다움 통합돌봄·수원새빛돌봄). **`nutritionist_involvement=direct`는
광주다움 통합돌봄(WLF00005102) 1건뿐**이며, 이는 UNKNOWN 142건 검토 전체를 통틀어 "영양사"가
원문에 직접 명시된 유일한 사례다.

## 9. NEEDS_REVIEW 통합 (3건)

`data/processed/unknown_needs_final_review.csv`에 저장했다.

| service_id | 서비스명 | 지역 | 출처 배치 |
|---|---|---|---|
| WLF00001309 | 행려자 귀향여비 및 급식비(안중출장소) | 경기도 평택시 | batch02 |
| WLF00003721 | 행려자 관리 | 강원특별자치도 횡성군 | batch03 |
| WLF00000783 | 행려자 귀향여비 및 급식비(송탄출장소) | 경기도 평택시 | batch03 |

세 건 모두 "행려자(귀향 희망 무숙식 여행자) 대상 여비·급식비 지원"이라는 동일 유형이다. 급식비
항목이 있어 고령 행려자도 해당될 수 있으나(SENIOR_CONDITIONAL), 여비·장제비·의료비와 묶인
일회성 긴급구호라 이 프로젝트가 다루는 "지속적 영양돌봄 서비스"에 해당하는지 판단이 서지 않아
세 배치에 걸쳐 일관되게 보류했다. 이 중 두 건(평택시 안중출장소/송탄출장소)은 **사실상 동일한
사업이 출장소별로 중복 등록**된 것으로 보인다 — 이 판정은 임의로 변경하지 않았다.

## 요약 표

| 항목 | 결과 |
|---|---|
| batch04 결과 | INCLUDE 0 / EXCLUDE 42 / NEEDS_REVIEW 0 (전부 산모·신생아 트리거로 재확인, 예외 없음) |
| UNKNOWN 142건 완결성 검사 | **OK** — 142=30+30+40+42, 고유 142, 중복 0, 미검토 0, 범위밖 0 |
| UNKNOWN 142건 최종 분류 | INCLUDE **21** / EXCLUDE **118** / NEEDS_REVIEW **3** |
| NEEDS_REVIEW 전체 목록 | 행려자 급식비 관련 3건(`unknown_needs_final_review.csv`) |
| 데이터 품질 문제 | 42건 중 6건에서 발견(더미 전화번호, 중복 연락처, 오탈자, 연락처 누락 등) — 원문 미수정 |
| 다음 단계(최종 병합) 진행 가능 여부 | 완결성 검사 OK, 병합 로직만 설계하면 진행 가능한 상태 — **단, 이번 단계에서는 병합을 시작하지 않음** |
