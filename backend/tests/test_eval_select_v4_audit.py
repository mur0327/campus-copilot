from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from eval.select_v4_audit import (  # noqa: E402
    AuditBundle,
    audit_row_ids,
    build_bundles,
    context_page_ids,
    exclude_completed_bundles,
    load_primary,
    main,
    render_ids_file,
    select_full_audit_bundles,
    select_repilot_bundles,
    select_stratified_bundles,
)


def bundle(
    index: int,
    *,
    label_class: str,
    targeted: bool,
) -> AuditBundle:
    question_id = f"Q{index:03d}"
    return AuditBundle(
        question_id=question_id,
        canonical_url=f"https://example.test/{index}",
        page_row_id=f"P|{question_id}|https://example.test/{index}",
        evidence_row_ids=(f"E|{question_id}|chunk-{index}",),
        label_class=label_class,
        rank_band="1-2" if index % 2 else "3-5",
        mode_presence="single" if index % 3 else "multiple",
        document_kind="special" if index % 4 == 0 else "general",
        question_type=("date", "fact", "procedure")[index % 3],
        source_scope=("central", "department")[index % 2],
        target_reasons=frozenset({"boundary"}) if targeted else frozenset(),
    )


def fixture_bundles() -> list[AuditBundle]:
    return [bundle(index, label_class="positive", targeted=index % 3 == 0) for index in range(1, 21)] + [
        bundle(index, label_class="invalid", targeted=index % 4 == 0) for index in range(21, 41)
    ]


def test_pilot_selection_is_balanced_and_deterministic():
    bundles = fixture_bundles()

    selected = select_stratified_bundles(bundles, 10, seed="fixed")
    selected_reversed = select_stratified_bundles(list(reversed(bundles)), 10, seed="fixed")

    assert selected == selected_reversed
    assert len(selected) == 10
    assert sum(item.label_class == "positive" for item in selected) == 5
    assert sum(item.label_class == "invalid" for item in selected) == 5
    assert {item.audit_track for item in selected} == {"targeted", "sample"}
    assert len({item.question_id for item in selected}) == 10


def test_full_selection_keeps_all_targeted_bundles_and_adds_sample():
    bundles = fixture_bundles()
    expected_targeted = {item.page_row_id for item in bundles if item.target_reasons}
    initial = select_stratified_bundles(bundles, 10, seed="fixed")
    pilot = select_repilot_bundles(bundles, 10, seed="fixed")

    selected, targeted_count = select_full_audit_bundles(bundles, 10, seed="fixed")

    assert targeted_count == len(expected_targeted)
    assert expected_targeted <= {item.page_row_id for item in selected}
    assert {item.page_row_id for item in pilot} <= {
        item.page_row_id for item in selected
    }
    excluded_initial_sample = {
        item.page_row_id for item in initial if not item.target_reasons
    }
    assert excluded_initial_sample.isdisjoint(
        {item.page_row_id for item in selected if not item.target_reasons}
    )
    assert len(selected) == targeted_count + 10


def test_repilot_is_balanced_deterministic_and_disjoint_from_initial_pilot():
    bundles = fixture_bundles()
    initial = select_stratified_bundles(bundles, 10, seed="fixed")

    selected = select_repilot_bundles(bundles, 10, seed="fixed")
    selected_reversed = select_repilot_bundles(
        list(reversed(bundles)),
        10,
        seed="fixed",
    )

    assert selected == selected_reversed
    assert len(selected) == 10
    assert sum(item.label_class == "positive" for item in selected) == 5
    assert sum(item.label_class == "invalid" for item in selected) == 5
    assert {item.page_row_id for item in initial}.isdisjoint(
        {item.page_row_id for item in selected}
    )


def test_ids_file_contains_bundle_controls_without_hidden_selection_metadata():
    selected = select_stratified_bundles(fixture_bundles(), 4, seed="fixed")

    row_ids = audit_row_ids(selected)
    output = render_ids_file(selected, phase="pilot", seed="fixed")

    assert len(row_ids) == 8
    assert all(row_id in output for row_id in row_ids)
    assert "label_class" not in output
    assert "target_reasons" not in output
    assert "positive" not in output
    assert "invalid" not in output


def test_completed_bundles_are_removed_only_when_page_and_evidence_are_complete():
    bundles = fixture_bundles()[:3]
    completed = {
        bundles[0].page_row_id,
        *bundles[0].evidence_row_ids,
    }

    remaining, completed_count = exclude_completed_bundles(bundles, completed)

    assert completed_count == 1
    assert remaining == bundles[1:]


def test_conflict_bundle_adds_uncontrolled_sibling_pages_as_context():
    bundles = build_bundles(load_primary())
    conflict = next(item for item in bundles if "conflict" in item.target_reasons)

    context_ids = context_page_ids([conflict], bundles)

    assert context_ids
    assert f"C|{conflict.page_row_id}" not in context_ids
    assert all(value.startswith(f"C|P|{conflict.question_id}|") for value in context_ids)


def test_pilot_cli_does_not_retroactively_add_context(monkeypatch, tmp_path):
    output_path = tmp_path / "pilot-ids.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "select_v4_audit.py",
            "--phase",
            "pilot",
            "--bundle-count",
            "10",
            "--out",
            str(output_path),
        ],
    )

    main()

    output = output_path.read_text(encoding="utf-8")
    assert "# context_pages=0" in output
    assert "\nC|" not in output


def test_frozen_primary_builds_expected_b2_target_volume():
    bundles = build_bundles(load_primary())
    targeted = [item for item in bundles if item.target_reasons]

    assert len(bundles) == 424
    assert all(item.evidence_row_ids for item in bundles)
    assert len(targeted) == 67
