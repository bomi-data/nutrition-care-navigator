# RAG Retrieval Layer v1 구현 보고서

> 이 단계는 **"근거 문서를 정확하게 찾을 수 있는 RAG Retrieval Layer"**까지입니다.
> Claude API 연결/LLM 답변 생성/Streamlit RAG 연결/챗봇/n8n/배포는 포함하지 않았습니다.

---

## 0. 시작 전 확인한 것 (전제)

- `src/recommender/`는 이번 단계에서 **한 줄도 수정하지 않았습니다.** 88개 테스트(기존 53개 +
  이후 추가된 35개, 실측)가 그대로 통과하는 상태에서 시작했고, 지금도 그대로 통과합니다.
- 요청서가 언급한 CSV 컬럼명 중 `region`, `senior_relation_v2`는 실제로 **존재하지 않습니다**
  (`docs/recommendation_system_design.md` §0.1에 이미 같은 경고가 있습니다). 실제로는
  `sido`/`sigungu`, `senior_relation`(버전 접미사 없음)입니다. 아래 전체 문서는 실제 컬럼명만
  사용합니다.
- 실행 환경은 **Python 3.10.11**입니다(요청서는 3.12를 가정했지만 실제로 설치된 버전은 3.10.11 —
  없는 사실을 있다고 가정하지 않기 위해 정정합니다). 아래 §6의 모델 선택은 3.10.11 기준으로
  실제 설치·실행까지 검증했습니다.

---

## 1. RAG의 목적

이 프로젝트에서 RAG는 **서비스를 추천하는 엔진이 아닙니다.** 이미 `src/recommender`가 규칙 기반으로
85건 중 관련성 높은 서비스를 골라 순위를 매기는 역할을 끝냈고(`ENGINE_VALIDATED`, 88/88 테스트
통과), RAG는 그 결과로 나온 `service_id`에 대해서만 공식 원문에서 근거 구절(지원대상/선정기준/
지원내용/신청방법)을 검색하는 역할만 합니다.

---

## 2. 추천엔진과 RAG의 역할 분리

| 구성요소 | 입력 | 출력 | 이번 단계에서 구현 여부 |
|---|---|---|---|
| **규칙 기반 추천엔진** (`src/recommender`) | `UserProfile` | 후보 필터링 → ranking → `service_id` 목록(`match_score`/`match_level` 포함) | 이미 완료(수정 안 함) |
| **RAG** (`src/rag`, 이번 단계) | 추천된 `service_id`(들) + 자연어 질문 | 해당 `service_id`의 공식 원문 근거 구절 | **이번 단계 구현** |
| **LLM** (향후 단계) | RAG가 찾은 근거 | 사용자가 이해하기 쉬운 문장 | 미구현 |

**RAG/LLM이 절대 하지 않는 일** (`docs/recommendation_system_design.md` §10과 동일 원칙을
코드 수준에서 강제):
- `recommender`의 순위(`match_score`/`match_level`)를 바꾸지 않습니다 — RAG는 `recommender`
  모듈을 **import조차 하지 않습니다** (`src/rag`는 `recommender.models`/`recommender.loader`의
  읽기 전용 타입만 참조).
- 새 서비스를 추천하지 않습니다 — `src/rag`에는 "전체 85건에서 검색"하는 공개 함수가
  **존재하지 않습니다.** `retrieve()`/`retrieve_for_service()` 둘 다 `service_ids`를 필수
  인자로 받고, 호출자가 미리 좁혀 놓은 집합 밖으로 검색 범위를 넓힐 방법이 없습니다.
- 이용자격을 확정하지 않습니다 — 이번 단계는 검색만 하며, 문장 생성/자격 판단은 다음 단계
  (LLM)의 몫으로 남겨두고 이번 코드에는 없습니다.

---

## 3. Source 데이터 확인 결과

`data/processed/welfare_services_recommendation_ready.csv` (85행, 34컬럼)를 직접 읽어 확인했습니다.

### 3.1 RAG에 사용 가능한 원문 컬럼

| 컬럼 | non-null(비어있지 않음) | 평균 길이 | 최대 길이 | 중복 문장 |
|---|---:|---:|---:|---:|
| `target_original` (지원대상) | 85/85 | 84.8자 | 964자 | 0건 |
| `criteria_original` (선정기준) | 85/85 | 79.1자 | 592자 | 1건 |
| `support_original` (지원내용) | 85/85 | 93.9자 | 1286자 | 0건 |
| `application_original` (신청방법) | 85/85 **셀 자체는** | 58.8자 | 467자 | 27건 |

