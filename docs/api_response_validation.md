# API 응답 검증 보고서 (API Response Validation)

작성일: 2026-08-21
검증 방법: 실제 발급받은 인증키로 두 API를 각각 **목록조회 5건 + 상세조회 1건** 호출하여 성공적으로 받은 원본 응답을 기준으로 작성했다.
API 인증키는 `.env`에서만 읽었으며, 이 문서/코드/로그 어디에도 키 값을 기록하지 않았다.

원본 응답 저장 위치:
- `data/raw/central_welfare_sample.xml` (중앙부처, 목록 5건)
- `data/raw/central_welfare_detail_sample.xml` (중앙부처, 상세 1건 — servId=WLF00000024 "아이돌봄서비스")
- `data/raw/local_welfare_sample.xml` (지자체, 목록 5건)
- `data/raw/local_welfare_detail_sample.xml` (지자체, 상세 1건 — servId=WLF00006657 "보훈명예수당", 경상북도 영주시)

---

## 1. API 연결 성공 여부

| API | 목록조회 | 상세조회 |
|---|---|---|
| 중앙부처복지서비스 | **성공** (HTTP 200, resultCode=0, resultMessage=SUCCESS, totalCount=461) | **성공** (HTTP 200, resultCode=0, SUCCESS) |
| 지자체복지서비스 | **성공** (HTTP 200, resultCode=0, SUCCESS, totalCount=4770) | **성공** (HTTP 200, resultCode=0, SUCCESS) |

두 API 모두 실제 인증키로 정상 호출되며, 발급 즉시(별도 승인 대기 없이) 사용 가능함을 확인했다(이전 보고서에서 확인한 "자동승인"과 일치).

**검증 도중 발견하고 조치한 문제**: 중간에 시도한 호출(검색어 "영양" 테스트)에서 `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`(HTTP 403, returnReasonCode=30)가 발생했다. 원인은 `.env` 파일의 두 키 값이 큰따옴표로 감싸인 채 **줄바꿈 문자를 포함한 상태**(`"키값\n"` 형태)로 저장되어 있었기 때문으로, 실제 요청 URL에 `serviceKey=...%0A`처럼 개행문자가 인코딩되어 붙어 인증이 실패했다. **키 값 자체는 보지 않고** 따옴표와 개행만 제거하는 방식으로 `.env` 포맷을 수정했고, 이후 재호출로 정상 작동을 확인했다(아래 결과는 모두 수정 후 재검증한 결과다).

---

## 2. 실제 사용한 Endpoint (공식 Swagger 문서를 코드로 직접 파싱해 확인, 페이지 요약이 아님)

| API | Base URL | 목록조회 | 상세조회 |
|---|---|---|---|
| 중앙부처복지서비스 | `https://apis.data.go.kr/B554287/NationalWelfareInformationsV001` | `GET /NationalWelfarelistV001` | `GET /NationalWelfaredetailedV001` |
| 지자체복지서비스 | `https://apis.data.go.kr/B554287/LocalGovernmentWelfareInformations` | `GET /LcgvWelfarelist` | `GET /LcgvWelfaredetailed` |

### 요청 파라미터 (실제 호출로 검증됨)

**중앙부처 — 목록조회** (`callTp`, `pageNo`, `numOfRows`, `srchKeyCode`가 Swagger상 **필수**로 명시되어 있고, 실제로 이 값들을 모두 채워야 성공함을 확인)
`serviceKey`(필수), `callTp`(필수, L=목록/D=상세), `pageNo`(필수), `numOfRows`(필수, 최대 500), `srchKeyCode`(필수, 001 제목/002 내용/003 제목+내용), `searchWrd`(옵션), `age`(옵션), `lifeArray`/`trgterIndvdlArray`/`intrsThemaArray`(옵션, 코드표 참조), `onapPsbltYn`(옵션), `orderBy`(옵션)

**중앙부처 — 상세조회**: `serviceKey`(필수), `callTp`(필수, D), `servId`(필수)

