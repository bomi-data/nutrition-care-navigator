# 데이터 보강 실행 계획 (Data Enrichment Plan)

> 이 문서는 **계획**입니다. 이번 단계에서는 실제 API 호출, 웹 크롤링, PDF 다운로드, CSV 병합,
> 추천엔진/RAG/Streamlit 수정을 전혀 하지 않았습니다. 아래 모든 수치와 판단은 기존에 이미
> 로컬에 존재하는 파일(`data/raw/*.xml`, `data/processed/candidates_stage1_raw.csv`,
> `data/processed/welfare_candidates_reviewed.csv`, `docs/*.md`)을 직접 읽어 확인한 것입니다.

---

## 1. 현재 데이터 구조 확인

`data/processed/welfare_services_recommendation_ready.csv` — **85행, 36개 컬럼**(v1.2에서
`special_eligibility_required`/`special_eligibility_note` 2개 추가된 최신 상태, 재확인함).

지침이 지정한 필드는 전부 실제로 존재합니다: `service_id`, `service_name`, `sido`, `sigungu`,
`region_scope`, `service_type_primary`, `meal_support_flag`, `food_cost_support_flag`,
`disability_required`, `low_income_required`, `single_household_required`,
`homebound_or_mobility_condition`, `special_eligibility_required`, `target_original`,
`criteria_original`, `support_original`, `application_original` 등. (`region`이라는 단일 컬럼은
없고 `sido`/`sigungu`/`region_scope` 3개로 표현됨 — 이전 보고서들과 동일하게 재확인.)

**중요하게 새로 확인한 것**: 이 85건은 파이프라인의 끝이 아니라 **더 큰 검토 파이프라인의 일부**입니다.

```
data/raw/central_welfare_all.xml (461건, 전국)  ─┐
data/raw/local_welfare_all.xml   (4,770건, 전국) ─┴─ candidates_stage1_raw.csv (키워드 매치, 고유 357건)
                                                        │
                                        ┌───────────────┼───────────────┐
                                  1순위(98)          2순위(142)      3순위(117)
                              likely_senior       unknown         likely_not_senior
                              → 검토완료            → 검토완료        → **미검토(0건 검토)**
                              INCLUDE 64            INCLUDE 21       (§5.3에서 상세)
                                        └───────────────┴───→ 85건(최종, 중앙 1 + 지자체 84)
```

이 구조를 재확인한 것이 이번 계획의 가장 중요한 전제입니다 — **"새 API를 어디서 찾을까"보다
먼저 "이미 수집해 둔 5,231건 중 아직 검토하지 않은 117건이 있다"**는 사실이 §5-6-13의 실행
순서를 결정합니다.

---

## 2. Coverage Gap 지역 분석 (실측)

`recommend()`/`apply_hard_filters()`(무수정)로 계산한 결과(이전 단계 `mvp_coverage_validation.md`
§4 재확인 + 신규 항목):

| 지역 | 현재 서비스 수 | meal_support | disability 관련 | low_income 관련 | community_care | food_cost_support | NATIONAL만으로 대체되는 항목 | 실제 지역서비스 공백 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| 경기도 화성시 | 3 (SIDO 1+NATIONAL 2) | 1(SIDO) | 0 | 1(SIDO) | 0 | 0 | disability/community_care/food_cost 전부 | 시군구 단위 서비스 0건 |
| 충청남도 천안시 | 2 (NATIONAL만) | 0 | 0 | 0 | 0 | 0 | **전부**(meal_support 포함) | 시/군 단위 서비스 자체가 0건 |
| 세종특별자치시 | 2 (NATIONAL만) | 0 | 0 | 0 | 0 | 0 | 전부 | API 원문에 세종 소재 항목 자체가 없음(§5.2) |
| 울산광역시 | 2 (NATIONAL만) | 0 | 0 | 0 | 0 | 0 | 전부 | 등록된 사업은 있으나 전부 아동/장애수당 등 타 범주 |
| 전북특별자치도 전주시 | 3 (SIGUNGU 1+NATIONAL 2) | 1 | 1 | 1 | 0 | 0 | community_care/food_cost | v1.2 세부구 fallback으로 확보된 1건 외 없음 |
| 서울특별시 성동구 | 4 (SIGUNGU 2+NATIONAL 2) | 2 | **2** | 2 | 0 | 0 | community_care/food_cost | disability 데이터가 실제로 있는 몇 안 되는 지역 |