요청서가 언급한 `region` 컬럼은 없고, 실제로는 `sido`/`sigungu`(지역), `contact`(문의처)가
같은 역할을 합니다.

### 3.2 RAG corpus로 사용하기 곤란한 필드 (실제로 발견한 문제)

- **`application_original`의 "[]" 플레이스홀더 — 25건.** 셀 자체는 비어있지 않지만
  (`.isna()`로는 안 잡힘) 값이 정확히 문자열 `"[]"`인 행이 85건 중 25건입니다. 신청방법 정보가
  실질적으로 없다는 뜻이며, 이를 실제 문장인 것처럼 임베딩하면 "신청방법: []"라는 의미 없는
  근거가 생성됩니다. → **corpus 생성 시 명시적으로 제외**(§4).
- **`application_original`의 중복 27건**: "[] 직접 지원(별도 신청사항 없음)"(4건) 등 정형화된
  문구가 여러 서비스에서 반복됩니다. 중복 자체는 문제가 아니지만(각 서비스는 별도 문서로 취급),
  임베딩 유사도가 우연히 높게 나올 수 있다는 점을 §17 cross-contamination 테스트에서 고려했습니다.
- **`review_note`(내부 검토 메모, 85/85)**: 100% 채워져 있지만 "내부 검토용" 문구로,
  `docs/recommendation_system_design.md` §0.1이 이미 "사용자 노출 부적합"으로 분류했습니다.
  → RAG corpus에 **포함하지 않음.**
- **`eligibility_summary`/`support_summary`**: 10/85건만 채워져 있고, `recommendation_system_design.md`
  §0.3이 "사람이 읽는 요약문, 규칙 매칭 입력으로는 부적합"이라고 이미 분류했습니다. 이번 RAG는
  **원문(`*_original`)만 근거로 사용**하고 이 요약 필드는 corpus에 넣지 않았습니다(요약은 실제
  원문과 표현이 달라, "원문에서 근거를 찾는다"는 §1 목적과 어긋날 수 있기 때문).

---

## 4. Document 스키마

서비스별 원문을 하나의 거대한 문자열로 합치지 않고, **의미 단위(section) Document**로 생성했습니다
(`src/rag/document_builder.py`).

```
RAGDocument
  doc_id                  # "{service_id}::{section}::{chunk_index}" (결정론적, 재실행해도 동일)
  service_id, service_name
  section                 # "target" | "criteria" | "support" | "application"
  content                 # 해당 section의 원문(또는 §5 sub-chunk)
  chunk_index, chunk_count
  sido, sigungu
  service_type_primary
  verification_level
  source_type             # ServiceRecord.source_api ("local"/"central")
```

section ↔ CSV 필드 매핑:

| section | CSV 필드 |
|---|---|
| `target` | `target_original` |
| `criteria` | `criteria_original` |
| `support` | `support_original` |
| `application` | `application_original` |

**"[]" 처리**: `application_original == "[]"`인 25개 섹션은 **Document를 생성하지 않습니다**
(빈 내용을 임베딩하지 않음). `count_excluded_sections()`로 정확히 25를 검증하는 테스트가 있습니다
(`tests/rag/test_document_builder.py`).

`service_type_primary`는 최종 `recommendation_ready.csv`에서 **85/85(100%) 채워져 있음을 확인**했습니다
(`meal_support` 72 / `community_care` 10 / `home_visit` 2 / `food_cost_support` 1). 참고: 더 이른
버전 문서인 `recommendation_system_design.md`는 이 필드가 31/85(36.5%)만 채워진 이전 CSV
(`welfare_services_final.csv`)를 기준으로 작성되어 수치가 다릅니다 — 최종 CSV 기준으로 갱신된
수치를 이 보고서에 반영했습니다.

---

## 5. Chunking 전략

**기본 전략은 필드/section 단위 chunking**입니다. 85건의 공공복지 원문은 긴 PDF가 아니라 이미
"지원대상/선정기준/지원내용/신청방법"으로 구조화된 짧은 필드이므로, fixed character chunking을
무조건 적용하지 않았습니다.

### 5.1 실측 근거

