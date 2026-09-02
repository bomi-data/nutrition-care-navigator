"""
사람이(Claude가) 직접 읽고 내린 검토 결과(review_decisions.json)를
welfare_candidates.csv와 병합해 최종 산출물을 만든다.

- data/processed/welfare_candidates_reviewed.csv : 357건 전체(이번에 검토하지 않은
  건은 review_status=NOT_YET_REVIEWED로 남김)
- data/processed/manual_review_queue.csv : 이번 회차에서 NEEDS_REVIEW로 분류된 건만
"""
import csv
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
CANDIDATES_PATH = PROCESSED_DIR / "welfare_candidates.csv"
DECISIONS_PATH = Path(
    r"C:\Users\이보미\AppData\Local\Temp\claude\C--Users-----PycharmProjects-nutrition-care-navigator"
    r"\7a1f5c05-8538-4103-9e17-ba9f86ce90c4\scratchpad\review_decisions.json"
)

REVIEWED_FIELDS = [
    "service_id", "source_api", "service_name", "sido", "sigungu",
    "senior_relevance",
    "review_status", "service_type", "verification_level",
    "target_original", "criteria_original", "support_original",
    "application_original", "contact",
    "nutritionist_involvement",
    "matched_keyword", "matched_field",
    "exclusion_reason", "review_note",
]

QUEUE_FIELDS = [
    "service_id", "service_name", "region",
    "target_original", "criteria_original", "support_original",
    "matched_keyword", "reason_for_review",
]


def main():
    with open(CANDIDATES_PATH, encoding="utf-8-sig") as f:
        candidates = list(csv.DictReader(f))

    decisions = {d["service_id"]: d for d in json.loads(DECISIONS_PATH.read_text(encoding="utf-8"))}

    reviewed_rows = []
    queue_rows = []

    for c in candidates:
        d = decisions.get(c["service_id"])
        row = {
            "service_id": c["service_id"],
            "source_api": c["source_api"],
            "service_name": c["service_name"],
            "sido": c["sido"],
            "sigungu": c["sigungu"],
            "senior_relevance": c["senior_relevance"],
            "review_status": d["review_status"] if d else "NOT_YET_REVIEWED",
            "service_type": d["service_type"] if d else "",
            "verification_level": d["verification_level"] if d else "",
            "target_original": c["target_original"],
            "criteria_original": c["criteria_original"],
            "support_original": c["support_original"],
            "application_original": c["application_original"],
            "contact": c["contact"],
            "nutritionist_involvement": d["nutritionist_involvement"] if d else "unknown",
            "matched_keyword": c["matched_keyword"],
            "matched_field": c["matched_field"],
            "exclusion_reason": c["exclusion_reason"],
            "review_note": d["review_note"] if d else "",
        }
        reviewed_rows.append(row)

        if d and d["review_status"] == "NEEDS_REVIEW":
            queue_rows.append({
                "service_id": c["service_id"],
                "service_name": c["service_name"],
                "region": f'{c["sido"]} {c["sigungu"]}'.strip(),
                "target_original": c["target_original"],
                "criteria_original": c["criteria_original"],
                "support_original": c["support_original"],
                "matched_keyword": c["matched_keyword"],
                "reason_for_review": d["review_note"],
            })

    out_path = PROCESSED_DIR / "welfare_candidates_reviewed.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=REVIEWED_FIELDS)
        w.writeheader()
        w.writerows(reviewed_rows)
    print(f"[저장] {out_path} ({len(reviewed_rows)}행)")

    queue_path = PROCESSED_DIR / "manual_review_queue.csv"
    with open(queue_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=QUEUE_FIELDS)
        w.writeheader()
        w.writerows(queue_rows)
    print(f"[저장] {queue_path} ({len(queue_rows)}행)")

    from collections import Counter
    print("\nreview_status 분포:", Counter(r["review_status"] for r in reviewed_rows))
    reviewed_only = [r for r in reviewed_rows if r["review_status"] != "NOT_YET_REVIEWED"]
    print("이번 회차 검토 건수:", len(reviewed_only))
    print("service_type 분포(INCLUDE만):", Counter(
        r["service_type"] for r in reviewed_rows if r["review_status"] == "INCLUDE"
    ))
    print("source_api 분포(INCLUDE만):", Counter(
        r["source_api"] for r in reviewed_rows if r["review_status"] == "INCLUDE"
    ))
    print("verification_level 분포(INCLUDE만):", Counter(
        r["verification_level"] for r in reviewed_rows if r["review_status"] == "INCLUDE"
    ))


if __name__ == "__main__":
    main()
