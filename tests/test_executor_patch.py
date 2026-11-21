from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from comsol_agent.executor import ExecutionError, ProfileExecutor
from comsol_agent.io_utils import sha256_file


class FakeSolverCollection:
    def tags(self):
        return []


class FakeJava:
    def sol(self):
        return FakeSolverCollection()


class FakeModel:
    def __init__(self):
        self.java = FakeJava()


class FakeClient:
    def __init__(self):
        self.loaded = []

    def load(self, path):
        self.loaded.append(path)
        return FakeModel()


def test_patch_model_is_copied_before_load_and_original_stays_unchanged(tmp_path: Path):
    original = tmp_path / "source.mph"
    original.write_bytes(b"fake-MPH-source")
    digest = sha256_file(original)
    manifest = {
        "metadata": {
            "mode": "patch",
            "source_model": str(original.resolve()),
            "profile_id": "not-loaded-in-this-test"
        }
    }
    client = FakeClient()
    executor = ProfileExecutor(client, manifest, tmp_path / "run")
    executor.output_dir.mkdir(parents=True)

    executor._load_patch_source()

    copy = tmp_path / "run" / "source_model_copy.mph"
    assert copy.is_file()
    assert sha256_file(copy) == digest
    assert client.loaded == [str(copy.resolve())]
    assert sha256_file(original) == digest
    assert executor.verify_source_unchanged()["source_unchanged"] is True


def test_patch_refuses_to_overwrite_existing_working_copy(tmp_path: Path):
    original = tmp_path / "source.mph"
    original.write_bytes(b"fake-MPH-source")
    output = tmp_path / "run"
    output.mkdir()
    (output / "source_model_copy.mph").write_bytes(b"existing-copy")
    executor = ProfileExecutor(FakeClient(), {
        "metadata": {"mode": "patch", "source_model": str(original.resolve())}
    }, output)
    with pytest.raises(ExecutionError, match="Refusing to overwrite"):
        executor._load_patch_source()
    assert original.read_bytes() == b"fake-MPH-source"