| 필드 | 중앙값 | 90th pct | 95th pct | 최댓값 | 300자 초과 행 수 |
|---|---:|---:|---:|---:|---:|
| `target_original` | 41자 | 197자 | 240자 | 964자 | 4건 |
| `criteria_original` | 31자 | 251자 | 318자 | 592자 | 6건 |
| `support_original` | 39자 | 199자 | 309자 | 1286자 | 5건 |
| `application_original` | 28자 | 131자 | 282자 | 467자 | 4건 |

대다수 section은 30~100자 수준이라 field 자체가 이미 하나의 적절한 chunk입니다.

### 5.2 sub-chunking이 필요한 경우

**`CHUNK_SIZE=400`, `CHUNK_OVERLAP=60`** (`src/rag/document_builder.py`)을 선택했습니다.

- 근거: 위 표에서 300자를 넘는 행이 필드당 4~6건뿐이고, 400자를 기준으로 하면 대부분의 section이
  분할 없이 그대로 하나의 Document가 됩니다. 반면 실제 최댓값(964/592/1286/467자)인 4개 행은
  분할이 필요합니다 — 특히 `support_original` 최댓값 1286자 행(`WLF00005102`, 광주+돌봄 서비스)은
  "1. 가사지원 / 2. 식사지원 / 3. 동행지원 / ..." 식으로 **7개 이상의 서로 다른 하위 프로그램을
  한 필드에 나열**하고 있어, 하나의 벡터로 뭉뚱그리면 "방문목욕 1회 84,000원"이라는 세부 근거가
  "AI 안부확인 무료"라는 다른 프로그램 설명에 묻혀 검색 품질이 떨어집니다.
- overlap 60자: 강제 분할이 실제로 일어나는 경우(자연스러운 구분자가 없는 긴 조각)에만 사용되며,
  분할 경계에서 조건/가격이 잘리더라도 앞뒤 맥락 일부가 양쪽에 남도록 하기 위함입니다.
- **분할 지점은 고정 길이가 아니라 원문에 실제로 쓰인 구분자**를 우선 사용합니다: 원문 조사 결과
  기관들이 실제로 `①②③...`, `●`, 줄바꿈, 문장부호(`.`/`!`/`?`)로 하위 항목을 구분하고 있어
  (§5.1 예시 원문 참고), 이 지점에서 자릅니다. 자연스러운 구분자가 없는 예외적으로 긴 조각만
  마지막 수단으로 고정폭 슬라이딩 윈도우(overlap 포함)로 나눕니다.

### 5.3 실측 결과

빌드 결과 326개 Document 중 target 88(85건+3 chunk), criteria 87(85+2), support 90(85+5),
application 61(60+1)로, **sub-chunking으로 늘어난 chunk는 총 11개뿐**입니다 — 예측대로 대부분의
section은 분할 없이 하나의 Document가 되었습니다.

---

## 6. Embedding 모델 선택

**조건**: 한국어 지원, Python 3.10 환경에서 실행 가능, 85개 서비스 규모에서 과도하게 무겁지 않음,
추가 API 키 없이 로컬 실행. Claude/Anthropic을 embedding provider로 가정하지 않았고, 이번 단계에서
유료 embedding API를 새로 도입하지 않았습니다.

### 6.1 후보 비교

| 후보 | 차원 | 크기(대략) | 학습 목적 | 한국어 |
|---|---:|---:|---|---|
| **`intfloat/multilingual-e5-small`** (채택) | 384 | ~470MB | **비대칭 검색**(질문 vs 문서) 전용 contrastive 학습 | O (multilingual) |
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384 | ~420MB | 대칭 STS/paraphrase 유사도(일반 목적) | O (multilingual) |
| `jhgan/ko-sroberta-multitask` | 768 | ~443MB | 한국어 전용 SBERT(KorSTS/KorNLI) | O (한국어 전용) |

### 6.2 선정 이유

**`intfloat/multilingual-e5-small`을 채택**했습니다. 실제로 `pip install sentence-transformers
faiss-cpu`로 로컬 설치 후 이 모델을 다운로드해 한국어 질문-문서 쌍으로 동작을 검증했습니다:

```
query: 누가 이용할 수 있나요?
passage: 만 65세 이상 거동이 불편한 저소득 독거노인
cosine similarity = 0.814
```