**지자체 — 목록조회** (실제로 `serviceKey`만 있어도 성공, 나머지는 모두 옵션임을 확인)
`serviceKey`(필수), `pageNo`/`numOfRows`(옵션), `ctpvNm`(옵션, **시도명**), `sggNm`(옵션, **시군구명**), `age`(옵션), `lifeArray`/`trgterIndvdlArray`/`intrsThemaArray`(옵션), `searchWrd`/`srchKeyCode`(옵션), `arrgOrd`(옵션)

**지자체 — 상세조회**: `serviceKey`(필수), `servId`(필수)

---

## 3. 실제 반환 형식

**두 API 모두 XML만 반환한다.** Swagger 문서의 `produces`에 `application/xml`만 명시되어 있고, 실제 응답의 `Content-Type` 헤더도 `application/xml`이었다. `type=json` 같은 비공식 파라미터는 테스트하지 않았다(공식 명세에 없는 옵션에 의존하지 않기 위함). **JSON은 지원하지 않는 것으로 확정한다.**

---

## 4. 목록조회 필드 (실제 응답 확인)

### 중앙부처 (`wantedList > servList`, 5건 확인)
`servId`, `servNm`, `servDgst`(서비스 요약), `servDtlLink`(복지로 원문 URL), `jurMnofNm`(소관부처명), `jurOrgNm`(소관조직명), `lifeArray`(생애주기, 예: `"청년,중장년,노년"`), `trgterIndvdlArray`(가구유형, 예: `"장애인,저소득"`), `intrsThemaArray`(관심주제, 예: `"생활지원,일자리,서민금융"`), `onapPsbltYn`(온라인신청가능, Y/N), `rprsCtadr`(문의처, 예: `"129"`), `sprtCycNm`(지원주기), `srvPvsnNm`(제공유형), `svcfrstRegTs`(서비스 등록일), `inqNum`(조회수)

**중요 확인**: `lifeArray`에 실제로 `"노년"`이라는 한글 값이 그대로 들어있음을 확인했다(코드가 아니라 사람이 읽을 수 있는 문자열). 이전 보고서에서 "코드표 미확인이라 고령자 필터링 가능 여부 불확실"이라고 판단했는데, **실제로는 코드표 없이도 `lifeArray` 문자열에 `"노년"` 포함 여부로 필터링이 가능하다.**

지원대상/선정기준/지원내용/신청방법/근거법령은 **목록조회에 없다.**

### 지자체 (`servList`, 5건 확인)
`servId`, `servNm`, `servDgst`, `servDtlLink`, `ctpvNm`(시도명), `sggNm`(시군구명, **일부 시도 단위 사업은 값이 비어 있음을 확인** — 예: "전남광주통합특별시" 사업 중 시군구가 지정되지 않은 건 존재), `bizChrDeptNm`(사업담당부서명), `aplyMtdNm`(신청방법명, 예: `"방문"`, `"방문, 전화"`), `lastModYmd`(최종수정일자), `lifeNmArray`(생애주기명, 옵션 — 값이 없는 항목도 있었음), `trgterIndvdlNmArray`(가구상황명, 옵션), `intrsThemaNmArray`(관심주제명, 옵션), `sprtCycNm`, `srvPvsnNm`, `inqNum`

**목록조회 단계에서 이미 신청방법명(`aplyMtdNm`)·지역(`ctpvNm`/`sggNm`)·최종수정일(`lastModYmd`)까지 확인된다** — 중앙부처 목록조회보다 정보가 더 풍부하다.

지원대상/선정기준/지원내용/신청방법 상세/문의처/근거법령은 **목록조회에 없다.**

---

## 5. 상세조회 필드 (실제 응답 확인)

