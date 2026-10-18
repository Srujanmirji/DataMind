from datamind.config import load_dataset
from datamind.schema import SchemaCatalog
from datamind.snowflake_client import ColumnInfo


def test_schema_catalog_render_for_prompt():
    dataset = load_dataset("tpch")
    sample_cols = [
        ColumnInfo(
            table="CUSTOMER", name="C_CUSTKEY", data_type="NUMBER(38,0)", comment="Customer key"
        ),
        ColumnInfo(table="CUSTOMER", name="C_NAME", data_type="VARCHAR(25)", comment=""),
        ColumnInfo(
            table="ORDERS", name="O_ORDERKEY", data_type="NUMBER(38,0)", comment="Order key"
        ),
    ]

    catalog = SchemaCatalog(dataset=dataset, columns=sample_cols)
    rendered = catalog.render_for_prompt(max_chars=5000)

    assert "Dataset:" in rendered
    assert "SNOWFLAKE_SAMPLE_DATA" in rendered
    assert "TPCH_SF1" in rendered
    assert "CUSTOMER" in rendered
    assert "C_CUSTKEY NUMBER(38,0)" in rendered
    assert "Relationships (Joins):" in rendered
    assert "Glossary (Business Definitions):" in rendered


def test_schema_catalog_render_max_chars_truncation():
    dataset = load_dataset("tpch")
    catalog = SchemaCatalog(dataset=dataset, columns=[])
    rendered = catalog.render_for_prompt(max_chars=100)

    assert len(rendered) <= 100
    assert "[TRUNCATED]" in rendered
