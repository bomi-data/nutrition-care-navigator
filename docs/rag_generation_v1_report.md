# Grounded RAG Generation v1 구현 보고서

> 이 단계는 **"추천된 서비스 + 공식 RAG 근거를 기반으로 Claude가 근거 밖의 사실을 만들지
> 않고 사용자 친화적인 설명을 생성하는 것"**까지입니다. Streamlit UI 수정/RAG 연결/자유형
> 챗봇/추가 PDF 수집/웹 크롤링/n8n/배포는 포함하지 않았습니다.

---

## 1. Generation Layer의 목적

`src/recommender`(규칙 기반 추천)와 `src/rag`의 retrieval 계층(`retriever.py`)은 이번 단계에서
**한 줄도 수정하지 않았습니다.** Generation Layer는 이 둘의 출력을 입력으로만 받아, 이해하기
쉬운 한국어 설명을 만드는 세 번째 계층입니다.

```
사용자 Profile
  ↓
recommender.recommend()          -- 변경 없음, 순위/점수 산출
  ↓ service_id
rag.retriever.retrieve_for_service()   -- 변경 없음, 해당 service_id 근거만 검색
  ↓ RetrievalResult[]
rag.generator.generate_answer()   -- 이번 단계, Claude 호출 + guardrail
  ↓
GroundedAnswer
```

## 2. 추천엔진 / RAG Retrieval / Generation 역할 분리 (재확인)

| 계층 | 결정하는 것 | 이번 단계에서 변경 |
|---|---|---|
| `src/recommender` | `service_id`, `match_score`, `match_level`, `matched_conditions`, `confirmation_needed` | **없음** |
| `src/rag/retriever.py` | 어떤 원문 문서가 근거로 채택되는지 (`service_id` 범위 내에서만) | **없음** |
| `src/rag/generator.py` (신규) | 위 결과를 사용자에게 어떤 문장으로 보여줄지 | 신규 구현 |

`src/rag/generator.py`는 `recommender`를 **import하지 않습니다** (기존 retrieval 계층과 동일한
경계 원칙). `GroundedGenerationRequest`가 이미 계산된 `recommendation_level`/
`recommendation_reasons`/`confirmation_needed`를 문자열/리스트로만 받기 때문에, Generation이
추천엔진을 다시 호출하거나 그 결과를 재계산할 방법이 구조적으로 없습니다.

## 3. Claude 역할

Claude는 **설명자**입니다. `LLMGeneratedFields`(pydantic 스키마, `src/rag/generation_models.py`)
가 Claude가 채울 수 있는 **유일한** 필드 집합이며, 여기에는 `service_id`도 `match_score`도
없습니다 — 애초에 Claude가 그런 값을 "출력"할 수 있는 슬롯 자체가 존재하지 않습니다.
`GroundedAnswer`의 나머지 필드(`service_id`/`service_name`/`evidence`/
`insufficient_information`/`safety_notice`/`status`)는 전부 Python이 `GroundedGenerationRequest`
와 검색된 문서로부터 직접 계산합니다.

---

## 4. Input Schema

```python
GroundedGenerationRequest(
    service_id: str
    service_name: str
    user_profile_summary: str
    recommendation_level: str          # RecommendationResult.match_level.value 그대로
    recommendation_reasons: List[str]  # RecommendationResult.recommendation_reasons 그대로
    confirmation_needed: List[str]     # RecommendationResult.confirmation_needed 그대로
    user_question: str
    retrieved_documents: List[RetrievalResult]  # 기존 rag.models.RetrievalResult 그대로 재사용
)
```

`retrieved_documents`는 기존 `RetrievalResult`를 **그대로** 사용합니다(새 타입을 만들지
않음) — `retrieve_for_service()`의 반환값을 변환 없이 바로 넣을 수 있습니다.

---

## 5. Output Schema

