# 천안시 공식 데이터 보강 결과 보고서

> 이 문서는 사용자가 `manual_source_check_required.csv`에 남아있던 2건의 천안시 공식
> 페이지(노인맞춤돌봄서비스, 의료·요양 통합돌봄)를 직접 열람하여 제공한 원문을 근거로,
> 중복/schema audit → 조건부 안전 반영 → classification 적용 → 추천엔진 재검증 →
> RAG rebuild/retrieval 테스트 → 회귀 테스트를 수행한 결과를 기록한다.
>
> **기존 85건 `welfare_services_recommendation_ready.csv`는 이번 단계에서도 전혀
> 수정하지 않았다.** 신규 2건은 별도 파일
> `data/processed/welfare_services_enrichment_cheonan_verified.csv`에만 존재하며,
> 최종 병합은 사용자 승인 후 별도 단계에서 진행한다(기존 COLLECTED≠VERIFIED≠INCLUDE 원칙).

---

## 0. 먼저 수행한 audit (반영 전)

### 0.1 중복 여부 audit

기존 85건에서 다음을 검색했다(정확 일치 + 부분 일치 + 의미상 유사명):

| 검색어 | 결과 |
|---|---|
| `노인맞춤돌봄` | 1건 — `WLF00000664` 노인맞춤돌봄지원 강화 사업(서울 은평구). **다른 서비스**(전국 표준 노인맞춤돌봄서비스에 지자체가 얹는 별도 "강화" 사업이며, 지역도 은평구로 다름) |
| `의료` / `요양` | 0건 |
| `통합돌봄` | 7건(대전/제주/춘천/광주/함양/수원/부산) — **충청남도/천안 소재 0건** |
| `천안` | 0건(sido/sigungu 어디에도 없음) |

→ **두 서비스 모두 기존 85건과 exact/semantic duplicate가 아니다.** (판정: 신규 추가 가능)

### 0.2 schema audit — 요구된 11개 개념을 기존 컬럼으로 표현 가능한지

| 개념 | 기존 스키마로 표현 가능? | 사용 필드 |
|---|---|---|
| region | 가능 | `sido`, `sigungu`, `region_scope` |
| age | 가능 | `min_age`, `max_age`, `age_condition_type`, `age_condition_note` (COMPOUND 타입이 이미 존재 — WLF00003248 선례) |
| low_income | 가능 | `low_income_required` (TriState) |
| disability | 가능 | `disability_required` (TriState) |
| recent_discharge | 가능 — 단 서비스 측 전용 TriState 필드는 없고, **`service_type`에 `discharge_support` 태그**를 부여하는 기존 메커니즘으로 표현(WLF00006261 함양군 통합돌봄사업 선례) | `service_type` |
| community_care | 가능 | `service_type`의 `community_care` 태그 |
| nutrition support (식사 아닌 지원) | 가능 — `nutrition_relevance`에 이미 `SUPPORTIVE_NUTRITION`("통합돌봄의 명시적 일부로 포함된 식사·영양지원") 값이 정의되어 있으나, 기존 85건 중 실제 사용 사례는 0건이었음(64건 blank / 21건 DIRECT_NUTRITION) | `nutrition_relevance="SUPPORTIVE_NUTRITION"` |
| application method | 가능 | `application_original` (원문 그대로) |
| eligibility uncertainty | 가능 | `special_eligibility_required` + `special_eligibility_note` (v1.2, WLF00003248 장기요양등급 판정 선례) |
| source / official source | **불가능 — 스키마 갭.** production 85건 CSV(36컬럼)에는 공식 출처 URL을 위한 전용 컬럼이 없다(로더가 요구하는 28개 `REQUIRED_COLUMNS`에도, 그 외 감사용 6개 컬럼에도 없음) | 없음 — 아래 §0.3 참고 |
| service content | 가능 | `target_original`/`criteria_original`/`support_original`/`support_summary` |

### 0.3 schema 갭 보고 (대규모 변경 없이 처리한 방식)

**"공식 출처 URL"을 저장할 전용 컬럼이 production 스키마에 없다.** 이는 `ServiceRecord`나
`loader.py`를 건드리는 스키마 변경 없이도, 기존에 이미 쓰이던 패턴 — enrichment 후보
파일에 `REQUIRED_COLUMNS` 외의 추가 컬럼을 얹는 방식(`welfare_services_enrichment_official_web_candidates.csv`의 `official_url`/`source_title`/`collected_at` 등) — 을 그대로 재사용해 해결했다.
`loader.py`는 `REQUIRED_COLUMNS`에 없는 초과 컬럼을 무시하므로 안전하다.
→ **대규모 schema 변경 불필요, 별도 컬럼 추가만으로 해결.** (production 85건 파일 자체는
여전히 이 컬럼이 없는 상태이며, 이번 단계에서 그 파일을 바꾸지 않았다.)

