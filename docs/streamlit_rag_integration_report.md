# Streamlit RAG 통합 v1 보고서

> 이 단계의 목표는 **"검증된 추천엔진 + RAG Retrieval + Grounded Generation을 기존
> Streamlit MVP에 안전하게 연결하여 실제 end-to-end 사용자 경험을 완성하는 것"**입니다.
> 새로운 추천/RAG 알고리즘 개발, 추가 PDF 수집, 배포, 대규모 디자인 변경은 하지 않았습니다.

---

## 1. 통합 Architecture

```
app/streamlit_app.py            -- 화면만 담당 (기존과 동일한 역할 원칙)
    ↓ 호출
src/recommender/                -- 무수정
src/rag/ (retriever/generator)  -- 무수정
src/streamlit_ui/
    adapter.py                  -- 기존, 무수정 (추천 UI 변환)
    rag_adapter.py               -- 신규, RAG UI 변환 (이번 단계)
```

`src/rag/generator.py`, `src/rag/retriever.py`, `src/rag/vectorstore.py`, `src/rag/
generation_models.py`, `src/rag/guardrails.py`, `src/rag/prompt_builder.py`, `src/recommender/*`
는 **이번 단계에서 한 줄도 수정하지 않았습니다.** `src/streamlit_ui/rag_adapter.py` 하나만
새로 추가했으며, 기존 `streamlit_ui/adapter.py`와 동일하게 **`streamlit`을 import하지 않는
순수 함수 모듈**입니다 -- `app/streamlit_app.py`만 `st.*`를 호출합니다.

---

## 2. UI 흐름

각 추천 카드(`st.container(border=True)`) 안에 기존 "자세히 보기(세부 정보 및 원문)"
expander 아래에 `st.divider()`로 구분한 뒤 **"🤖 AI로 자세히 알아보기"** 영역을 추가했습니다.

```
1. 저소득 재가노인 식사배달
관련성이 높은 서비스
✅ 왜 추천되었나요?
❓ 추가 확인이 필요한 조건
▸ 자세히 보기 (세부 정보 및 원문)      -- 기존 그대로, 무수정

────────────────────────
🤖 AI로 자세히 알아보기
[이 서비스는 어떤 서비스인가요?] [어떤 지원을 받을 수 있나요?]
[제가 대상일 가능성이 있나요?]   [어떻게 신청하나요?]
직접 질문하기: [________________________]  [근거 기반 답변 보기]

(버튼을 누르면)
질문: 어떤 지원을 받을 수 있나요?
**서비스 요약** / **왜 추천되었나요?** / **지원 내용** / ...
추가 확인이 필요한 부분
(고정 안전 문구)
▸ 📄 답변 근거 보기 (공식 원문)
```

기존 기능(본인/보호자, 시/도, 시/군/구, 연령, 장애/저소득/독거/거동불편/식사준비어려움/
최근퇴원, 원하는 도움, 추천 실행, Top-K 결과, match level, 추천 이유, 확인 필요 조건, 공식
원문 expander)은 **제거하거나 재설계하지 않았습니다.**

---

## 3. Recommendation → Retrieval → Generation 흐름

```python
# app/streamlit_app.py (신규 추가 부분만 발췌)
retrieved = retrieve_for_service(rag_store, rag_embedder, r.service_id, question, top_k=3)
request = rag_adapter.build_generation_request(r, profile, question, retrieved)
answer = generate_answer(generation_client.client, request)
```

이 흐름은 `rag_adapter.run_generation()`/`safe_run_generation()` 하나로 캡슐화되어 있습니다.
UI 코드는 `request` 조립 → generation interface 호출 → `GroundedAnswer` 표시, 이 세 단계만
담당하며 **Claude prompt를 UI 내부에서 새로 만들지 않습니다** — `SYSTEM_PROMPT`/
`build_user_prompt()`는 기존 `src/rag/prompt_builder.py`를 그대로 사용합니다.

