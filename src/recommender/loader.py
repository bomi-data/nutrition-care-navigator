"""Loads welfare_services_recommendation_ready.csv into typed ServiceRecords.

Uses the standard-library csv module on purpose (no pandas dependency) --
the file has 85 rows and needs only row-by-row typed access, which csv.
DictReader already provides. See docs/recommendation_engine_v1_report.md for
the reasoning.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Optional

from .models import AgeConditionType, RegionScope, ServiceRecord, TriState

DEFAULT_CSV_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "processed"
    / "welfare_services_recommendation_ready.csv"
)

# Columns the engine actually reads. If any of these is missing from the CSV
# header, loading fails loudly instead of silently treating the field as
# empty for every row.
REQUIRED_COLUMNS = [
    "service_id", "service_name", "source_api",
    "sido", "sigungu", "region_scope",
    "min_age", "max_age", "age_condition_type", "age_condition_note",
    "disability_required", "low_income_required",
    "single_household_required", "homebound_or_mobility_condition",
    "service_type", "service_type_primary",
    "nutritionist_involvement", "nutrition_relevance", "verification_level",
    "contact", "application_original", "target_original",
    "criteria_original", "support_original",
    "eligibility_summary", "support_summary", "data_quality_note",
    "special_eligibility_required", "special_eligibility_note",
]


class LoaderError(Exception):
    """Raised when the CSV does not match the schema the engine expects."""


def _parse_int(value: str) -> Optional[int]:
    v = (value or "").strip()
    if v == "" or v.lower() == "unknown":
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _parse_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = value.strip()
    return v or None


def load_services(csv_path: Path = DEFAULT_CSV_PATH) -> List[ServiceRecord]:
    """Read the recommendation-ready CSV and return typed ServiceRecords.

    Raises LoaderError if required columns are missing or if service_id is
    not unique -- both are hard prerequisites the rest of the engine relies
    on (recommendation_data_readiness.md integrity checks 1-3).
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise LoaderError(f"CSV not found: {csv_path}")

    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
        if missing:
            raise LoaderError(
                "CSV is missing columns the engine requires: "
                f"{missing}. Refusing to invent them."
            )
        rows = list(reader)

    seen_ids = set()
    records: List[ServiceRecord] = []
    for row in rows:
        sid = row["service_id"].strip()
        if sid in seen_ids:
            raise LoaderError(f"Duplicate service_id in CSV: {sid}")
        seen_ids.add(sid)

        raw_types = [t.strip() for t in (row["service_type"] or "").split("|") if t.strip()]

        records.append(
            ServiceRecord(
                service_id=sid,
                service_name=row["service_name"].strip(),
                source_api=row["source_api"].strip(),
                sido=_parse_str(row["sido"]),
                sigungu=_parse_str(row["sigungu"]),
                region_scope=RegionScope.from_raw(row["region_scope"]),
                min_age=_parse_int(row["min_age"]),
                max_age=_parse_int(row["max_age"]),
                age_condition_type=AgeConditionType.from_raw(row["age_condition_type"]),
                age_condition_note=(row["age_condition_note"] or "").strip(),
                disability_required=TriState.from_raw(row["disability_required"]),
                low_income_required=TriState.from_raw(row["low_income_required"]),
                single_household_required=TriState.from_raw(row["single_household_required"]),
                homebound_or_mobility_condition=TriState.from_raw(
                    row["homebound_or_mobility_condition"]
                ),
                service_type=frozenset(raw_types),
                service_type_primary=(row["service_type_primary"] or "").strip(),
                nutritionist_involvement=(row["nutritionist_involvement"] or "").strip(),
                nutrition_relevance=(row["nutrition_relevance"] or "").strip(),
                verification_level=(row["verification_level"] or "").strip(),
                contact=(row["contact"] or "").strip(),
                application_original=(row["application_original"] or "").strip(),
                target_original=(row["target_original"] or "").strip(),
                criteria_original=(row["criteria_original"] or "").strip(),
                support_original=(row["support_original"] or "").strip(),
                eligibility_summary=(row["eligibility_summary"] or "").strip(),
                support_summary=(row["support_summary"] or "").strip(),
                data_quality_note=(row["data_quality_note"] or "").strip(),
                special_eligibility_required=TriState.from_raw(row["special_eligibility_required"]),
                special_eligibility_note=(row["special_eligibility_note"] or "").strip(),
            )
        )

    return records