그 외 발견한 표현 불가 항목(스키마 변경 없이 텍스트로만 보존, §5 한계에서 재정리):
- "유사 중복사업 제외" 조건과 "지자체장 예외 인정" 조항 — 구조화된 배제/예외 필드가 없어
  `criteria_original`/`eligibility_summary`에 원문 그대로만 보존(알고리즘적으로 강제되지 않음).

---

## 1. 기존 중복 여부

**중복 없음.** §0.1 참고. 두 서비스 모두 신규.

## 2. 실제 신규 추가 서비스 수

**2건** — 별도 candidate 파일에만 존재(production 85건 미병합).

## 3. 추가된 서비스명

| service_id | 서비스명 | 지역 |
|---|---|---|
| `ENR-CHEONAN-01` | 노인맞춤돌봄서비스 | 충청남도 천안시 |
| `ENR-CHEONAN-02` | 의료·요양 통합돌봄 | 충청남도 천안시 |

## 4. 각 서비스의 핵심 공식 근거

**ENR-CHEONAN-01 (노인맞춤돌봄서비스)**: 사용자가 천안시 공식 홈페이지를 직접 열람해
확인. 자격 — 65세 이상 + (국민기초생활수급자/차상위계층/기초연금수급자 중 하나) + 유사
중복사업(장기요양보험 등급자 등) 비대상, 지자체장 인정 시 예외 신청 가능. 서비스 내용 —
복지자원 발굴/연계, 생활교육, 정기 안전확인, 정서적 지원. **원문에 도시락/식사배달/반찬
언급 없음 — meal_support 미부여.**

**ENR-CHEONAN-02 (의료·요양 통합돌봄)**: 사용자가 천안시 공식 홈페이지를 직접 열람해
확인. 대상 — 돌봄이 필요한 65세 이상 또는 장애인 등 8개 병렬 하위대상(장기요양 등급자/
등급외자/판정대기·기각자, 퇴원환자, 노인맞춤돌봄 중점돌봄군, 고령장애인, 65세 미만
장애인, 기타). 서비스 내용 — 보건의료(방문진료 등)/일상생활(방문가사·방문목욕·**영양지원**·
외출동행 등)/주거지원(환경개선 등). **선정 절차 — 돌봄필요도조사(행정복지센터) →
건보공단 통합판정 → 통합지원회의를 거쳐 지원 여부 최종 결정(자동 확정 아님).**

## 5. classification 결과

| 필드 | ENR-CHEONAN-01 | ENR-CHEONAN-02 | 근거/규칙 |
|---|---|---|---|
| `service_type` | `community_care` | `community_care`, `discharge_support`, `home_visit` | B는 "방문의료/방문가사/방문목욕/방문운동" 등 명시적 방문형 서비스가 다수 → `home_visit` 추가. 퇴원환자가 병렬 대상 중 하나로 명시 → `discharge_support` 추가(WLF00006261 선례). **둘 다 `meal_support` 미부여**(지시사항 준수) |
| `disability_required` | `unknown`(언급 없음) | `unknown` | `recommendation_data_readiness.md`의 규칙: "장애 언급이 없거나, 여러 대상군 중 하나로만 병렬 열거되어 필수조건인지 불명확한 경우 → unknown". B는 장애인이 8개 병렬 대상 중 하나일 뿐 유일 조건이 아니므로 `true`가 아니라 `unknown` — 기존 WLF00006261(함양군 통합돌봄, 동일 패턴)과 동일하게 처리 |
| `low_income_required` | `true`(수급자/차상위/기초연금 중 하나가 필수) | `unknown`(원문에 소득 조건 언급 없음) | A는 공식 자격요건에 명시된 필수조건이므로 true. B는 원문에 소득 기준 자체가 없어 unknown |
| `recent_discharge` 대응 | 해당 없음 | `discharge_support` 태그로 반영(§0.2) | UserProfile 쪽 recent_discharge는 기존 `_discharge_component`(scorer.py)가 이미 처리 — 신규 로직 없음 |
| `special_eligibility_required` | `false`(제도적 판정 절차 없음) | **`true`**(통합판정+통합지원회의) | B는 WLF00003248(재가급여, 장기요양등급 판정)과 동일한 패턴의 기관 판정 게이트 — 이 필드로 반영하면 `open_count`를 통해 자동으로 POSSIBLE_MATCH 이하로 제한되고 `confirmation_needed`가 항상 채워짐 |
| `nutrition_relevance` | (blank, 원문에 영양 관련 언급 없음) | **`SUPPORTIVE_NUTRITION`** | "영양지원"이 통합돌봄 패키지의 명시적 일부 항목으로 원문에 있음 → `classification_criteria.md`의 정의("통합돌봄의 명시적 일부로 포함된 식사·영양지원")에 정확히 해당. `DIRECT_NUTRITION`(식사/도시락 자체 제공)과는 구분 |
| `nutritionist_involvement` | `not_specified` | `not_specified` | 영양사 등 전문인력 참여 언급 원문에 없음 |

