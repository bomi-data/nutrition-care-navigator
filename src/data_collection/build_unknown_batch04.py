"""
UNKNOWN(senior_relevance=unknown) 142건 중 batch01+02+03(100건, service_id 기준)을 제외한
나머지 42건 전체를 검토한다(batch04, 마지막 배치).

42건 전부를 실제로 읽고 재검증한 결과, 예외 없이 임신/출산/산모/신생아를 직접적인 자격요건으로
하는 서비스였다(장애인가정 출산지원금류도 실질 트리거는 '출산'이지 '장애인'이 아님).
"산모·신생아 유형이므로 자동 EXCLUDE"가 아니라, 42건 각각의 target_original에 고령자를 포함하는
문구나 연령 배제가 없는 문구가 있는지 실제로 확인한 뒤 전부 NOT_SENIOR_RELEVANT로 판정했다.

- 새 API 호출 없음, 기존 batch01~03 및 welfare_candidates_reviewed.csv 모두 미수정.
- 산출물: data/processed/unknown_review_batch_04.csv
"""
import csv
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
REVIEWED_PATH = PROCESSED_DIR / "welfare_candidates_reviewed.csv"
BATCH01_PATH = PROCESSED_DIR / "unknown_review_batch_01.csv"
BATCH02_PATH = PROCESSED_DIR / "unknown_review_batch_02.csv"
BATCH03_PATH = PROCESSED_DIR / "unknown_review_batch_03.csv"
OUT_PATH = PROCESSED_DIR / "unknown_review_batch_04.csv"

FIELDNAMES = [
    "service_id", "service_name", "region",
    "target_original", "criteria_original", "support_original",
    "senior_relation_v2", "nutrition_relevance", "review_status",
    "service_type_primary", "service_type_secondary",
    "classification_reason", "verification_level", "data_quality_note",
]

