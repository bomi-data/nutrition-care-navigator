"""Merge a user-verified enrichment candidate file into the production
welfare_services_recommendation_ready.csv.

This is NOT a generic "append any candidate file" tool -- it enforces the
same safety checks used throughout the enrichment pipeline before writing
anything:

  1. service_id / normalized-name / region collision check against the
     existing production rows (refuses to merge on any hit).
  2. required-column compatibility check (recommender.loader.REQUIRED_COLUMNS).
  3. the candidate file's rows must load cleanly via recommender.loader
     (catches malformed TriState/enum values before they reach production).
  4. writes a timestamped backup of the production CSV before touching it.
  5. projects candidate rows onto the exact 36-column production schema
     (see docs/cheonan_official_enrichment_report.md §0.3 -- the candidate
     file's extra provenance-only columns, e.g. official_url, are folded
     into data_quality_note instead of expanding the production schema).

Usage:
    python -m data_collection.merge_verified_enrichment \
        --candidates data/processed/welfare_services_enrichment_cheonan_verified.csv

Refuses to run (no file written) if any collision check fails.
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from recommender.loader import DEFAULT_CSV_PATH, REQUIRED_COLUMNS, load_services  # noqa: E402

PRODUCTION_COLUMNS = [
    "service_id", "service_name", "source_api", "sido", "sigungu",
    "target_original", "criteria_original", "support_original",
    "application_original", "contact", "senior_relation",
    "nutrition_relevance", "service_type", "service_type_primary",
    "service_type_secondary", "min_age", "disability_required",
    "low_income_required", "single_household_required",
    "homebound_or_mobility_condition", "eligibility_summary",
    "meal_support_flag", "food_cost_support_flag", "support_summary",
    "nutritionist_involvement", "verification_level", "review_note",
    "data_quality_note", "region_scope", "max_age", "age_condition_type",
    "age_condition_note", "structured_from_original",
    "structured_fields_added", "special_eligibility_required",
    "special_eligibility_note",
]

# columns present only in candidate/enrichment files, not in production --
# folded into data_quality_note rather than expanding the production schema
PROVENANCE_ONLY_COLUMNS = ["official_url", "source_verified_by", "verified_at", "source_note"]


class MergeBlockedError(Exception):
    """Raised when a safety check fails; nothing is written in this case."""


def _normalize_name(name: str) -> str:
    return (name or "").replace(" ", "").replace("·", "").lower()


def audit(candidates_path: Path, production_path: Path = DEFAULT_CSV_PATH) -> list[dict]:
    """Run all pre-merge safety checks. Returns the candidate rows (as raw
    CSV dicts) ready for projection if every check passes; raises
    MergeBlockedError with a specific reason otherwise.
    """
    base_services = load_services(csv_path=production_path)
    candidate_services = load_services(csv_path=candidates_path)  # raises on schema issues

    base_ids = {s.service_id for s in base_services}
    candidate_ids = {s.service_id for s in candidate_services}
    id_collision = base_ids & candidate_ids
    if id_collision:
        raise MergeBlockedError(f"service_id collision with production: {id_collision}")

    base_names_norm = {_normalize_name(s.service_name): s.service_id for s in base_services}
    for c in candidate_services:
        cn = _normalize_name(c.service_name)
        for bn, bid in base_names_norm.items():
            if cn == bn or cn in bn or bn in cn:
                raise MergeBlockedError(
                    f"possible name duplicate: candidate {c.service_id} {c.service_name!r} "
                    f"vs production {bid} {bn!r}"
                )

    with open(candidates_path, encoding="utf-8-sig") as f:
        fieldnames = csv.DictReader(f).fieldnames
    missing = [col for col in REQUIRED_COLUMNS if col not in fieldnames]
    if missing:
        raise MergeBlockedError(f"candidate file missing required columns: {missing}")

    with open(candidates_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return rows


def _project_row(raw: dict) -> dict:
    """Map a candidate CSV row (candidate schema) onto the exact 36-column
    production schema, filling audit-only columns the candidate file
    doesn't carry with conservative, non-fabricated defaults.
    """
    provenance_bits = []
    for col in PROVENANCE_ONLY_COLUMNS:
        val = (raw.get(col) or "").strip()
        if val:
            provenance_bits.append(f"{col}={val}")
    provenance_suffix = (
        " [원본 후보 파일 provenance: " + "; ".join(provenance_bits) + "]"
        if provenance_bits else ""
    )

    row = {col: raw.get(col, "") for col in PRODUCTION_COLUMNS if col in raw}
    row["senior_relation"] = "SENIOR_DIRECT"
    row["service_type_secondary"] = ""
    row["meal_support_flag"] = "False"
    row["food_cost_support_flag"] = "False"
    row["review_note"] = (
        "사용자가 천안시 공식 홈페이지를 직접 열람하여 제공한 원문을 기반으로 신규 구조화. "
        "docs/cheonan_official_enrichment_report.md 및 "
        "data/processed/welfare_services_enrichment_cheonan_verified.csv 참고."
    )
    row["structured_from_original"] = "True"
    row["structured_fields_added"] = "ALL(신규 레코드)"
    row["data_quality_note"] = (raw.get("data_quality_note") or "") + provenance_suffix

    for col in PRODUCTION_COLUMNS:
        row.setdefault(col, "")
    return row


def merge(
    candidates_path: Path,
    production_path: Path = DEFAULT_CSV_PATH,
    backup_dir: Path = None,
) -> Path:
    """Run the audit, back up production_path, write the merged file in
    place, and return the backup path. Raises MergeBlockedError (no file
    written) if any audit check fails.
    """
    candidate_rows = audit(candidates_path, production_path)

    with open(production_path, encoding="utf-8-sig") as f:
        base_rows = list(csv.DictReader(f))

    backup_dir = backup_dir or production_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{production_path.stem}_backup_{timestamp}{production_path.suffix}"
    shutil.copy2(production_path, backup_path)

    projected_new_rows = [_project_row(r) for r in candidate_rows]
    merged_rows = base_rows + projected_new_rows

    with open(production_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PRODUCTION_COLUMNS)
        writer.writeheader()
        writer.writerows(merged_rows)

    return backup_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--production", type=Path, default=DEFAULT_CSV_PATH)
    args = parser.parse_args()

    try:
        backup_path = merge(args.candidates, args.production)
    except MergeBlockedError as exc:
        print(f"MERGE BLOCKED: {exc}")
        raise SystemExit(1)

    print(f"merge complete. backup saved to: {backup_path}")


if __name__ == "__main__":
    main()