- **이 프로젝트의 검색 형태(짧은 질문 → 긴 공식 원문 구절)와 정확히 일치하는 비대칭(asymmetric)
  검색용으로 학습된 모델**이라는 점이 결정적이었습니다. MiniLM-L12-v2는 "두 문장이 같은 뜻인가"를
  판단하는 대칭 유사도용으로 학습되어, 질문↔문서처럼 형태가 다른 텍스트 쌍에는 상대적으로 덜
  최적화되어 있습니다.
- 차원(384)이 `ko-sroberta-multitask`(768)의 절반이라 85개 서비스 규모에서 저장 공간과 계산량이
  더 작습니다(§12 실측: `index.faiss` 489KB).
- `sentence-transformers` 라이브러리(LangChain 없이도 순수 Python에서 사용 가능)로 바로 사용
  가능하고, 실제로 Python 3.10.11 환경에 정상 설치·다운로드·추론까지 확인했습니다.
- `ko-sroberta-multitask`는 한국어 전용이라 향후 다국어 확장 여지가 없고, 차원이 커 이 규모의
  MVP에는 과합니다. MiniLM-L12-v2는 크기는 비슷하지만 검색 목적에 덜 맞아 후순위로 두었습니다.
  (두 후보는 공개된 모델 카드 스펙 기준으로 비교했고, 이번 저장소에서 실제로 다운로드해 비교하지는
  않았습니다 — 1차 후보가 이미 실측으로 요구 조건을 충족했기 때문입니다.)
- `query: `/`passage: ` 접두사가 필요한 모델이라는 점이 유일한 사용상 제약이며, `src/rag/embeddings.py`
  의 `Embedder.embed_query()`/`embed_documents()`가 이를 자동으로 붙여 호출부가 신경 쓸 필요가
  없도록 감쌌습니다.

---

## 7. Vector Store 선택

**FAISS(`IndexFlatIP`)를 채택**했습니다.

- 이 규모(326개 벡터, 384차원)에서는 근사 검색(ANN) 인덱스가 이득이 없고 오히려 근사 오차라는
  리스크만 추가합니다. `IndexFlatIP`는 완전탐색(exact) 내적 검색이며, 임베딩을 L2 정규화했으므로
  내적 = 코사인 유사도입니다.
- **실제 발견한 환경 이슈와 해결**: `faiss.write_index()`/`faiss.read_index()`는 내부적으로 C++
  `fopen()`을 사용하는데, 이 프로젝트 경로에 한글 사용자명(`이보미`)이 포함되어 있어
  `RuntimeError: ... could not open ... Illegal byte sequence`로 **실제로 저장에 실패했습니다.**
  이를 `faiss.serialize_index()`/`faiss.deserialize_index()`로 메모리에서 바이트로 변환한 뒤
  Python 자체의 파일 I/O(유니코드 경로를 정상 처리함)로 쓰고 읽도록 우회해 해결했습니다
  (`src/rag/vectorstore.py`의 `save()`/`load()` 주석 참고). 한글 경로를 쓰는 Windows 환경에서
  이 문제를 다시 만날 수 있으므로 기록해 둡니다.
- 로컬 저장 경로: `data/vectorstore/`(`index.faiss` + `documents.jsonl` + `meta.json`).
  `.gitignore`에 `data/vectorstore/`를 추가해 빌드 산출물이 저장소에 커밋되지 않도록 했습니다
  (언제든 `python -m rag.build_index`로 재생성 가능).
- `save()`/`load()`로 재실행할 때마다 다시 임베딩하지 않아도 됩니다 — 실측 load 시간 0.038초
  (§12).

---

## 8. Retrieval 구조와 service_id 제한

**가장 중요한 원칙**: 이 RAG는 85개 서비스 전체를 대상으로 마음대로 semantic search해서 새 서비스를
추천하지 않습니다. 추천엔진이 `service_id`를 결정한 이후에만 그 `service_id`의 문서만 검색합니다.

```python
retrieve(store, embedder, query, service_ids=[...], top_k=3)
retrieve_for_service(store, embedder, service_id, query, top_k=3)
```

**구조적으로 강제되는 방식** (단순히 결과를 사후 필터링하는 것이 아님):

1. `VectorStore.documents_for_service_ids(service_ids)`가 요청된 `service_id` 집합에 속하는
   벡터의 행 인덱스만 골라냅니다.