**공통 발견**: 6개 지역 전부 `community_care`와 `food_cost_support`가 0건입니다 — 이는 §2의
개별 지역 문제가 아니라 §4에서 다루는 **전국적 서비스유형 편중** 문제의 지역별 발현입니다.

---

## 3. 데이터 보강 목표량 제안

**전체 추가 약 25~30건을 제안합니다** (40건은 근거 부족으로 비권장, 20건은 지역+유형 두 축을
동시에 개선하기에 부족).

**근거**:
- §5.3에서 확인했듯 현재 남아있는, **이미 수집된(API 재호출 불요) 미검토 후보는 117건뿐**이고,
  그중 P0 지역(화성/천안/세종/울산) 관련은 사실상 0건입니다(§5.2). 즉 "이미 있는 데이터에서
  40건을 더 뽑아낸다"는 시나리오는 현재 근거로 뒷받침되지 않습니다.
- 반대로 20건은 §8(Top-K 부족 원인의 21.4%를 차지하는 SUPPORT_TYPE_COVERAGE)와 §2(지역
  공백) 두 문제를 동시에 완화하기에는 너무 적습니다.
- 25~30건은 "5일 MVP에서 실제로 검증 가능한 규모"(기존 85건을 74→85건으로 늘리는 데 약
  N일이 걸렸는지는 `data_preprocessing_final_summary.md` 등 기존 기록으로 가늠 가능하며, 그
  작업량의 1/3 규모)이면서, 지역 4곳 + 유형 2종(community_care/disability)을 각각 의미 있게
  개선할 수 있는 최소량입니다.

**지역별/유형별 배분(근거 기반)**:

| 항목 | 목표 | 근거 |
|---|---:|---|
| 화성시 | +2~3 | 현재 3건(그마저 SIDO/NATIONAL). §5.2에서 기존 후보 풀에 신규 후보 없음을 확인 → MANUAL 소스 필요, 현실적 상한은 인근 시군 사업량(예: 경기도 평균 SIGUNGU 5건/시도) 대비 적은 수 |
| 천안시 | +2 | 현재 2건(NATIONAL만). §5.2에서 확인한 대로 등록된 25개 지자체 사업 중 식사/영양 관련 0건 — MANUAL 확인 필요, 보수적 목표 |
| 세종 | +1~2 | API 원문 자체에 세종 소재 항목이 없어(§5.2) 가장 불확실 — 목표를 낮게 설정 |
| 울산 | +2 | 등록 사업(102건) 중 키워드 매치는 있었으나 전부 타 범주 — MANUAL 확인 필요 |
| disability 확대(전국) | +5 | 현재 12/85(14.1%). §2에서 있을 때 영향력이 크다고 실증됨(성동구 사례) — `manual_review_queue.csv`의 EXCLUDE 33건 중 장애 관련 재검토 여지 확인 필요 |
| community_care 확대(전국) | +8 | Top-K 부족 원인의 21.4%(SUPPORT_TYPE_COVERAGE) 대응, 현재 12/85(14.1%)로 가장 얇은 실사용 유형 |
| 기타(food_cost_support 등) | +3~5 | 현재 1/85, 옵션 다양성 확보 |
| **합계** | **약 25~30** | |

---

## 4. 우선 보강할 서비스 유형

| 유형 | 현재 건수 | 분류 | 근거 |
|---|---:|---|---|
| meal_support | 81(95.3%) | **NOT_NEEDED_NOW** | 이미 충분. 추가로 늘리면 오히려 §5(desired_support)의 변별력을 더 낮추는 역효과(85건 중 81건이 이미 같은 태그) |
| **disability meal support** | 12(14.1%, 그중 meal_support 결합은 다수) | **P0** | Scenario 검증에서 있을 때 순위를 완전히 뒤바꾸는 유일한 카테고리(정보가치 §7 재확인) |
| **community_care** | 12(14.1%) | **P0** | Top-K 부족의 21.4% 원인(§8 정량 분석), 프로젝트명("통합돌봄")과 직결 |
| home_visit | 6(7.1%) | **P1** | 이미 NATIONAL 2건이 있어 최소한의 매칭은 되나, 지역 기반 home_visit이 거의 없어 지역성 없는 추천만 반복됨 |
| food_cost_support | 1(1.2%) | **P1** | 옵션 자체는 존재하나 선택지가 1건뿐이라 사실상 무의미 |
| nutrition counseling / nutrition education | **0건**(태그 자체 없음) | **P2** | `candidate_review_summary.md`/`unknown_review_batch_04_summary.md`가 이미 확인: 357건 전체 후보 중 `nutritionist_involvement=direct`가 단 1건(WLF00005102, 이미 포함됨). 태그 자체가 원문에 거의 등장하지 않아 **P0/P1으로 올려도 단기간에 확보 가능성이 낮음** — 무리한 목표를 세우지 않음 |
| discharge support | 1(1.2%) | **P2** | §10에서 별도 판단 |
| single household support(독거 특화) | 9(10.6%) | **P2** | §2에서 영향력이 확인되지만, 원문 재검토(신규 수집 아님)로도 개선 가능해 우선순위를 낮게 둠 |

