"""
데이터 수집·전처리 단계 최종 마무리 스크립트.

순서: 입력 검증 -> NEEDS_REVIEW 3건 최종판정 -> UNKNOWN 142건 완결성 재검증
      -> welfare_candidates_reviewed.csv 병합 -> 병합 후 무결성 검사
      -> welfare_services_final.csv 생성 -> 최종 QA

원칙:
- 새 API 호출 없음, 새 서비스 수집 없음.
- 원문 필드(target_original/criteria_original/support_original/application_original 등)는
  절대 수정하지 않는다.
- 근거 없는 값은 추정하지 않고 빈 값으로 남긴다.
- 검증 단계에서 실패하면 이후 단계(파일 저장)를 진행하지 않는다.
"""
import csv
import sys
import io
from pathlib import Path
from collections import Counter

ROOT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT_DIR / "data" / "processed"

REVIEWED_PATH = PROCESSED_DIR / "welfare_candidates_reviewed.csv"
BATCH_PATHS = {
    "batch01": PROCESSED_DIR / "unknown_review_batch_01.csv",
    "batch02": PROCESSED_DIR / "unknown_review_batch_02.csv",
    "batch03": PROCESSED_DIR / "unknown_review_batch_03.csv",
    "batch04": PROCESSED_DIR / "unknown_review_batch_04.csv",
}
NEEDS_REVIEW_PATH = PROCESSED_DIR / "unknown_needs_final_review.csv"

FINAL_DATASET_PATH = PROCESSED_DIR / "welfare_services_final.csv"

REPORT_PATH = Path(
    r"C:\Users\이보미\AppData\Local\Temp\claude\C--Users-----PycharmProjects-nutrition-care-navigator"
    r"\7a1f5c05-8538-4103-9e17-ba9f86ce90c4\scratchpad\finalize_dataset_report.txt"
)

REPORT_LINES = []


def log(*args):
    line = " ".join(str(a) for a in args)
    REPORT_LINES.append(line)
    print(line)


def fail(msg):
    log("[FAIL]", msg)
    log("\n검증 실패로 최종 파일을 생성하지 않고 중단합니다.")
    with io.open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(REPORT_LINES))
    sys.exit(1)