2. `search_within()`은 **이 행 인덱스에서 직접 벡터를 reconstruct해서만** 유사도를 계산합니다 —
   전체 코퍼스에 대해 검색한 뒤 걸러내는 방식이 아니라, 애초에 다른 서비스의 벡터를 읽지도
   않습니다.
3. `src/rag/__init__.py`는 "전체 코퍼스 검색" 함수를 export하지 않습니다 — `retrieve()`/
   `retrieve_for_service()`만 공개 API이고 둘 다 `service_ids`가 필수입니다.

§17에서 이 원칙이 실제로 지켜지는지 자동 테스트로 검증했습니다(`cross_service_contamination = 0`).

---

## 9. Section-aware Retrieval

질문 유형에 따라 관련 section을 **우선** 검색하되, 키워드 규�칙 때문에 근거가 누락되지 않도록
**vector fallback을 항상 유지**합니다 (`src/rag/retriever.py`).

| 키워드 예시 | hint section |
|---|---|
| "신청", "어떻게", "방법", "서류", "접수" | `application` |
| "얼마나", "몇 번", "지원 내용", "혜택", "제공", "받을 수" | `support` |
| "저소득", "수급자", "차상위", "소득", "선정기준", "기준" | `criteria` |
| "거동", "장애", "독거", "연령", "대상", "자격", "누가", "이용할 수" | `target`, `criteria` (둘 다) |

동작 방식:
1. hint section이 있으면 그 section(들)로 범위를 좁혀 먼저 검색합니다.
2. `top_k`가 채워지지 않으면(hint section에 문서가 없거나 부족하면) **같은 service_id 범위 안에서**
   section 제한 없는 순수 vector 검색으로 나머지를 채웁니다.
3. hint 결과는 fallback 결과보다 항상 앞에 옵니다 — 전체를 점수로 재정렬하면 "질문 유형에 따라
   section을 우선한다"는 원칙이 무의미해지기 때문에, 의도적으로 재정렬하지 않았습니다.
4. 키워드가 전혀 매칭되지 않는 애매한 질문(예: "이거 괜찮나요?")은 hint 없이 곧바로 순수 vector
   검색으로 넘어갑니다(§18).

`"신청" ∈ "신청 조건이 무엇인가요?"`처럼 신청(application) 키워드와 조건(criteria) 키워드가 한
질문에 같이 등장하는 경우, 현재 규칙은 application을 먼저 매칭합니다 — 이는 실제로 실험에서 발견된
한계이며 §16에 기록했습니다.

---

## 10. Retrieval 결과 Schema

```python
RetrievalResult(
    service_id: str,
    service_name: str,
    section: str,          # "target" | "criteria" | "support" | "application"
    content: str,
    score: float,           # cosine similarity, 높을수록 관련성 높음
    metadata: dict,         # sido/sigungu/service_type_primary/verification_level/
                            # source_type/chunk_index/chunk_count/doc_id
)
```

나중에 LLM이 어떤 근거를 사용했는지 `metadata["doc_id"]`로 추적할 수 있습니다.

---

## 11. 테스트 방법

`tests/rag/`(pytest, `tests/test_*.py`와 동일한 컨벤션) — 34개, 기존 recommender 88개와 **완전히
분리**되어 있고 서로 import하지 않습니다.

| 파일 | 개수 | 검증 내용 |
|---|---:|---|
| `test_document_builder.py` | 8 | section당 Document 생성, "[]" 제외(25건), metadata 필수값, doc_id 유일성, 긴 필드 sub-chunking, 짧은 필드 미분할 |
| `test_vectorstore.py` | 7 | 길이 일치, service_id 필터링, section 필터링, **save/load 왕복 후 검색 결과 동일성**, 없는 디렉터리 에러 |
| `test_retriever.py` | 12 | section hint 추론(A~G 질문 유형), service_id 범위 제한, 빈 질문, 존재하지 않는 service_id, "[]" 신청방법 서비스에서 크래시 없이 fallback, top_k 준수, 결과 schema |
| `test_contamination.py` | 3 | 의미적으로 유사한 서비스 쌍(재가급여 vs 국가유공자재가복지지원 등) 교차오염 0건, 복수 service_id 요청 시 범위 준수, 30개 평가 질의 전체 오염 0건 |
| `test_evaluation.py` | 3 | Hit@1/Hit@3 v1 기준 통과, 모든 평가 질의가 결과 반환, 애매한 질문 크래시 없음 |
| **합계** | **34** | **전부 통과** |

