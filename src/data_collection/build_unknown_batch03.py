"""
UNKNOWN(senior_relevance=unknown) 142건 중 batch01+batch02(60건, service_id 기준)를 제외한
나머지 82건 중, 산모·신생아 편중(50/82=61%)을 피하기 위해 층화 표집한 40건을 검토한다.

표집 방식:
- 비(非) 산모·신생아 32건 전부 포함 (장애인9 + 노인·고령자7 + 지역사회돌봄4 + 기타3 + 식사급식영양3
  + 아동청소년3 + 저소득층기타2 + 기관운영지원1)
- 산모·신생아 50건 중 체계적 표집(매 7번째, index 0,7,14,21,28,35,42,49) 8건

- 새 API 호출 없음, welfare_candidates_reviewed.csv/batch01/batch02 파일 모두 미수정.
- 산출물: data/processed/unknown_review_batch_03.csv
"""
import csv
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
REVIEWED_PATH = PROCESSED_DIR / "welfare_candidates_reviewed.csv"
BATCH01_PATH = PROCESSED_DIR / "unknown_review_batch_01.csv"
BATCH02_PATH = PROCESSED_DIR / "unknown_review_batch_02.csv"
OUT_PATH = PROCESSED_DIR / "unknown_review_batch_03.csv"

FIELDNAMES = [
    "service_id", "service_name", "region",
    "target_original", "criteria_original", "support_original",
    "senior_relation_v2", "nutrition_relevance", "review_status",
    "service_type_primary", "service_type_secondary",
    "classification_reason", "verification_level", "data_quality_note",
]

NON_MATERNAL_32 = [
    "WLF00001667", "WLF00004268", "WLF00006404", "WLF00006240", "WLF00001460", "WLF00001522", "WLF00001842", "WLF00002047", "WLF00000757",
    "WLF00002076", "WLF00001509", "WLF00003300", "WLF00004743", "WLF00006231", "WLF00000115", "WLF00005857",
    "WLF00005698", "WLF00005102", "WLF00006243", "WLF00005718",
    "WLF00001983", "WLF00003721", "WLF00006232",
    "WLF00002345", "WLF00006413", "WLF00000783",
    "WLF00006374", "WLF00000138", "WLF00004352",
    "WLF00002523", "WLF00003400",
    "WLF00006205",
]
MATERNAL_SAMPLE_8 = [
    "WLF00002434", "WLF00003818", "WLF00000315", "WLF00005669",
    "WLF00005721", "WLF00003627", "WLF00000438", "WLF00005287",
]
BATCH3_IDS = NON_MATERNAL_32 + MATERNAL_SAMPLE_8

