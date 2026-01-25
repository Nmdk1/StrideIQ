import zipfile

import pytest

from tasks.import_tasks import _safe_extract_zip


def test_safe_extract_zip_blocks_zip_slip(tmp_path):
    z = tmp_path / "bad.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("../evil.txt", b"nope")

    with pytest.raises(ValueError) as e:
        _safe_extract_zip(z, tmp_path / "out")

    assert "zip_slip_detected" in str(e.value)


def test_safe_extract_zip_extracts_normal_paths(tmp_path):
    z = tmp_path / "ok.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("DI_CONNECT/DI-Connect-Fitness/file.json", b"{}")

    out = tmp_path / "out"
    stats = _safe_extract_zip(z, out)
    assert stats["extracted_files"] == 1
    assert (out / "DI_CONNECT" / "DI-Connect-Fitness" / "file.json").exists()