**on-demand 원칙**: `recommend()`는 검색 버튼(`🔍 내게 맞는 서비스 찾아보기`)을 눌렀을 때만
실행되고, Generation은 사용자가 카드 안의 preset 질문 버튼 또는 "근거 기반 답변 보기"를
눌렀을 때만 실행됩니다. 추천 결과가 몇 건이든 자동으로 모든 서비스에 대해 Claude를 호출하지
않습니다 -- `test_A_search_alone_does_not_trigger_generation`으로 검증했습니다(검색만 했을 때
어떤 `rag_answer::*` 세션 키도 생성되지 않음을 확인).

---

## 4. service_id Boundary

`rag_retrieval_v1_report.md` §8의 "cross-service contamination = 0" 보장이 Streamlit
레이어에서도 깨지지 않도록 다음을 구조적으로 강제했습니다.

- 모든 preset/자유질문 버튼과 텍스트 입력 위젯의 Streamlit `key=`가
  `f"preset_{service_id}_{idx}"` / `f"rag_free_text::{service_id}"` 형태로 **service_id를
  포함**합니다 -- 위젯 자체가 서비스별로 분리되어 있어 다른 카드의 버튼을 눌러도 다른
  service_id로 갈 방법이 없습니다.
- `_render_ai_explanation_section(r, profile)`는 `RecommendationResult` 하나(`r`)만 받고,
  내부에서 `retrieve_for_service(store, embedder, r.service_id, question)`을 호출합니다 --
  "현재 선택된 서비스"라는 전역 상태가 없고, 항상 그 카드의 `r.service_id`를 명시적으로
  전달합니다.
- `test_BCD_each_service_question_stays_scoped_to_its_own_card`, `test_safe_run_generation
  _service_boundary_two_services_stay_separate`가 실제 두 개의 서로 다른 서비스에 대해
  질문을 실행하고 각 답변의 `evidence`가 오직 해당 service_id에만 속함을 검증합니다.

---

## 5. Cache 전략

| 리소스 | 캐시 방식 | 효과 |
|---|---|---|
| `load_services()` (85건 CSV) | 기존 `@st.cache_resource` (무수정) | 기존과 동일 |
| `region_codes.csv` | 기존 `@st.cache_resource` (무수정) | 기존과 동일 |
| **`VectorStore` + `Embedder`** | **신규** `@st.cache_resource` (`_load_rag_resources_cached`, `rag_adapter.load_rag_resources`를 감쌈) | 프로세스당 1회만 embedding model 로드 + FAISS index 로드/빌드 |

`rag_adapter.load_rag_resources()` 자체는 `data/vectorstore/`에 이미 빌드된 인덱스가 있으면
`VectorStore.load()`(실측 0.04초, `rag_retrieval_v1_report.md` §18)로 빠르게 불러오고, 없으면
그 자리에서 `build_documents()` + `Embedder.embed_documents()` + `VectorStore.build()`로
한 번 빌드한 뒤 best-effort로 디스크에 저장합니다(저장 실패해도 이번 실행에서는 메모리 상의
인스턴스를 계속 사용). `st.cache_resource`가 이 함수 전체를 감싸므로, **이후의 모든 rerun/버튼
클릭에서는 이 함수가 다시 호출되지 않습니다.**

**실측으로 캐시가 왜 필요한지 확인**: `load_rag_resources()`를 캐시 없이 같은 프로세스에서
두 번 호출했을 때 각각 24.09초, 9.60초가 걸렸습니다(§13). `st.cache_resource` 없이 배포했다면
**질문 버튼을 누를 때마다 최대 10~24초의 지연이 반복**되었을 것입니다.

---

## 6. Session State 전략

| 키 | 형태 | 용도 |
|---|---|---|
| `results` / `profile` / `search_error` | 기존, 무수정 | 추천 결과 유지 |
| `rag_answer::{service_id}` | 신규 | 그 서비스 카드의 마지막 `GroundedAnswer` |
| `rag_pending_question::{service_id}` | 신규 | 실행된 질문 텍스트(표시용) |
| `rag_error::{service_id}` | 신규 | 그 서비스의 마지막 오류 안내 메시지 |
| `rag_free_text::{service_id}` | 신규 (위젯 자체 키) | 자유 질문 입력값 |