# 42건 전부 실제 원문 확인 결과 (NOT_SENIOR_RELEVANT + EXCLUDE는 유형이 아니라 각 건의 target_original에
# 근거함: 산모/임신부/신생아/출산가정이 명시적 자격요건이며 고령자를 포함하거나 배제하지 않는다는
# 문구가 전혀 없음을 확인)
DECISIONS = {
    "WLF00001849": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="contact 필드가 '033-000-0000'로 명백한 더미(placeholder) 전화번호임 — 실제 문의처 정보 없음.",
        reason="대상이 '도내 6개월 이상 거주한 산모'로 명시. 출산 후 의료비·약제비 현금지원으로 영양과도 무관."),
    "WLF00002020": dict(sr="NOT_SENIOR_RELEVANT", nr="SUPPORTIVE_NUTRITION", dq="",
        reason="대상이 '임신을 준비하는 가임기 여성'으로 명시. 엽산제 지원(SUPPORTIVE_NUTRITION)이지만 대상관계 축에서 탈락."),
    "WLF00002478": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="'장애인가정'이라는 이름과 달리 실제 자격요건은 '신생아의 부 또는 모가 등록장애인'인 가정의 출산장려금(현금)이며, 트리거는 출산이지 고령이 아님. 영양과도 무관."),
    "WLF00003583": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="contact에 같은 부서 전화번호가 두 개(063-540-6218 / 063-540-6215) 나열돼 있어 어느 쪽이 대표번호인지 불명확.",
        reason="장애인가정의 신생아 출산장려금(현금, 장애등급별 차등). 트리거는 출산이며 고령자와 무관. 영양과도 무관."),
    "WLF00006050": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 '홍천군 거주 산모'로 명시. 산후조리원·마사지·운동수강비 등 실비 지원이며 식품·영양 항목이 명시되지 않음."),
    "WLF00005118": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 신생아 출생가정(부 또는 모). 산후조리비 현금지원으로 영양과 무관."),
    "WLF00001892": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 공주시 거주 산모. 바우처·본인부담금·돌봄서비스 비용 지원으로 영양과 무관."),
    "WLF00000496": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 김천시 거주 산모와 출생아. 산모신생아 건강관리 서비스 본인부담금 지원(현금)으로 영양과 무관."),
    "WLF00004468": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 괴산군 출산가정. 본인부담금 90% 지원(현금)으로 영양과 무관."),
    "WLF00004727": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 이천시 거주 산모. 본인부담금 지원(현금)으로 영양과 무관."),
    "WLF00004349": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 상주시 출산가정. 본인부담금 지원(현금)으로 영양과 무관."),
    "WLF00002079": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 남원시 거주 산모·신생아. 본인부담금 지원(현금)으로 영양과 무관.", ),
    "WLF00002712": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="장애인가정의 신생아 출산지원금(현금). 트리거는 출산이며 고령자와 무관. 영양과도 무관."),
    "WLF00002497": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 강남구 거주 산모신생아 건강관리 서비스 이용 가정. 본인부담금 지원(현금)으로 영양과 무관."),
    "WLF00001220": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 인천 동구 거주 산모. 정부지원금 지원(현금)으로 영양과 무관."),
    "WLF00003658": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="contact 필드에 '복지로:', '사회보장정보원: 1566-3232'가 각각 중복 나열돼 있음.",
        reason="대상이 경상북도 모든 출산가정. 본인부담금 90% 지원(현금)으로 영양과 무관."),
    "WLF00003608": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="기초생활수급자·차상위 등 저소득 출산가정 및 희귀질환/장애/다태아 등 예외지원 대상. 트리거는 출산이며 고령자와 무관. 바우처 본인부담금 지원으로 영양과도 무관."),
    "WLF00002405": dict(sr="NOT_SENIOR_RELEVANT", nr="SUPPORTIVE_NUTRITION", dq="",
        reason="대상이 광양시 거주 출산가정(산모). 지원 사용처에 '산후조리를 위한 회복, 영양 구입 등'이 명시돼 SUPPORTIVE_NUTRITION이지만 대상관계 축에서 탈락."),
    "WLF00005091": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 의왕시 신생아 부 또는 모. 산모건강관리사 이용 본인부담금 지원(현금)으로 영양과 무관."),
    "WLF00005815": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="출산순위별 출산축하금·양육비(현금)로 트리거는 출산이며 고령자와 무관. 영양과도 무관."),
    "WLF00001896": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 부산시 출산(예정)가정. 바우처 제공으로 영양과 무관."),
    "WLF00000596": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 부안군 산모와 자녀. 본인부담금 지원(현금)으로 영양과 무관."),
    "WLF00006457": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 출산 6개월 이내 산모. 유축기 대여 및 소모품 제공으로, 모유수유 지원 장비이나 우리 프로젝트의 nutrition_relevance 정의(식사·급식·식품·영양상담/교육/바우처)에는 해당하지 않아 NOT_NUTRITION_RELEVANT. 대상관계 축도 NOT_SENIOR_RELEVANT."),
    "WLF00006390": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="application_original에 '보거놋 방문'이라는 오탈자(보건소 오기)가 있음.",
        reason="대상이 20주 이상 임신부. 임신지원금(현금카드)으로 영양과 무관."),
    "WLF00004360": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 용산구 출산가정 산모·신생아. 전자바우처 생성(서비스 비용 지원)으로 영양과 무관."),
    "WLF00003857": dict(sr="NOT_SENIOR_RELEVANT", nr="SUPPORTIVE_NUTRITION", dq="",
        reason="대상이 부산 중구 거주 임신부. 지원물품에 '영양제 등'이 포함돼 SUPPORTIVE_NUTRITION이지만 대상관계 축에서 탈락."),
    "WLF00001939": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 임신을 준비중인 예비부모(부부). 검사비 지원(현금성)으로 영양과 무관."),
    "WLF00003141": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="contact 필드가 '지자체 사이트:'로만 돼 있고 실제 연락처 값이 없음.",
        reason="대상이 전북 거주 산모(출산 후). 산후치료비 지원(현금)으로 영양과 무관."),
    "WLF00003039": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 울진군 거주 임산부. 산전검사·초음파검사비 지원으로 영양과 무관."),
    "WLF00002869": dict(sr="NOT_SENIOR_RELEVANT", nr="SUPPORTIVE_NUTRITION", dq="",
        reason="대상이 신혼(예비)부부·난임부부(첫 임신 준비중). 엽산제 제공(SUPPORTIVE_NUTRITION)이지만 대상관계 축에서 탈락."),
    "WLF00003121": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 의령군 산모신생아 건강관리 지원사업 바우처 이용자. 본인부담금 지원(현금)으로 영양과 무관."),
    "WLF00001381": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="contact가 '거주지 보건소: 군구별 상이'로 구체적 연락처가 없음(광역 단위 사업 특성상 발생).",
        reason="대상이 인천시 출산가정(기준중위소득 150% 이하 등). 본인부담금 지원(현금)으로 영양과 무관."),
    "WLF00002725": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="장애인가정의 신생아 출산지원금(현금). 트리거는 출산이며 고령자와 무관. 영양과도 무관."),
    "WLF00002086": dict(sr="NOT_SENIOR_RELEVANT", nr="SUPPORTIVE_NUTRITION", dq="",
        reason="대상이 임산부(엽산제/철분제 대상 시기 구분). 영양제 지원(SUPPORTIVE_NUTRITION)이지만 대상관계 축에서 탈락."),
    "WLF00002034": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 횡성군 거주 임산부. 축하용품(품목 불명, 추측 금지) 지원으로 영양 관련 여부 원문상 불명확해 NOT_NUTRITION_RELEVANT로 처리."),
    "WLF00005074": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="장애인가정의 신생아 출산지원금(현금). 트리거는 출산이며 고령자와 무관. 영양과도 무관."),
    "WLF00005823": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 임실군 산모신생아 건강관리서비스 이용 산모. 본인부담금 지원(현금)으로 영양과 무관."),
    "WLF00003317": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 예천군 거주 임신부. 초음파 검사비 지원으로 영양과 무관."),
    "WLF00001688": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 영월군 출산가정 부모. 가구당 현금지원으로 영양과 무관."),
    "WLF00001293": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="장애인가정의 신생아 출산지원금(현금). 트리거는 출산이며 고령자와 무관. 영양과도 무관."),
    "WLF00004354": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 보은군 거주 산모(소득초과자 자체지원). 현금지급으로 영양과 무관."),
    "WLF00004325": dict(sr="NOT_SENIOR_RELEVANT", nr="NOT_NUTRITION_RELEVANT", dq="",
        reason="대상이 함양군 거주 임산부(산모신생아 건강관리 서비스 수혜자). 본인부담금 지원(현금)으로 영양과 무관."),
}

