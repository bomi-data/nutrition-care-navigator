"""
분류 기준 v2(docs/classification_criteria.md) 적용:
1) welfare_candidates_reviewed.csv에 확장 필드(senior_relation 등)를 추가한다.
2) manual_review_queue.csv의 11건을 저장된 원문(target/criteria/support_original)만
   다시 확인해 재판정하고 반영한다. 새 API 호출은 하지 않는다.
3) 기존 54건 INCLUDE / 33건 EXCLUDE 중 새 기준과 충돌할 가능성이 있는 항목을
   review_note 텍스트 기반으로 탐지해 목록만 출력한다(자동 수정하지 않음).

이 스크립트는 기존 파일을 덮어쓰지만 삭제하지 않으며, 다른 파이프라인 단계를
재실행하지 않는다.
"""
import csv
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
REVIEWED_PATH = PROCESSED_DIR / "welfare_candidates_reviewed.csv"
QUEUE_PATH = PROCESSED_DIR / "manual_review_queue.csv"

NEW_FIELDS = [
    "senior_relation", "service_type_primary", "min_age",
    "disability_required", "low_income_required", "single_household_required",
    "homebound_or_mobility_condition", "meal_support_flag", "food_cost_support_flag",
    "eligibility_summary", "support_summary",
]

# 11건 재판정 (원문을 다시 읽고 검증한 결과, 사용자 권장안과 모순 없음을 확인)
DECISIONS_V2 = {
    "WLF00003248": dict(
        review_status="INCLUDE", service_type="home_visit", service_type_primary="home_visit",
        verification_level="A", nutritionist_involvement="not_specified",
        senior_relation="SENIOR_DIRECT", min_age="65",
        disability_required="false", low_income_required="false",
        single_household_required="unknown", homebound_or_mobility_condition="true",
        meal_support_flag="false", food_cost_support_flag="false",
        eligibility_summary="65세 이상 노인(또는 65세 미만 노인성질환자)으로 장기요양 1~5등급/인지지원등급 판정자. 소득기준 없음(본인부담 15%).",
        support_summary="장기요양요원의 가정방문을 통한 방문요양·방문목욕·방문간호, 주야간보호, 단기보호, 복지용구 대여. 식사/영양을 직접 지원한다는 내용은 원문에 없음.",
        review_note="원문 재확인 결과 65세 이상 대상은 명확(SENIOR_DIRECT)하나 지원내용에 식사/영양 관련 문구가 전혀 없어 meal_support로 분류하지 않음. home_visit(방문형 재가서비스)로만 분류하고, 최종 서비스에서는 영양 서비스와 동일선상이 아니라 '연계 가능한 돌봄 서비스'로 별도 표시할 것을 권장.",
    ),
    "WLF00001054": dict(
        review_status="INCLUDE", service_type="meal_support", service_type_primary="meal_support",
        verification_level="A", nutritionist_involvement="not_specified",
        senior_relation="SENIOR_CONDITIONAL", min_age="unknown",
        disability_required="true", low_income_required="true",
        single_household_required="unknown", homebound_or_mobility_condition="unknown",
        meal_support_flag="true", food_cost_support_flag="false",
        eligibility_summary="성북구 거주 결식우려 저소득 재가장애인(정원 50명). 연령 제한 명시 없음 → 65세 이상 저소득 재가장애인도 조건 충족 시 후보 가능.",
        support_summary="주1회(수요일) 밑반찬(1식 3찬) 가정 배달.",
        review_note="연령 제한이 원문에 없고 고령자를 배제하는 조건도 없어 SENIOR_CONDITIONAL로 분류. 밑반찬 배달 내용이 명확해 meal_support.",
    ),
    "WLF00003036": dict(
        review_status="INCLUDE", service_type="food_cost_support", service_type_primary="food_cost_support",
        verification_level="B", nutritionist_involvement="not_specified",
        senior_relation="SENIOR_DIRECT", min_age="65",
        disability_required="false", low_income_required="unknown",
        single_household_required="unknown", homebound_or_mobility_condition="unknown",
        meal_support_flag="false", food_cost_support_flag="true",
        eligibility_summary="장성군 거주 65세 이상 노인(시설입소자·장기입원자 제외). 기초연금 수급 여부에 따라 '건강권'/'일반권'으로 나뉘며 혜택 내용이 다름.",
        support_summary="반기별 바우처카드 충전 지급. 건강권(기초연금수급자)만 식당·식재료구입(12만원)+목욕이미용(18만원) 가능, 일반권은 목욕이미용(30만원)만 가능 — 식품 관련 혜택은 대상자 절반(건강권)에게만 해당하는 다목적 바우처.",
        review_note="식사·식재료구입에 쓸 수 있으나 목욕·이미용과 묶인 다목적 바우처이고, 그마저 기초연금수급자(건강권) 그룹에만 해당돼 meal_support가 아닌 food_cost_support로 분류. 신청방법 원문이 비어 있어 B.",
    ),
    "WLF00001000": dict(
        review_status="INCLUDE", service_type="meal_support", service_type_primary="meal_support",
        verification_level="A", nutritionist_involvement="not_specified",
        senior_relation="SENIOR_CONDITIONAL", min_age="unknown",
        disability_required="true", low_income_required="true",
        single_household_required="unknown", homebound_or_mobility_condition="unknown",
        meal_support_flag="true", food_cost_support_flag="false",
        eligibility_summary="성동구 거주 기초생활수급자·차상위계층 장애인. 연령 제한 명시 없음 → 65세 이상 저소득 장애인도 조건 충족 시 후보 가능.",
        support_summary="점심식사 무료 제공(방문 신청).",
        review_note="연령 제한 없고 고령자 배제 조건 없어 SENIOR_CONDITIONAL. 무료 점심식사 제공이 명확해 meal_support.",
    ),
    "WLF00000895": dict(
        review_status="INCLUDE", service_type="meal_support", service_type_primary="meal_support",
        verification_level="B", nutritionist_involvement="not_specified",
        senior_relation="SENIOR_CONDITIONAL", min_age="unknown",
        disability_required="true", low_income_required="true",
        single_household_required="unknown", homebound_or_mobility_condition="unknown",
        meal_support_flag="true", food_cost_support_flag="false",
        eligibility_summary="이천시 기초생활수급자·차상위계층 등록 중증 재가장애인. 연령 제한 명시 없음.",
        support_summary="주1회 밑반찬 배달 서비스.",
        review_note="연령 제한 없어 SENIOR_CONDITIONAL. 밑반찬 배달 명확해 meal_support. 신청방법 정보 없어 B.",
    ),
    "WLF00001001": dict(
        review_status="INCLUDE", service_type="meal_support", service_type_primary="meal_support",
        verification_level="B", nutritionist_involvement="not_specified",
        senior_relation="SENIOR_CONDITIONAL", min_age="unknown",
        disability_required="true", low_income_required="unknown",
        single_household_required="unknown", homebound_or_mobility_condition="true",
        meal_support_flag="true", food_cost_support_flag="false",
        eligibility_summary="성동구 거동곤란 중증 재가장애인. 연령·소득 조건 명시 없음(장애 및 거동곤란만 조건으로 확인됨).",
        support_summary="무침류·나물류 등 밑반찬 조리·배달(주1회).",
        review_note="연령 제한 없어 SENIOR_CONDITIONAL. 거동곤란 조건은 원문에 명시돼 true로 표시, 소득조건은 원문에 없어 unknown 유지. 신청방법 정보 없어 B.",
    ),
    "WLF00001481": dict(
        review_status="INCLUDE", service_type="meal_support", service_type_primary="meal_support",
        verification_level="B", nutritionist_involvement="not_specified",
        senior_relation="SENIOR_CONDITIONAL", min_age="unknown",
        disability_required="true", low_income_required="true",
        single_household_required="unknown", homebound_or_mobility_condition="unknown",
        meal_support_flag="true", food_cost_support_flag="false",
        eligibility_summary="문경시 저소득 장애인가구, 장애인종합복지관을 통해 선정. 연령 제한 명시 없음.",
        support_summary="밑반찬 지원(빈도 등 세부 내용은 원문에 부족).",
        review_note="연령 제한 없어 SENIOR_CONDITIONAL. 밑반찬 지원 내용은 있으나 target/criteria/support 모두 매우 간략해 B.",
    ),
    "WLF00000628": dict(
        review_status="INCLUDE", service_type="meal_support", service_type_primary="meal_support",
        verification_level="A", nutritionist_involvement="not_specified",
        senior_relation="SENIOR_CONDITIONAL", min_age="unknown",
        disability_required="true", low_income_required="true",
        single_household_required="true", homebound_or_mobility_condition="unknown",
        meal_support_flag="true", food_cost_support_flag="false",
        eligibility_summary="계룡시 거주 저소득 중증 독거장애인. 연령 제한 명시 없음.",
        support_summary="주1회 가정방문 반찬 지원.",
        review_note="연령 제한 없어 SENIOR_CONDITIONAL. '독거'가 원문에 명시돼 single_household_required=true. 신청방법·문의처 명확해 A.",
    ),
    "WLF00006344": dict(
        review_status="EXCLUDE", service_type="", service_type_primary="",
        verification_level="", nutritionist_involvement="",
        senior_relation="NOT_SENIOR_RELEVANT", min_age="65",
        disability_required="false", low_income_required="unknown",
        single_household_required="unknown", homebound_or_mobility_condition="true",
        meal_support_flag="false", food_cost_support_flag="false",
        eligibility_summary="담양군 거주 65세 이상 거동불편 어르신.",
        support_summary="병원 이동지원 및 진료 동행(보호자 역할). 식사·영양 관련 내용 없음.",
        review_note="대상 자체는 SENIOR_DIRECT(65세 이상 명시)이지만 지원내용이 병원 이동지원/동행뿐이고 식사·영양·식생활 관련 내용이 전혀 없어 영양돌봄 관련성 기준(2절)에서 탈락. '통합돌봄' 문구만으로 포함하지 않는다는 원칙에 따라 최종 senior_relation=NOT_SENIOR_RELEVANT, EXCLUDE 유지.",
    ),
    "WLF00003075": dict(
        review_status="INCLUDE", service_type="meal_support", service_type_primary="meal_support",
        verification_level="B", nutritionist_involvement="not_specified",
        senior_relation="SENIOR_CONDITIONAL", min_age="unknown",
        disability_required="true", low_income_required="true",
        single_household_required="unknown", homebound_or_mobility_condition="unknown",
        meal_support_flag="true", food_cost_support_flag="false",
        eligibility_summary="서천군 저소득 장애인(소득인정액 최저생계비 120% 이하). 연령 제한 명시 없음. 원문 내 대상인원이 target(20세대)과 support(25가구)로 서로 달라 데이터 품질 이슈로 별도 기록.",
        support_summary="주1회 밑반찬 가정방문 제공.",
        review_note="연령 제한 없어 SENIOR_CONDITIONAL. 밑반찬 배달 명확해 meal_support. 신청방법 정보 없고 원문 내 대상 인원 수치가 불일치해 B.",
    ),
    "WLF00003500": dict(
        review_status="INCLUDE", service_type="meal_support", service_type_primary="meal_support",
        verification_level="B", nutritionist_involvement="not_specified",
        senior_relation="SENIOR_CONDITIONAL", min_age="unknown",
        disability_required="true", low_income_required="true",
        single_household_required="unknown", homebound_or_mobility_condition="unknown",
        meal_support_flag="true", food_cost_support_flag="false",
        eligibility_summary="충청북도장애인복지관 '이용자' 중 저소득(기초수급·차상위) 장애인 — 단순 저소득 장애인이 아니라 해당 복지관 등록·이용이라는 추가 전제조건이 있음. 연령 제한 명시 없음.",
        support_summary="장애인복지관을 통한 급식 지원(구체적 빈도·단가는 원문에 없음).",
        review_note="연령 제한 없어 SENIOR_CONDITIONAL. '장애인복지관 이용자'라는 전제조건을 eligibility_summary에 보존함(단순 저소득 장애인 전체가 아님에 유의). target/criteria/support가 거의 동일 문장 반복이고 신청방법 정보 없어 B.",
    ),
}