모든 신규 키가 `service_id`를 포함하므로, 서비스 1의 질문에 답한 뒤 서비스 2의 버튼을 눌러도
서비스 1의 `st.session_state["rag_answer::WLF...1"]`은 그대로 남아 있고 서비스 2의 카드에는
서비스 2 전용 키(`rag_answer::WLF...2`)로 별도 저장됩니다 -- 카드가 다시 그려질 때마다 각자
자기 키만 읽으므로 answer가 뒤섞일 수 없습니다. `test_BCD_...`, `test_K_...`로 실제 rerun을
시뮬레이션해 검증했습니다.

---

## 7. API Key 처리

- 하드코딩된 API Key 없음 (`grep -rn "sk-ant" src/ app/` 결과 0건).
- `rag_adapter.api_key_configured()`(기존 `rag.generator` 함수 재사용)가 `ANTHROPIC_API_KEY`
  존재 여부만 확인 -- 값 자체를 화면에 출력하는 코드는 어디에도 없습니다.
- 3가지 모드(`resolve_generation_client`, 지침 §9):
  - `RAG_GENERATION_MODE=fake` -- 항상 `FakeGenerationClient`, 카드에
    **"🧪 테스트 모드 응답이에요 (실제 Claude 답변이 아니에요)"** 캡션이 항상 함께 표시됩니다.
    Fake 답변이 실제 답변으로 오인될 수 없도록 시각적으로 구분했습니다.
  - `RAG_GENERATION_MODE=claude` -- 항상 실제 Claude, 키 없으면 `unavailable`.
  - 기본값(`auto`, 환경변수 미설정) -- 키가 있으면 Claude, 없으면 `unavailable`. **Fake로
    조용히 대체되지 않습니다** -- 실수로 프로덕션에서 Fake 답변이 나갈 위험을 구조적으로
    차단했습니다.
- 키가 없을 때: 앱 전체가 아니라 **AI 설명 영역만** "AI 기반 설명 기능이 현재 설정되지
  않았습니다. 기존 추천 결과와 공식 원문은 계속 확인할 수 있습니다."를 표시하고, 추천 카드의
  나머지 부분(추천 이유/확인 필요 조건/원문 expander)은 정상 동작합니다(`test_G_...`).

---

## 8. Error Fallback

| 상황 | 처리 |
|---|---|
| RAG 리소스(Embedder/VectorStore) 로드 자체 실패 | `try/except`로 감싸고 `rag_available=False`로 표시, **추천엔진은 계속 정상 동작**(§8의 CSV 로드 실패와 구조적으로 동일한 방어 패턴) |
| Generation 호출 중 예외(네트워크/인증/기타) | `rag_adapter.safe_run_generation()`이 모든 예외를 잡아 stderr에만 전체 traceback을 남기고, 화면에는 고정 문구 "AI 설명을 불러오지 못했습니다. 추천 결과와 공식 원문은 계속 확인할 수 있습니다."만 표시 (`test_H_...`로 예외 메시지/키 문자열이 화면에 노출되지 않음을 실제로 검증) |
| Claude 호출 중 로딩 | `st.spinner("공식 서비스 정보를 바탕으로 확인하고 있어요...")` |

기존 `recommend()` 실패 처리(§16, 무수정)와 동일한 스타일(고정 안내 문구 + 서버 로그에만
상세 기록)을 그대로 재사용했습니다.

---

## 9. Evidence 표시

`rag_adapter.evidence_grouped_by_section()`이 `GroundedAnswer.evidence`를 `target → criteria →
support → application` 고정 순서로 묶어 반환하고, `app/streamlit_app.py`는 이를 **"📄 답변
근거 보기 (공식 원문)"** expander 안에 `[지원대상]`/`[선정기준]`/`[지원내용]`/`[신청방법]`
라벨과 함께 표시합니다. Expander 진입 직후 캡션으로 **"아래는 AI가 쓴 문장이 아니라 공식
원문 그대로예요. 위 AI 설명과 구분해서 참고해주세요."**를 고정으로 넣어, LLM 생성 문장과
공식 원문을 시각적으로 명확히 분리했습니다(지침 §14 요구사항).

