import json

import pytest

from news_ingestion.persistence.json_artifacts import (
    read_json_object_array,
    write_json_atomically,
)


def test_atomic_json_write_preserves_existing_artifact_on_failure(
    tmp_path, monkeypatch
):
    output_path = tmp_path / "records.json"
    output_path.write_text('[{"existing": true}]\n', encoding="utf-8")

    def fail_json_dump(*args, **kwargs):
        raise TypeError("not serializable")

    monkeypatch.setattr(json, "dump", fail_json_dump)

    with pytest.raises(TypeError, match="not serializable"):
        write_json_atomically([{"replacement": True}], output_path)

    assert json.loads(output_path.read_text(encoding="utf-8")) == [{"existing": True}]
    assert list(tmp_path.glob("*.tmp")) == []


def test_read_json_object_array_rejects_non_object_entries(tmp_path):
    input_path = tmp_path / "records.json"
    input_path.write_text('[{"valid": true}, 1]', encoding="utf-8")

    with pytest.raises(TypeError, match="every record"):
        read_json_object_array(input_path)
