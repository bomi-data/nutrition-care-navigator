# 데이터 소스 조사 계획 (Data Source Plan)

작성일: 2026-08-21
작성 범위: 「우리동네 영양돌봄 내비게이터」 MVP를 위한 데이터 소스 조사 결과
작성 원칙: 아래 표의 모든 항목은 실제 웹 검색 및 공식 페이지(WebFetch) 확인을 통해 존재를 확인한 것만 기재한다.
존재를 추정했거나 문서를 직접 열어보지 못한 항목은 "비고"란에 **미확인**으로 명시한다.

## 범례

- **수집 방식**: `OPEN_API` / `CSV_DOWNLOAD` / `OFFICIAL_WEB` / `PDF` / `MANUAL_REQUIRED` / `UNSUITABLE`
- **자동수집 가능 여부**: `AUTO`(Python/API로 자동 확보 가능) / `SEMI_AUTO`(공식 웹·PDF에서 추출 후 사람 검증 필요) / `MANUAL`(사용자 직접 작업 필요)
- **신뢰도**: 3장(verification_level 사전판단 기준 A/B/C)과 동일한 기준을 적용한 잠정 등급. 실제 등급은 개별 서비스 데이터 입력 시 원문 대조 후 최종 확정한다.

---

## 0. 지역 표준 데이터 (시도 / 시군구 / 행정구역코드)