---

## 10. UNKNOWN 처리

- `rag_adapter.format_profile_summary()`가 `TriState.UNKNOWN`을 항상 `"확인 필요(모름)"`로
  렌더링합니다 -- `"아니오"`/`False`로 표시되는 경로가 코드에 없습니다
  (`test_format_profile_summary_never_renders_unknown_as_no`로 검증).
- `GroundedGenerationRequest.confirmation_needed`는 recommender가 이미 산출한 문자열을 그대로
  전달하며, Generation Layer(무수정)가 UNKNOWN을 임의로 확정하지 않는다는 원칙은
  `rag_generation_v1_report.md` §10에서 이미 검증된 그대로 유지됩니다.
- UI는 `answer.confirmation_items`를 "추가 확인이 필요한 부분"으로 그대로 나열합니다 --
  새로운 문구를 만들지 않습니다.

---

## 11. 실제 화성 사례

`tests/test_streamlit_app_ui.py::test_hwaseong_case_recommendation_unchanged_by_rag_pipeline`
이 AppTest로 다음을 실제 위젯 조작으로 재현합니다.

1. 경기도 화성시 동탄구 / 75세 / 저소득=예 / 독거=예 / 거동불편=예 / 식사준비어려움=예 /
   최근퇴원=아니오 / 식사·도시락·반찬 지원 희망 입력 후 검색 실행.
2. 1위 서비스가 `HIGH_MATCH`임을 확인(`tests/test_real_case_gyeonggi_hwaseong.py`의 기존
   회귀 테스트와 동일한 기대값).
3. 그 1위 서비스 카드에서 **"어떤 지원을 받을 수 있나요?"** 버튼 클릭 → RAG Retrieval →
   Generation 전체 파이프라인 실행.
4. 클릭 전후로 `st.session_state["results"]`의 `(service_id, match_score, match_level)` 튜플
   목록이 **정확히 동일함**을 확인.

---

## 12. 테스트 결과

```
python -m pytest -q
202 passed, 4 skipped in ~67s
```

| 파일 | 개수 | 검증 내용 |
|---|---:|---|
| (기존) recommender | 88 | 무수정, 전부 통과 |
| (기존) RAG retrieval | 34 | 무수정, 전부 통과 |
| (기존) RAG generation | 51 (+1 skip) | 무수정, 전부 통과 |
| `tests/test_streamlit_rag_adapter.py` (신규) | 18 | profile summary UNKNOWN 처리, request 매핑, session key 유일성, 3가지 client 모드, service boundary, 오류 미노출, evidence/필드 표시 순서 |
| `tests/test_streamlit_app_ui.py` (신규, `streamlit.testing.v1.AppTest` 기반) | 11 | 지침 §21 A~L 전부 + 화성 사례 회귀. 실제 위젯(selectbox/radio/text_input/multiselect/button) 조작으로 실행 -- curl/수동 확인이 아니라 진짜 스크립트 실행 결과를 검사 |
| `tests/test_streamlit_rag_smoke.py` (신규, §19) | 0 실행 (+3 skip) | 실제 Claude API로 A/B/C 질문 검증 -- `ANTHROPIC_API_KEY` 없어 전부 SKIPPED |
| **합계** | **206** (202 passed + 4 skipped) | |

`streamlit.testing.v1.AppTest`(Streamlit 공식 헤드리스 테스트 프레임워크, 1.62.0에 포함)로
`app/streamlit_app.py`를 실제 실행하며 위젯 상호작용을 시뮬레이션했습니다 -- pixel test가
아니라 스크립트를 그대로 구동해 `at.exception`(예외 없음), `at.session_state`(키 값), `at.info
/warning/expander`(렌더된 텍스트)를 검사하는 방식입니다.

---

## 13. 성능 (실측)

