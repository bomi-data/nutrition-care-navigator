"""
UNKNOWN(senior_relevance=unknown) 142건 중 첫 30건에 대해
docs/classification_criteria.md v2.1(2축 판단)을 적용한 결과를 저장한다.

- 새 API 호출 없음: welfare_candidates_reviewed.csv에 이미 저장된 원문만 사용한다.
- welfare_candidates_reviewed.csv 자체는 수정하지 않는다(원문 컬럼 보존 원칙).
- 산출물: data/processed/unknown_review_batch_01.csv
"""
import csv
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
REVIEWED_PATH = PROCESSED_DIR / "welfare_candidates_reviewed.csv"
OUT_PATH = PROCESSED_DIR / "unknown_review_batch_01.csv"

FIELDNAMES = [
    "service_id", "service_name", "region",
    "target_original", "criteria_original", "support_original",
    "senior_relation_v2", "nutrition_relevance", "review_status",
    "service_type_primary", "service_type_secondary",
    "classification_reason", "verification_level",
]

# 30건 판정 결과 (원문을 직접 읽고 판단, 사용자 권장안 없이 신규 검토)
DECISIONS = {
    "WLF00003176": dict(sr="NOT_SENIOR_RELEVANT", nr="DIRECT_NUTRITION", status="EXCLUDE", p="", s="", vl="",
        reason="지원대상이 생계급여 수급가구 중 임산부·영유아·아동·청년(34세 이하)으로 명시. 노인 언급이 전혀 없고 영양플러스 사업 이용자는 별도 제외 대상으로 명시돼 있어 고령자 대상 서비스가 아님."),
    "WLF00006299": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="장애인·예비장애인 대상이라 연령 제한은 없으나(SENIOR_CONDITIONAL), 지원내용이 장애인 건강보건관리·모성보건사업·기관연계뿐으로 식사·영양 내용이 전혀 없음."),
    "WLF00001141": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 9~24세 청소년으로 명시. 상담·자립지원 서비스로 영양돌봄과도 무관."),
    "WLF00005858": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 20~49세로 명시(연령 상한 있음). 임신 전 건강검진 비용 지원으로 영양과도 무관."),
    "WLF00000896": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="지원대상이 개인 고령자가 아니라 중독관리통합지원센터(기관) 설치·운영비. 내용도 중독자 상담·재활로 영양과 무관."),
    "WLF00001160": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="지원대상이 중독관리통합지원센터 운영비(기관)이며 노숙인·주취범죄자 사례관리 내용. 개인 고령자 대상 서비스가 아니고 영양과도 무관."),
    "WLF00005034": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="법정 장애인 대상, 연령 제한 없어 SENIOR_CONDITIONAL이나 만성질환·장애 건강관리(주치의 방문진료·방문간호)뿐으로 식사·영양 내용이 전혀 없음."),
    "WLF00006236": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="고교 3학년 졸업(예정)자 취업장려금. 고령자와 무관, 영양과도 무관."),
    "WLF00002827": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 출산 산모로 명시. 산모건강관리비 현금지급이며 식사 제공이 아님."),
    "WLF00000229": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 산모신생아 바우처 이용자. 본인부담금 현금지급이며 영양과 무관."),
    "WLF00003517": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="산모·신생아 건강관리사로 '활동하려는' 인력 양성 교육비·교통비 지원. 서비스를 받는 개인 고령자가 아니라 돌봄인력 양성 대상자이며 영양과도 무관."),
    "WLF00006740": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="장애인 가정의 출산지원금·36개월 미만 영아 양육지원금. 고령자와 무관한 현금지원."),
    "WLF00002418": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="셋째아 이상 출산 산모 대상 산후관리 본인부담금 지원. 고령자와 무관."),
    "WLF00005239": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="community_care", s="meal_support", vl="A",
        reason="대상이 '돌봄이 필요한 시민 누구나'로 연령 제한이 없고 거동·가족부재 등 기능적 조건 기반. 13대 돌봄서비스 중 '식사지원: 기본적인 식생활 유지를 위한 식사 배달'이 명시돼 있어 DIRECT_NUTRITION. 대상/기준/내용/신청/문의처 모두 상세해 A."),
    "WLF00004850": dict(sr="NOT_SENIOR_RELEVANT", nr="SUPPORTIVE_NUTRITION", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 임신부로 명시. 가사돌봄 중 식사 준비 보조가 포함돼 SUPPORTIVE_NUTRITION이지만 대상관계 축에서 탈락해 EXCLUDE."),
    "WLF00004182": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="출산가정(산모) 대상 산모·신생아 건강관리 바우처. 고령자와 무관."),
    "WLF00004375": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="출산가정 대상 산모신생아건강관리 본인부담금 지원. 고령자와 무관."),
    "WLF00005194": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="출산 산모 대상 산모건강관리비(지역화폐) 지원. 고령자와 무관."),
    "WLF00004071": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="출산가정 대상 산모신생아 건강관리 바우처 지원. 고령자와 무관."),
    "WLF00001919": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="출생신고 가정 대상 산후건강관리비 현금지급. 고령자와 무관."),
    "WLF00003083": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="저소득 임산부 대상 산후조리원 이용료 지원. 고령자와 무관."),
    "WLF00004595": dict(sr="SENIOR_DIRECT", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="", vl="A",
        reason="'결식우려 거동불편 저소득노인' 대상으로 SENIOR_DIRECT. 도시락 제조·배달이 명시된 DIRECT_NUTRITION. 대상/기준/내용/신청/문의처 모두 명확해 A."),
    "WLF00004507": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="", vl="B",
        reason="차상위·저소득·장애인·독거노인·조손가정 등 여러 취약계층 중 '독거노인'(거동불편 독거노인 우선 추천 포함)이 명시적으로 포함돼 SENIOR_CONDITIONAL. 월2회 반찬지원·설떡국떡·김장김치 지원이 명시돼 DIRECT_NUTRITION. 신청방법 정보가 없어 B."),
    "WLF00002930": dict(sr="NOT_SENIOR_RELEVANT", nr="SUPPORTIVE_NUTRITION", status="EXCLUDE", p="", s="", vl="",
        reason="대상이 가임기 여성(19~49세)·임신준비/출산 후 여성으로 명시. 영양제 지원이라 SUPPORTIVE_NUTRITION이지만 대상관계 축에서 탈락해 EXCLUDE."),
    "WLF00002558": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="지역아동센터 이용 초등학생 대상 치과 주치의 사업. 고령자·영양 모두와 무관."),
    "WLF00004305": dict(sr="SENIOR_CONDITIONAL", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="기초수급·차상위 중증장애인 대상(연령 제한 없음)이라 SENIOR_CONDITIONAL이나, 지원내용이 월 3만원 현금수당뿐으로 식사·영양과 무관."),
    "WLF00005326": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="2자녀 이상 출산 산모 대상 진료비 지원. 고령자와 무관."),
    "WLF00005842": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="출산 산모 대상 산후조리비(현금/카드충전) 지원. 고령자와 무관. (원문 자체가 target/criteria/support/application 4개 필드에 동일 문장이 반복되는 데이터 품질 이슈 있음)"),
    "WLF00005583": dict(sr="SENIOR_CONDITIONAL", nr="DIRECT_NUTRITION", status="INCLUDE", p="meal_support", s="", vl="A",
        reason="장애인복지관 이용 기초수급·차상위 장애인 대상(연령 제한 없음)이라 SENIOR_CONDITIONAL. 복지관 점심 무료제공+식사/밑반찬 배달이 명시돼 DIRECT_NUTRITION. 대상선정 절차까지 상세해 A."),
    "WLF00002163": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", status="EXCLUDE", p="", s="", vl="",
        reason="출산가정 대상 산모신생아 건강관리 이용료(바우처 본인부담금) 지원. 고령자와 무관."),
}


def main():
    with open(REVIEWED_PATH, encoding="utf-8-sig") as f:
        rows = {r["service_id"]: r for r in csv.DictReader(f)}

    out_rows = []
    for sid, d in DECISIONS.items():
        r = rows[sid]
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


if __name__ == "__main__":
    main()