### 중앙부처 (`wantedDtl`, servId=WLF00000024 "아이돌봄서비스")
`servId`, `servNm`, `jurMnofNm`, `tgtrDtlCn`(대상자 상세내용, 긴 자연어 텍스트), `slctCritCn`(선정기준 내용, 긴 자연어 텍스트), `alwServCn`(급여서비스 내용), `crtrYr`(기준연도, 예: `"2026"`), `rprsCtadr`(문의처), `wlfareInfoOutlCn`(서비스요약), `sprtCycNm`, `srvPvsnNm`, `lifeArray`, `trgterIndvdlArray`, `intrsThemaArray`, `applmetList`(신청 절차 목록: 신청기관/조사기관/결정기관/이의신청접수기관별 안내가 반복 요소로 들어옴), `inqplCtadrList`(문의처명 + 전화번호), `inqplHmpgReldList`(사이트명 + URL), `basfrmList`(서식/자료명 + **다운로드 가능한 PDF 링크**, 실제로 "2026년 아이돌봄 지원사업 안내.pdf" 링크 확인됨), `baslawList`(근거법령명), `resultCode`, `resultMessage`

**중요 확인**: 목록조회에 있던 `servDtlLink`(복지로 원문 URL)와 `svcfrstRegTs`(서비스 등록일)는 **상세조회 응답에는 없다.** 원문 URL이 필요하면 목록조회 응답을 함께 보관해야 한다.

**중요 확인**: `applmetList`의 실제 내용은 필드 설명("서비스 이용 및 신청방법")과 다르게, `servSeDetailNm`에는 "신청기관연락처목록"/"조사기관연락처목록"/"결정기관연락처목록"/"이의신청접수기관연락처목록" 같은 **범주명**이, `servSeDetailLink`에는 실제 안내 문장(예: "거주지 읍/면/동 주민센터... '서비스 신청'")이 들어있다. 즉 필드명의 의미와 실제 값의 역할이 문서 설명과 다르게 조합되어 있어, **자동 파싱 시 실제 값을 보고 판단해야 한다.**

### 지자체 (servId=WLF00006657 "보훈명예수당", 경상북도 영주시)
`resultCode`, `resultMessage`, `servId`, `servNm`, `enfcBgngYmd`(시행시작일자, 예: `"20140101"`), `enfcEndYmd`(시행종료일자, 예: `"99991231"`), `bizChrDeptNm`, `ctpvNm`, `sggNm`, `servDgst`, `trgterIndvdlNmArray`, `intrsThemaNmArray`, `sprtCycNm`, `srvPvsnNm`, `aplyMtdNm`, `sprtTrgtCn`(지원대상 내용), `slctCritCn`(선정기준 내용, 이 샘플에서는 `"기준 없음"`이라는 값도 실제로 존재함을 확인 — 즉 일부 서비스는 선정기준이 없다는 사실 자체가 유효한 데이터임), `alwServCn`, `aplyMtdCn`(신청방법 내용), `inqNum`, `lastModYmd`, `inqplCtadrList`(문의처명 + 전화번호, 필드명은 `wlfareInfoReldNm`/`wlfareInfoReldCn`으로 **중앙부처와 다름**), `baslawList`(근거법령명)

**중요 확인**: `enfcEndYmd`(시행종료일자)에 `"99991231"`이라는 값이 실제로 나타난다. 이는 "무기한/상시 운영"을 뜻하는 관례적 표기로 보인다. **`enfcEndYmd`가 존재한다고 해서 곧 종료 예정이라고 해석하면 안 되며, `"99991231"`(또는 이에 준하는 먼 미래 날짜)은 "종료일 미정/상시"로 처리해야 한다.**

**중요 확인**: 지자체 API의 하위 리스트(`inqplCtadrList`, `baslawList` 등)는 중앙부처와 필드명이 다르다(`wlfareInfoReldNm`/`wlfareInfoReldCn`/`wlfareInfoDtlCd` vs 중앙부처의 `servSeCode`/`servSeDetailNm`/`servSeDetailLink`). **두 API의 파서를 절대 공유하면 안 된다.**

---

## 6. 목록조회 vs 상세조회 차이 요약