# ------------------------------------------------------------------
# 0. 입력 파일 존재/컬럼 확인
# ------------------------------------------------------------------
def load_rows(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


log("=== 0. 입력 파일 검증 ===")
required_files = [REVIEWED_PATH, *BATCH_PATHS.values(), NEEDS_REVIEW_PATH]
for p in required_files:
    if not p.exists():
        fail(f"필수 입력 파일이 없습니다: {p}")
log("모든 필수 입력 파일 존재 확인 완료.")

reviewed_rows = load_rows(REVIEWED_PATH)
reviewed_cols = list(reviewed_rows[0].keys())
log(f"welfare_candidates_reviewed.csv: {len(reviewed_rows)}행, 컬럼 {len(reviewed_cols)}개")

batches = {name: load_rows(p) for name, p in BATCH_PATHS.items()}
for name, rows in batches.items():
    log(f"{name}: {len(rows)}행")

needs_review_rows = load_rows(NEEDS_REVIEW_PATH)
log(f"unknown_needs_final_review.csv: {len(needs_review_rows)}행")

# ------------------------------------------------------------------
# 1. NEEDS_REVIEW 3건 최종 판정
# ------------------------------------------------------------------
log("\n=== 1. NEEDS_REVIEW 3건 최종 판정 ===")

# 원문 재확인 결과에 근거한 최종 판정 (docs/classification_criteria.md v2.1 대조).
# 세 건 모두 '행려자'(귀향 희망, 관할지역 비거주자) 대상의 여비 지원 사업이며,
# 급식비는 여비·장제비·의료비와 묶인 일회성 긴급구호의 부수적 항목이다.
# 결정적 근거: WLF00000783 원문에 "평택시민 신청 불가"가 명시돼 있어, 이 사업이
# 지역사회 거주자를 위한 서비스가 아니라 오히려 거주자를 배제하는 통과객 대상
# 긴급구호임이 확인된다. 세 건 모두 동일 성격(같은 '행려자' 사업 유형)이므로
# 이 근거를 동일하게 적용한다(유형만 보고 일괄 처리한 것이 아니라, 결정적 문구가
# 확인된 사례를 근거로 동일 유형 나머지 건에도 동일 논리를 적용한 것).
FINAL_NEEDS_REVIEW_DECISIONS = {
    "WLF00001309": dict(
        nutrition_relevance="NOT_NUTRITION_RELEVANT",  # SUPPORTIVE_NUTRITION에서 하향 조정
        review_status="EXCLUDE",
        reason=(
            "대상 '행려자'는 관내 거주자가 아니라 타 지역으로 귀향(귀가)하려는 통과객이다. "
            "급식비(8,000원)는 여비·장제비·의료비와 묶인 1회성 긴급구호의 부수 항목일 뿐, "
            "본 프로젝트가 다루는 '지속적/반복적으로 이용 가능한 식사·영양돌봄'(A) 또는 "
            "'고령자가 실제 이용 가능한 지역사회 영양지원'(B)에 해당하지 않고, "
            "'일회성 긴급구호 과정의 부수적 급식'(C)에 해당한다. "
            "동일 유형인 WLF00000783 원문에 '평택시민 신청 불가'가 명시돼 있어, "
            "이 유형의 사업이 지역사회 거주 고령자 대상 서비스가 아님을 뒷받침한다. "
            "nutrition_relevance를 SUPPORTIVE_NUTRITION에서 NOT_NUTRITION_RELEVANT로 재조정하고 EXCLUDE로 확정."
        ),
    ),
    "WLF00003721": dict(
        nutrition_relevance="NOT_NUTRITION_RELEVANT",
        review_status="EXCLUDE",
        reason=(
            "대상 '관외거주 행려자'는 정의상 지역사회 거주자가 아니다. 숙박비·교통비·급식비를 묶은 "
            "1회성 긴급구호(귀향 버스요금 및 숙박비 지급)이며, 지속적·반복적 식사·영양 지원이 아니다. "
            "'일회성 긴급구호 과정의 부수적 급식'(C)에 해당해 EXCLUDE. WLF00001309와 동일 논리."
        ),
    ),
    "WLF00000783": dict(
        nutrition_relevance="NOT_NUTRITION_RELEVANT",
        review_status="EXCLUDE",
        reason=(
            "원문에 '평택시민 신청 불가'가 명시돼 있어, 이 사업은 지역 거주자를 명시적으로 "
            "배제하고 타 지역으로 귀향하려는 통과객만 대상으로 한다는 것이 원문으로 확인된다. "
            "급식비(실비)는 여비의 부수 항목이며 '일회성 긴급구호 과정의 부수적 급식'(C)에 "
            "해당해 EXCLUDE. 이 문구가 세 건 모두에 동일 논리를 적용하는 결정적 근거가 된다."
        ),
    ),
}

nr_ids = {r["service_id"] for r in needs_review_rows}
if nr_ids != set(FINAL_NEEDS_REVIEW_DECISIONS.keys()):
    fail(f"NEEDS_REVIEW 3건의 service_id가 예상과 다릅니다: {nr_ids}")

for r in needs_review_rows:
    d = FINAL_NEEDS_REVIEW_DECISIONS[r["service_id"]]
    log(f'{r["service_id"]} | {r["service_name"]} -> {d["review_status"]} '
        f'(nutrition_relevance: {r["nutrition_relevance"]} -> {d["nutrition_relevance"]})')

log("NEEDS_REVIEW 3건 모두 EXCLUDE로 최종 확정 (원문 재검토로 판단 가능했으며, 억지 판정이 아님).")
log("최종 NEEDS_REVIEW 건수: 0")

# ------------------------------------------------------------------
# 2. UNKNOWN 142건 완결성 재검증 (batch 결과 + 3건 최종판정 반영)
# ------------------------------------------------------------------
log("\n=== 2. UNKNOWN 142건 완결성 재검증 ===")

unk_ids_in_order = [r["service_id"] for r in reviewed_rows if r["senior_relevance"] == "unknown"]
unk_set = set(unk_ids_in_order)
log(f"원래 UNKNOWN service_id 수: {len(unk_ids_in_order)} (고유 {len(unk_set)})")

batch_ids = {name: [r["service_id"] for r in rows] for name, rows in batches.items()}
for name in BATCH_PATHS:
    log(f"{name} 수: {len(batch_ids[name])} (고유 {len(set(batch_ids[name]))})")
    if len(batch_ids[name]) != len(set(batch_ids[name])):
        fail(f"{name} 내부에 중복 service_id가 있습니다.")

expected_counts = {"batch01": 30, "batch02": 30, "batch03": 40, "batch04": 42}
for name, expected in expected_counts.items():
    if len(batch_ids[name]) != expected:
        fail(f"{name} 건수가 예상({expected})과 다릅니다: {len(batch_ids[name])}")

batch_sets = {name: set(ids) for name, ids in batch_ids.items()}
union_all = set()
for s in batch_sets.values():
    union_all |= s
log(f"네 batch 합집합 고유 service_id 수: {len(union_all)}")

from itertools import combinations
dup_ids = set()
for a, b in combinations(BATCH_PATHS.keys(), 2):
    dup_ids |= (batch_sets[a] & batch_sets[b])
log(f"batch 간 중복 service_id 수: {len(dup_ids)}")

not_reviewed = unk_set - union_all
log(f"아직 검토되지 않은 service_id 수: {len(not_reviewed)}")

not_in_unknown = union_all - unk_set
log(f"원래 UNKNOWN에 없는데 batch에 들어간 service_id 수: {len(not_in_unknown)}")

if not (len(unk_set) == 142 and len(union_all) == 142 and len(dup_ids) == 0
        and len(not_reviewed) == 0 and len(not_in_unknown) == 0):
    fail("UNKNOWN 142건 완결성 검증 실패.")
log("완결성 검증: OK (142 = 30+30+40+42, 고유 142, 중복 0, 미검토 0, 범위밖 0)")

# batch 데이터 통합 (NEEDS_REVIEW 3건은 최종판정으로 덮어씀)
merged_batch_by_id = {}
for name, rows in batches.items():
    for r in rows:
        merged_batch_by_id[r["service_id"]] = dict(r, source_batch=name)

for sid, d in FINAL_NEEDS_REVIEW_DECISIONS.items():
    merged_batch_by_id[sid]["review_status"] = d["review_status"]
    merged_batch_by_id[sid]["nutrition_relevance"] = d["nutrition_relevance"]
    merged_batch_by_id[sid]["classification_reason"] = d["reason"]

status_counter = Counter(r["review_status"] for r in merged_batch_by_id.values())
log(f"최종(3건 판정 반영) review_status 분포: {dict(status_counter)}")
if status_counter.get("NEEDS_REVIEW", 0) != 0:
    fail("NEEDS_REVIEW가 0건이 아닙니다.")

srv2_counter = Counter(r["senior_relation_v2"] for r in merged_batch_by_id.values())
nutr_counter = Counter(r["nutrition_relevance"] for r in merged_batch_by_id.values())
log(f"senior_relation_v2 분포: {dict(srv2_counter)}")
log(f"nutrition_relevance 분포: {dict(nutr_counter)}")

prev_stats = "batch04 요약 보고서 기준: INCLUDE 21 / EXCLUDE 118 / NEEDS_REVIEW 3"
log(f"\n(참고) 이전 보고값: {prev_stats}")
log(f"이번 최종값과의 차이 이유: NEEDS_REVIEW 3건을 전부 EXCLUDE로 재판정했기 때문에 "
    f"EXCLUDE가 118 -> {status_counter['EXCLUDE']}로 증가하고 NEEDS_REVIEW는 3 -> 0이 됨. "
    f"INCLUDE 건수(21)는 변동 없음.")

# ------------------------------------------------------------------
# 3. welfare_candidates_reviewed.csv 병합
# ------------------------------------------------------------------
log("\n=== 3. welfare_candidates_reviewed.csv 병합 ===")

PROTECTED_FIELDS = ["service_id", "service_name", "sido", "sigungu",
                     "target_original", "criteria_original", "support_original",
                     "application_original", "contact", "source_api",
                     "matched_keyword", "matched_field", "senior_relevance"]

NEW_COLUMNS = ["nutrition_relevance", "service_type_secondary", "data_quality_note", "source_batch"]

before_snapshot = {r["service_id"]: {k: r[k] for k in PROTECTED_FIELDS} for r in reviewed_rows}

new_fieldnames = reviewed_cols + [c for c in NEW_COLUMNS if c not in reviewed_cols]

merged_rows = []
nutritionist_direct_ids = {"WLF00005102"}  # batch03 검토에서 원문에 '전문 영양사 진단'이 명시된 유일 사례

for r in reviewed_rows:
    row = dict(r)
    for c in NEW_COLUMNS:
        row.setdefault(c, "")

    sid = row["service_id"]
    if sid in merged_batch_by_id:
        b = merged_batch_by_id[sid]
        row["review_status"] = b["review_status"]
        row["senior_relation"] = b["senior_relation_v2"]  # 기존 senior_relation 컬럼에 v2 값 반영(중복 컬럼 생성 안 함)
        row["nutrition_relevance"] = b["nutrition_relevance"]
        row["verification_level"] = b["verification_level"]
        row["service_type_primary"] = b["service_type_primary"]
        row["service_type_secondary"] = b["service_type_secondary"]
        row["data_quality_note"] = b.get("data_quality_note", "")
        row["review_note"] = b["classification_reason"]
        row["source_batch"] = b["source_batch"]

        if b["service_type_primary"]:
            types = [b["service_type_primary"]]
            if b["service_type_secondary"]:
                types.append(b["service_type_secondary"])
            row["service_type"] = "|".join(types)

        if b["review_status"] == "EXCLUDE" and not row.get("exclusion_reason"):
            row["exclusion_reason"] = b["classification_reason"]

        if b["review_status"] == "INCLUDE":
            row["nutritionist_involvement"] = "direct" if sid in nutritionist_direct_ids else "not_specified"
            if b["service_type_primary"] == "meal_support" or b["service_type_secondary"] == "meal_support":
                row["meal_support_flag"] = "true"
            if b["service_type_primary"] == "food_cost_support" or b["service_type_secondary"] == "food_cost_support":
                row["food_cost_support_flag"] = "true"
        # min_age/disability_required/low_income_required/single_household_required/
        # homebound_or_mobility_condition/eligibility_summary/support_summary는 batch01~04에서
        # 세부 판정을 하지 않았으므로 값을 임의로 채우지 않고 비워 둔다(추정 금지 원칙).

    merged_rows.append(row)

# 원문 보존 검증
protected_diff = 0
for row in merged_rows:
    sid = row["service_id"]
    before = before_snapshot.get(sid)
    if before is None:
        fail(f"병합 후 존재하지 않는 service_id가 발견됨: {sid}")
    for k in PROTECTED_FIELDS:
        if row[k] != before[k]:
            protected_diff += 1
            log(f"  [경고] 보호필드 변경 감지: {sid}.{k}")

if protected_diff > 0:
    fail(f"보호 필드가 {protected_diff}건 변경되었습니다. 병합을 중단합니다.")
log("원문/보호 필드 변경 건수: 0 (검증 통과)")

if len(merged_rows) != len(reviewed_rows):
    fail(f"병합 전후 행 개수가 다릅니다: {len(reviewed_rows)} -> {len(merged_rows)}")
log(f"행 개수 동일 확인: {len(reviewed_rows)} -> {len(merged_rows)}")

merged_ids = [row["service_id"] for row in merged_rows]
if len(merged_ids) != len(set(merged_ids)):
    fail("병합 결과에 service_id 중복이 있습니다.")
if any(not sid for sid in merged_ids):
    fail("병합 결과에 service_id가 비어있는 행이 있습니다.")
if set(merged_ids) != set(before_snapshot.keys()):
    fail("병합 전후 service_id 집합이 달라졌습니다(손실 또는 추가 발생).")
log("service_id 무결성 확인: null 없음, 중복 없음, 손실/추가 없음.")

merged_status = Counter(row["review_status"] for row in merged_rows)
log(f"병합 후 review_status 분포(357건 전체): {dict(merged_status)}")

not_yet_among_unknown = sum(
    1 for row in merged_rows if row["service_id"] in unk_set and row["review_status"] == "NOT_YET_REVIEWED"
)
log(f"UNKNOWN 142건 중 NOT_YET_REVIEWED로 남은 건수: {not_yet_among_unknown}")
if not_yet_among_unknown != 0:
    fail("UNKNOWN 142건 중 NOT_YET_REVIEWED가 남아있습니다.")

# 논리적 모순 탐지 (자동 수정하지 않고 보고만)
log("\n--- 논리적 모순 탐지 (자동 수정 없음, 보고만) ---")
contradictions = []
for row in merged_rows:
    sid = row["service_id"]
    status = row["review_status"]
    sr = row.get("senior_relation", "")
    nr = row.get("nutrition_relevance", "")
    if status == "INCLUDE" and sr == "NOT_SENIOR_RELEVANT":
        contradictions.append((sid, "INCLUDE인데 senior_relation=NOT_SENIOR_RELEVANT"))
    if status == "INCLUDE" and nr and nr == "NOT_NUTRITION_RELEVANT":
        contradictions.append((sid, "INCLUDE인데 nutrition_relevance=NOT_NUTRITION_RELEVANT"))
    if status == "INCLUDE" and row.get("meal_support_flag") == "true" and "밑반찬" not in row["support_original"] \
            and "식사" not in row["support_original"] and "급식" not in row["support_original"] \
            and "도시락" not in row["support_original"] and "반찬" not in row["support_original"] \
            and "식품" not in row["support_original"] and "영양" not in row["support_original"] \
            and "식료품" not in row["support_original"]:
        contradictions.append((sid, "meal_support_flag=true인데 support_original에 식사 관련 단어가 보이지 않음(재확인 필요)"))
    if row.get("nutritionist_involvement") == "direct" and "영양사" not in row["support_original"] \
            and "영양사" not in row["target_original"] and "영양사" not in row["criteria_original"]:
        contradictions.append((sid, "nutritionist_involvement=direct인데 원문에 '영양사' 문구가 보이지 않음(재확인 필요)"))

if contradictions:
    log(f"탐지된 모순/재확인 필요 항목: {len(contradictions)}건")
    for sid, msg in contradictions:
        log(f"  - {sid}: {msg}")
else:
    log("탐지된 모순 없음.")

# ------------------------------------------------------------------
# 4. welfare_candidates_reviewed.csv 저장
# ------------------------------------------------------------------
with open(REVIEWED_PATH, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=new_fieldnames)
    w.writeheader()
    w.writerows(merged_rows)
log(f"\n[저장] {REVIEWED_PATH} ({len(merged_rows)}행, 컬럼 {len(new_fieldnames)}개)")

# ------------------------------------------------------------------
# 5. 최종 추천 후보 데이터셋 생성 (welfare_services_final.csv)
# ------------------------------------------------------------------
log("\n=== 5. 최종 추천 후보 데이터셋 생성 ===")

final_candidates = [row for row in merged_rows if row["review_status"] == "INCLUDE"]
log(f"review_status == INCLUDE 인 행: {len(final_candidates)}건")

# INCLUDE 조건이 classification_criteria.md와 충돌하지 않는지 재검증
invalid_include = []
for row in final_candidates:
    sr = row.get("senior_relation", "")
    if sr == "NOT_SENIOR_RELEVANT":
        invalid_include.append((row["service_id"], "senior_relation=NOT_SENIOR_RELEVANT"))
    # service_type이 비어있는 INCLUDE는 지원내용 근거가 없다는 뜻이므로 재확인 필요
    if not row.get("service_type") and not row.get("service_type_primary"):
        invalid_include.append((row["service_id"], "service_type 정보 없음"))

if invalid_include:
    log(f"[경고] classification_criteria.md와 충돌 가능성이 있는 INCLUDE {len(invalid_include)}건:")
    for sid, msg in invalid_include:
        log(f"  - {sid}: {msg}")
else:
    log("INCLUDE 조건 재검증: classification_criteria.md와 충돌 없음.")

FINAL_FIELDS = [
    "service_id", "service_name", "source_api", "sido", "sigungu",
    "target_original", "criteria_original", "support_original", "application_original", "contact",
    "senior_relation", "nutrition_relevance", "service_type", "service_type_primary", "service_type_secondary",
    "min_age", "disability_required", "low_income_required", "single_household_required",
    "homebound_or_mobility_condition", "eligibility_summary",
    "meal_support_flag", "food_cost_support_flag", "support_summary", "nutritionist_involvement",
    "verification_level", "review_note", "data_quality_note",
]

final_rows = []
for row in final_candidates:
    out = {k: row.get(k, "") for k in FINAL_FIELDS}
    final_rows.append(out)

with open(FINAL_DATASET_PATH, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=FINAL_FIELDS)
    w.writeheader()
    w.writerows(final_rows)
log(f"[저장] {FINAL_DATASET_PATH} ({len(final_rows)}행)")

# ------------------------------------------------------------------
# 6. 최종 데이터 품질 QA
# ------------------------------------------------------------------
log("\n=== 6. 최종 데이터 품질 QA (welfare_services_final.csv) ===")

log(f"1. 총 서비스 수: {len(final_rows)}")

ids = [r["service_id"] for r in final_rows]
log(f"2. service_id 중복: {len(ids) - len(set(ids))}건")
log(f"3. service_id null: {sum(1 for r in final_rows if not r['service_id'])}건")
log(f"4. service_name null: {sum(1 for r in final_rows if not r['service_name'])}건")

region_blank = sum(1 for r in final_rows if not r["sido"] and not r["sigungu"])
log(f"5. region(sido+sigungu) 둘 다 비어있는 행: {region_blank}건")

log(f"6. service_type_primary 분포: {dict(Counter(r['service_type_primary'] for r in final_rows))}")
log(f"7. senior_relation 분포: {dict(Counter(r['senior_relation'] for r in final_rows))}")
log(f"8. nutrition_relevance 분포: {dict(Counter(r['nutrition_relevance'] for r in final_rows))}")
log(f"9. verification_level 분포: {dict(Counter(r['verification_level'] for r in final_rows))}")
log(f"10. nutritionist_involvement 분포: {dict(Counter(r['nutritionist_involvement'] for r in final_rows))}")

log(f"11. 지역별(sido) 서비스 수: {dict(Counter(r['sido'] or '(전국/미기재)' for r in final_rows))}")
log(f"12. source_api(중앙부처/지자체) 분포: {dict(Counter(r['source_api'] for r in final_rows))}")

missing_core = sum(
    1 for r in final_rows
    if not r["target_original"] or not r["support_original"]
)
log(f"13. 원문 핵심 필드(target_original/support_original) 누락 건수: {missing_core}")

dq_count = sum(1 for r in final_rows if r["data_quality_note"])
log(f"14. data_quality_note가 기록된 서비스 수: {dq_count}")

log("\n--- 추가 모순/중복 검사 ---")
no_nutrition = [r["service_id"] for r in final_rows if r["nutrition_relevance"] == "NOT_NUTRITION_RELEVANT"]
log(f"영양 관련성 없는데 INCLUDE: {len(no_nutrition)}건 {no_nutrition if no_nutrition else ''}")
not_senior = [r["service_id"] for r in final_rows if r["senior_relation"] == "NOT_SENIOR_RELEVANT"]
log(f"고령자 관련성 없는데 INCLUDE: {len(not_senior)}건 {not_senior if not_senior else ''}")
no_support = [r["service_id"] for r in final_rows if not r["support_original"].strip()]
log(f"지원내용(support_original)이 비어있는 INCLUDE: {len(no_support)}건 {no_support if no_support else ''}")

name_counter = Counter(r["service_name"] for r in final_rows)
similar_names = {name: c for name, c in name_counter.items() if c > 1}
log(f"동일 service_name이 여러 지역에서 등록된 경우(참고용, 삭제 안 함): {len(similar_names)}종")
for name, c in similar_names.items():
    matching_ids = [r["service_id"] for r in final_rows if r["service_name"] == name]
    log(f"  - '{name}' {c}건: {matching_ids}")

with io.open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(REPORT_LINES))
log(f"\n[저장] 상세 리포트: {REPORT_PATH}")
log("\n=== 완료 ===")