def main():
    with open(REVIEWED_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        old_fieldnames = reader.fieldnames
        rows = list(reader)

    new_fieldnames = old_fieldnames + [c for c in NEW_FIELDS if c not in old_fieldnames]

    updated_queue_removed = []
    for row in rows:
        for c in NEW_FIELDS:
            row.setdefault(c, "")

        sid = row["service_id"]
        if sid in DECISIONS_V2:
            d = DECISIONS_V2[sid]
            row["review_status"] = d["review_status"]
            row["service_type"] = d["service_type"]
            row["verification_level"] = d["verification_level"]
            row["nutritionist_involvement"] = d["nutritionist_involvement"]
            row["review_note"] = d["review_note"]
            row["senior_relation"] = d["senior_relation"]
            row["service_type_primary"] = d["service_type_primary"]
            row["min_age"] = d["min_age"]
            row["disability_required"] = d["disability_required"]
            row["low_income_required"] = d["low_income_required"]
            row["single_household_required"] = d["single_household_required"]
            row["homebound_or_mobility_condition"] = d["homebound_or_mobility_condition"]
            row["meal_support_flag"] = d["meal_support_flag"]
            row["food_cost_support_flag"] = d["food_cost_support_flag"]
            row["eligibility_summary"] = d["eligibility_summary"]
            row["support_summary"] = d["support_summary"]
            updated_queue_removed.append(sid)

    with open(REVIEWED_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=new_fieldnames)
        w.writeheader()
        w.writerows(rows)
    print(f"[갱신] {REVIEWED_PATH} ({len(rows)}행, 신규 컬럼 {len(NEW_FIELDS)}개 추가, 11건 재판정 반영)")

    # manual_review_queue.csv: 이번에 해소된 11건을 제외하고 재생성 (현재는 전부 해소되어 0건)
    with open(QUEUE_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=[
            "service_id", "service_name", "region", "target_original",
            "criteria_original", "support_original", "matched_keyword", "reason_for_review",
        ])
        w.writeheader()
    print(f"[갱신] {QUEUE_PATH} (해소된 {len(updated_queue_removed)}건 제거, 남은 대기 0건)")

    # --- 기존 54건 INCLUDE / 33건 EXCLUDE 중 새 기준과 충돌 가능성 탐지 (자동 수정 없음) ---
    print("\n=== 충돌/재검토 후보 탐지 (읽기 전용, 수정 없음) ===")
    flagged = []
    for row in rows:
        sid = row["service_id"]
        if sid in DECISIONS_V2:
            continue
        status = row["review_status"]
        note = row.get("review_note", "")
        target = row.get("target_original", "")
        if status == "EXCLUDE" and ("장애인" in note or "장애인" in target) and "고령자" not in note.replace("비고령자", ""):
            flagged.append((sid, row["service_name"], status, "EXCLUDE 사유에 '장애인'이 언급됨 — 새 기준(SENIOR_CONDITIONAL)으로 재검토 여지가 있는지 확인 필요"))
    import io
    report_path = PROCESSED_DIR.parent / "raw" / "_conflict_scan_report.txt"
    with io.open(report_path, "w", encoding="utf-8") as rf:
        if flagged:
            for sid, name, status, reason in flagged:
                line = f"  - {sid} | {name} | {status} | {reason}"
                rf.write(line + "\n")
        else:
            rf.write("  (해당 없음)\n")
    print(f"[저장] {report_path} (충돌 후보 {len(flagged)}건, 콘솔 인코딩 문제로 파일로 출력)")


if __name__ == "__main__":
    main()