---

## 5. 기존 API 재활용 가능성 검토 (실제 호출 없이, 기존 raw 파일만으로 확인)

### 5.1 지자체복지서비스 API는 이미 지역 필터 없이 전국 전체를 수집했었다

`src/data_collection/collect_local_welfare_full.py`/`collect_central_welfare_full.py`를 다시
읽었습니다. **두 스크립트 모두 `sido`/`sigungu` 쿼리 파라미터를 전혀 사용하지 않고, `pageNo`/
`numOfRows`만으로 전체 페이지네이션**했습니다(지자체 4,770건 = 5페이지×1000, 중앙 461건 = 1페이지).
즉 **"지역 쿼리를 놓쳐서 화성시/천안시가 빠졌다"는 가설은 기각**됩니다 — 애초에 지역 필터를 걸지
않고 전량을 가져왔습니다.

### 5.2 실제로 raw XML에 해당 지역 데이터가 있는지 직접 확인

`data/raw/local_welfare_all.xml`(4,770건)을 직접 파싱해 확인했습니다.

- **세종특별자치시: `ctpvNm`이 "세종"인 행이 0건**입니다(전체 14개 시도 집계에 세종 자체가
  없음). API 재호출로는 해결되지 않을 가능성이 높습니다 — 이 API에 세종시가 사업을 등록하지
  않았거나 표기 방식이 다른 것으로 추정되며, **단정하지 않고 재수집 시 1차로 재확인이 필요**합니다.
- **울산광역시: 102건 존재**하나, `sggNm`에 "울산"이 들어간 전체 목록을 확인한 결과 등록된
  102건 중 영양/식사 관련은 없었고, 키워드 매치 3건(§5.3)도 전부 아동급식/장애수당으로 이미
  올바르게 제외되었습니다.
- **화성시: `sggNm`="화성시"인 행 23건 전부**를 직접 열람했습니다. 고용지원·주거지원·출산장려금
  등이며, 유일하게 애매한 후보는 **"노인복지관 운영"(WLF00005011)** — 그런데 이 후보는 현재
  16개 키워드 중 어느 것과도 일치하지 않아 **`candidates_stage1_raw.csv`에 아예 들어간 적이
  없습니다**(§7에서 상세).
- **천안시: `sggNm`="천안시"인 행 25건 전부**를 열람했습니다. 보훈수당·장애인지원·한부모지원
  등이며, 식사/영양 관련은 없었습니다.

### 5.3 pagination/keyword/region normalization 문제였는가?

| 질문 | 답 |
|---|---|
| pagination 때문에 놓친 데이터가 있는가? | **아니오.** `*_collection_log.json`에서 `missing_count: 0`(중복/누락 없음 확인됨, 무수정 재확인) |
| region field normalization 때문에 누락된 서비스가 있는가? | **아니오, 이번 조사 범위 내에서는.** 화성/천안/울산 모두 `sggNm`이 정상적으로 채워져 있었고, region_codes.csv와 원문 CSV의 sido 표기(`전남광주통합특별시` 등)도 일치함을 확인(v1.2 세부구 문제와 달리 sido/sigungu명 자체의 불일치는 이번 4개 지역에서 발견 안 됨) |
| 기존 후보 추출 keyword가 너무 좁았는가? | **부분적으로 예.** §7에서 "노인복지관" 키워드 부재로 화성시의 유일한 애매 후보(WLF00005011)가 후보 목록에 아예 오르지 못한 것을 확인 |
| **이미 수집된 데이터 중 검토가 안 끝난 게 있는가?** | **예, 이것이 가장 큰 기회입니다.** 357건 중 3순위(`likely_not_senior`) **117건이 통째로 미검토** 상태입니다(`candidate_review_summary.md` 원문 확인). 다만 §5.2에서 화성/천안/세종은 이 117건에도 0건, 울산만 2건(이미 아동급식으로 확인된 것과 동일 건)이 존재해, **이 117건 재검토가 P0 4개 지역의 공백을 채우지는 못할 가능성이 높습니다.** 그러나 disability/community_care 전국 확대(§4)에는 기여할 수 있습니다 — 117건을 전부 재검토하지는 않았지만 최소한 존재를 확인했습니다. |