```python
GroundedAnswer(
    service_id: str, service_name: str,          # Python이 request에서 그대로 복사

    summary: str                                   # Claude 생성 (sanitize 후)
    why_recommended: str                            # Claude 생성 (sanitize 후)
    eligibility_explanation: str                    # Claude 생성 (sanitize 후)
    support_explanation: str                        # Claude 생성 (sanitize 후)
    application_explanation: str                    # Claude 생성 또는 Python 강제 대체
    confirmation_items: List[str]                   # Claude 생성 또는 Python 보강

    evidence: List[EvidenceItem]                    # Python이 retrieved_documents에서 직접 생성
    insufficient_information: List[str]              # Python이 근거 없는 section만 나열
    safety_notice: str                               # Python 고정 문구
    status: str                                       # "OK" | "INSUFFICIENT_EVIDENCE", Python 결정
)
```

`EvidenceItem`은 `section`/`section_label`(한글)/`content`/`service_id`/`score`를 담아 나중에
LLM이 어떤 근거를 사용했는지 추적할 수 있게 합니다(§16과 연결).

Claude가 실제로 채우는 필드는 이 중 6개(`summary`/`why_recommended`/`eligibility_explanation`/
`support_explanation`/`application_explanation`/`confirmation_items`)뿐이며, 이는 별도의 좁은
pydantic 스키마 `LLMGeneratedFields`로 강제됩니다 — `client.messages.parse(output_format=
LLMGeneratedFields)`를 사용해 Claude 응답이 이 스키마를 벗어날 수 없도록 API 수준에서
강제했습니다.

---

## 6. Prompt 구조

`src/rag/prompt_builder.py`.

**System Prompt**(`SYSTEM_PROMPT`)는 지시된 원칙을 문자 그대로 포함합니다:
- 역할 선언: "당신은 공공 영양·복지서비스의 공식 정보를 이해하기 쉽게 설명하는 도우미입니다."
- 금지 표현 목록(신청할 수 있습니다/지원 대상입니다/받을 수 있습니다)과 권장 표현
  (관련 조건이 확인됩니다/대상일 가능성이 있어요/추가 확인이 필요해요)을 예시로 명시
- "현재 보유한 공식 정보에서는 확인할 수 없습니다" 원칙
- 전화번호/URL/담당기관/신청장소/지원금액/신청기간을 지어내지 말라는 명시적 금지
- UNKNOWN을 임의로 예/아니오로 해석하지 말라는 원칙
- `recommendation_level`을 바꾸지 말라는 원칙
- adversarial 요청(무조건 받을 수 있다고 말해달라 등)에도 원칙을 유지하라는 지시

**User Prompt**(`build_user_prompt`)는:
- 서비스 정보(`service_id`/`service_name`)
- 사용자 프로필 요약
- "절대 변경하지 말고 그대로 참고만 하세요"라고 명시한 `recommendation_level`/
  `recommendation_reasons`/`confirmation_needed`
- 사용자 질문
- CONTEXT: `[지원대상]`/`[선정기준]`/`[지원내용]`/`[신청방법]` 4개 section 라벨로 구성하되,
  **근거가 없는 section은 "근거 없음 -- 이 항목은 절대 추측하지 마세요"라고 명시적으로
  표시**합니다(비어있는 채로 침묵하지 않음 — 이게 없으면 모델이 "언급이 없으니 문제없다"고
  착각할 위험이 있습니다).

---

## 7. Retrieval Context 구성 (§7 요구사항)

Vector DB 전체를 Claude에게 전달하지 않습니다. `GroundedGenerationRequest.retrieved_documents`
는 호출자가 미리 `retrieve_for_service(store, embedder, service_id, question, top_k=3)`로 얻은
결과만 담습니다. `rag_retrieval_v1_report.md`의 실측대로 Hit@1이 90%, Hit@3가 96.7%이므로,
**모든 호출부(테스트/스모크 테스트 포함)에서 `top_k=3`을 기본값으로 사용**해 Top-1 하나에만
의존하지 않도록 했습니다. `retrieve_for_service`의 section-aware retrieval(기존 구현, 미변경)이
질문 유형에 따라 target/criteria/support/application 중 관련 section을 우선 포함합니다.

