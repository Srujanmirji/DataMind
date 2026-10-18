import csv
import io
import json
from decimal import Decimal
from zipfile import ZipFile

import pytest

from scripts.demo import begin_report, record_failure
from scripts.uci_wine import FEATURES, SOURCE, parse_archive, prepare_data, verify_table


def archive_fixture(path, quality="7", headers=None):
    content = io.StringIO()
    writer = csv.writer(content, delimiter=";")
    writer.writerow(headers if headers is not None else [*FEATURES, "quality"])
    writer.writerow([*(["1.25"] * 10), "9.53333333333333", quality])
    with ZipFile(path, "w") as archive:
        for kind in ("red", "white"):
            archive.writestr(f"winequality-{kind}.csv", content.getvalue())


def test_real_source_parser_preserves_decimal_precision_and_rows(tmp_path):
    path = tmp_path / "source.zip"
    archive_fixture(path)
    rows = parse_archive(path)
    assert len(rows) == 2
    assert rows[0][0:2] == ("red-00001", "RED")
    assert rows[1][0:2] == ("white-00001", "WHITE")
    assert rows[0][-2] == Decimal("9.53333333333333")
    assert rows[0][-1] == 7


@pytest.mark.parametrize("quality", ["11", "-1", "not a score"])
def test_parser_rejects_invalid_scores(tmp_path, quality):
    path = tmp_path / "source.zip"
    archive_fixture(path, quality=quality)
    with pytest.raises(ValueError):
        parse_archive(path)


def test_parser_rejects_wrong_source_schema(tmp_path):
    path = tmp_path / "source.zip"
    archive_fixture(path, headers=["unexpected"])
    with pytest.raises(ValueError, match="columns"):
        parse_archive(path)


def test_corrupt_cached_download_is_rejected_without_network(tmp_path):
    (tmp_path / "wine-quality.zip").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="hash mismatch"):
        prepare_data(tmp_path)
    assert not (tmp_path / "manifest.json").exists()


def test_full_table_verification_rejects_changed_source_value():
    from unittest.mock import Mock

    cursor = Mock()
    cursor.fetchall.return_value = [("red-00001", "RED", Decimal("9.5"), 8)]
    with pytest.raises(RuntimeError, match="differs from original UCI"):
        verify_table(cursor, SOURCE, [("red-00001", "RED", Decimal("9.5"), 7)])


def test_failed_setup_invalidates_old_proof(tmp_path):
    (tmp_path / "REPORT.md").write_text("Previously PASSED")
    (tmp_path / "proof.json").write_text('{"status":"passed"}')
    begin_report(tmp_path)
    assert "PASSED" not in (tmp_path / "REPORT.md").read_text()
    record_failure(RuntimeError("secret exception value must not be persisted"), tmp_path)
    report = json.loads((tmp_path / "proof.json").read_text())
    assert report["status"] == "failed"
    assert report["error_type"] == "RuntimeError"
    assert "secret exception" not in (tmp_path / "proof.json").read_text()
