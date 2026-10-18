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
    data = yaml.safe_load((REPO / "eval" / "questions_tpch.yaml").read_text())
    ids = [q["id"] for q in data["questions"]]
    assert len(ids) == len(set(ids))
    statuses = {"answered", "needs_clarification", "no_data", "unsupported", "refused"}
    for q in data["questions"]:
        assert q["expected_status"] in statuses, q["id"]
        if q["expected_status"] == "answered":
            assert q["reference_sql"], q["id"]