**결론(§6 요구사항에 대한 답)**: 기존 API의 쿼리 방식 자체는 문제가 없었습니다(전국 전체
수집 완료). 문제는 (1) 키워드가 "노인복지관" 같은 일부 합리적 후보를 놓쳤다는 점(소규모),
(2) 세종/천안/화성은 **애초에 이 두 API의 현재 스냅샷에 해당 유형 사업이 없거나 발견되지
않았다는 점**입니다. 따라서 **새 API를 찾기 전에 먼저 재확인해야 할 것은 "같은 API를 최신
날짜로 다시 호출했을 때 새로 등록된 사업이 있는지"**이며(§13 Step 1), 그래도 없다면 §10과
`data_source_plan.md` C장의 MANUAL 지자체 홈페이지 확인으로 넘어가야 합니다.

---

## 6. Keyword 전략 재검토 (실제 재추출 없이, 기존 원문에 시험 매치만 수행)

현재 `extract_candidates_stage1.py`의 keyword 16개: `영양, 식사, 급식, 도시락, 밑반찬, 반찬,
식생활, 결식, 식품, 방문건강, 건강관리, 통합돌봄, 통합지원, 노인돌봄, 퇴원, 재가`.

기존 raw XML(4,770건)에 대해 **후보 키워드를 시험 매치만 해보고(재추출 실행은 안 함)** 다음을
확인했습니다.

| 키워드 후보 | 기존 16개로 못 잡는 신규 매치 수 | 판정 |
|---|---:|---|
| "경로식당" | 0건 | **불필요**(이미 "급식"/"식사" 등으로 전부 중복 커버됨) |
| "식재료" | 0건 | **불필요**(동일) |
| **"노인복지관"** | 2건(화성시 WLF00005011 포함) | **추가 권장** — 매치 수가 적어(전국 2건) 오탐 위험이 낮고, P0 지역 공백을 직접 겨냥함 |
| "바우처" | 75건 | **추가 비권장** — 표본 확인 결과 아동/청소년/신혼부부/주택 바우처 등 **대부분 식품과 무관**(오탐률 매우 높음) |
| "돌봄센터" | 4건 | **추가 비권장** — 전부 "다함께돌봄센터"(아동 대상 돌봄시설)로 확인, 고령자와 무관 |

**유지할 keyword**: 16개 전부(오탐 사례가 `candidate_review_summary.md` §8에 이미 기록되어
있지만 — "영양군"[지명]/"식품위생 종사자" 등 — 이는 **검토 단계에서 사람이 걸러내는 것**이 맞고
키워드 자체를 제거할 근거는 아닙니다. 키워드는 "넓게 후보를 잡는" 1차 스크리닝 목적이므로).

**오탐이 많은 keyword**: "건강관리"(화성시 사례에서 건강보험료 지원사업을 오탐), "재가"(화성시
사례에서도 오탐 발생 가능성 확인) — **제거하지 말고 검토 단계에서 우선순위를 낮게** 두는 것을
권장합니다(키워드를 좁히면 §5.3에서 확인한 "노인복지관" 같은 진짜 후보도 함께 놓칠 위험).

**추가할 keyword**: **"노인복지관"** 1개만 근거 있게 추가 권장합니다. "방문"(단독), "돌봄"(단독)
등은 시험하지 않았으나 기존 "방문건강"/"통합돌봄"/"노인돌봄"과 결합어라 단독으로 풀면 오탐이
급증할 가능성이 높아(위 "돌봄센터" 사례 참고) **권장하지 않습니다.**

**지역/유형별 보조 keyword**: 이번 조사 범위에서는 지역별로 다른 keyword 세트가 필요하다는
근거를 찾지 못했습니다(같은 16개+1개가 전국에 동일하게 적용 가능해 보임).

---

## 7. Disability 데이터 보강 전략

**A(실제로 장애인 영양·식사지원 서비스가 적은 것) vs B(추출 방식이 놓친 것) 구분**:

- 현재 85건의 `disability_required=true` 12건은 전부 `meal_support` 계열입니다(재확인).
- `candidate_review_summary.md` §11이 이미 기록한 대로, **1차 검토에서 NEEDS_REVIEW로 분류된
  11건 중 6건이 "장애인 대상 서비스인데 고령자 전용 여부 불분명"**한 경우였습니다
  (WLF00001054, WLF00000628, WLF00000895, WLF00003075, WLF00003500 등 — 이 중 다수는 이후
  재검토를 거쳐 이미 최종 85건에 포함됨, 예: WLF00000895/WLF00003500/WLF00001842 등이 현재
  disability_required=true 12건 안에 있음).
- **결론: A와 B가 섞여 있습니다.** 이미 알려진 장애인 대상 서비스 후보(NEEDS_REVIEW였던 것들)는
  대부분 B(추출/재검토 과정에서 이미 상당수 구제됨)에 해당하고, 그 이상으로 더 있는지는 §5.3의
  117건 미검토 풀과 새 API 재수집에서 확인해야 합니다 — **이번 단계에서 "장애인 영양서비스 자체가
  전국적으로 적다/많다"를 단정하지 않습니다.**

**우선 찾아야 할 유형(지침 예시 그대로, 존재 여부는 단정 안 함)**: 재가장애인 식사배달,
장애인 밑반�찬, 장애인 무료급식, 중증장애인 식사지원 — **이미 85건 안에 각 유형의 실사례가
1건 이상씩 존재**하므로(예: WLF00000895 "재가장애인 식사배달사업비 지원"), 완전히 새로운
유형이 아니라 **같은 유형의 다른 지역 사례**를 P0 지역 중심으로 추가 확보하는 방향이 현실적입니다.

---

## 8. Community_care 보강 전략

현재 12/85(14.1%), Top-K 부족 원인의 21.4%(§8 정량 분석, `mvp_coverage_validation.md` 재인용)를
차지합니다. 이미 포함된 12건은 강원·경남·서울·경기·부산·제주·전남광주·대전에 흩어져 있고,
**화성시/천안시/세종/울산 4개 P0 지역에는 0건**입니다(§2).

권장 보강 방향(지침이 예시한 4개 하위유형 기준):
- **지역 통합돌봄**: 이미 85건에 "OO형 통합돌봄"류 사례가 다수 있어(춘천형/대전형/광주다움/
  수원새빛/부산형 등) 같은 패턴의 다른 지자체 사례를 P0 지역 중심으로 탐색.
- **방문지원/식사 연계**: `home_visit`과 겹치는 영역이라 §4의 home_visit(P1) 보강과 함께 진행 가능.
- **재가 지원**: `재가`가 이미 keyword에 포함되어 있어 §5.3의 117건 미검토 풀 재확인만으로도
  일부 확보 가능성.

**정량 제안**: §3의 +8건이 이 유형의 목표입니다 — 12건→20건이 되면 전체 대비 비율이
14.1%→약 23%(85+25건 기준)로 오르고, 6개 표본 지역 중 최소 2~3곳에서 SUPPORT_TYPE_COVERAGE
원인이 해소될 것으로 기대합니다(§11).

---

## 9. Recent_discharge 처리 판단

**Option B(OPTIONAL 유지)를 권장하며, 부분적으로 Option D(v2로 이월)를 함께 권장합니다.**

근거:
- 현재 1/85(1.2%)로 가장 희소하며, `data_source_plan.md` B장이 이미 확인한 대로 관련 공식
  자료(HIRA 퇴원지원 시범사업 지침)는 **병원 단위 서비스라 "신청방법"이 병원별로 갈릴 가능성이
  높고, 참여 병원 목록 공개 여부가 미확인** 상태입니다 — 5일 MVP 규모로 신뢰도 있게 확보하기
  어렵습니다.
- `recommendation_system_design.md` §2가 이미 `recent_discharge`를 **"선택(optional) 입력"**으로
  설계해 두었으므로(무수정 확인), Option B는 사실 기존 설계를 유지하는 것과 같습니다 — 새로운
  변경이 아닙니다.
- Option A(적극 보강)는 이번 정량 분석에서 근거가 부족합니다(§13에서 관련 데이터를 P2로
  분류한 이유와 동일).
- Option C(UI엔 남기되 score 영향 최소화)는 **이미 사실상 그런 상태**입니다 —
  `discharge_bonus_max=5.0`(전체 배점 중 가장 작은 축에 속함, `config.py` 무수정 확인)이고
  사용자가 명시적으로 선택했을 때만 활성화됩니다.