**classification과 원문의 충돌**: 없음. 다만 "disability가 공식 대상에 명시되어 있는데
`disability_required=unknown`인 것이 원문과 모순처럼 보일 수 있어 원인을 명시한다 — 이는
분류 규칙의 오류가 아니라, "여러 병렬 대상 중 하나"와 "유일한 필수조건"을 구분하는 기존
규칙(§표 3번째 줄)을 정확히 적용한 결과이며, 기존 85건의 WLF00006261에도 동일하게
적용되어 온 일관된 처리다. `disability_required=true`로 바꾸면 장애가 없는 다른 7개
경로(장기요양 등급자 등)로 자격을 얻는 사용자를 부당하게 걸러내는 하드 필터가 되어 버려
원문을 오히려 왜곡한다.

## 6. 기존 서비스 수 → 보강 후 서비스 수

**85건 → (candidate 파일 기준) 87건.** production CSV는 여전히 85건(미병합 유지).
아래 §7~11, §12 시나리오는 모두 "85 vs 85+2(테스트용 결합)" 비교다.

## 7. 천안 region coverage 변화

**0건 → 2건.** `region_codes.csv` 기준 천안시/천안시 동남구/천안시 서북구 3개 sigungu
코드가 존재했으나 대응 서비스 데이터는 기존 0건이었다(Phase 5/8에서 반복 확인된 갭).
이번 보강으로 천안시(SIGUNGU) 스코프 서비스가 2건 생겼다.

## 8. community_care coverage 변화

전국 기준 7건 → 9건(+2, 모두 천안). 충청남도/천안 지역 기준으로는 0건 → 2건.

## 9. disability coverage 변화

**구조화된 `disability_required=true` 건수는 변화 없음(12건 → 12건, 신규 2건 모두
`unknown`)** — §5에서 설명한 대로 병렬 대상 규칙에 따른 의도된 결과다. 다만 **장애인이
공식 대상으로 명시된 텍스트 근거를 가진 서비스**는 천안 지역 기준 0건 → 1건(B)으로
늘었다 — 구조화 필드 수치와 원문 텍스트 근거는 별개로 봐야 한다.

## 10. recent_discharge coverage 변화

`discharge_support` 태그 보유 서비스: 전국 기준 1건(WLF00006261, 경남 함양군) → 2건(+B,
천안). 천안 지역 기준 0건 → 1건.

## 11. nutrition/meal_support coverage 변화

- `meal_support` 태그: **변화 없음(신규 2건 모두 미부여)** — 지시사항대로 공식 근거 없는
  서비스에 임의로 부여하지 않았다.
- `nutrition_relevance=SUPPORTIVE_NUTRITION`: 0건 → 1건(B). 기존 85건에는 정의만 있고
  실사용 사례가 없던 값이었다.
- `nutrition_relevance=DIRECT_NUTRITION`: 변화 없음(21건 유지).

## 12. Scenario A~E Before/After

공통: `services=85건` vs `services=85건+2건`(테스트 결합, production 미병합), `top_k=10`.