| 정보 | 중앙부처 목록 | 중앙부처 상세 | 지자체 목록 | 지자체 상세 |
|---|---|---|---|---|
| 지원대상/선정기준/지원내용 | X | O | X | O |
| 신청방법 | X | O(applmetList) | O(명칭만, aplyMtdNm) | O(명칭+내용, aplyMtdNm/aplyMtdCn) |
| 문의처(전화번호) | O(rprsCtadr만) | O(구조화) | X | O(구조화) |
| 지역(시도/시군구) | 해당없음(전국사업) | 해당없음 | O | O |
| 원문 URL(servDtlLink) | O | **X (상세엔 없음)** | O | **X (상세엔 없음)** |
| 시행시작/종료일 | X | X (필드 자체 없음) | X | O |
| 근거법령 | X | O | X | O |

**결론**: 서비스 후보를 "찾아서 목록으로 보여주는 단계"에서는 목록조회만으로 부족하고, "왜 후보인지/신청방법/문의처까지 보여주는 단계"에서는 반드시 상세조회를 추가로 호출해야 한다. 또한 **원문 URL(official_url)을 상세조회 시점에도 쓰려면 목록조회 때 받은 `servDtlLink`를 미리 저장해 둬야 한다** (상세조회 응답에는 없으므로).

---

## 7. 지역 필터링 가능 여부

- **중앙부처복지서비스**: 지역 필터 자체가 없다(전국 대상 서비스이므로 설계상 당연함).
- **지자체복지서비스**: `ctpvNm="서울특별시"`로 실제 필터 호출을 검증했다. **정상 작동을 확인**했다(HTTP 200, resultCode=0, `totalCount=395`로 필터가 적용되지 않은 전체 4,770건과 다른 값이 나와 실제로 필터링되고 있음을 확인). 반환된 5건 모두 `ctpvNm`이 "서울특별시"였고, `sggNm`은 시 단위 사업일 경우 비어 있었다(예: "희망두배 청년통장").
- 응답에 포함된 `ctpvNm`/`sggNm` 값의 표기 중 **"전남광주통합특별시"**처럼 통상 알려진 시도명(전라남도/광주광역시)과 다른 표기가 실제로 존재함을 확인했다. 이는 데이터가 최신 행정구역 개편(통합 등)을 반영한 것일 수도, 소관 기관의 입력 오류일 수도 있어 **원인을 확정하지 못했다** — `region_sido` 표준화 시 이 표기를 그대로 신뢰하지 말고 별도 매핑표를 만들 필요가 있다.

---

## 8. Pagination 방식

`pageNo`(페이지 번호, 1부터 시작) + `numOfRows`(페이지당 건수) 방식. 중앙부처는 `numOfRows` 최대 500까지 명시되어 있고, `totalCount`로 전체 건수를 알 수 있다(이번 테스트에서 중앙부처 461건, 지자체 4770건 확인). 지자체는 최대값이 Swagger에 명시되어 있지 않아 **다음 단계에서 큰 값(예: 1000)으로 시도해 실제 상한을 확인해야 한다.**

---

## 9. 영양돌봄 프로젝트에 실제 사용할 수 있는 필드

| 우리 필드 | 중앙부처 API | 지자체 API |
|---|---|---|
| service_id | `servId` | `servId` |
| service_name | `servNm` | `servNm` |
| service_description | `servDgst`/`wlfareInfoOutlCn` | `servDgst` |
| provider / 담당기관 | `jurMnofNm`/`jurOrgNm` | `bizChrDeptNm` |
| region_sido / region_sigungu | 없음(전국) | `ctpvNm`/`sggNm` |
| qualitative_eligibility(지원대상) | `tgtrDtlCn` | `sprtTrgtCn` |
| 선정기준 | `slctCritCn` | `slctCritCn` |
| 지원내용 | `alwServCn` | `alwServCn` |
| application_method | `applmetList` (텍스트에서 추출 필요) | `aplyMtdNm`/`aplyMtdCn` |
| contact_phone | `inqplCtadrList` | `inqplCtadrList`(필드명 다름) |
| official_url | 목록의 `servDtlLink` | 목록의 `servDtlLink` |
| 근거법령 | `baslawList` | `baslawList` |
| operation_period | 없음 | `enfcBgngYmd`/`enfcEndYmd` |
| source_updated_date | `svcfrstRegTs`(등록일, 목록에만) | `lastModYmd`(최종수정일) |
| 고령자 필터링 단서 | `lifeArray`에 `"노년"` 포함 여부 | `lifeNmArray`에 `"노년"` 포함 여부(옵션 필드라 값이 없는 항목도 있음) |