---

## 8. 신청방법 데이터 부족 처리

`application_original == "[]"`인 25개 서비스(`rag_retrieval_v1_report.md` §3)에 대해:

1. 해당 서비스에 대한 검색에서는 애초에 `application` section 문서가 존재하지 않으므로
   `retrieved_documents`에 `application` 근거가 없습니다.
2. `generate_answer()`는 Claude 호출 **이후** `sections_with_evidence(retrieved_documents)`를
   Python에서 직접 확인하고, `"application" not in present_sections`이면 Claude가 무엇을
   썼든 **무조건** `application_explanation`을 고정 문구로 덮어씁니다:

   > "현재 보유한 공식 정보에서는 이 서비스의 구체적인 신청방법을 확인할 수 없습니다."

이 판단은 **LLM이 아니라 Python이** 내립니다(지시사항 §8 그대로). 테스트
(`test_no_application_evidence_forces_deterministic_fallback_even_if_llm_invents_one`,
`test_question_ten_contact_never_fabricated_when_not_grounded`)에서 Claude 역할의 fake
client가 그럴듯한 신청방법을 지어내도 최종 답변은 항상 고정 문구로 대체됨을 확인했습니다.

---

## 9. 근거 부족 Guardrail

`generate_answer()`는 Claude를 호출하기 **전에** `has_any_evidence(retrieved_documents)`를
확인합니다. `retrieved_documents == []`이면:

- Claude API를 **아예 호출하지 않고** (`FakeGenerationClient.call_count == 0`으로 테스트 검증)
- `status = "INSUFFICIENT_EVIDENCE"`
- 모든 설명 필드를 "현재 보유한 공식 정보에서는 확인할 수 없습니다"로 채운
  `GroundedAnswer`를 즉시 반환합니다.