| Scenario | Before(85) | After(87) | 신규 서비스 순위/사유 |
|---|---|---|---|
| **A** 75세/저소득=예/독거=예/거동불편=예/식사준비어려움=예/disability=아니오/desired=meal_support | Top-2, 전국 서비스만(WLF00000098, WLF00003248) 모두 NEEDS_CONFIRMATION(15.8점, 특수자격요건 확인 필요) | Top-4. `ENR-CHEONAN-01`이 1위(15.8점, NEEDS_CONFIRMATION, confirm_needed=[] — 지역/연령/저소득 모두 명확히 충족), `ENR-CHEONAN-02`가 2위(15.8점, 특수자격요건 확인 필요). **meal_support desired_support 점수는 두 신규 서비스 모두 0**(둘 다 meal_support 태그가 없으므로) — 과장된 부스트 없음 |
| **B** A와 동일 + disability=예 | 동일(Before A와 결과 동일) | **A와 완전히 동일한 순위/점수.** disability 답변이 두 신규 서비스 점수에 전혀 영향을 주지 않음(`disability_required=unknown`이므로 하드필터/소프트스코어 모두 disability를 채점 요소로 쓰지 않음) — 장애 여부 하나만으로 순위가 흔들리지 않음을 확인 |
| **C** 70세/recent_discharge=예/community_care 요청 | Top-2, 전국 서비스만(5.6점, 거동불편 조건 미확인 페널티 포함) | Top-4. **`ENR-CHEONAN-02`가 1위(77.8점, POSSIBLE_MATCH)** — 지역 정밀 일치 + community_care 서비스타입 일치 + (recent_discharge=예이므로 discharge 보너스) 반영. `ENR-CHEONAN-01`이 2위(72.2점, POSSIBLE_MATCH) — community_care 일치는 있으나 discharge 보너스 없음. **둘 다 HIGH_MATCH가 아닌 POSSIBLE_MATCH**(B는 special_eligibility로 상한 고정) |
| **D** 60세/disability=예/community_care 요청 | Top-2, 전국 서비스만(5.9점) | Top-3. **`ENR-CHEONAN-02`가 1위(76.5점)이지만 match_level=NEEDS_CONFIRMATION**(POSSIBLE_MATCH가 아님 — 연령이 COMPOUND라 미확정 + special_eligibility 미확정, 두 개의 open 조건). `ENR-CHEONAN-01`은 **Top-3에 없음** — `min_age=65`(SIMPLE_MIN)에 60세가 하드 미달로 배제됨(대체 경로 없음, 의도된 하드필터 동작). → **장애 조건 하나만으로 1위가 고정되긴 하지만 HIGH_MATCH/POSSIBLE_MATCH가 아니라 NEEDS_CONFIRMATION에 머물러 "무조건 확정 대상"으로 과장되지 않음을 확인** |
| **E** disability=아니오/recent_discharge=아니오/저소득=아니오/취약조건 거의 없음 | Top-2, 전국 서비스만(14.3점) | Top-3. `ENR-CHEONAN-02`가 1위(42.9점, NEEDS_CONFIRMATION, 연령 미입력+특수자격요건 확인 필요로 조건 2개 미확정) — 순수 지역 정밀도만으로 상위이나 확정과는 거리가 멂. **`ENR-CHEONAN-01`은 Top-3에 없음** — 저소득=아니오가 A의 `low_income_required=true`와 정면 MISMATCH로 하드 배제(정확한 하드필터 동작) |

**결론**: 의료·요양 통합돌봄은 disability/discharge/community_care 조건에서 합리적으로
순위가 상승하지만, `special_eligibility_required=true`(통합판정 게이트) 때문에 단일
조건만으로 HIGH_MATCH나 무조건적 확정 자격에 도달하지 않는다(Scenario C/D 모두
POSSIBLE_MATCH 이하). 노인맞춤돌봄서비스는 저소득/연령 요건을 만족하지 않는 사용자에게는
정확히 하드 배제된다(Scenario D/E).

## 13. RAG retrieval 결과

기존 `rag.build_index`의 함수(`build_documents`, `Embedder`, `VectorStore.build/save`)를
그대로 재사용해 **별도 스테이징 인덱스**(`data/vectorstore_staging_cheonan_test/`, 테스트 후
삭제 — production `data/vectorstore/`는 손대지 않음)를 85+2건으로 빌드했다. 문서 334개
(신규 2건 → target/criteria/support/application 4섹션씩 총 8개 청크, 빈 섹션 없음).

4개 질의를 서비스 경계별로 3중 확인:

| 질의 | 스코프 | 결과 |
|---|---|---|
| "천안 퇴원 후 받을 수 있는 돌봄 서비스" | `ENR-CHEONAN-02` 단독 | support(0.849)/target(0.873)/criteria(0.855) 모두 자기 서비스만 반환, 누출 0 |
| "천안 장애인이 받을 수 있는 통합돌봄" | `ENR-CHEONAN-02` 단독 | support(0.841)/criteria(0.879)/target(0.879), 누출 0 |
| "천안에서 영양 지원을 받을 수 있는 돌봄 서비스" | `ENR-CHEONAN-02` 단독 | support(0.860)/target(0.875)/criteria(0.870), 누출 0 |
| "노인맞춤돌봄서비스 신청 방법" | `ENR-CHEONAN-01` 단독 | application(0.860)/target(0.913)/criteria(0.886), 누출 0 |