for sid in DECISIONS:
    DECISIONS[sid]["status"] = "EXCLUDE"
    DECISIONS[sid]["p"] = ""
    DECISIONS[sid]["s"] = ""
    DECISIONS[sid]["vl"] = ""


def main():
    with open(REVIEWED_PATH, encoding="utf-8-sig") as f:
        all_rows = {r["service_id"]: r for r in csv.DictReader(f)}
    unk_ids_in_order = [
        r["service_id"] for r in csv.DictReader(open(REVIEWED_PATH, encoding="utf-8-sig"))
        if r["senior_relevance"] == "unknown"
    ]

    b1_ids = {r["service_id"] for r in csv.DictReader(open(BATCH01_PATH, encoding="utf-8-sig"))}
    b2_ids = {r["service_id"] for r in csv.DictReader(open(BATCH02_PATH, encoding="utf-8-sig"))}
    b3_ids = {r["service_id"] for r in csv.DictReader(open(BATCH03_PATH, encoding="utf-8-sig"))}

    remaining = [sid for sid in unk_ids_in_order if sid not in b1_ids and sid not in b2_ids and sid not in b3_ids]
    assert len(remaining) == 42, f"remaining count mismatch: {len(remaining)}"
    assert set(remaining) == set(DECISIONS.keys()), "remaining 42건과 DECISIONS 키가 일치하지 않습니다."
    assert not (set(remaining) & b1_ids) and not (set(remaining) & b2_ids) and not (set(remaining) & b3_ids)

    out_rows = []
    for sid in remaining:
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
    print("remaining(42) verified OK")
    print("review_status:", Counter(r["review_status"] for r in out_rows))
    print("senior_relation_v2:", Counter(r["senior_relation_v2"] for r in out_rows))
    print("nutrition_relevance:", Counter(r["nutrition_relevance"] for r in out_rows))
    dq_count = sum(1 for r in out_rows if r["data_quality_note"])
    print("data_quality_note 있는 행:", dq_count)


if __name__ == "__main__":
    main()