DECISIONS = {
    "WLF00001667": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="장애인 및 장애인가족 대상(연령무관)이라 SENIOR_CONDITIONAL이나, 필라테스·스트레칭 등 건강교실로 식사·영양과 무관.", dq=""),
    "WLF00004268": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="", vl="A",
        reason="저소득 재가장애인 대상(연령무관)이라 SENIOR_CONDITIONAL. 매주 1회 밑반찬·반조리식품 제공이 명시돼 DIRECT_NUTRITION. 대상/기준/내용/신청/문의처 모두 명확해 A.", dq=""),
    "WLF00006404": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="수급자·차상위·한부모·장애인·기초연금수급자 등 여러 취약계층(연령무관, 기초연금수급자 포함으로 고령자 배제 없음)이라 SENIOR_CONDITIONAL이나, 저장강박증 가구 주거환경개선비 지원으로 식사·영양과 무관.", dq=""),
    "WLF00006240": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="community_care", vl="A",
        reason="안동시 통합돌봄 체계에서 선정된 대상자 중 식사배달 필요자(연령무관, 통합돌봄은 노인·장애인 등 포괄)라 SENIOR_CONDITIONAL. 유동식/일반식 등급·단가까지 명시돼 DIRECT_NUTRITION. 통합돌봄 하위서비스라 community_care를 보조 태그로 부여. 대상/기준/내용/신청/문의처 모두 상세해 A.", dq=""),
    "WLF00001460": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="재가 중증장애인 대상(연령무관)이라 SENIOR_CONDITIONAL이나, 월 3만원 생계보조수당(현금)으로 식사·영양과 무관.", dq=""),
    "WLF00001522": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="재가 중증장애인 대상(연령무관)이라 SENIOR_CONDITIONAL이나, 이동변기·기저귀 등 위생용품 지원으로 식사·영양과 무관.", dq=""),
    "WLF00001842": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="", vl="B",
        reason="저소득 장애인 대상(연령무관)이라 SENIOR_CONDITIONAL. '식사 제공'이 명시돼 DIRECT_NUTRITION이나 지원내용이 매우 간략해 B.", dq=""),
    "WLF00002047": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="", vl="B",
        reason="저소득 거동불편 장애인 대상(연령무관)이라 SENIOR_CONDITIONAL. 도시락 배달이 명시돼 DIRECT_NUTRITION이나 지원내용이 매우 간략해 B.", dq=""),
    "WLF00000757": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="기초수급·차상위 등록장애인 대상(연령무관)이라 SENIOR_CONDITIONAL이나, 주택 리모델링(경사로·화장실 개조 등)으로 식사·영양과 무관.", dq=""),
    "WLF00002076": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="", vl="A",
        reason="저소득 취약세대 중 '독거노인, 장애인 세대'가 선정기준에 명시돼 SENIOR_CONDITIONAL. 매월 밑반찬 재료 구입·조리·방문전달이 명시돼 DIRECT_NUTRITION. 대상인원(165가구)·신청방법·문의처 모두 명확해 A.", dq=""),
    "WLF00001509": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="home_visit", vl="A",
        reason="여러 하위서비스 중 이동목욕서비스 대상에 '노인'이 명시돼 SENIOR_CONDITIONAL. 밑반찬서비스(밑반찬·부식 전달 및 안부확인)가 명시돼 DIRECT_NUTRITION. 이동목욕 등 방문형 서비스도 포함돼 home_visit을 보조 태그로 부여. 대상/기준/내용/신청/문의처 모두 상세해 A.", dq=""),
    "WLF00003300": dict(sr="SENIOR_DIRECT", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="", vl="A",
        reason="'거동불편 저소득노인'이 target에 명시돼 SENIOR_DIRECT. 월 2회 이상 밑반찬 제공이 명시돼 DIRECT_NUTRITION. 대상/기준/내용/신청/문의처 모두 명확해 A.", dq=""),
    "WLF00004743": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="", vl="A",
        reason="'독거노인, 부자가정, 장애인가구 등' 저소득 소외계층 중 독거노인이 명시돼 SENIOR_CONDITIONAL. 밑반찬(300가구)·김장김치(200가구) 지원이 명시돼 DIRECT_NUTRITION. 대상인원까지 명확해 A.", dq=""),
    "WLF00006231": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="community_care", vl="A",
        reason="통합돌봄 대상자 중 식사준비 어려움·결식우려자(연령무관)라 SENIOR_CONDITIONAL. 선정기준에 '영양불균형으로 인해 건강 악화가 우려'라는 문구가 명시돼 DIRECT_NUTRITION 근거가 뚜렷함. 통합돌봄 하위서비스라 community_care를 보조 태그로 부여. 대상/기준/내용/신청/문의처 모두 상세해 A.", dq=""),
    "WLF00000115": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="", vl="B",
        reason="target에 '(노인,아동,장애인 급식 대상이 아닌 자)'라는 문구가 있으나, 이는 연령 자체를 배제하는 것이 아니라 '이미 다른 급식사업 수혜 중인 자'만 제외하는 중복지원 방지 조항으로 해석됨 — 다른 노인급식을 받지 않는 고령자는 여전히 대상이 될 수 있어 SENIOR_CONDITIONAL로 판단. 재가 도시락·반찬 지원이 명시돼 DIRECT_NUTRITION. 이례적인 제외 문구로 실제 적용 방식에 추가 확인 여지가 있어 B.", dq="target_original의 '(노인,아동,장애인 급식 대상이 아닌 자)' 문구가 연령 배제인지 중복지원 방지 조항인지 문면만으로는 다소 모호함."),
    "WLF00005857": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="community_care", s="meal_support", vl="A",
        reason="'돌봄이 필요한 노인, 장애인 등 부산시민 누구나'로 SENIOR_CONDITIONAL(노인 명시 포함). '(식사지원) 연 60식 범위 내 질병·거동불편 등으로 식사 및 식사준비가 어려운 사람 대상 식사 서비스 제공'이 명시돼 DIRECT_NUTRITION. '(퇴원환자 안심돌봄)'도 포함돼 있어 discharge_support 성격도 있으나 태그 슬롯 한계로 classification_reason에만 기록. 구군별 문의처까지 상세해 A.", dq=""),
    "WLF00005698": dict(sr="SENIOR_DIRECT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="'65세이상 기초생활수급자(차상위)'가 명시돼 SENIOR_DIRECT이나, 지원내용이 진료이송(택시·구급차)과 '가사·건강 돌봄'뿐이며 식사·영양이 원문에 구체적으로 명시되지 않아 NOT_NUTRITION_RELEVANT(추측 금지 원칙에 따라 '가사돌봄'에 식사가 포함된다고 임의로 판단하지 않음).", dq=""),
    "WLF00005102": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="community_care", s="meal_support", vl="A",
        reason="'돌봄이 필요한 광주시민 누구나'로 SENIOR_CONDITIONAL. 지원내용에 '2. 식사지원: 맞춤형 영양설계(전문 영양사 진단)/무료, 영양음식 조리·배달'이 명시돼 DIRECT_NUTRITION이며, **'전문 영양사 진단'이라는 문구가 원문에 직접 명시된 최초 사례**라 nutritionist_involvement=direct로 판단. 방문진료(건강지원)도 포함돼 있어 home_visit 성격도 있으나 태그 슬롯 한계로 기록만 함. 대상/기준/내용/신청/문의처 모두 매우 상세해 A.", dq=""),
    "WLF00006243": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="통합돌봄 체계 선정 대상자(연령무관)라 SENIOR_CONDITIONAL이나, '방문요양 서비스 제공'이라고만 되어 있고 식사·영양 내용이 원문에 없어 NOT_NUTRITION_RELEVANT(장기요양 재가급여 사례와 동일한 논리).", dq=""),
    "WLF00005718": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="community_care", s="meal_support", vl="A",
        reason="'돌봄이 필요한 수원시민(누구나)'로 SENIOR_CONDITIONAL. '식사지원: 기본적인 식생활 유지가 곤란한 경우, 도시락 제공(일반식, 죽식 제공)'이 명시돼 DIRECT_NUTRITION. 7대 15종 서비스, 다양한 신청경로까지 상세해 A.", dq="region 필드가 '경기도'만 있고 시군구(수원시)가 비어 있음 — 서비스명·문의처(수원시)로 보아 수원시 한정 사업으로 추정되나 sigungu 필드 누락."),
    "WLF00001983": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="18~39세 청년근로자로 명시. 고령자·영양 모두와 무관.", dq=""),
    "WLF00003721": dict(sr="SENIOR_CONDITIONAL", nr="SUPPORTIVE_NUTRITION", status="NEEDS_REVIEW", p="meal_support", s="", vl="",
        reason="'관외거주 행려자'는 연령 제한이 없어 고령자도 해당 가능(SENIOR_CONDITIONAL). 숙박비·교통비·급식비를 묶은 일회성 긴급구호이며, batch02의 유사 사례(WLF00001309 행려자 귀향여비 및 급식비)와 동일한 이유로 지속적 영양돌봄 서비스에 해당하는지 판단이 서지 않아 NEEDS_REVIEW로 남김(일관성 유지).", dq=""),
    "WLF00006232": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="퇴원(예정) 환자 지역사회 연계 대상(연령무관)이라 SENIOR_CONDITIONAL이나, support_original에 '* 급여서비스 없음'이라고 명시돼 있어 실제 제공되는 서비스 내용이 없다고 판단, service_type을 부여하지 않고 EXCLUDE.", dq="지원내용 필드에 '급여서비스 없음'이라고 명시돼 있어, 사업명(퇴원환자 지역사회 연계사업)만으로 discharge_support를 추측 부여하지 않음."),
    "WLF00002345": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="", vl="B",
        reason="고독사 등 고위험가구(연령 제한 명시 없음)라 SENIOR_CONDITIONAL. 반찬지원 및 안부확인(주1회)이 명시돼 DIRECT_NUTRITION. 신청방법 정보가 없어 B.", dq=""),
    "WLF00006413": dict(sr="NOT_SENIOR_RELEVANT", nr="DIRECT_NUTRITION", status="EXCLUDE", p="", s="", vl="",
        reason="연령기준에 '중장년: 40세~64세 1인가구'로 명시돼 65세 이상이 배제됨(batch01의 고독사 예방 밑반찬 사례와 동일 패턴). 도시락 관련 지역화폐 지급(DIRECT_NUTRITION 성격)이지만 대상관계 축에서 탈락.", dq="target_original과 criteria_original이 완전히 동일한 문장(전체 블록) 반복."),
    "WLF00000783": dict(sr="SENIOR_CONDITIONAL", nr="SUPPORTIVE_NUTRITION", status="NEEDS_REVIEW", p="meal_support", s="", vl="",
        reason="평택시 송탄출장소 관할의 행려자 대상 여비·급식비(실비) 지원. WLF00001309(batch02), WLF00003721(본 배치)과 동일 유형·동일 시 관할 다른 출장소 사업으로, 일관성을 위해 동일하게 NEEDS_REVIEW로 남김.", dq="WLF00001309(batch02, 안중출장소)와 사실상 동일한 사업이 출장소별로 별도 service_id로 등록돼 있음(평택시 내 중복 유사사업)."),
    "WLF00006374": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="만 18세 미만 아동으로 명시. 고령자와 무관.", dq=""),
    "WLF00000138": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="결혼이민자 대상 일자리(어린이집 급식도우미) 사업. 신청자가 급식을 받는 것이 아니라 급식 보조 업무에 취업하는 것이며 고령자·영양돌봄과 무관.", dq=""),
    "WLF00004352": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="관내 고등학교 기숙사생·석식희망 학생 대상. 고령자와 무관.", dq=""),
    "WLF00002523": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="", vl="A",
        reason="저소득층(우선순위에 '조손가정, 거동이 불편한 취약계층' 포함, 연령 제한 명시 없음)이라 SENIOR_CONDITIONAL. 푸드뱅크 연계로 식료품을 매월 무상 수령한다는 내용이 명시돼 DIRECT_NUTRITION. 선정 우선순위·신청방법·문의처 모두 명확해 A.", dq=""),
    "WLF00003400": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="저소득주민(생계·주거급여수급자, 차상위, 한부모) 대상(연령무관)이라 SENIOR_CONDITIONAL이나, 건강보험료 대납으로 식사·영양과 무관.", dq=""),
    "WLF00006205": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="수혜자가 건강가정지원센터 종사자(기관 종사자)이며 개인 고령자가 아님. 월 2만원 보조비로 영양과도 무관.", dq=""),
    "WLF00002434": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="예비·신혼부부 중 초산 전 가임기 여성 대상 산전검사. 고령자와 무관.", dq=""),
    "WLF00003818": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="출산가정(산모) 대상 본인부담금 환급. 고령자와 무관.", dq=""),
    "WLF00000315": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="장애인가정의 출산 지원금(현금)으로 출산이 트리거인 사업. 고령자와 무관.", dq=""),
    "WLF00005669": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="도내 출산가정 대상 산모·신생아 건강관리사 파견. 고령자와 무관.", dq=""),
    "WLF00005721": dict(sr="NOT_SENIOR_RELEVANT", nr="SUPPORTIVE_NUTRITION", status="EXCLUDE", p="", s="", vl="",
        reason="출산 산모 대상 산후건강관리비. 사용용도에 '영양식이관리'가 포함돼 SUPPORTIVE_NUTRITION이지만 대상관계 축에서 탈락.", dq=""),
    "WLF00003627": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="중위소득 150% 초과 전체 산모 대상 바우처. 고령자와 무관.", dq=""),
    "WLF00000438": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="군위군 관내 임산부 대상 산모신생아 건강관리사 지원. 고령자와 무관.", dq=""),
    "WLF00005287": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="출산가정 대상 산모신생아 건강관리 지원 확대사업. 고령자와 무관.", dq=""),
}


