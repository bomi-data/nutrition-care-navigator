"""src/data_collection/merge_verified_enrichment.py -- the script that
merged the Cheonan candidates into production
(docs/cheonan_official_enrichment_report.md). Exercises the safety checks
directly rather than re-running a real merge (which is destructive/one-shot
by design -- see the script's own backup-before-write behavior).
"""
import csv

import pytest

from data_collection.merge_verified_enrichment import MergeBlockedError, audit
from recommender.loader import DEFAULT_CSV_PATH


def test_audit_passes_on_the_already_merged_cheonan_rows(tmp_path):
    """The two Cheonan rows are already in production -- re-running audit
    against a copy of the SAME two rows as a "candidate" file must be
    blocked on service_id collision (proves the collision check is live)."""
    candidates_path = tmp_path / "self_dup_candidates.csv"
    with open(DEFAULT_CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    cheonan_rows = [r for r in rows if r["service_id"].startswith("ENR-CHEONAN-")]
    assert len(cheonan_rows) == 2

    with open(candidates_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cheonan_rows)

    with pytest.raises(MergeBlockedError, match="collision"):
        audit(candidates_path)


def test_audit_blocks_on_normalized_name_duplicate(tmp_path):
    """A candidate with a fresh service_id but a name that already exists
    in production must still be blocked (name-collision check)."""
    with open(DEFAULT_CSV_PATH, encoding="utf-8-sig") as f:
        fieldnames = csv.DictReader(f).fieldnames

    existing_name = "재가급여"  # WLF00003248, known to exist in production
    fake_row = {col: "" for col in fieldnames}
    fake_row.update(
        service_id="ENR-FAKE-DUP",
        service_name=existing_name,
        source_api="official_web_user_verified",
        sido="충청남도", sigungu="천안시", region_scope="SIGUNGU",
        min_age="65", age_condition_type="SIMPLE_MIN",
        disability_required="unknown", low_income_required="unknown",
        single_household_required="unknown", homebound_or_mobility_condition="unknown",
        service_type="community_care", service_type_primary="community_care",
        nutritionist_involvement="not_specified", verification_level="A",
        special_eligibility_required="false",
    )
    candidates_path = tmp_path / "name_dup_candidates.csv"
    with open(candidates_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(fake_row)

    with pytest.raises(MergeBlockedError, match="duplicate"):
        audit(candidates_path)


def test_cheonan_rows_present_exactly_once_in_production():
    """Confirms the actual merge landed cleanly: no duplicates, both rows
    present, existing rows untouched in count."""
    with open(DEFAULT_CSV_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    ids = [r["service_id"] for r in rows]
    assert len(ids) == len(set(ids))
    assert ids.count("ENR-CHEONAN-01") == 1
    assert ids.count("ENR-CHEONAN-02") == 1
    assert len(rows) == 87