`tests/rag/eval_queries.py`는 30개 ground-truth 질의(§13-15)를 정의하며 테스트 파일이 아닙니다
(test_ 접두사 없음, pytest가 수집하지 않음) — `test_evaluation.py`/`test_contamination.py`가
import해서 사용합니다.

전체 테스트: `python -m pytest -q` → **122 passed** (recommender 88 + rag 34), 기존 88개
recommender 테스트는 이번 단계에서 **하나도 수정하지 않았고** 그대로 통과합니다.

---

## 12. 실측 결과 — Vector DB 생성 통계

`python -m rag.build_index` 실행 결과(`data/processed/welfare_services_recommendation_ready.csv`
기준):

| 항목 | 값 |
|---|---:|
| 서비스 수 | 85 |
| Document 수 | 326 |
| ㄴ target | 88 |
| ㄴ criteria | 87 |
| ㄴ support | 90 |
| ㄴ application | 61 |
| null 원문("[]")으로 제외된 section 수 | 25 (전부 application) |
| Embedding 차원 | 384 |
| `index.faiss` 크기 | 489.0 KB |
| `documents.jsonl` 크기 | 170.4 KB |

---

## 13-15. Retrieval 테스트 Query / Ground Truth / 실제 서비스 기반 테스트

`tests/rag/eval_queries.py`에 **10개 서비스 × 3개 질의 = 30개** ground-truth 질의를 정의했습니다.
`service_type` 기준 실제 존재하는 4개 유형을 모두 포함합니다:

| 유형 | 포함된 서비스 |
|---|---|
| `meal_support` | WLF00003518(사랑이음 밥차 운영), WLF00000383(경로식당 무료급식사업), WLF00002028(저소득 재가노인 식사배달), WLF00001509(재가복지 서비스) |
| `food_cost_support` | WLF00003036(노인 효도권 지원) — 85건 중 **이 유형은 1건뿐**이라 이 서비스 하나로 대표 |
| `community_care` | WLF00000664(노인맞춤돌봄지원 강화 사업), WLF00005770(대전형 지역사회통합돌봄), WLF00005308(춘천형 노인통합돌봄사업) |
| `home_visit` | WLF00000098(국가유공자재가복지지원), WLF00003248(재가급여), WLF00001509/WLF00005770/WLF00005308(중복 태그) |

질문 A~G(요청서 §13)를 실제 서비스 원문에 맞게 배치했습니다. **application_original이 정확히
"[]"인 3개 서비스(WLF00003518/WLF00000383/WLF00003036)에는 D(신청방법) 질문을 배정하지 않았습니다**
— 존재하지 않는 근거에 대한 기대값을 만들지 않기 위함입니다. 각 expected_section은 해당
service_id의 **실제 원문**을 읽고 정했습니다(§3의 원칙 그대로: 정답을 새로 만들지 않음).

애매한 질문(§18) 2건("이거 괜찮나요?", "도움 받을 수 있어요?")도 별도로 테스트했습니다 — 결과가
있는지/크래시가 없는지만 확인하고, 어떤 section이 "정답"인지는 주장하지 않습니다.

---

## 16. Retrieval 평가 지표 (실측)

| 지표 | 값 | 정의 |
|---|---:|---|
| **Hit@1** | **90.0%** (27/30) | 기대 section이 top-1 결과에 있음 |
| **Hit@3** | **96.7%** (29/30) | 기대 section이 top-3 결과 안에 있음 |
| **MRR** | **0.928** | 평균 역순위(첫 정답 등장 순위의 역수 평균) |

**유일한 실패 케이스** (top-3 안에도 없음): `WLF00005308`(춘천형 노인통합돌봄사업)의 "신청 조건이
무엇인가요?" — §9에서 이미 언급한 "신청"/"조건" 키워드 충돌로 application section이 먼저
hint되었고, vector fallback에서도 criteria가 target/support보다 낮은 유사도로 밀려 top-3 밖으로
빠졌습니다. 30개 중 1개(3.3%)의 사례이며, §21 개선 과제로 남겨둡니다.

---

## 17. Cross-service Contamination

**`cross_service_contamination = 0`** — 다음 세 가지 방식으로 검증했습니다(`tests/rag/test_contamination.py`):

