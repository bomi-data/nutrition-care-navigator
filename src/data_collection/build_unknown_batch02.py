"""
UNKNOWN(senior_relevance=unknown) 142건 중, batch01(30건)을 service_id 기준으로 제외한
나머지 112건 중 파일 순서상 다음 30건에 대해 classification_criteria.md v2.1을 적용한다.

- 새 API 호출 없음, welfare_candidates_reviewed.csv 원본 미수정, batch01 파일 미수정.
- 산출물: data/processed/unknown_review_batch_02.csv
"""
import csv
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
REVIEWED_PATH = PROCESSED_DIR / "welfare_candidates_reviewed.csv"
BATCH01_PATH = PROCESSED_DIR / "unknown_review_batch_01.csv"
OUT_PATH = PROCESSED_DIR / "unknown_review_batch_02.csv"

FIELDNAMES = [
    "service_id", "service_name", "region",
    "target_original", "criteria_original", "support_original",
    "senior_relation_v2", "nutrition_relevance", "review_status",
    "service_type_primary", "service_type_secondary",
    "classification_reason", "verification_level", "data_quality_note",
]

DECISIONS = {
    "WLF00005598": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="community_care", s="meal_support", vl="A",
        reason="대상이 '돌봄이 필요한 제주도민 누구나'(연령무관, 기능조건: 일상생활수행 어려움+돌봄가족 없음+기존서비스 미이용). 5대 9종 서비스 중 '식사지원: 도시락, 반찬 및 죽 배달'이 명시돼 DIRECT_NUTRITION. 대상/기준/내용/신청/문의처 모두 매우 상세해 A.", dq=""),
    "WLF00004994": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 임신 20주 이상 임신부로 명시. 임신축하금(현금)으로 영양과도 무관.", dq=""),
    "WLF00000236": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="선정기준에 '만18세 이상~64세 이하'로 연령 상한이 명시돼 65세 이상 배제. 산모신생아관리사 양성 교육비 지원으로 영양과도 무관.", dq="target_original은 모호한 문구뿐이고 구체적 연령 상한은 criteria_original에만 명시됨(필드 간 정보 불균등)."),
    "WLF00001563": dict(sr="NOT_SENIOR_RELEVANT", nr="SUPPORTIVE_NUTRITION", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 출산가정(산모)으로 명시. 지원내용에 '영양관리 등'이 포함돼 SUPPORTIVE_NUTRITION이지만 대상관계 축에서 탈락.", dq=""),
    "WLF00003058": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 출산가정. 산모신생아 건강관리사 지원 서비스로 세부내용 불명확하나 산모 대상이라 EXCLUDE.", dq=""),
    "WLF00002482": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 출산가정. 건강관리사의 가사활동·정서지원 서비스로 식사 관련 언급 없음.", dq=""),
    "WLF00006696": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="중위소득 80% 이하 등록장애인 대상(연령무관)이라 SENIOR_CONDITIONAL이나, 입원 의료비 본인부담금 지원뿐으로 식사·영양과 무관.", dq=""),
    "WLF00005779": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="'지역주민' 전체를 대상으로 하는 찾아가는 보건복지서비스 체계로 연령 배제가 없어 SENIOR_CONDITIONAL이나, 지원내용이 의료비·생활지원비·자활교육비·기타지원비로 식사·영양 관련 내용이 전혀 없어 EXCLUDE.", dq="target_original, criteria_original, application_original 세 필드가 완전히 동일한 문장(사업 설명)을 반복하고 있어 실질적인 자격조건·신청방법 정보가 없음."),
    "WLF00001390": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="등록장애인 대상(연령무관)이라 SENIOR_CONDITIONAL이나, 장애인복지신문 무료구독으로 식사·영양과 무관.", dq=""),
    "WLF00001291": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="", vl="B",
        reason="주간보호시설 이용 장애인 및 '일반인'까지 포함하는 대상이라 연령 배제 없음(SENIOR_CONDITIONAL). 중·간식 및 중식 제공이 명시돼 DIRECT_NUTRITION. target/criteria가 동일 문장 반복이고 신청방법 정보가 없어 B.", dq="target_original과 criteria_original이 완전히 동일한 문장."),
    "WLF00001309": dict(sr="SENIOR_CONDITIONAL", nr="SUPPORTIVE_NUTRITION", status="NEEDS_REVIEW", p="meal_support", s="", vl="",
        reason="대상 '행려자'(귀향 희망 무숙식 여행자)는 연령 제한이 없어 고령자도 해당될 수 있으나, 지원내용이 여비·급식비(8천원)·장제비·의료비를 묶은 일회성 긴급구호라 지속적 영양돌봄 서비스로 볼 수 있는지 판단이 서지 않음. 급식비 항목은 있으나(SUPPORTIVE_NUTRITION 가능성) 이 프로젝트가 다루려는 '영양돌봄 서비스'의 범위에 해당하는지 원문만으로 확정하기 어려워 NEEDS_REVIEW로 남김.", dq=""),
    "WLF00005769": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="출산가정 대상 산모신생아 건강관리 바우처. 고령자와 무관.", dq=""),
    "WLF00003098": dict(sr="NOT_SENIOR_RELEVANT", nr="DIRECT_NUTRITION", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 관내 고등학교 재학생으로 명시. 무상급식(DIRECT_NUTRITION)이지만 대상관계 축에서 탈락.", dq=""),
    "WLF00006683": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="지원대상이 산모신생아 건강관리 '제공인력'(종사자)의 교통비이며 산모·신생아 본인이 아님. 개인 고령자 대상 서비스도 아니고 영양과도 무관.", dq=""),
    "WLF00006651": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 출산가정 산모로 명시. 산후조리 본인부담금 현금지원으로 영양과도 무관.", dq=""),
    "WLF00005945": dict(sr="NOT_SENIOR_RELEVANT", nr="SUPPORTIVE_NUTRITION", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 출생신고 가정(부모)으로 명시. 외식쿠폰(식비 바우처)이라 SUPPORTIVE_NUTRITION이지만 대상관계 축에서 탈락.", dq=""),
    "WLF00005944": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 출산가정 산모. 산후조리비 현금지급으로 영양과도 무관.", dq=""),
    "WLF00005937": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 출산가정(첫째아). 산모신생아 건강관리 서비스 확대지원으로 고령자와 무관.", dq=""),
    "WLF00005649": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 출산 산모. 산후조리비 현금지급으로 영양과도 무관.", dq=""),
    "WLF00004943": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 신생아 출생가정. 산후조리비 현금급여로 고령자와 무관.", dq=""),
    "WLF00004934": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 출산 산모. 쿠폰 발급(20만원)이나 용도가 진료비이며 영양과 무관.", dq=""),
    "WLF00004488": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="장애인활동지원 이용 장애인 대상(연령무관)이라 SENIOR_CONDITIONAL이나, 활동지원 바우처(가사·자립·직장생활 지원)로 식사·영양이 원문에 명시되지 않음.", dq=""),
    "WLF00002021": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 서울시 모든 출산가정. 산모신생아 건강관리 바우처로 고령자와 무관.", dq=""),
    "WLF00003568": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 산모신생아 건강관리서비스를 받은 산모. 본인부담금 환급으로 영양과 무관.", dq=""),
    "WLF00002361": dict(sr="NOT_SENIOR_RELEVANT", nr="SUPPORTIVE_NUTRITION", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 임산부·영유아(3~36개월)로 명시. 엽산제·철분제·영양제 지원(SUPPORTIVE_NUTRITION)이지만 대상관계 축에서 탈락.", dq=""),
    "WLF00000334": dict(sr="NOT_SENIOR_RELEVANT", nr="SUPPORTIVE_NUTRITION", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 결혼~첫 임신 전 신혼부부로 명시. 종합영양제 지원(SUPPORTIVE_NUTRITION)이지만 대상관계 축에서 탈락.", dq=""),
    "WLF00002354": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 출산가정 산모. 산후조리비용(현금) 지원으로 고령자와 무관.", dq=""),
    "WLF00002864": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 출산가정. 산모신생아 건강관리 본인부담금 및 건강관리사 교통비 지원으로 고령자와 무관.", dq=""),
    "WLF00004515": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 임신 24주 이상 여성. 건강관리비 현금지원(소득무관)으로 고령자·영양과 무관.", dq=""),
    "WLF00003318": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 산모신생아 건강관리 서비스 바우처 이용자(출산가정). 본인부담금 지원으로 고령자와 무관.", dq=""),
}


def main():
    with open(REVIEWED_PATH, encoding="utf-8-sig") as f:
        all_rows = {r["service_id"]: r for r in csv.DictReader(f)}
    with open(BATCH01_PATH, encoding="utf-8-sig") as f:
        batch1_ids = {r["service_id"] for r in csv.DictReader(f)}

    unk_ids_in_order = [
        r["service_id"] for r in
        csv.DictReader(open(REVIEWED_PATH, encoding="utf-8-sig"))
        if r["senior_relevance"] == "unknown"
    ]
    remaining = [sid for sid in unk_ids_in_order if sid not in batch1_ids]
    batch2_ids = remaining[:30]

    assert set(batch2_ids) == set(DECISIONS.keys()), "batch2 id 목록과 DECISIONS 키가 일치하지 않습니다."
    assert not (set(batch2_ids) & batch1_ids), "batch01과 겹치는 service_id가 있습니다."

    out_rows = []
    for sid in batch2_ids:
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
    print("review_status:", Counter(r["review_status"] for r in out_rows))
    print("senior_relation_v2:", Counter(r["senior_relation_v2"] for r in out_rows))
    print("nutrition_relevance:", Counter(r["nutrition_relevance"] for r in out_rows))

    maternal_kw = ["산모", "신생아", "임신", "산후", "출산"]
    maternal_count = sum(1 for r in out_rows if any(k in r["service_name"] for k in maternal_kw))
    print("maternal/postpartum-related service_name count:", maternal_count)


if __name__ == "__main__":
    main()