이번 단계에서는 "근거가 일부만 있음"(예: target만 있고 support는 없음)은 완전한
`INSUFFICIENT_EVIDENCE`로 취급하지 않고, `insufficient_information` 필드(§5)에 어떤 section이
없는지만 기록합니다 — 부분 근거로도 답할 수 있는 질문(예: target만으로도 답이 되는 "누가
이용할 수 있나요?")까지 전면 차단하면 과도하기 때문입니다.

---

## 10. UNKNOWN 처리

1. **System Prompt**에서 UNKNOWN을 예/아니오로 해석하지 말라고 명시.
2. **구조적 보강**: `request.confirmation_needed`(추천엔진이 이미 판단한 "확인 필요" 목록)가
   있는데 Claude가 반환한 `confirmation_items`가 비어있으면, Python이 `request.confirmation_needed`
   를 **그대로**(새로 지어내지 않고) `confirmation_items`에 채웁니다
   (`test_unknown_coercion_is_backfilled_from_recommender_confirmation_needed`).
3. **감사(audit)**: `check_groundedness()`가 이 상황(`unknown_coercion`)을 별도 카테고리로
   플래그합니다 — §10(Groundedness 검증)의 E번 항목.

---

## 11. Groundedness 검증

`src/rag/guardrails.py`가 두 가지 역할을 분리해서 수행합니다.

### 11.1 감사(read-only) — `check_groundedness()`

Claude의 원본 출력을 그대로 분석해 카테고리 A~E를 보고합니다(수정하지 않음):

| 카테고리 | 검사 방법 |
|---|---|
| A. Unsupported policy fact (금액/퍼센트) | 응답 텍스트의 금액(`\d[\d,]*원`)/퍼센트(`\d+%`) 토큰이 근거 텍스트에 자릿수 기준으로 존재하는지 확인 |
| B. Eligibility overclaim | "신청할 수 있습니다"/"지원 대상입니다"/"받을 수 있습니다" 등 16개 금지 표현 포함 여부 |
| C. Fabricated application | `application` section 근거가 없는데 `application_explanation`이 비어있지 않은지 |
| D. Fabricated contact | 전화번호/URL 패턴이 근거 텍스트에 존재하는지(자릿수 기준) |
| E. UNKNOWN coercion | `confirmation_needed`가 있는데 `confirmation_items`가 비어있는지 |

### 11.2 강제(enforcement) — `sanitize_answer()`

**감사만으로 끝내지 않고, 실제로 답변을 고쳐서 내보냅니다.** Claude가 시스템 프롬프트를
완전히 무시하더라도(적대적 사용자 요청에 순응하는 최악의 경우 포함) 최종적으로 사용자에게
가는 텍스트는:

- 금지 표현 → 안전한 대체 문구("대상일 가능성이 있어요(확정이 아니며 추가 확인이
  필요해요)")로 치환
- 근거에 없는 전화번호/URL → `[출처 확인 필요]`로 치환
- 근거에 없는 금액/퍼센트 → `[출처 확인 필요]`로 치환

이 로직은 `LLMGeneratedFields`의 6개 필드 전부와 `confirmation_items`의 각 항목에 적용됩니다.
즉 **groundedness는 "모델이 잘 따랐는지 감지"가 아니라 "모델이 안 따라도 결과가 안전한지
보장"**하는 방식으로 구현했습니다.

---

## 12. 테스트 결과

```
python -m pytest -q
173 passed, 1 skipped in ~31s
```

| 파일 | 개수 | 검증 내용 |
|---|---:|---|
| `test_generation_models.py` | 6 | Request/Response 스키마, pydantic 필수 필드 검증 |
| `test_prompt_builder.py` | 6 | System prompt 금지 표현 포함, 근거 없는 section 명시적 표시 |
| `test_guardrails.py` | 14 | overclaim/전화번호/URL/금액 탐지, groundedness A~E, sanitize 동작 |
| `test_generator.py` | 15 | context 생성, empty evidence, application fallback, overclaim/전화번호/URL/금액 sanitize, UNKNOWN 보강, adversarial(다른 서비스 추천 시도), fake client, api_key_configured |
| `test_generation_integration.py` | 2 | **화성 실사용 사례** -- 추천 결과 불변, 실제 retrieval 연동 |
| `test_generation_real_usage.py` | 9 (4개 서비스 × parametrize 포함) | 실사용 질문 10종 × 4개 실제 서비스(4개 유형), adversarial 질문 4종 × 실제 서비스 |
| `test_generation_smoke.py` | 1 | 실제 Claude API (ANTHROPIC_API_KEY 없어 **SKIPPED**) |
| **합계** | **52** (51 실행 + 1 skip) | |

기존 recommender 88개 + RAG retrieval 34개는 **무수정 상태로 전부 통과**합니다. 전체
174개(173 passed + 1 skipped) 중 실패 0건.

---

## 13. 실제 사례 -- 화성시 75세 케이스

`tests/test_real_case_gyeonggi_hwaseong.py`와 동일한 프로필(75세/경기도 화성시 동탄구/저소득/
독거/거동불편/식사준비어려움/식사지원 희망)을 재사용했습니다.

1. `recommend()` 호출 → 1위 서비스 확인(기존 회귀 테스트가 이미 검증한 대로 `HIGH_MATCH`).
2. `retrieve_for_service()`로 그 `service_id`의 근거 검색.
3. `generate_answer()`로 "왜 추천되었나요?"/"무엇을 지원하나요?"/"어떤 부분을 확인해야
   하나요?" 3개 질문에 대한 답변 생성.
4. **Generation 실행 전후로 `recommend()`를 다시 호출해 `(service_id, match_score,
   match_level)` 튜플이 정확히 동일한지 비교** — 통과. Generation은 추천 결과에 어떤
   부수효과도 만들지 않습니다.

---

## 14. 발견된 문제

### 14.1 Python 정규식의 `\b`가 한글 뒤에서 작동하지 않는 버그 (실제로 발견, 수정함)

전화번호 탐지 정규식에 처음에는 `\b`(단어 경계)를 사용했습니다. 그런데 실제 테스트
(`"문의는 02-9999-9999로 연락하세요."`)에서 **전화번호가 전혀 탐지되지 않는** 문제를
발견했습니다.

원인: Python의 `\b`는 `\w`/`\W` 전이 지점에서만 성립하는데, Python 3 유니코드 정규식에서
**한글 음절도 `\w`로 분류**됩니다. `"9999"`(숫자, `\w`) 바로 뒤에 조사 `"로"`(한글, 역시
`\w`)가 공백 없이 붙으면 둘 다 `\w`라 경계가 성립하지 않아 `\b`가 매치를 거부합니다. 한국어
문장에서 "02-9999-9999**로** 연락하세요"처럼 숫자 뒤에 조사가 공백 없이 바로 붙는 경우가
매우 흔하기 때문에, 이 상태로 배포했다면 **전화번호 hallucination guardrail이 조용히
무력화**될 뻔했습니다.

수정: `\b`를 숫자 전용 경계 `(?<!\d)`/`(?!\d)`로 교체(`src/rag/guardrails.py`의
`PHONE_PATTERN`). 테스트로 회귀 방지 확인.

### 14.2 `messages.parse` 구조화 출력 선택

Claude 응답을 자유 텍스트로 받아 직접 파싱하는 대신 `client.messages.parse(output_format=
LLMGeneratedFields)`(Anthropic SDK 1.0.0의 구조화 출력 기능)를 사용했습니다. 장점: Claude가
스키마 밖 필드(예: `service_id` 재정의 시도)를 출력할 수 있는 통로 자체가 API 수준에서 없고,
JSON 파싱 실패로 인한 예외 처리 코드가 필요 없습니다.

---

## 15. 현재 한계

1. **Groundedness 감사(§11.1)가 자동으로 답변을 막지는 않습니다.** `check_groundedness()`는
   읽기 전용 보고서이며, 실제 안전은 `sanitize_answer()`의 치환/삭제로 보장합니다. 즉
   "위반이 있었는지 로그로 남기고 싶다"는 요구가 생기면 `check_groundedness()`를
   `generate_answer()` 파이프라인에 명시적으로 연결해야 합니다(현재는 별도 호출 필요).
2. **금액/퍼센트 unsupported 판정은 숫자만 비교합니다** (`digits_only()` 비교). "9,000원"과
   "9000원"은 같다고 정확히 인식하지만, 반대로 우연히 같은 숫자가 근거의 다른 맥락(예:
   "65세 이상"의 "65")에 등장하면 실제로는 무관한데 "지원됨"으로 오판할 이론적 여지가
   있습니다. 85건 실측 데이터로는 발생하지 않았지만 알려진 한계로 남깁니다.
3. **overclaim 문구 치환은 문장 흐름을 다소 어색하게 만들 수 있습니다** (예:
   "도시락을 받을 수 있습니다" → "도시락을 대상일 가능성이 있어요(확정이 아니며 추가 확인이
   필요해요)"). 안전을 우선한 설계이며, 다음 단계에서 문구 자연스러움을 개선할 여지가
   있습니다.
4. **실제 Claude API 호출은 이번 세션에서 검증하지 못했습니다** (`ANTHROPIC_API_KEY` 미설정,
   `ant` CLI도 미설치). `ClaudeGenerationClient`는 Anthropic 공식 문서 패턴을 그대로
   따랐지만, 실제 API 응답 형태·품질·latency는 키가 설정된 환경에서 `test_generation_smoke.py`
   를 실행해 확인해야 합니다.
5. **`insufficient_information`은 "완전히 없는 section"만 표시**하고, "검색은 됐지만
   유사도가 낮은" 경우는 구분하지 않습니다 -- retrieval 품질(Hit@1 90%)에 의존하는
   부분이며, `rag_retrieval_v1_report.md` §19의 한계가 그대로 이어집니다.

---

## 16. Streamlit 연결 준비 상태

- `generate_answer(client, request) -> GroundedAnswer` 하나의 함수 호출로 완결되므로 UI
  통합이 단순합니다.
- `GroundedAnswer.as_dict()`가 JSON 직렬화 가능한 dict를 반환해 Streamlit 세션 상태/캐시에
  바로 저장할 수 있습니다.
- Citation 태그(`[근거: 지원대상]` 등)가 `eligibility_explanation`/`support_explanation`/
  `application_explanation` 문자열 안에 이미 포함되어 있어, Streamlit에서 별도 파싱 없이
  그대로 표시 가능합니다. `evidence` 리스트의 원문 전체는 최종 UI의 expander에 표시할 용도로
  이미 구조화되어 있습니다(§5).
- `ClaudeGenerationClient`/`FakeGenerationClient`가 동일한 `GenerationClient` 프로토콜을
  구현하므로, Streamlit 개발 중에는 `FakeGenerationClient`로 API 비용 없이 UI를 먼저 완성한
  뒤 `ClaudeGenerationClient`로 교체할 수 있습니다.
- **아직 연결하지 않은 것**: Streamlit 세션 상태에 `VectorStore`/`Embedder`/
  `ClaudeGenerationClient` 인스턴스를 캐싱하는 코드(`rag_retrieval_v1_report.md` §22의 다음
  단계와 동일한 지적) -- 이번 단계 범위 밖.

---

## 17. 완료 기준 체크리스트

- [x] Claude client abstraction (`GenerationClient` Protocol, `ClaudeGenerationClient`,
      `FakeGenerationClient`)
- [x] `GroundedGenerationRequest`
- [x] `GroundedAnswer`
- [x] Prompt Builder
- [x] Retrieval → Generation 연결 (`retrieve_for_service` 결과를 그대로 `RetrievalResult`로 전달)
- [x] evidence 추적 (`EvidenceItem`, citation 태그)
- [x] insufficient evidence fallback (Claude 호출 자체를 생략)
- [x] application 누락 fallback (Python 강제 override)
- [x] eligibility 확정 금지 (system prompt + sanitize)
- [x] hallucination guardrail (overclaim/전화번호/URL/금액, 감사 + 강제 이중 구조)
- [x] adversarial 테스트 (4종 × 실제 서비스)
- [x] 기존 122 tests 유지 (recommender 88 + retrieval 34, 무수정)
- [x] Generation tests 추가 (52개, 51 실행 + 1 skip)
- [x] 실제 사례 검증 (화성 케이스, 추천 결과 불변 확인)
- [x] 보고서 생성 (`rag_generation_v1_report.md`, 이 문서)

---

## 18. 최종 보고

| 항목 | 결과 |
|---|---|
| Recommender tests | 88/88 PASS (무수정) |
| Retrieval tests | 34/34 PASS (무수정) |
| Generation tests | 51/51 PASS, 1 SKIPPED (API key 없음) |
| 전체 tests | 174 (173 passed, 1 skipped), 실패 0 |
| Claude API | Anthropic SDK 1.0.0, `messages.parse` 구조화 출력, 기본 모델 `claude-opus-5`. 실제 호출은 이번 세션에서 키 부재로 미검증(SKIPPED) |
| Groundedness | 감사(`check_groundedness`, A~E 카테고리) + 강제(`sanitize_answer`)의 이중 구조로 구현 |
| Eligibility overclaim | 방지됨 (system prompt + sanitize, adversarial 테스트로 확인) |
| Fabricated application | 방지됨 (근거 없으면 Python이 무조건 고정 문구로 대체) |
| Fabricated contact | 방지됨 (전화번호/URL 탐지 후 `[출처 확인 필요]`로 치환) -- 탐지 정규식의 한글 `\b` 버그를 실제로 발견·수정(§14.1) |
| UNKNOWN handling | System prompt 금지 + 누락 시 추천엔진의 `confirmation_needed`로 자동 보강 |
| 화성 실사용 사례 | 통과 -- Generation 전후 `match_score`/`match_level` 완전 동일 확인 |
| 보고서 | `docs/rag_generation_v1_report.md` (이 문서) |
| **최종 판정** | **GENERATION_V1_READY** |

### 1. Streamlit에 RAG 답변을 연결해도 되는가?

**예.** `generate_answer()` 하나의 함수로 완결되고, `FakeGenerationClient`로 UI를 먼저
완성한 뒤 `ClaudeGenerationClient`로 교체하는 개발 흐름이 가능합니다. §16에서 정리한 대로
캐싱 코드만 추가하면 됩니다.

### 2. 현재 가장 큰 hallucination 위험은 무엇인가?

**신청방법·전화번호·금액처럼 "구체적이고 확인 가능해 보이는" 정보를 그럴듯하게 지어내는
것**입니다. 실제로 §14.1에서 전화번호 탐지 정규식이 한글 조사 뒤에서 조용히 실패하는 버그를
발견했는데, 이는 "가드레일이 있다고 믿었지만 실제로는 뚫려 있던" 정확히 그 종류의 위험을
보여주는 사례입니다. 이번 단계는 감사(감지)와 강제(치환)를 분리해 감사가 실패하더라도 강제가
독립적으로 동작하도록 설계했지만, §15-2에서 언급한 숫자 비교의 이론적 허점처럼 완전히 닫힌
문제는 아닙니다.

### 3. PDF/외부 공식 문서를 추가하지 않아도 MVP가 성립하는가?

**예, 성립합니다.** `target_original`/`criteria_original`/`support_original`/
`application_original` 원문(85건, `rag_retrieval_v1_report.md` §3)만으로 Hit@1 90%/Hit@3
96.7%의 retrieval과, 이번 단계에서 검증한 근거 기반 설명 생성까지 동작합니다. 다만
25개 서비스의 신청방법 정보 부재, 그리고 `recommendation_rules_spec.md` §15가 이미 지적한
"복합 하위서비스 레코드"(경로식당+식사배달+밑반찬배달이 한 행에 묶인 경우)처럼, 원문 자체의
한계는 Generation 단계로 해결되지 않고 그대로 노출됩니다(설명이 부실해지는 게 아니라
"확인할 수 없습니다"로 정직하게 안내되는 형태로).

### 4. 외부 공식 문서를 추가한다면 어느 단계에서 추가하는 것이 좋은가?

**Streamlit UI 연결 이후, 별도의 데이터 보강 단계로 분리해서 추가하는 것을 권장합니다.**
근거는:
- 이번 단계의 corpus/retrieval/generation 파이프라인은 "85건 × 4 section" 구조에 맞춰
  설계되어 있어(section 단위 chunking, service_id 범위 제한), 외부 PDF를 추가하려면
  `document_builder.py`의 corpus 구축 단계부터 다시 설계해야 합니다(예: PDF 파싱, 새로운
  section 체계, `service_id`와의 매핑 방식).
- 지금은 UI 없이도 retrieval/generation 품질을 검증할 수 있는 단계였지만, 외부 문서 추가는
  "정말 필요한 격차가 무엇인지"(예: 25개 서비스의 신청방법 정보 부재가 실사용자에게 얼마나
  문제가 되는지)를 Streamlit으로 실사용자 피드백을 받은 뒤 판단하는 편이 더 근거 있는
  우선순위 결정입니다.