1. 의미적으로 특히 유사한 3개 서비스 쌍(재가급여 vs 국가유공자재가복지지원, 대전형 vs 춘천형
   통합돌봄, 이름이 거의 같은 두 "저소득 재가노인 식사배달"류 서비스) × 4개 공통 질의 = 12회 검색,
   **오염 0건**.
2. 복수 `service_id`를 동시에 요청하는 경우(실제 top-K 추천 시나리오)에도 결과가 요청 집합
   밖으로 나가지 않음.
3. §13-16의 30개 평가 질의 전체에서 오염 0건.

이 결과는 §8에서 설명한 구조(요청된 service_id의 벡터만 reconstruct)에서 나온 것이지, 사후
필터링으로 우연히 0이 된 것이 아닙니다.

---

## 18. 성능 (실측)

| 항목 | 값 |
|---|---:|
| 최초 Vector Store build 시간 (임베딩 모델 로드 포함) | 25.95초 |
| Vector Store load 시간 (저장된 파일에서) | 0.038초 |
| 평균 retrieval 시간 (임베딩 모델 warm 상태, 질의 1건당) | 0.017초 |

85개 서비스 규모에서 build는 최초 1회만 필요(이후 `load()`로 0.04초 이내 재사용)하고, 개별 검색은
사용자가 체감하기 어려운 수준(20ms 미만)입니다. 이번 단계에서는 추가 최적화가 필요하지 않습니다.

---

## 19. 한계

1. **"신청"/"조건" 키워드 충돌**(§9, §16): "신청 조건이 무엇인가요?" 같은 질문은 신청방법
   질문처럼 보이지만 실제로는 선정기준 질문일 수 있습니다. 규칙 기반 키워드 hint의 구조적
   한계이며, 30개 질의 중 1개(3.3%)에서 top-3 실패로 나타났습니다. fallback vector 검색이
   있어 완전히 유실되지는 않지만(다른 서비스 대부분에서는 hint가 없어도 vector 유사도만으로
   문제없이 상위에 옴), 이 특정 조합에서는 fallback도 충분하지 않았습니다.
2. **`application_original`의 25건 "[]"**: 해당 서비스는 신청방법 질문에 애초에 근거가 없어
   target/criteria/support로 fallback합니다 — 크래시하지 않고 동작하는 것은 확인했지만, "신청
   방법 정보가 없습니다"라는 명시적 안내는 이번 단계(순수 retrieval)의 책임이 아니라 다음
   LLM/UI 단계에서 처리해야 합니다.
3. **`food_cost_support` 유형은 85건 중 1건뿐**이라(§13) 이 유형에 대한 평가는 서비스 다양성
   면에서 통계적으로 약합니다 — recommender 쪽 기존 한계(`recommendation_engine_v1_report.md`
   §10-5)와 동일한 데이터 희소성 문제이며, RAG가 만든 문제가 아닙니다.
4. **키워드 hint 사전은 이번 30개 질의를 기준으로 만들어졌습니다.** 실제 사용자가 던질 수 있는
   질문 표현은 훨씬 다양할 것이므로, 다음 단계에서 실사용 질문 로그가 쌓이면 hint 사전을
   재검토해야 합니다.
5. **평가셋 자체가 30건으로 작습니다.** MVP 단계 목표(과도한 평가 시스템을 만들지 않음)에는
   맞지만, LLM 생성 단계로 넘어간 뒤 실사용 질문 기준으로 재평가가 필요합니다.
6. **FAISS Windows 경로 이슈**(§7): 한글이 포함된 파일 경로에서 `faiss.write_index`/
   `read_index`가 실패하는 것을 실제로 겪었고 우회했습니다. 다른 Windows 환경(다른 한글/비ASCII
   사용자명)에서 재발할 수 있는 라이브러리 버그이므로, 새 환경에 배포할 때 다시 확인이
   필요합니다.

---

## 20. 다음 단계

1. Claude API를 이용한 LLM 답변 생성 계층 연결 — RAG가 반환한 `RetrievalResult` 목록을
   입력으로 받아 문장을 재서술하되, `match_score`/`match_level`(recommender)과
   `service_id`/`section`/`content`(RAG)를 절대 바꾸지 않는 프롬프트 경계를 설계.