def main():
    with open(REVIEWED_PATH, encoding="utf-8-sig") as f:
        all_rows = {r["service_id"]: r for r in csv.DictReader(f)}
        f.seek(0)
        unk_ids_in_order = [r["service_id"] for r in csv.DictReader(open(REVIEWED_PATH, encoding="utf-8-sig")) if r["senior_relevance"] == "unknown"]

    with open(BATCH01_PATH, encoding="utf-8-sig") as f:
        b1_ids = {r["service_id"] for r in csv.DictReader(f)}
    with open(BATCH02_PATH, encoding="utf-8-sig") as f:
        b2_ids = {r["service_id"] for r in csv.DictReader(f)}

    remaining = [sid for sid in unk_ids_in_order if sid not in b1_ids and sid not in b2_ids]
    assert len(remaining) == 82, f"remaining count mismatch: {len(remaining)}"
    assert set(BATCH3_IDS).issubset(set(remaining)), "batch3 선정 id 중 remaining 82건에 없는 것이 있습니다."
    assert len(BATCH3_IDS) == 40 and len(set(BATCH3_IDS)) == 40
    assert set(BATCH3_IDS) == set(DECISIONS.keys())
    assert not (set(BATCH3_IDS) & b1_ids) and not (set(BATCH3_IDS) & b2_ids)

    out_rows = []
    for sid in BATCH3_IDS:
        r = all_rows[sid]
        d = DECISIONS[sid]
        out_rows.append({
            "service_id": sid,
            "service_name": r["service_name"],
            "region": f'{r["sido"]} {r["sigungu"]}'.strip(),
            "target_original": r["target_original"],
            "criteria_original": r["criteria_original"],
            "support_original": r["support_original"],
            "senior_relation_v2": d["sr"],
            "nutrition_relevance": d["nr"],
            "review_status": d["status"],
            "service_type_primary": d["p"],
            "service_type_secondary": d["s"],
            "classification_reason": d["reason"],
            "verification_level": d["vl"],
            "data_quality_note": d["dq"],
        })

    with open(OUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        w.writerows(out_rows)
    print(f"[저장] {OUT_PATH} ({len(out_rows)}행)")

    from collections import Counter
    print("remaining(82) verified OK")
    print("review_status:", Counter(r["review_status"] for r in out_rows))
    print("senior_relation_v2:", Counter(r["senior_relation_v2"] for r in out_rows))
    print("nutrition_relevance:", Counter(r["nutrition_relevance"] for r in out_rows))
    print("INCLUDE ids:", [r["service_id"] for r in out_rows if r["review_status"] == "INCLUDE"])
    print("NEEDS_REVIEW ids:", [r["service_id"] for r in out_rows if r["review_status"] == "NEEDS_REVIEW"])


if __name__ == "__main__":
    main()
