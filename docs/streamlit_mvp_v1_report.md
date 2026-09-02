# Streamlit MVP v1 보고서

> 규칙 기반 추천엔진 v1(`src/recommender`)을 실제 화면에서 사용할 수 있는지 검증하기 위한
> 최소 기능 Streamlit 프로토타입입니다. RAG/LangChain/Vector DB/Claude API/n8n/배포는
> 포함하지 않았습니다.

---

## 0. 구현 전 확인 사항

- `src/recommender/` (models/loader/matcher/filters/scorer/recommender)는 **전혀 수정하지
  않았습니다.** 이번 단계에서 추가/변경한 것은 `RecommendationResult`에 원문 참조용
  `target_original`/`criteria_original` 두 필드를 추가한 것뿐이며, 이는 rules_spec.md §11이
  이미 "필요한 경우 원문 참조 필드도 유지"라고 명시한 INFORMATION_ONLY 필드를 채운 것이지
  매칭/점수 로직 변경이 아닙니다(`recommender.py`의 `evaluate_service()`가 이 두 값을 그대로
  전달하도록 두 줄만 추가했습니다). 기존 53개 테스트는 변경 없이 그대로 통과합니다.
- `data/processed/welfare_services_recommendation_ready.csv`, `docs/recommendation_rules_spec.md`,
  `docs/recommendation_engine_v1_report.md`를 다시 확인했습니다.
- 지역 목록은 `data/processed/region_codes.csv`(16개 시/도, 273개 시/군/구, 전국 실제 행정구역
  코드)를 그대로 사용했습니다. **하드코딩된 지역명은 없습니다.** `data/processed/
  region_aliases.csv`도 함께 존재하지만 이번 UI는 정식 명칭만 선택지로 쓰므로 별칭 변환은
  사용하지 않았습니다(향후 자유 텍스트 입력을 받을 경우에 대비한 참고 자료로만 남겨둠).
- `streamlit`이 실행 환경에 설치되어 있지 않아 설치했습니다(`requirements.txt`에는 이미
  "예정 기술 스택"으로 포함되어 있었음). `pytest`도 이전 단계에서 설치했습니다.

---

## 1. 앱 구조

```
app/
    streamlit_app.py     # Streamlit 진입점 (화면만 담당, 로직 없음)

src/
    recommender/          # 기존 추천엔진 -- 이번 단계에서 미변경(단, §0 참고)
    streamlit_ui/
        __init__.py
        adapter.py         # UI 문자열 <-> recommender 타입 변환 전용, 매칭/점수 로직 없음

tests/
    test_streamlit_adapter.py   # adapter 전용 단위 테스트 (25개)
    (기존 5개 테스트 파일은 무변경)
```

**실행 방법**: `streamlit run app/streamlit_app.py` (프로젝트 루트에서 실행, §20 참고)

`app/streamlit_app.py`는 화면 렌더링과 세션 상태 관리만 담당하고, `src/streamlit_ui/adapter.py`는
"UI 라벨 ↔ recommender 타입" 순수 변환 함수만 담당합니다. 두 파일 모두 매칭/필터/점수 계산을
전혀 재구현하지 않으며, 오직 `recommender.recommend()`를 그대로 호출하고 그 결과를 표시만 합니다.

---

## 2. 입력항목

`docs/recommendation_rules_spec.md` §2 `UserProfile` 스키마를 그대로 따릅니다.

| 화면 항목 | 위젯 | 대응 UserProfile 필드 |
|---|---|---|
| 누가 입력하고 있나요? (본인/보호자) | radio | `respondent_type` (매칭에는 미사용, 향후 문구 톤 조정용) |
| 거주 시/도 | selectbox (region_codes.csv 기반) | `sido` |
| 거주 시/군/구 | selectbox (선택한 시/도에 종속) | `sigungu` |
| 연령 | 텍스트 입력, 비워두면 모름 | `age` |
| 장애/저소득/독거/거동불편/식사준비어려움 | radio (예/아니오/잘 모르겠어요) | 각 tri-state 필드 |
| 최근 퇴원 여부 | radio (예/아니오/잘 모르겠어요) | `recent_discharge` |
| 원하는 도움 | multiselect | `desired_support` |

**전국(NATIONAL) 서비스는 사용자가 선택하는 항목이 아닙니다.** region_scope=NATIONAL 처리는
전적으로 엔진 내부(`recommender.matcher.evaluate_region`)에서 이뤄지며, UI는 시/도·시/군/구
선택지만 제공합니다(지시사항 §5 그대로 반영).

---

## 3. 추천엔진 연결 방식

```python
profile = adapter.build_user_profile(...)          # UI 라벨 -> UserProfile
results = recommend(profile, services=services, top_k=5)  # 기존 엔진 그대로 호출
```