2. Streamlit UI에 RAG 연결 — 사용자가 추천 결과 카드에서 "더 자세히" 등을 눌렀을 때
   `retrieve_for_service(store, embedder, service_id, user_question)`을 호출하는 방식.
   이때 vector store/embedder는 세션당 1회만 로드(§18 load 0.04초 활용).
3. §19-1의 키워드 hint 충돌 사례 같은 실제 실패 패턴을, 실사용 질문 로그가 쌓이는 대로 hint
   사전에 반영.
4. §19-4에서 언급한 대로, LLM 연결 이후 실사용 질문 기준 재평가.

---

## 21. 완료 기준 체크리스트

- [x] 85개 서비스 기반 RAG corpus 구축
- [x] section별 Document 생성
- [x] metadata 구성
- [x] embedding 모델 결정 (`intfloat/multilingual-e5-small`, 실측 검증)
- [x] Vector Store 구축 (FAISS `IndexFlatIP`)
- [x] save/load (한글 경로 이슈 우회 포함)
- [x] service_id 제한 retrieval (구조적 보장, 사후 필터링 아님)
- [x] section-aware retrieval (hint + vector fallback)
- [x] 최소 30 query 평가 (정확히 30건, 4개 실제 서비스 유형 포함)
- [x] Hit@1 계산 (90.0%)
- [x] Hit@3 계산 (96.7%)
- [x] cross-service contamination = 0 (구조적 검증 + 3가지 테스트)
- [x] pytest 작성 (34개)
- [x] 기존 recommender 테스트 유지 (88개, 무수정, 전부 통과)
- [x] `rag_retrieval_v1_report.md` 생성

---

## 22. 최종 보고

| 항목 | 결과 |
|---|---|
| RAG 서비스 수 | 85 |
| Documents | 326 (target 88 / criteria 87 / support 90 / application 61) |
| Embedding 모델 | `intfloat/multilingual-e5-small` (384차원, 로컬, API 키 불필요) |
| Vector Store | FAISS `IndexFlatIP` (489.0 KB) |
| Hit@1 | 90.0% (27/30) |
| Hit@3 | 96.7% (29/30) |
| Cross-service contamination | 0 |
| RAG 테스트 수 | 34 |
| 전체 테스트 | 122 (recommender 88 + rag 34) |
| Build 시간 | 25.95초 (모델 로드 포함, 최초 1회) |
| 평균 retrieval 시간 | 0.017초 |
| 보고서 | `docs/rag_retrieval_v1_report.md` (이 문서) |
| **최종 판정** | **RETRIEVAL_V1_READY** |

### 1. Retrieval 품질은 LLM 생성 단계로 넘어갈 수준인가?

**예.** Hit@1 90%/Hit@3 96.7%, cross-service contamination 0건은 "정답 section이 근거로
포함되는지"를 기준으로 LLM이 문장을 재서술할 재료로 충분합니다. 다만 §19-1의 키워드 충돌
사례처럼 완벽하지 않은 지점이 있다는 것을 LLM 프롬프트 설계 시 알고 있어야 합니다(예: RAG가
top-1로 준 section이 항상 최적이라고 LLM이 과신하지 않도록, 여러 section 근거를 함께 넘기는
편이 안전).

### 2. Claude API를 이제 붙여도 되는가?

**예.** RAG 계층의 입력/출력 schema(`RetrievalResult`)가 안정적이고, `recommender`와의 경계도
import 수준에서 분리되어 있어 LLM 계층을 추가해도 이 두 계층을 건드릴 필요가 없습니다.

### 3. Streamlit에 RAG를 붙이기 전에 해결해야 할 문제가 있는가?

크게 막는 문제는 없지만 두 가지는 미리 알아둘 필요가 있습니다:
- **Vector store가 세션마다 재빌드되지 않도록** Streamlit의 `@st.cache_resource` 등으로
  `VectorStore.load()`/`Embedder()` 인스턴스를 앱 시작 시 1회만 생성해야 합니다(§18의 0.04초
  load 이점을 실제로 살리려면 필수).
- **`application_original == "[]"`인 25개 서비스**에 대해 "신청방법 정보가 없습니다" 안내를
  어디서 낼지 결정이 필요합니다 — 이미 `src/streamlit_ui/adapter.py`에 유사한 안내 문구 처리
  선례(`scarce_support_warning` 등)가 있으므로 그 패턴을 재사용할 수 있습니다.
