"""
UNKNOWN 142건 전체 완결성 검사 + batch01~04 통합 통계 + NEEDS_REVIEW 통합 파일 생성.

- 어떤 기존 파일도 수정하지 않는다(welfare_candidates_reviewed.csv, batch01~04 모두 읽기 전용).
- 최종 병합(welfare_candidates_reviewed.csv에 반영)은 하지 않는다.
- 산출물: data/processed/unknown_needs_final_review.csv
"""
import csv
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
NEEDS_REVIEW_OUT = PROCESSED_DIR / "unknown_needs_final_review.csv"
REPORT_OUT = Path(
    r"C:\Users\이보미\AppData\Local\Temp\claude\C--Users-----PycharmProjects-nutrition-care-navigator"
    r"\7a1f5c05-8538-4103-9e17-ba9f86ce90c4\scratchpad\finalize_report.txt"
)


def load_rows(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    out = []

    unk_ids = [
        r["service_id"] for r in
        csv.DictReader(open(REVIEWED_PATH, encoding="utf-8-sig"))
        if r["senior_relevance"] == "unknown"
    ]
    unk_set = set(unk_ids)

    batches = {name: load_rows(p) for name, p in BATCH_PATHS.items()}
    batch_ids = {name: [r["service_id"] for r in rows] for name, rows in batches.items()}
    batch_sets = {name: set(ids) for name, ids in batch_ids.items()}

    out.append("=== 완결성 검사 ===")
    out.append(f"원래 UNKNOWN service_id 수: {len(unk_ids)} (고유 {len(unk_set)})")
    for name in BATCH_PATHS:
        out.append(f"{name} 수: {len(batch_ids[name])} (고유 {len(batch_sets[name])})")

    union_all = set()
    for name in BATCH_PATHS:
        union_all |= batch_sets[name]
    out.append(f"네 batch 합집합 고유 service_id 수: {len(union_all)}")

    # 중복(둘 이상의 batch에 동시에 존재하는 id) 계산
    from itertools import combinations
    dup_ids = set()
    for a, b in combinations(BATCH_PATHS.keys(), 2):
        dup_ids |= (batch_sets[a] & batch_sets[b])
    out.append(f"batch 간 중복 service_id 수: {len(dup_ids)}")
    if dup_ids:
        out.append(f"  중복 id 목록: {sorted(dup_ids)}")

    not_reviewed = unk_set - union_all
    out.append(f"아직 검토되지 않은 service_id 수: {len(not_reviewed)}")
    if not_reviewed:
        out.append(f"  목록: {sorted(not_reviewed)}")

    not_in_unknown = union_all - unk_set
    out.append(f"원래 UNKNOWN에 없는데 batch에 들어간 service_id 수: {len(not_in_unknown)}")
    if not_in_unknown:
        out.append(f"  목록: {sorted(not_in_unknown)}")

    all_ok = (
        len(unk_set) == 142
        and len(union_all) == 142
        and len(dup_ids) == 0
        and len(not_reviewed) == 0
        and len(not_in_unknown) == 0
    )
    out.append(f"\n전체 정합성: {'OK' if all_ok else 'FAIL - 아래 통계는 참고용, 문제 해결 필요'}")

    # === 142건 전체 통계 ===
    out.append("\n=== UNKNOWN 142건 전체 결과 통계 ===")
    all_rows = []
    for name, rows in batches.items():
        for r in rows:
            r["_source_batch"] = name
            all_rows.append(r)

    out.append(f"검토 총 건수: {len(all_rows)}")
    out.append("review_status: " + str(Counter(r["review_status"] for r in all_rows)))
    out.append("senior_relation_v2: " + str(Counter(r["senior_relation_v2"] for r in all_rows)))
    out.append("nutrition_relevance: " + str(Counter(r["nutrition_relevance"] for r in all_rows)))

    include_rows = [r for r in all_rows if r["review_status"] == "INCLUDE"]
    out.append(f"\n=== INCLUDE 전체 목록 ({len(include_rows)}건) ===")
    for r in include_rows:
        out.append(
            f'{r["service_id"]} | {r["service_name"]} | {r["region"]} | '
            f'{r["senior_relation_v2"]} | {r["nutrition_relevance"]} | '
            f'{r["service_type_primary"]} | {r["verification_level"]} | ({r["_source_batch"]})'
        )

    # === NEEDS_REVIEW 통합 ===
    needs_review_rows = [r for r in all_rows if r["review_status"] == "NEEDS_REVIEW"]
    out.append(f"\n=== NEEDS_REVIEW 전체 목록 ({len(needs_review_rows)}건) ===")
    for r in needs_review_rows:
        out.append(f'{r["service_id"]} | {r["service_name"]} | {r["region"]} | ({r["_source_batch"]})')

    # welfare_candidates_reviewed.csv에서 application_original을 보강해서 unknown_needs_final_review.csv 작성
    with open(REVIEWED_PATH, encoding="utf-8-sig") as f:
        reviewed_lookup = {r["service_id"]: r for r in csv.DictReader(f)}

    nr_fieldnames = [
        "service_id", "service_name", "region",
        "target_original", "criteria_original", "support_original", "application_original",
        "senior_relation_v2", "nutrition_relevance",
        "classification_reason", "data_quality_note", "source_batch",
    ]
    nr_out_rows = []
    for r in needs_review_rows:
        full = reviewed_lookup[r["service_id"]]
        nr_out_rows.append({
            "service_id": r["service_id"],
            "service_name": r["service_name"],
            "region": r["region"],
            "target_original": r["target_original"],
            "criteria_original": r["criteria_original"],
            "support_original": r["support_original"],
            "application_original": full["application_original"],
            "senior_relation_v2": r["senior_relation_v2"],
            "nutrition_relevance": r["nutrition_relevance"],
            "classification_reason": r["classification_reason"],
            "data_quality_note": r.get("data_quality_note", ""),
            "source_batch": r["_source_batch"],
        })

    with open(NEEDS_REVIEW_OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=nr_fieldnames)
        w.writeheader()
        w.writerows(nr_out_rows)
    out.append(f"\n[저장] {NEEDS_REVIEW_OUT} ({len(nr_out_rows)}행)")

    with io.open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("done, see report")
    print("all_ok:", all_ok)
    print("include count:", len(include_rows))
    print("needs_review count:", len(needs_review_rows))


if __name__ == "__main__":
    main()