추가로 (a) 두 신규 서비스에 동시에 스코프를 걸었을 때도 서로 다른 두 service_id가 섞여
나올 뿐 제3의 서비스는 절대 등장하지 않았고, (b) 기존 서비스(`WLF00003248`)에만 스코프를
걸었을 때는 4개 질의 모두 신규 서비스 콘텐츠가 전혀 나타나지 않았다(누출 0/0/0/0).
→ **cross-service contamination 없음** — retriever의 구조적 service_id 경계 보장이
신규 레코드에도 동일하게 적용됨을 확인.

## 14. 전체 테스트 결과

- 기존 baseline: **226 passed / 4 skipped**
- 이번 단계 후: **235 passed / 4 skipped** (신규 `tests/test_cheonan_enrichment_candidates.py` 9건 추가, 기존 226건은 전부 그대로 통과)
- **회귀 0건.** production 소스 코드(recommender/rag/streamlit_ui 어느 것도) 수정하지 않았으므로 당연한 결과이나 실제로 재실행하여 확인함.

## 15. 발견된 한계

1. **연락처(contact) 정보 없음** — 사용자가 제공한 원문에 담당 부서 전화번호가 없어 두
   서비스 모두 `contact`를 비워둠(임의 기재 금지 원칙 준수). 실사용 전 반드시 보완 필요.
2. **`official_url`이 최상위 도메인만 기록됨** — 정확한 하위 경로가 이번 검증 과정에서
   확정되지 않아 `https://www.cheonan.go.kr (사용자 직접 확인, 정확한 하위 경로 미기록)`로만
   남김. 추후 실제 URL 재확인 권장.
3. **"유사 중복사업 제외"/"지자체장 예외 인정" 조건은 구조적으로 강제되지 않음** — 텍스트로만
   보존되며, 추천엔진이 자동으로 걸러내거나 예외를 반영하지 않는다(§0.3). 다만 이는 프로젝트
   전체가 "추천 = 후보 제시, 최종 확정은 담당기관"이라는 원칙을 이미 일관되게 따르고 있어
   구조적 위험은 아니다.
4. **production 85건 CSV에 아직 병합되지 않음** — 이번 단계는 검증까지이며, 병합은 사용자
   승인 후 별도 스크립트로 진행해야 한다(단순 append가 아니라 `service_id` 네임스페이스
   전환 등 검토 필요).
5. **천안시 하위 행정구역(동남구/서북구) 세분화 정보 없음** — 사용자가 확인한 원문이 천안시
   전체 단위였기 때문에 `sigungu="천안시"`(기본 구역)로만 저장했다. 기존 `_sigungu_base()`
   폴백 로직 덕분에 사용자가 "동남구"/"서북구"를 선택해도 정상 매칭되지만, 하위구역별
   차이(있다면)는 반영되지 않는다.
6. **공식 출처 URL 전용 컬럼이 production 스키마에 없다는 점은 여전히 미해결** — 이번엔
   후보 파일의 추가 컬럼으로 우회했으나(§0.3), 병합 시점에는 이 정보를 어떻게 유지할지
   별도 결정이 필요하다.

## 16. 추가 데이터 수집이 아직 필요한지

**예, 필요하다.** 이번 보강은 천안시 커버리지를 0 → 2건으로 개선했지만:
- Phase 5/7/8에서 반복 확인된 전국적 REGION_DATA_COVERAGE(78.6%)/SUPPORT_TYPE_COVERAGE
  (21.4%) 갭은 이번 작업 범위(천안 2건) 밖이라 그대로 남아있다.
- 화성/세종/울산에서 발견한 OWEB 후보 7건은 아직 review/최종 판단 대기 상태다.
- 천안 2건 자체도 production 병합 전 단계이며, §15의 한계(연락처/URL 하위경로 미확정)가
  해소되어야 병합 품질이 더 높아진다.

---

## 최종 판정

**`CHEONAN_ENRICHMENT_VALIDATED_WITH_LIMITATIONS`**

근거: 중복 없음을 확인 후 안전하게 신규 반영, schema 변경 없이 기존 필드(특히
`special_eligibility_required`/`nutrition_relevance=SUPPORTIVE_NUTRITION`/
`discharge_support` 태그)만으로 모든 요구 개념을 정확히 표현, 5개 시나리오 모두 의도된
대로(단일 조건으로 무조건 확정되지 않음, 정당한 하드 배제는 유지됨) 동작, RAG 신규 검색
가능 + contamination 0, 회귀 테스트 0건 — 검증 자체는 완전히 성공했다. 다만 연락처/URL
하위경로 미확정, production 미병합, 구조적으로 강제되지 않는 배제조건 등 §15의 실질적
한계가 남아있어 `_WITH_LIMITATIONS`로 판정한다.