| 항목 | 값 |
|---|---:|
| 최초 RAG resource load (Embedder 생성 + VectorStore 로드, 프로세스 1회) | 24.09초 |
| (참고) 캐시 없이 같은 프로세스에서 두 번째로 다시 부른 경우 | 9.60초 -- **캐시가 없으면 매번 이 비용이 반복된다는 뜻** |
| `st.cache_resource` 적용 후 이후 rerun/버튼 클릭 | 사실상 0초 (캐시 hit, 함수 재실행 없음) |
| 추천 계산 (`recommend()`, Generation 제외, 10회 평균) | 0.83ms |
| Retrieval (캐시된 store/embedder 재사용, 질문 4종 평균) | 34.74ms |
| 실제 Claude API 사용 시 Generation 시간 | **미측정** -- 이번 세션에 `ANTHROPIC_API_KEY`가 없어 실제 호출 불가 (§19) |

**Streamlit rerun마다 25초 수준의 embedding/vector build가 반복되는 구조는 만들지 않았습니다**
-- `st.cache_resource`가 이를 프로세스당 1회로 제한합니다.

---

## 14. 발견된 문제

1. **`Embedder()` 생성 자체가 무거움**: `VectorStore.load()`는 0.04초로 매우 빠르지만,
   `SentenceTransformer` 모델 객체를 새로 만드는 비용은 (가중치 파일이 이미 디스크 캐시에
   있어도) 약 9.6초로 측정됐습니다(§13). 처음에는 "인덱스만 캐시하면 충분하다"고 가정하기
   쉬운데, 실제로는 **`Embedder`도 반드시 `VectorStore`와 함께 캐시해야 한다**는 것을 실측으로
   확인했습니다 -- `rag_adapter.load_rag_resources()`가 둘을 항상 같이 반환하고
   `_load_rag_resources_cached()`가 튜플 전체를 캐시하는 이유입니다.
2. **AppTest의 `session_state` 프록시가 `.get()`/`.keys()`를 지원하지 않음**: Streamlit의
   `SafeSessionState`는 속성 접근을 전부 `__getitem__`으로 위임하기 때문에
   `at.session_state.get(...)`을 호출하면 `.get`이라는 *키*를 찾으려다 실패해 `AttributeError`
   가 납니다. 테스트 작성 중 실제로 이 문제에 부딪혔고, `try/except KeyError`로 우회했습니다
   (테스트 코드에만 해당, 앱 코드에는 영향 없음).

---

## 15. 현재 한계

1. **실제 Claude API 호출은 이번 세션에서 검증하지 못했습니다** (`ANTHROPIC_API_KEY` 미설정).
   `rag_generation_v1_report.md`의 한계와 동일하게, 실제 응답 품질/지연시간은 키가 설정된
   환경에서 재확인이 필요합니다.
2. **다중 세션/동시 사용자 환경에서의 `st.cache_resource` 공유는 검증하지 않았습니다** --
   `streamlit_mvp_v1_report.md` §8-4가 이미 밝힌 기존 한계와 동일합니다.
3. **브라우저 수동 클릭 테스트는 수행하지 않았습니다.** `streamlit.testing.v1.AppTest`로
   실제 스크립트 실행과 위젯 상호작용을 검증했지만, 실제 브라우저 렌더링(레이아웃/모바일
   반응형 등)은 사용자가 직접 확인해야 합니다.
4. **자유 질문의 "범위 밖 질문" 처리는 Generation Layer의 system prompt에만 의존합니다** --
   Streamlit 쪽에 별도의 주제 필터링 로직을 추가하지 않았습니다(지침 §18과 §7이 이미
   "prompt guardrail을 유지하라"고 명시했으므로 의도된 설계입니다). 이번 단계에서는 이 동작을
   FakeGenerationClient로만 확인했고, 실제 Claude가 오프토픽 질문에 실제로 얼마나 잘
   저항하는지는 §19 스모크 테스트(현재 SKIPPED)로 별도 확인이 필요합니다.

---

## 16. 다음 단계

