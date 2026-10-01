from backend.benchmark import load_dataset

def test_dataset_has_unique_ids_and_required_fields():
    rows=load_dataset()
    assert len(rows) >= 100
    ids=[x["case_id"] for x in rows]
    assert len(ids)==len(set(ids))
    required={"case_id","category","difficulty","prompt","reference_answer","evaluation_criteria"}
    assert all(required.issubset(x) for x in rows)