---

## 10. 부족한 필드 (추측하지 않고 명시)

- **영양사 참여 여부(`nutritionist_involvement`)**: 두 API 어디에도 전용 필드가 없다. `alwServCn`/`sprtTrgtCn` 같은 자연어 텍스트 안에 "영양사"라는 단어가 있는지 직접 찾아야 한다. `searchWrd="영양"`으로 실제 검색해 중앙부처 6건(예: "영양플러스 사업", "농식품바우처", "통합건강증진사업"), 지자체 29건을 확인했지만, 이번에 열어본 상세 샘플(지자체 "저소득층 생신 축하해드리기")에는 "영양사"라는 단어가 없었다 — **이는 "영양사가 없다"는 뜻이 아니라 "이 표본에 우연히 없었다"는 뜻**이며, 진짜 영양 상담·영양 교육류 서비스의 상세조회를 별도로 열어봐야 확정할 수 있다.
- **키워드 검색의 정밀도 한계(실제로 확인됨)**: `searchWrd="영양"` 지자체 검색 결과 중 "저소득층 생신 축하해드리기"가 포함되어 있었는데, 실제 매칭 이유는 지원내용(`alwServCn`)에 있는 **"영양떡"**이라는 단어 때문이었다. 즉 `searchWrd`는 단순 부분 문자열 검색이라 **재현율은 높지만 정밀도가 낮다** — 검색 결과를 그대로 서비스 후보로 쓰지 말고, 사람(또는 LLM)이 실제 내용을 보고 관련성을 다시 판단해야 한다.
- **긍정적으로 확인된 점**: 지자체 상세조회의 `slctCritCn`(선정기준)에 **"독거노인"**이라는 문구가 실제 원문 그대로 존재하는 것을 확인했다(예시 서비스: "저소득층 생신 축하해드리기"). 이는 `single_household_required` 같은 우리 필드를 텍스트 매칭으로 채울 수 있는 실마리가 된다는 뜻이다.
- **연령(min_age/max_age) 숫자 필드**: 없다. `tgtrDtlCn`/`sprtTrgtCn` 자연어 안에 "12세 이하", "65세 이상" 같은 표현으로만 존재한다(이번 상세조회 샘플에서 "아동의 연령이 12세 이하" 문장으로 실제 확인).
- **소득조건(income_rule) 숫자 필드**: 없다. 자연어 텍스트 안에 "기준 중위소득 250% 이하" 같은 문장으로만 존재한다(실제 확인).
- **service_type(우리 6개 분류) 매핑 코드**: 없다. `intrsThemaArray`(관심주제)가 있지만 이번 5건에서 나온 값(`"보육,보호·돌봄"`, `"생활지원,일자리,서민금융"`, `"서민금융"` 등)은 우리 6개 분류와 1:1 대응하지 않는다. **서비스명·설명을 사람이 읽고 수작업으로 분류해야 한다.**
- **지역명 표준화**: `ctpvNm`/`sggNm` 값의 표기가 행정안전부 표준 명칭과 항상 일치하는지 검증되지 않았다(예: "전남광주통합특별시" 같은 표기 확인 — 행정구역 개편 여부 확인 필요).

---

## 11. 다음 데이터 수집 단계에서 주의할 점