| 데이터명 | 데이터 목적 | 제공기관 | 공식 출처 | 수집 방식 | API 존재 | 인증키 | 파일 형식 | 자동수집 | 예상 활용 필드 | 최신성 | 신뢰도 | 우선순위 | 비고 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 행정안전부_행정표준코드_법정동코드 | `region_sido`/`region_sigungu`/`region_code` 표준화 | 행정안전부 | [data.go.kr/data/15077871/openapi.do](https://www.data.go.kr/data/15077871/openapi.do) (엔드포인트: `apis.data.go.kr/1741000/StanReginCd`) | OPEN_API | Y | Y (공공데이터포털 발급) | JSON/XML | AUTO | region_sido, region_sigungu, region_code | 상시(법정동 변경 반영) | A | 최상 (필수 기반데이터) | 개발계정 10,000건/일. 활용신청 승인 필요 |
| 국가데이터처(통계청)_SGIS 행정구역 통계 및 경계 | 위 API의 보조/검증용 CSV | 국가데이터처(통계청) | [data.go.kr/data/15129688/fileData.do](https://www.data.go.kr/data/15129688/fileData.do) | CSV_DOWNLOAD | 별도 SGIS Data API 존재(미상세조사) | 파일 다운로드는 로그인 필요 여부 미확인 | CSV/SHP | SEMI_AUTO | region_sido, region_sigungu, region_code | 연 1회(2025.06.30 기준본 확인) | A | 중 (보조) | 경계(SHP)는 본 프로젝트에 불필요, CSV만 활용 |
| 행정안전부_행정표준코드_전체코드_다운로드 | 법정동코드 외 전체 표준코드 일괄 확보(대안) | 행정안전부 | [data.go.kr/data/15092039/fileData.do](https://www.data.go.kr/data/15092039/fileData.do) | CSV_DOWNLOAD | - | 미확인 | 미확인(제목상 파일데이터) | SEMI_AUTO | region_sido, region_sigungu, region_code | 2023-11-06 등록본 확인 | B (최신 파일 재확인 필요) | 중 | API(위 항목)가 더 최신일 가능성 높음. 실제 사용 전 재확인 필요 |

**결론**: 지역 표준 데이터는 행정안전부 법정동코드 Open API를 1순위로 사용하고, SGIS 파일데이터로 교차검증한다. **AUTO로 확보 가능**하나 공공데이터포털 활용신청(승인) 절차가 필요하다.

---

## A. 전국 공통 공공서비스 — 구조화 데이터(API)

| 데이터명 | 데이터 목적 | 제공기관 | 공식 출처 | 수집 방식 | API 존재 | 인증키 | 파일 형식 | 자동수집 | 예상 활용 필드 | 최신성 | 신뢰도 | 우선순위 | 비고 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 한국사회보장정보원_중앙부처복지서비스 | 중앙부처 시행 복지사업(영양/식사/돌봄 포함) 목록+상세 확보 | 한국사회보장정보원(복지로) | [data.go.kr/data/15090532/openapi.do](https://www.data.go.kr/data/15090532/openapi.do) | OPEN_API | Y | Y | XML | AUTO | service_name, provider, service_description, 지원대상, 선정기준, application_method, contact_phone, service_type 후보 | 상시 갱신(복지로 연동) | B→A(원문 대조 후 상향) | 최상 | 상세조회에서 지원대상·선정기준·신청방법·문의처·서비스분야·소관기관 제공 확인(WebFetch로 API 설명 확인). 개발계정 100건/일 |
| 한국사회보장정보원_지자체복지서비스 | 지자체 시행 복지사업(영양/식사/돌봄 포함) 목록+상세, **시군구 단위** 확보 | 한국사회보장정보원(복지로) | [data.go.kr/data/15108347/openapi.do](https://www.data.go.kr/data/15108347/openapi.do) | OPEN_API | Y | Y | XML | AUTO | 위와 동일 + **시군구 지역정보** | 상시 갱신 | B→A | 최상 | 지자체 사업의 전국 확장에 가장 핵심적인 데이터. 개발계정 1,000건/일. 코드표·SWAGGER 문서 제공 확인 |
| 한국사회보장정보원_복지서비스정보 (파일) | 위 API의 스냅샷 CSV, 서비스 존재 여부 스크리닝용 | 한국사회보장정보원 | [data.go.kr/data/15083323/fileData.do](https://www.data.go.kr/data/15083323/fileData.do) | CSV_DOWNLOAD | - | 무료 다운로드(회원가입 필요 여부는 미확인) | CSV | SEMI_AUTO | service_id 후보, service_name, provider, official_url, contact_phone | 2025-07-22 등록, 연 1회 | B (요약 수준, 세부 자격조건 없음) | 중 | 367건. 세부 자격조건이 없어 1차 스크리닝 용도로만 사용, 최종 데이터는 API/원문 대조 필요 |
| 한국사회보장정보원_사회복지시설정보서비스 | 시설 기반 서비스(경로식당 등 포함 여부 확인 필요)의 시설명·주소·연락처 | 한국사회보장정보원 | [data.go.kr/data/15001848/openapi.do](https://www.data.go.kr/data/15001848/openapi.do) | OPEN_API | Y | Y | XML | AUTO | provider, application_location, contact_phone, region | 미확인 | A(시설정보 자체는 공식) | 중 | "시설종류코드 조회" 서비스로 시설유형 확인 가능. 급식지원시설 코드 포함 여부는 **추가 확인 필요(미확인)** |
| 전국사회복지시설표준데이터 | 전국 사회복지시설 표준 데이터(지자체 개방의무 표준데이터) | 한국사회보장정보원 / 각 지자체 | [data.go.kr/data/15096296/standard.do](https://www.data.go.kr/data/15096296/standard.do) | OPEN_API | Y | Y | XML | AUTO | provider, application_location, contact_phone, region | 미확인(지자체별 갱신) | A | 중 | "노인의료복지시설" 등 일부 유형 확인됨. 경로식당/재가노인복지시설 포함 여부는 **추가 확인 필요(미확인)** |

**결론**: 이 그룹이 이번 MVP의 **핵심 자동수집 대상**이다. 특히 중앙부처복지서비스·지자체복지서비스 API는 지원대상·선정기준·신청방법·문의처를 모두 제공한다고 공식 문서에서 확인했다. 다만 API 응답은 여전히 "1차 원문"이므로, `verification_level A` 부여 전에는 응답에 포함된 `official_url`(복지로 등)로 재대조하는 검증 절차가 필요하다.

---

## B. 전국 공통 공공서비스 — 개별 서비스 원문 / PDF (RAG·근거 자료용)

| 데이터명 | 데이터 목적 | 제공기관 | 공식 출처 | 수집 방식 | 자동수집 | 예상 활용 필드 | 최신성 | 신뢰도 | 우선순위 | 비고 |
|---|---|---|---|---|---|---|---|---|---|---|
| 복지로 서비스 상세페이지 | 서비스별 지원대상·신청방법·문의처 원문(최종 근거) | 보건복지부/한국사회보장정보원 | bokjiro.go.kr (서비스별 URL, 예: [WLF00004001](https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId=WLF00004001)) | OFFICIAL_WEB | **MANUAL_REQUIRED** | official_url, 전체 대상조건, application_method, contact_phone | 상시 | A(육안 확인 시) | 최상 | **실제 WebFetch 테스트 결과** 정적 HTML에 텍스트가 없고 JavaScript 렌더링이 필요함을 확인. 자동 스크래핑 불가 → 브라우저 자동화(별도 승인 필요) 또는 사람이 직접 열람 필요 |
| 정부24(gov.kr) 민원안내 페이지 | 복지로 접근 실패 시 대체 원문(신청방법·자격요건·문의처) | 행정안전부/보건복지부 | 예: [gov.kr 노인맞춤돌봄서비스 신청](https://www.gov.kr/mw/AA020InfoCappView.do?CappBizCD=13520000045) | OFFICIAL_WEB | SEMI_AUTO | application_method, contact_phone, qualitative_eligibility | 상시 | A | 상 | WebSearch로 신청자격·신청방법·문의처(129) 확인. 페이지별 정적 접근 가능 여부는 개별 확인 필요 |
| 찾기쉬운 생활법령정보 | 제도의 법적 근거 설명(RAG 보조) | 법제처 | easylaw.go.kr | OFFICIAL_WEB | SEMI_AUTO | official_url, service_description, source_organization | 상시 | A(법령 자체) | 중 | 실무 신청정보(전화번호 등)는 최신이 아닐 수 있어 실무 필드의 1차 근거로는 사용하지 않음 |
| 2026년 노인맞춤돌봄서비스 사업안내 | service_type=`community_care`/`meal_support` 관련 서비스유형(식사관리, 퇴원환자 단기지원 시 영양지원 등) 상세 확인 | 보건복지부 / 한국노인인력개발원(수탁) | [1661-2129.or.kr 다운로드](https://www.1661-2129.or.kr/download/2026%EB%85%84%20%EB%85%B8%EC%9D%B8%EB%A7%9E%EC%B6%A4%EB%8F%8C%EB%B4%84%EC%84%9C%EB%B9%84%EC%8A%A4%20%EC%82%AC%EC%97%85%EC%95%88%EB%82%B4.pdf) / [mohw.go.kr 게시글(2025년판)](https://www.mohw.go.kr/board.es?mid=a10411010100&bid=0019&act=view&list_no=1484224) | PDF | SEMI_AUTO | service_description, qualitative_eligibility, nutritionist_involvement 판단 근거 | 연 1회 개정 | A | 최상 | 서비스유형에 "식사관리", "퇴원환자 단기집중서비스(영양지원 포함)"가 명시됨을 검색으로 확인. **본문 전체는 아직 열람하지 않음 — PDF 원문 확보 후 재확인 필요** |
| 지역사회 통합돌봄 전용 누리집 및 보도자료 | service_type=`community_care`, `discharge_support` 정의 및 전국 시행 현황 | 보건복지부 | [mohw.go.kr/integratedcare](https://www.mohw.go.kr/integratedcare/) | OFFICIAL_WEB/PDF | SEMI_AUTO | service_description, operation_period, source_updated_date | 2026-03-27 법 전면시행 예정(진행 중) | B(전국 시행 초기, 지자체별 세부 미확정) | 상 | 2026-03-27 전면 시행 예정 확인. **지자체별 실제 운영 여부·신청창구는 개별 확인 전까지 A등급 부여 금지** |
| 급성기 환자 퇴원지원 및 지역사회 연계활동 시범사업 지침 | service_type=`discharge_support` 정의 및 운영기준 | 건강보험심사평가원/보건복지부 | [hira.or.kr PDF](https://www.hira.or.kr/bbs/157/2025/01/BZ202501141057184.pdf) | PDF | SEMI_AUTO | service_description, application_method(병원 경유) | 2025-01 개정판 확인 | A(지침 자체) | 중 | 참여 병원 목록이 별도 공개되어 있는지는 **미확인**. 병원 단위 서비스로 만들 경우 신청정보(병원별)가 부족할 수 있음 |

---

## C. 지역별 서비스 (지자체 개별 시행, 전국 통합 데이터 없음)

| 데이터명 | 데이터 목적 | 제공기관 | 공식 출처(예시) | 수집 방식 | 자동수집 | 신뢰도 | 우선순위 | 비고 |
|---|---|---|---|---|---|---|---|---|
| 저소득 재가노인 식사배달 / 무료급식(경로식당) / 도시락·밑반찬 배달 | service_type=`meal_support` 실사례 다수 확보 | 각 시군구(보건복지부 지침 기반, 운영은 지자체 재량) | 지자체 홈페이지, 복지로 지자체서비스, 일부는 지자체 열린데이터광장(예: [서울 열린데이터광장](https://data.seoul.go.kr)) | OFFICIAL_WEB | **MANUAL**(전국 통합 API/CSV 없음을 확인함) | 지자체 원문 확인 시 A, 미확인 시 B/C | 최상(MVP 핵심 서비스유형) | 전국 시군구(약 226개) 단위로 운영기관·이용요일·제공식수가 상이함을 확인. **전국 단일 출처가 존재하지 않는 것이 이번 조사의 가장 큰 리스크** |
| 방문건강관리사업(보건소, 영양상담 포함) | service_type=`home_visit` 실사례 확보 | 각 시군구 보건소 | 보건소별 개별 홈페이지(예: 강남구, 영등포구 등 확인) | OFFICIAL_WEB | MANUAL | 지자체 원문 확인 시 A | 상 | 대상자 정보는 지역보건의료정보시스템(PHIS) 내부 관리로 외부 공개 API 없음을 확인. 보건소별 페이지를 개별 조사해야 함 |
| 지역사회 통합건강증진사업(영양 분야) | service_type=`nutrition_counseling`/`nutrition_education` 후보 | 보건복지부(지침) / 각 시군구 보건소(운영) | [mohw.go.kr 안내서](https://www.mohw.go.kr/board.es?mid=a10411010100&bid=0019&act=view&list_no=1483973) | PDF + OFFICIAL_WEB(지자체) | SEMI_AUTO(지침) / MANUAL(지자체별 실제 프로그램) | B~C(전 연령 대상 사업이라 고령자 특화 여부 불명확) | 중 | 지침은 전국 공통이나, 실제 프로그램명·대상은 지자체 재량이라 개별 확인 없이는 A등급 불가 |

**결론**: 지역별 서비스는 자동수집이 사실상 불가능하다(MANUAL). 226개 시군구를 모두 조사하는 것은 이번 단계의 범위를 벗어나므로, **표본 지자체를 선정하는 전략에 대해 사용자 결정이 필요**하다(10장 참고).

---

## D. 조사했으나 이번 MVP에서 제외/보류하는 항목

| 데이터명 | 사유 | 분류 |
|---|---|---|
| 영양플러스사업 | 대상이 임산부·영유아(만 72개월 미만)로 확인됨. 고령자 대상이 아니므로 이번 서비스 목록에서 명시적으로 제외 | UNSUITABLE(고령자 무관) |
| 국민건강보험공단 장기요양기관 관련 데이터 | 신체수발·요양시설 중심으로 영양돌봄 핵심 범주 밖. 이번 MVP `service_type` 6종에 해당 사항 없음. 필요 시 추후 별도 논의 | 보류(범주 밖) |
| 한국사회보장정보원_민간복지서비스정보 | 민간(비영리단체 등) 제공 서비스로 공식성 검증 부담이 큼. 존재만 확인([data.go.kr/data/15116392](https://www.data.go.kr/data/15116392/fileData.do)), 이번 단계 미채택 | 보류 |
| 언론기사·블로그(검색 과정에서 다수 발견) | 서비스 "존재"를 알아차리는 단서로만 사용. 자격조건·전화번호 등 핵심 필드의 근거로 사용 금지 | UNSUITABLE(핵심 근거 불가) |

---

## 종합 판단

- **AUTO로 즉시 확보 가능**: 행정구역코드(0장), 중앙부처복지서비스·지자체복지서비스 API, 사회복지시설 관련 API(A장) — 단, 모두 공공데이터포털 활용신청(키 발급) 절차 필요
- **SEMI_AUTO(문서 확보 후 사람 검증 필요)**: 노인맞춤돌봄서비스 사업안내 PDF, 지역사회 통합돌봄 자료, 퇴원환자 연계사업 지침(B장)
- **MANUAL(사용자 작업 또는 개별 수작업 조사 필요)**: 복지로 상세페이지(JS 렌더링), 지자체별 급식지원사업 전수 조사(C장)
- **UNSUITABLE/제외**: 영양플러스사업, 언론기사·블로그 단독 근거(D장)
