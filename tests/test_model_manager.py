"""Tests for model discovery, recommendations, and downloads."""
from __future__ import annotations

from pathlib import Path

import pytest

from vizier.core.llm import model_manager as mm


@pytest.fixture()
def manager(tmp_path, monkeypatch):
    monkeypatch.setattr(mm, "get_models_dir", lambda: tmp_path)
    return mm.ModelManager()


def test_recommendations_are_tier_aware(manager) -> None:
    cpu = manager.recommend_models("cpu")
    assert cpu
    assert all(model.hardware_tier == "cpu" for model in cpu)

    gpu8 = manager.recommend_models("gpu_8")
    assert {model.hardware_tier for model in gpu8} == {"cpu", "gpu_8"}

    high = manager.recommend_models("gpu_64+")
    assert len(high) == len(mm.CURATED_MODELS)
    # Strongest models are listed first.
    assert high[0].vram_gb >= high[-1].vram_gb


def test_recommendations_have_download_urls(manager) -> None:
    for model in manager.recommend_models("gpu_16"):
        assert model.download_url.startswith("https://huggingface.co/")
        assert model.filename.endswith(".gguf")
        assert model.quant


def test_refresh_local_discovers_gguf(manager, tmp_path) -> None:
    (tmp_path / "nested").mkdir()
    target = tmp_path / "nested" / "tiny-model.gguf"
    target.write_bytes(b"x" * 1024)

    models = manager.refresh_local()
    assert len(models) == 1
    assert models[0].display_name == "tiny-model"
    assert models[0].local_path == str(target)
    assert models[0].downloaded is True
    assert manager.get_local_models() == models


def test_download_model_writes_file(manager, tmp_path, monkeypatch) -> None:
    class FakeResponse:
        headers = {"content-length": "6"}

        def raise_for_status(self) -> None:
            return None

        def iter_content(self, chunk_size: int = 8192):
            yield b"abc"
            yield b"def"

    class FakeRequests:
        @staticmethod
        def get(url, stream=True, timeout=30):
            return FakeResponse()

    monkeypatch.setattr(mm, "_requests", lambda: FakeRequests)

    progress: list[tuple[int, int, str]] = []
    path = manager.download_model(
        "owner/repo",
        "model.gguf",
        target_dir=tmp_path,
        on_progress=lambda done, total, name: progress.append((done, total, name)),
    )
    assert Path(path).read_bytes() == b"abcdef"
    assert progress == [(3, 6, "model.gguf"), (6, 6, "model.gguf")]


def test_download_model_requires_requests(manager, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mm, "_REQUESTS_AVAILABLE", False)
    with pytest.raises(RuntimeError):
        manager.download_model("owner/repo", "model.gguf", target_dir=tmp_path)


def test_search_hf_returns_empty_without_requests(manager, monkeypatch) -> None:
    monkeypatch.setattr(mm, "_REQUESTS_AVAILABLE", False)
    assert manager.search_hf("qwen") == []