**결론**: UI/score 변경이 이번 데이터 보강 우선순위에서 recent_discharge를 특별 취급할 필요는
없습니다. 데이터 확보 시도는 **P2(향후 확장)**로 남겨둡니다.

---

## 10. 데이터 소스 계획 (조사만, 실제 수집 없음)

공식성 우선순위(지침 순서)와 `data_source_plan.md`(기존 문서, 무수정) 매핑:

| 순위 | 소스 유형 | P0 지역·유형에 대한 적용 |
|---|---|---|
| 1. 공공데이터포털 API | 한국사회보장정보원 중앙부처/지자체복지서비스 API(이미 사용 중) | **1차로 재확인**: 최신 날짜로 재수집해 신규 등록 사업 유무 확인(§13 Step 1). API/인증키/엔드포인트는 기존 `.env`/`data_source_plan.md` A장 그대로, 새 소스 아님 |
| 2. 복지로/중앙·지자체 API 상세조회 | 위와 동일 API의 상세조회 | "노인복지관 운영"(화성시) 등 애매 후보의 원문 확인용 |
| 3. 시·도/시·군·구 공식 홈페이지 | 화성시청, 천안시청, 세종시청, 울산광역시청 복지 관련 게시판 | §5.2에서 API 자체에 후보가 없음을 확인했으므로 **P0 지역은 사실상 이 단계가 핵심**(data_source_plan.md C장이 이미 "전국 통합 소스 없음, MANUAL"로 명시) |
| 4. 보건소 공식 홈페이지 | 방문건강관리사업(`home_visit` 후보) | data_source_plan.md C장에 이미 "MANUAL, 보건소별 개별 조사 필요"로 명시됨(재확인, 신규 아님) |
| 5. 공식 사업 안내 PDF | 노인맞춤돌봄서비스 사업안내, 퇴원지원 시범사업 지침(둘 다 data_source_plan.md B장에 기존 확인됨) | community_care/discharge_support 정의 보강용, 신규 사례 발굴보다는 기준 문서 |
| 6. 기타 공식 페이지 | 정부24(gov.kr) 민원안내 | 복지로 상세페이지가 JS 렌더링이라 자동 확보가 안 될 때의 대체 원문(B장, 기존 확인) |

**언론기사/블로그/민간 요약사이트는 이번 계획에서도 최종 근거로 사용하지 않습니다**
(`data_source_plan.md` D장 원칙 유지).

**실제로 존재하지 않는 기관/데이터셋명을 만들지 않았습니다** — 위 표는 전부
`docs/data_source_plan.md`에 이미 존재를 확인해 둔 항목의 재인용입니다.

---

## 11. 데이터 보강 이후 기대효과 (정성적)

| 항목 | 기대 개선 정도 | 근거 |
|---|---|---|
| 화성시 Top-K 후보 수 | **LOW~MEDIUM** | §5.2에서 기존 데이터 풀에 후보가 거의 없음을 확인 — MANUAL 확보가 성공해야 개선, 성공해도 지역 특성상 대량 확보는 어려울 가능성 |
| 천안시 Top-K 후보 수 | **LOW~MEDIUM** | 동일 이유 |
| 세종/울산 지역 사용 가능성 | **LOW(세종)/MEDIUM(울산)** | 세종은 API 원문 자체 부재로 가장 불확실. 울산은 등록 사업 자체는 있어(102건) MANUAL 확인 시 발견 가능성이 세종보다 높음 |
| disability 입력 민감도 | **MEDIUM~HIGH** | 이미 있는 곳에서 강한 효과가 실증되었으므로(§7/§2), 지역이 늘어나는 만큼 효과가 나타나는 지역도 비례해 늘어날 것으로 기대 |
| desired_support 입력 민감도 | **MEDIUM** | 이미 전반적으로 정상 작동 중(로직 문제 아님) — community_care 보강은 "효과가 보이는 지역의 수"를 늘리는 것이지 "로직 자체의 민감도"를 바꾸는 것은 아님 |
| community_care 추천 다양성 | **MEDIUM~HIGH** | Top-K 부족 원인의 21.4%를 직접 겨냥한 보강이라 가장 직접적인 개선 예상 |
| 전국 서비스(NATIONAL) 반복 상위 노출 감소 | **MEDIUM** | 지역/유형 후보가 늘어날수록 `open_count`/`score`가 더 높은 지역 서비스가 NATIONAL을 자연스럽게 밀어낼 기회가 늘어남(로직 변경 없이) |

