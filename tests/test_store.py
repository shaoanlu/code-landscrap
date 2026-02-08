from __future__ import annotations

from code_landscrap.store import Store


def test_insert_fragments_given_duplicates_when_inserted_then_only_new_rows_are_counted(
    tmp_path,
    fragment_model,
) -> None:
    # Given
    store = Store(tmp_path / "landscrap.db")
    store.init_db()
    second_fragment = fragment_model.model_copy(
        update={
            "line_no": 11,
            "content": "return newer_value",
        },
    )

    # When
    inserted = store.insert_fragments([fragment_model, fragment_model, second_fragment])

    # Then
    assert inserted == 2
    all_rows = store.fetch_candidate_fragments(limit=20)
    assert len(all_rows) == 2
    assert {row["line_no"] for row in all_rows} == {7, 11}


def test_fetch_candidate_fragments_given_repo_filter_when_fetched_then_results_match_requested_repo(
    tmp_path,
    fragment_model,
) -> None:
    # Given
    store = Store(tmp_path / "landscrap.db")
    store.init_db()
    other_repo_fragment = fragment_model.model_copy(
        update={
            "repo_name": "other-repo",
            "line_no": 17,
            "content": "def drift(): pass",
        },
    )
    store.insert_fragments([fragment_model, other_repo_fragment])

    # When
    filtered = store.fetch_candidate_fragments(repo_name="demo-repo", limit=20)

    # Then
    assert len(filtered) == 1
    assert filtered[0]["repo_name"] == "demo-repo"


def test_save_artifact_given_fragment_ids_when_saved_then_artifact_and_links_are_retrievable(
    tmp_path,
    fragment_model,
    artifact_record_model,
) -> None:
    # Given
    store = Store(tmp_path / "landscrap.db")
    store.init_db()
    second_fragment = fragment_model.model_copy(
        update={
            "line_no": 8,
            "content": "print('trace')",
        },
    )
    store.insert_fragments([fragment_model, second_fragment])
    rows = store.fetch_candidate_fragments(limit=20)
    fragment_ids = sorted(int(row["id"]) for row in rows)

    # When
    store.save_artifact(artifact_record_model, fragment_ids)
    artifact = store.get_artifact(artifact_record_model.artifact_id)
    linked = store.get_artifact_fragments(artifact_record_model.artifact_id)

    # Then
    assert artifact is not None
    assert artifact["output_title"] == "Local Landscrap Study"
    assert len(linked) == 2
    assert {row["line_no"] for row in linked} == {7, 8}