1. `ANTHROPIC_API_KEY`가 설정된 환경에서 `tests/rag/test_generation_smoke.py`와 이번 단계의
   §19 스모크 시나리오(A/B/C)를 실행해 실제 Claude 응답 품질과 지연시간을 확인.
2. 실제 브라우저로 `streamlit run app/streamlit_app.py` 수동 확인(레이아웃/모바일 반응형).
3. `rag_retrieval_v1_report.md`/`rag_generation_v1_report.md`가 이미 남긴 v2 과제(키워드 hint
   충돌, tie-break 아티팩트 등)는 이번 통합 단계의 범위 밖으로 그대로 유지.

---

## 17. 완료 기준

- [x] 기존 Streamlit 추천 기능 유지 (무수정)
- [x] 추천 카드에 RAG 설명 UI 추가
- [x] preset 질문 (4종)
- [x] 자유 질문
- [x] on-demand Generation (검색만으로는 호출 안 됨, 실측 검증)
- [x] service_id boundary 유지 (구조적 + 테스트로 검증)
- [x] Retrieval 연결 (`retrieve_for_service`, 무수정 그대로 사용)
- [x] Generation 연결 (`generate_answer`, 무수정 그대로 사용)
- [x] `GroundedAnswer` 표시 (빈 필드 숨김)
- [x] evidence expander (공식 원문임을 명시, AI 문장과 시각적 구분)
- [x] application 없음 fallback (UI에서 실측 검증)
- [x] UNKNOWN 안전 처리
- [x] API Key 없음 fallback (앱 전체 crash 없음)
- [x] Generation error fallback (예외/키 미노출 확인)
- [x] `st.cache_resource` 적용 (실측으로 필요성 재확인)
- [x] `session_state` 적용 (service_id 스코프)
- [x] 기존 173 tests 유지 (88+34+51=173, 여기에 신규 33개 추가해 총 206, 그중 4개는 API 키 없어 skip)
- [x] Streamlit integration tests 추가 (32개: adapter 18 + UI 11 + smoke 3(skip))
- [x] 화성 사례 회귀 테스트 (AppTest로 실제 위젯 조작 재현)
- [x] 보고서 생성 (`streamlit_rag_integration_report.md`, 이 문서)

---

## 18. 최종 보고

| 항목 | 결과 |
|---|---|
| Recommender tests | 88/88 PASS (무수정) |
| Retrieval tests | 34/34 PASS (무수정) |
| Generation tests | 51/51 PASS, 1 SKIPPED (무수정) |
| Streamlit integration tests | 29/29 PASS + 3 SKIPPED (adapter 18 + UI 11 + smoke 3, 신규) |
| 전체 tests | 206 (202 passed, 4 skipped), 실패 0 |
| 기존 추천 결과 불변 | 확인됨 (화성 사례, `(service_id, match_score, match_level)` 완전 동일) |
| RAG resource cache | `st.cache_resource` 적용, 실측으로 필요성 확인(캐시 없으면 매 호출 9.6~24초) |
| On-demand API 호출 | 확인됨 (검색만으로는 `rag_answer::*` 세션 키가 전혀 생성되지 않음) |
| Service boundary | 확인됨 (구조적 설계 + 실제 두 서비스 교차 테스트) |
| Evidence 표시 | 구현됨 (section별 expander, "공식 원문" 라벨과 AI 설명 시각적 분리) |
| UNKNOWN 처리 | 구현됨 ("확인 필요(모름)"로만 표시, "아니오"로 렌더링 경로 없음) |
| Missing application 처리 | 구현됨 (UI에서 고정 문구 실측 확인) |
| API Key 없음 처리 | 구현됨 (AI 영역만 안내, 추천엔진은 계속 정상 동작) |
| Generation 오류 처리 | 구현됨 (예외/키 문자열 미노출, 고정 안내 문구만 표시) |
| 화성 사례 | 통과 (AppTest로 실제 위젯 조작 재현) |
| 보고서 | `docs/streamlit_rag_integration_report.md` (이 문서) |
| **최종 판정** | **STREAMLIT_RAG_READY** |