- `adapter.build_user_profile()`은 라벨 문자열을 `TriState`/`DesiredSupport`/`UserProfile`로
  변환만 하고 어떤 판정도 내리지 않습니다.
- `recommend()` 호출 결과(`List[RecommendationResult]`)는 **재정렬하거나 값을 바꾸지 않고
  그대로** 화면에 전달합니다. Streamlit 코드에는 `if`/`sort`/점수 계산 등 추천 로직에
  해당하는 코드가 전혀 없습니다.
- 결과는 `st.session_state`에 저장해, 카드의 expander를 열고 닫는 등 다른 위젯 조작으로
  화면이 다시 그려져도 추천을 다시 계산하지 않고 마지막 결과를 유지합니다.

---

## 4. 결과 표시 방식

각 결과는 카드(`st.container(border=True)`)로 표시하며, 최소 다음을 포함합니다.

- 서비스명, 지역(전국/시도/시군구), 서비스 유형(한국어 라벨)
- 추천 등급(한국어 표현, §9 참고) — 카드 상단에 항상 표시
- **✅ 왜 추천되었나요?** — `recommendation_reasons` 그대로 나열
- **❓ 추가 확인이 필요한 조건** — `confirmation_needed` 그대로 나열, "오류가 아니라 확인이
  더 필요하다는 뜻"이라는 안내 문구 동반
- `expander("자세히 보기")` 안에:
  - `match_score` 숫자 (지시사항 §8에 따라 기본 화면에는 노출하지 않고 expander 안에서만,
    "참고용 점수이며 절대적 자격 점수가 아님"이라는 문구와 함께 표시)
  - `verification_level`, `nutritionist_involvement` (친화적 문구로 변환, adapter.py)
  - `exclusion_warnings`(참고 사항), `unknown_conditions`(아직 확인되지 않은 조건)
  - 원문 참조: `eligibility_summary`, `target_original`, `criteria_original`,
    `support_summary`, `application_method`, `contact` — **LLM 요약/재작성 없이 원문 그대로**

---

## 5. UNKNOWN 안내

`confirmation_needed`/`unknown_conditions`는 오류 색상(빨강)이 아니라 안내 톤으로 표시하고,
"확인이 어려워요"/"확인이 필요해요"라는 완곡 문구를 그대로 사용합니다(엔진이 이미 이런
문구로 이유를 생성하므로 Streamlit에서 새로 작성하지 않았습니다). 카드 안에는 고정 캡션으로
"아래 조건은 원문만으로는 확인이 어려워요. 오류가 아니라 '확인이 더 필요하다'는 뜻입니다."를
추가해 오해를 방지했습니다.

---

## 6. 데이터 부족 안내

`adapter.scarce_support_warning()`이 사용자가 고른 `desired_support`가 **전부**
`nutrition_counseling`/`discharge_support`(rules_spec.md §0/§8에서 확인된, 매칭 대상이 각각
1건/1건뿐인 유형)일 때만 경고를 띄웁니다. 경고 문구에는 **실제 데이터 기준 건수**를 동적으로
계산해 넣습니다(하드코딩 아님) — 예: "영양상담(현재 데이터 1건)". 사용자가 이 유형과 함께
`meal_support` 등 데이터가 충분한 유형도 같이 선택했다면 경고를 띄우지 않습니다(다른 유형으로
결과가 충분히 나올 수 있으므로). 결과가 0건이어도 **다른 서비스 유형을 억지로 추천하지
않습니다** — 화면에는 "조건에 맞는 공공서비스를 찾지 못했어요" 안내만 표시됩니다.

---

## 7. 테스트 결과

```
80 passed in 0.24s   (pytest 9.1.1)
```

- 기존 recommender 테스트 53개: **전부 그대로 통과** (무변경 확인)
- 신규 `test_streamlit_adapter.py`: **25개 전부 통과** — tri-state 변환, desired_support
  매핑, UserProfile 조립, `region_codes.csv` 실제 로딩(정상/누락/형식오류 3가지 케이스),
  데이터부족 경고 조건, 정보부족 안내 조건, 등급/검증등급/영양사 라벨이 확정적 표현을
  포함하지 않는지 검증

### 수동 검증 시나리오 (§18) — 코드 수준 실행 결과

Streamlit 위젯을 실제 브라우저로 클릭하는 대신, 화면이 호출하는 것과 동일한
`adapter.build_user_profile()` + `recommend()` 조합을 코드로 그대로 실행해 검증했습니다
(브라우저 조작 자동화 도구 없이도 앱의 실제 판단 경로를 그대로 재현합니다).

