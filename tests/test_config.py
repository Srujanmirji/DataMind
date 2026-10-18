from pathlib import Path

import pytest
import yaml

from datamind.config import ConfigError, available_datasets, load_dataset

REPO = Path(__file__).resolve().parents[1]


def test_shipped_datasets_load():
    names = available_datasets()
    assert {"tpch", "owid_energy"} <= set(names)
    for name in names:
        cfg = load_dataset(name)
        assert cfg.tables, name
        assert cfg.guardrails.max_rows > 0


def test_allowed_tables_are_fully_qualified_upper_case():
    cfg = load_dataset("tpch")
    assert "SNOWFLAKE_SAMPLE_DATA.TPCH_SF1.ORDERS" in cfg.allowed_tables
    assert all(t.count(".") == 2 and t == t.upper() for t in cfg.allowed_tables)


def test_dataset_env_var_selects_config(monkeypatch):
    monkeypatch.setenv("DATAMIND_DATASET", "owid_energy")
    assert load_dataset().name == "owid_energy"


def test_missing_dataset_raises():
    with pytest.raises(ConfigError, match="not found"):
        load_dataset("does_not_exist")


def test_empty_allowlist_rejected(tmp_path):
    (tmp_path / "bad.yaml").write_text(
        "name: bad\nsnowflake: {database: D, schema: S}\ntables: []\n"
    )
    with pytest.raises(ConfigError, match="allowlist"):
        load_dataset("bad", config_dir=tmp_path)


def test_malformed_dataset_raises(tmp_path):
    (tmp_path / "bad.yaml").write_text("name: bad\ntables: [{name: T}]\n")
    with pytest.raises(ConfigError, match="Malformed"):
        load_dataset("bad", config_dir=tmp_path)


def test_eval_questions_only_reference_allowlisted_dataset():
    try:
        import sqlglot
    except ImportError:
        sqlglot = None

    for filename in ("questions_tpch.yaml", "questions_owid_energy.yaml"):
        path = REPO / "eval" / filename
        if not path.is_file():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        seen_ids = set()
        statuses = {"answered", "needs_clarification", "no_data", "unsupported", "refused"}
        for q in data["questions"]:
            qid = q["id"]
            assert qid not in seen_ids, f"Duplicate ID {qid} in {filename}"
            seen_ids.add(qid)

            assert q["expected_status"] in statuses, f"Invalid status in {qid} of {filename}"
            assert q.get("question"), f"Question text empty in {qid} of {filename}"

            if "follows" in q:
                err_msg = f"follows '{q['follows']}' not found prior to {qid} in {filename}"
                assert q["follows"] in seen_ids, err_msg

            if q.get("reference_sql"):
                if sqlglot:
                    parsed = sqlglot.parse_one(q["reference_sql"], read="snowflake")
                    assert parsed is not None, f"Cannot parse SQL in {qid} of {filename}"
            elif q["expected_status"] == "answered":
                raise AssertionError(f"Missing reference_sql for {qid} in {filename}")