### 1. 내가 지금 직접 Streamlit을 실행해봐도 되는가?

**예.** `streamlit run app/streamlit_app.py`로 바로 실행 가능합니다. `ANTHROPIC_API_KEY`가
없어도 앱은 정상 기동하며(headless 스모크 확인 완료), AI 설명 영역에만 "현재 설정되지
않았습니다" 안내가 뜨고 나머지 추천 기능은 그대로 동작합니다. 개발/테스트 목적으로 실제
Claude 답변처럼 화면을 확인하고 싶다면 `RAG_GENERATION_MODE=fake streamlit run app/
streamlit_app.py`로 실행하면 됩니다(단, 화면에 "🧪 테스트 모드" 표시가 항상 함께 뜹니다).

### 2. 실제 Claude API가 현재 연결되어 있는가, 아니면 FakeGenerationClient 상태인가?

**연결 코드는 완성되어 있지만, 이번 세션 환경에는 `ANTHROPIC_API_KEY`가 설정되어 있지
않습니다.** 기본(`auto`) 모드에서는 이 경우 Fake로 자동 대체되지 않고 **"AI 기반 설명 기능이
현재 설정되지 않았습니다"** 상태가 됩니다. 키를 설정하면 코드 변경 없이 바로 실제 Claude가
연결됩니다(`resolve_generation_client()`가 `ANTHROPIC_API_KEY` 존재 여부만으로 자동 전환).

### 3. API Key가 없다면 앱에서 정확히 어떤 기능까지 사용 가능한가?

- 사용 가능: 시/도·시/군/구·연령·장애·저소득·독거·거동불편·식사준비어려움·최근퇴원·원하는
  도움 입력, 추천 실행, Top-K 결과, match level, 추천 이유, 확인 필요 조건, 기존 "자세히
  보기" expander(원문/점수/검증등급 등) -- **RAG 이전 단계의 모든 기능**.
- 사용 불가: "🤖 AI로 자세히 알아보기"의 실제 답변 생성만 -- 해당 영역에는 안내 문구만
  표시되고 앱이 멈추거나 오류 화면이 뜨지 않습니다.

### 4. 현재 사용자에게 표시되는 AI 답변은 실제 Claude 답변인지 Fake 답변인지 어떻게 구분되는가?

카드마다 AI 설명 영역 바로 위에 캡션으로 명시됩니다: 실제 Claude 응답이면 **"Claude API
기반 설명이에요."**, `RAG_GENERATION_MODE=fake`로 명시적으로 켠 테스트 응답이면 **"🧪 테스트
모드 응답이에요 (실제 Claude 답변이 아니에요)."** 두 상태가 절대 같은 문구를 쓰지 않도록
설계했고, 기본 모드에서는 Fake가 나타날 수조차 없습니다(§7).

### 5. 추천 버튼을 누르는 것만으로 Claude API가 호출되는가?

**아니오.** `test_A_search_alone_does_not_trigger_generation`으로 실제 위젯 클릭을 재현해
검증했습니다 -- 검색 버튼을 눌러 Top-K 결과가 표시된 직후에는 어떤 서비스에 대해서도
`rag_answer::*` 세션 키가 생성되지 않으며, 이는 곧 `generate_answer()`(그리고 그 안의 Claude
호출)가 전혀 실행되지 않았다는 뜻입니다. Claude는 사용자가 preset 질문 버튼 또는 "근거 기반
답변 보기"를 직접 눌렀을 때만 호출됩니다.

### 6. 현재 MVP에서 반드시 수정해야 할 문제가 남아 있는가?

**막는(blocking) 문제는 없습니다.** 다만 §15에 정리한 대로, 실제 API 키를 넣은 실사용
검증(§19 스모크 테스트, §14/브라우저 수동 확인)은 이번 세션 환경 제약(키 없음)으로 완료하지
못했습니다 -- 배포 전에 반드시 한 번은 실행해봐야 하는 항목으로 남겨둡니다.