| 시나리오 | 안내 메시지 | 결과 |
|---|---|---|
| A. 75세/독거/저소득/거동불편/식사준비어려움(강원) | 없음(정보 충분) | 5건, 전부 강원 지역 식사배달 서비스, `NEEDS_CONFIRMATION`(장애·퇴원 정보가 없어 강등) |
| B. 68세/장애 있음/식사지원 필요(서울 성동구) | 없음 | 4건, 장애인 대상 급식 서비스가 1~2위(`POSSIBLE_MATCH`/`HIGH_MATCH`) |
| C. 대부분 잘 모르겠음(지역도 미선택) | "입력하신 정보가 적어... 전국 단위 서비스가 상위에 표시될 수 있어요" 표시됨 | 5건, 전부 `NEEDS_CONFIRMATION`, 1위가 전국 서비스(§13에서 이미 분석된 tie-break 현상 재확인) |
| D. 특정 시군구 선택(강원 속초시) | 없음 | 4건, 속초시 지역 서비스가 `HIGH_MATCH`로 상위 |
| E. 영양상담만 선택 | "선택하신 도움 유형(영양상담(현재 데이터 1건))에 해당하는... 충분하지 않아요" 표시됨 | 5건이 나오긴 하지만 전부 영양상담 자체와 무관한 약한 매칭(지역/검증등급 위주 점수) — 억지로 "영양상담에 딱 맞다"고 표시하지 않고 데이터 부족 경고와 함께 노출됨 |

앱이 죽거나 예외를 던진 경우는 없었습니다.

---

## 8. 알려진 한계

1. **`recommendation_engine_v1_report.md`의 NATIONAL tie-break 현상이 UI에도 그대로 나타남**
   (시나리오 C에서 재확인). 이번 단계 지시에 따라 **엔진의 랭킹 코드는 수정하지 않았고**,
   대신 `adapter.sparse_input_notice()`로 "정보가 적으면 전국 서비스가 상위에 나올 수 있다"는
   안내만 추가했습니다. 근본적인 tie-break 개선은 여전히 v2 과제로 남아 있습니다
   (`recommendation_engine_v1_report.md` §11).
2. **match_score를 완전히 숨기지 않고 expander 안에 남겨두었습니다.** 완전히 제거하는 대신
   "참고용이며 절대적 자격 점수가 아님"이라는 문구를 붙이는 절충안을 택했습니다 — 개발/검증
   단계에서는 점수가 보이는 것이 디버깅에 유용하기 때문입니다. 정식 배포 전에는 완전히
   숨기거나 등급으로만 표시하는 방안을 재검토해야 합니다.
3. **지역 자동완성/오타 교정 없음**: `region_aliases.csv`(예: "광주" → "전남광주통합특별시")를
   이번 UI에서는 사용하지 않았습니다(선택지 UI라 오타 문제가 없기 때문). 향후 자유 텍스트
   주소 입력을 지원한다면 이 파일을 활용해야 합니다.
4. **다중 세션/동시 사용자 테스트 없음**: `st.cache_resource`로 데이터를 세션 간 공유하도록
   했지만, 실제 다중 사용자 동시 접속 환경에서의 동작은 검증하지 않았습니다(MVP 범위 밖).
5. **브라우저 수동 클릭 테스트는 수행하지 않았습니다.** 대신 (a) 헤드리스로 서버를 띄워
   HTTP 200 응답 및 시작 로그에 예외가 없음을 확인했고, (b) 화면이 호출하는 것과 동일한
   함수 조합을 코드로 실행해 §18의 5개 시나리오를 검증했습니다. 위젯 클릭에 따른 리렌더링
   자체는 사용자가 직접 브라우저에서 확인해야 합니다(§20 실행 방법 참고).

---

## 9. RAG 추가 전 수정 필요사항

**치명적으로 막는 문제는 없습니다.** 다만 RAG를 붙이기 전에 다음을 검토하면 좋습니다.

- RAG가 원문 검색 결과를 어디에 노출할지 정할 때, 이번 단계에서 이미 노출 중인
  `target_original`/`criteria_original`/`support_summary`/`eligibility_summary`
  expander 영역과 역할이 겹치지 않도록 UI 배치를 조정해야 합니다.
- `recommend()`가 반환하는 `RecommendationResult`는 이미 RAG/LLM이 참고할 수 있는 모든
  구조화 정보(matched/unknown/confirmation_needed 등)를 담고 있으므로, RAG 계층은 이 값을
  **입력으로만** 받고 절대 덮어쓰지 않아야 합니다(설계 문서 §10 경계 그대로 유지).
- §8의 한계 1(NATIONAL tie-break)은 RAG와 무관하지만, 사용자 체감 품질에 영향을 주므로
  RAG 도입 전에 한 번은 별도로 다뤄볼 가치가 있습니다(선택 사항, 차단 요소는 아님).

---