1. **`.env` 파일 포맷 문제(이번에 실제로 발생)**: 값에 큰따옴표를 쓰거나 값 끝에 빈 줄이 들어가면 python-dotenv가 개행문자까지 값의 일부로 읽어 `serviceKey=...%0A`가 되어 인증 실패(`SERVICE_KEY_IS_NOT_REGISTERED_ERROR`, HTTP 403)가 발생한다. **`.env`에는 `CENTRAL_WELFARE_API_KEY=키값`처럼 따옴표 없이, 줄 끝에 공백/빈 줄 없이 한 줄로만 입력해야 한다.**
2. `applmetList`/`inqplCtadrList` 등 하위 리스트의 실제 값 배치가 필드 설명과 다를 수 있으므로, 자동 파싱 로직은 실제 값을 보고 검증하며 만들어야 한다.
3. 중앙부처와 지자체 API의 하위 리스트 필드명이 서로 다르다(`servSeCode/servSeDetailNm/servSeDetailLink` vs `wlfareInfoDtlCd/wlfareInfoReldNm/wlfareInfoReldCn`) — 파서를 분리해서 작성해야 한다.
4. `enfcEndYmd="99991231"`처럼 "먼 미래 날짜 = 상시/무기한"을 뜻하는 관례적 표기가 있으므로, 종료 여부 판단 로직에서 이를 특별 처리해야 한다.
5. 지자체 목록조회의 `numOfRows` 상한이 공식 문서에 없으므로, 실제 대량 수집 전에 상한을 별도로 확인해야 한다.
6. 지역 필터(`ctpvNm="서울특별시"`)는 실제 호출로 검증 완료했다(6번 항목 참고). 다만 `sggNm`까지 동시에 지정하는 조합, 그리고 `ctpvNm` 표기가 실제 표준 시도명과 다른 경우(위 "전남광주통합특별시" 사례)의 처리 방식은 추가 검증이 필요하다.
7. `searchWrd="영양"` 키워드 검색도 실제 호출로 검증 완료했다(중앙 6건/지자체 29건 확인). 다만 위에서 확인했듯 부분 문자열 매칭이라 오탐(예: "영양떡")이 섞이므로, 다음 단계에서는 검색 결과를 그대로 신뢰하지 않고 상세조회 원문으로 재확인하는 절차를 반드시 포함해야 한다. "영양플러스 사업"이 실제로 `lifeArray="영유아,임신 · 출산"`로 반환되어, 이전 조사에서 "고령자 대상이 아님"이라고 판단했던 것이 API 데이터로도 재확인됐다.

---

## 12. 최종 판단

## GO

**이유**:
- 두 API 모두 실제 인증키로 정상 연결되며(HTTP 200, resultCode=0), 목록조회·상세조회 모두 우리 서비스에 필요한 핵심 필드(지원대상, 선정기준, 지원내용, 신청방법, 문의처, 담당기관, 근거법령, 지자체는 지역·시행기간까지)를 실제로 반환하는 것을 원본 응답으로 확인했다.
- 지역 필터(`ctpvNm`)와 키워드 검색(`searchWrd`)도 실제 호출로 검증했다 — 지자체 API에서 시도 단위 필터링이 실제로 동작하고, 키워드 검색으로 영양 관련 서비스(영양플러스 사업, 통합건강증진사업 등)를 실제로 찾아냈다.
- `.env` 포맷 오류(따옴표+개행으로 인한 인증키 손상)를 실제로 겪었고 원인을 특정해 조치했다 — 이는 앞으로도 재발할 수 있는 운영 리스크이므로 아래 "다음 조치"에 재발 방지 방법을 포함했다.
- 부족한 부분(영양사 여부, 연령/소득의 숫자화, service_type 매핑, 키워드 검색의 낮은 정밀도)은 API의 구조적 한계이지 연결 실패가 아니며, 자연어 텍스트를 사람이 확인하는 반자동(SEMI_AUTO) 절차로 보완 가능하다는 것이 이전 보고서의 결론과 일치한다.
- 연결·구조·필터·검색까지 모두 실제 호출로 검증을 마쳤으므로, **다음 단계(검색어·지역 기반 후보 수집)로 바로 진행해도 좋다.**