수치 예측은 하지 않았습니다(지침 준수) — 데이터가 실제로 얼마나 발견될지는 §13 실행 후에만
알 수 있습니다.

---

## 12. 최종 데이터 보강 Plan

### P0 — 반드시 먼저

| # | 지역/유형 | 목표 추가 건수 | 우선 데이터 소스 | 수집 방법 | 검증 방법 | 해결하는 문제 |
|---|---|---:|---|---|---|---|
| 1 | 지자체복지서비스 API **재수집**(전국, 날짜 갱신 확인용) | 0건(수집 자체가 목표, §13 Step1) | 기존 API(재사용) | AUTO(기존 스크립트 재실행) | `*_collection_log.json`의 `total_count_reported` 변화 확인 | 신규 등록 사업 반영 여부 확인 |
| 2 | 화성시 | +2~3 | 화성시청 홈페이지(MANUAL) + "노인복지관 운영"(WLF00005011) 상세조회 | SEMI_AUTO(상세조회 1건) + MANUAL(시청 홈페이지) | 원문 대조, verification_level A/B 판정 | REGION_DATA_COVERAGE |
| 3 | 천안시 | +2 | 천안시청 홈페이지(MANUAL) | MANUAL | 원문 대조 | REGION_DATA_COVERAGE |
| 4 | 세종특별자치시 | +1~2 | 세종시청 홈페이지(MANUAL, API 원문 부재 확인됨) | MANUAL | 원문 대조 | REGION_DATA_COVERAGE(가장 불확실) |
| 5 | 울산광역시 | +2 | 지자체복지서비스 API 재수집분 우선 확인 후 울산시청 홈페이지 | SEMI_AUTO→MANUAL | 원문 대조 | REGION_DATA_COVERAGE |
| 6 | community_care 전국 확대 | +8 | 기존 API(재수집분) + `unknown_needs_final_review.csv`/117건 미검토 풀 재확인 | SEMI_AUTO | 원문 대조, service_type 재분류 | SUPPORT_TYPE_COVERAGE(21.4%) |

### P1 — 그다음

| # | 항목 | 목표 | 소스 | 방법 | 검증 | 해결하는 문제 |
|---|---|---:|---|---|---|---|
| 1 | disability meal support 확대 | +5 | 기존 API 재수집분 + `manual_review_queue.csv`의 장애 관련 재검토 여지 확인 | SEMI_AUTO | 원문 대조 | disability 정보가치 지역 확대 |
| 2 | home_visit 지역 확대 | +3 | 기존 API 재수집분 | SEMI_AUTO | 원문 대조 | home_visit 지역성 확보 |

### P2 — 향후 확장

| # | 항목 | 목표 | 소스 | 방법 | 검증 | 해결하는 문제 |
|---|---|---:|---|---|---|---|
| 1 | food_cost_support 다양성 | +3 | 기존 API 재수집분 | SEMI_AUTO | 원문 대조 | 옵션 다양성 |
| 2 | single_household 구조화 확대 | 신규 수집 아님, 기존 85건+신규 확보분 원문 재검토 | 기존 원문 | SEMI_AUTO(재검토) | 원문 대조 | single_household 정보가치 |
| 3 | recent_discharge 관련 | 목표 미설정(§9 참고, 적극 수집 보류) | HIRA PDF(data_source_plan.md B장) | PDF/SEMI_AUTO | 원문 대조 | 낮은 우선순위로 유지 |
| 4 | nutrition_counseling/education | 목표 미설정(§4 참고, 357건 전체에서 사실상 0건 확인됨) | — | — | — | 무리한 목표 지양 |

---

## 13. 다음 실제 수집 단계 준비 (현재 코드 구조 기준)

```
Step 1  기존 API 재검색
        collect_central_welfare_full.py / collect_local_welfare_full.py 재실행
        (엔드포인트/인증 방식 무수정, 재실행만) → data/raw/*.xml 갱신,
        *_collection_log.json으로 이전 대비 totalCount 변화 확인

Step 2  P0 지역 keyword query 확대
        extract_candidates_stage1.py의 KEYWORDS 리스트에 "노인복지관" 추가한
        별도 실행(기존 파일 덮어쓰지 않고 새 산출물로 — 아래 §14 참고)

Step 3  후보 신규 데이터 별도 CSV 저장
        기존 candidates_stage1_raw.csv 패턴을 따르되 별도 파일명 사용(§14)

Step 4  원문 기반 수동/반자동 검증
        collect_candidate_details.py 패턴 재사용(상세조회) +
        candidate_review_summary.md/unknown_review_batch*.md와 동일한 방식의
        사람 판독 기록

Step 5  기존 85개와 merge 전 duplicate 검사
        service_id 기준 교집합 확인(기존 loader.py의 "Duplicate service_id"
        방어 로직과 동일한 원칙을 병합 스크립트에도 적용)

Step 6  classification v2 적용
        apply_classification_v2.py / classification_criteria.md 기준 재사용
        (새 기준 만들지 않음)

Step 7  추천엔진 회귀 테스트
        기존 226 passed 유지 확인 + 신규 서비스가 실제로 새 시나리오에서
        나타나는지 tests/test_v1_2_scenarios.py 패턴으로 추가 검증

Step 8  RAG corpus rebuild
        python -m rag.build_index 재실행(기존 스크립트 그대로)

Step 9  coverage 재평가
        mvp_coverage_validation.md와 동일한 방법론으로 재측정,
        Before/After 비교
```

**이번 단계에서는 Step 1~9 중 어느 것도 실행하지 않았습니다.**

---

## 14. 데이터 보존 원칙 (Provenance)

기존 `welfare_services_recommendation_ready.csv`를 직접 덮어쓰지 않는 구조를 권장합니다.
이미 이 프로젝트의 기존 파이프라인(`candidates_stage1_raw.csv` →
`welfare_candidates_reviewed.csv` → `unknown_review_batch_0N.csv` →
`unknown_needs_final_review.csv` → 최종 CSV)이 **바로 이 원칙을 따르고 있음을 확인**했습니다
— 새로 발명할 필요 없이 같은 패턴을 한 번 더 반복하면 됩니다.

```
data/processed/
    welfare_services_recommendation_ready.csv        # 기존 85건 (v1.2), 이번 보강 동안 무수정
    enrichment_candidates_v1.csv                       # 신규 후보 원본(키워드 매치 직후, Step 3)
    enrichment_candidates_v1_reviewed.csv              # 사람이 원문 대조 완료(Step 4)
    enrichment_needs_final_review.csv                  # 판단 보류분(기존 unknown_needs_final_review.csv와 동일 역할)
    welfare_services_recommendation_ready_v1_3.csv     # 최종 merge 결과물 (Step 5~6 이후, 새 버전 파일)
```

`welfare_services_recommendation_ready_v1_3.csv`가 검증까지 끝난 뒤에야
`recommender/loader.py`의 `DEFAULT_CSV_PATH`를 이 새 파일로 바꾸는 것을 제안합니다(이번
단계에서는 경로도 변경하지 않았습니다) — 이렇게 하면 병합 도중 문제가 생겨도 기존 85건 기반
서비스가 계속 정상 동작합니다.

---

## 15. 예상 효과

§11에 정성적으로 정리했습니다. 요약: disability/community_care 정보가치는 MEDIUM~HIGH로 개선될
가능성이 높고, 화성시/천안시/세종은 API만으로는 한계가 뚜렷해(§5.2) MANUAL 지자체 홈페이지
확인이 성공해야 실질적 개선(LOW~MEDIUM)이 가능합니다. **로직은 이미 건강하다는
`recommendation_engine_v1_2_validation.md`/`mvp_coverage_validation.md`의 결론을 이번 조사도
재확인**했으므로, 이번 계획을 실행해도 추천엔진 코드는 그대로 두는 것이 맞습니다.

---

## 완료 체크리스트

- [x] 실제 데이터 구조 확인(코드/CSV 무수정)
- [x] 지역 gap 정량 확인(6개 지역)
- [x] 목표량 근거 기반 제안(25~30건)
- [x] 서비스 유형별 P0/P1/P2/NOT_NEEDED_NOW 분류
- [x] 기존 API 재활용 가능성 실제 원문 대조로 확인(재호출 없이)
- [x] keyword 시험 매치로 개선안 도출(재추출 없이)
- [x] disability A/B 원인 구분
- [x] community_care 전략
- [x] recent_discharge Option 판단
- [x] 데이터 소스 계획(기존 문서 재인용, 신규 발명 없음)
- [x] 수집 순서(Step 1~9) 현재 코드 구조 기준 제안
- [x] provenance 보존 원칙 제안
- [x] 실제 API 호출/크롤링/PDF 다운로드/merge/CSV 수정/추천엔진 수정/RAG rebuild/Streamlit
      수정 **전혀 하지 않음**
- [x] 기존 baseline(226 passed, 4 skipped) 무변경 확인
