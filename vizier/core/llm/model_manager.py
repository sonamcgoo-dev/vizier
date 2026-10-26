"""
Model manager — discovers, downloads, and manages GGUF models from
Hugging Face.

Also provides hardware-aware model recommendations so users can quickly
find the right model for their PC.
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from functools import cache
from importlib.util import find_spec
from pathlib import Path

from vizier.utils import get_hardware_tier, get_models_dir

log = logging.getLogger("vizier.model_manager")

_REQUESTS_AVAILABLE = find_spec("requests") is not None


@cache
def _requests():
    """Import requests only when a network call is actually made."""
    import requests

    return requests

_HF_API = "https://huggingface.co/api/models"


@dataclass
class ModelInfo:
    """Metadata for a model found on Hugging Face or on disk."""
    name: str          # HuggingFace repo id
    display_name: str  # Human-friendly name
    filename: str = ""
    size_hf: str = ""       # "3.8B"
    vram_gb: float = 0
    ram_minimum_gb: float = 0
    quant: str = ""
    download_url: str = ""
    local_path: str = ""
    downloaded: bool = False
    description: str = ""
    hardware_tier: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = "huggingface"

    def to_dict(self) -> dict:
        return dict(vars(self))


# Curated GGUF models, organized by hardware tier.
CURATED_MODELS = [
    {"name": "Qwen/Qwen3-0.6B-GGUF", "filename": "qwen3-0.6b-q4_k_m.gguf",
     "vram_gb": 1.0, "ram_minimum_gb": 2, "quant": "Q4_K_M", "size_hf": "0.6B",
     "tier": "cpu", "desc": "Tiny Qwen 3 — fastest model for CPU."},
    {"name": "Qwen/Qwen3-1.8B-GGUF", "filename": "qwen3-1.8b-q4_k_m.gguf",
     "vram_gb": 1.3, "ram_minimum_gb": 4, "quant": "Q4_K_M", "size_hf": "1.8B",
     "tier": "cpu", "desc": "Balanced tiny model, good reasoning on CPU."},
    {"name": "google/gemma-2b-it-GGUF", "filename": "gemma-2b-it-q4_k_m.gguf",
     "vram_gb": 1.5, "ram_minimum_gb": 4, "quant": "Q4_K_M", "size_hf": "2B",
     "tier": "cpu", "desc": "Gemma 2B — excellent instruction following."},
    {"name": "microsoft/Phi-3-mini-4k-instruct-GGUF", "filename": "Phi-3-mini-4k-instruct-q4.gguf",
     "vram_gb": 2.2, "ram_minimum_gb": 4, "quant": "Q4_K_M", "size_hf": "3.8B",
     "tier": "cpu", "desc": "Phi-3 Mini — strong coding & reasoning on CPU."},
    {"name": "Qwen/Qwen3-8B-GGUF", "filename": "qwen3-8b-q4_k_m.gguf",
     "vram_gb": 5.1, "ram_minimum_gb": 8, "quant": "Q4_K_M", "size_hf": "8B",
     "tier": "gpu_8", "desc": "Qwen 3 8B — best overall for 8 GB GPUs."},
    {"name": "meta-llama/Llama-3.2-3B-Instruct-GGUF", "filename": "llama-3.2-3b-instruct-q4_k_m.gguf",
     "vram_gb": 2.1, "ram_minimum_gb": 6, "quant": "Q4_K_M", "size_hf": "3B",
     "tier": "gpu_8", "desc": "Llama 3.2 3B — great coding & reasoning, fits 8 GB."},
    {"name": "google/gemma-2-9b-it-GGUF", "filename": "gemma-2-9b-it-q4_k_m.gguf",
     "vram_gb": 5.8, "ram_minimum_gb": 8, "quant": "Q4_K_M", "size_hf": "9B",
     "tier": "gpu_8", "desc": "Gemma 2 9B — strong math and reasoning."},
    {"name": "Qwen/Qwen3-14B-GGUF", "filename": "qwen3-14b-q4_k_m.gguf",
     "vram_gb": 8.4, "ram_minimum_gb": 12, "quant": "Q4_K_M", "size_hf": "14B",
     "tier": "gpu_16", "desc": "Qwen 3 14B — near-frontier quality on 16 GB."},
    {"name": "meta-llama/Meta-Llama-3.1-8B-Instruct-GGUF", "filename": "meta-llama-3.1-8b-instruct-q4_k_m.gguf",
     "vram_gb": 5.0, "ram_minimum_gb": 10, "quant": "Q4_K_M", "size_hf": "8B",
     "tier": "gpu_16", "desc": "Llama 3.1 8B — excellent general-purpose model."},
    {"name": "mistralai/Mistral-Small-24B-Instruct-GGUF", "filename": "mistral-small-24b-q4_k_m.gguf",
     "vram_gb": 14.0, "ram_minimum_gb": 16, "quant": "Q4_K_M", "size_hf": "24B",
     "tier": "gpu_16", "desc": "Mistral Small 24B — coding powerhouse on 16 GB."},
    {"name": "Qwen/Qwen3-30B-A3B-GGUF", "filename": "qwen3-30b-a3b-q4_k_m.gguf",
     "vram_gb": 17.0, "ram_minimum_gb": 24, "quant": "Q4_K_M", "size_hf": "30B MoE",
     "tier": "gpu_24", "desc": "Qwen 3 30B MoE — exceptional coding & reasoning."},
    {"name": "Qwen/Qwen3-32B-GGUF", "filename": "qwen3-32b-q4_k_m.gguf",
     "vram_gb": 20.0, "ram_minimum_gb": 32, "quant": "Q4_K_M", "size_hf": "32B",
     "tier": "gpu_24", "desc": "Qwen 3 32B dense — best quality on 24-32 GB."},
    {"name": "deepseek-ai/DeepSeek-R1-32B-GGUF", "filename": "DeepSeek-R1-32B-Q4_K_M.gguf",
     "vram_gb": 20.0, "ram_minimum_gb": 32, "quant": "Q4_K_M", "size_hf": "32B",
     "tier": "gpu_24", "desc": "DeepSeek R1 32B — reasoning champion."},
    {"name": "Qwen/Qwen3-72B-GGUF", "filename": "qwen3-72b-q4_k_m.gguf",
     "vram_gb": 44.0, "ram_minimum_gb": 64, "quant": "Q4_K_M", "size_hf": "72B",
         "tier": "gpu_64+", "desc": "Qwen 3 72B — frontier-level quality."},
]

#: Hardware tiers ordered from weakest to strongest.
_TIER_ORDER = {
    "cpu": 0,
    "gpu_8": 1,
    "gpu_16": 2,
    "gpu_24": 3,
    "gpu_48": 4,
    "gpu_64+": 5,
}


class ModelManager:
    """Manages model discovery, download, and local catalogue."""

    def __init__(self):
        self.models_dir = get_models_dir()
        self._catalog_cache: list[ModelInfo] | None = None

    # -- local discovery --------------------------------------------------

    def refresh_local(self) -> list[ModelInfo]:
        """Scan the local models directory and return discovered models."""
        self._catalog_cache = None
        results: list[ModelInfo] = []
        if not self.models_dir.exists():
            return results
        for gguf_file in sorted(self.models_dir.rglob("*.gguf")):
            size_mb = gguf_file.stat().st_size / (1024 * 1024)
            results.append(ModelInfo(
                name=gguf_file.stem,
                display_name=gguf_file.stem,
                filename=gguf_file.name,
                local_path=str(gguf_file),
                downloaded=True,
                vram_gb=round(size_mb / 1024, 1),
                description=f"Local model ({size_mb:.0f} MB)",
                source="local",
            ))
        self._catalog_cache = results
        return results

    def get_local_models(self) -> list[ModelInfo]:
        if self._catalog_cache is None:
            return self.refresh_local()
        return self._catalog_cache

    def scan_for_models(self) -> list[ModelInfo]:
        return self.refresh_local()

    # -- hardware-based recommendations -----------------------------------

    def recommend_models(self, tier: str | None = None) -> list[ModelInfo]:
        """Return models recommended for the given (or detected) hardware tier."""
        if tier is None:
            tier = get_hardware_tier()
        tier_rank = _TIER_ORDER.get(tier, 0)
        recs: list[ModelInfo] = []
        for entry in CURATED_MODELS:
            if _TIER_ORDER.get(entry["tier"], 0) > tier_rank:
                continue
            recs.append(ModelInfo(
                name=entry["name"],
                display_name=entry["name"].split("/")[-1],
                filename=entry["filename"],
                vram_gb=entry["vram_gb"],
                ram_minimum_gb=entry["ram_minimum_gb"],
                quant=entry["quant"],
                size_hf=entry["size_hf"],
                description=entry["desc"],
                hardware_tier=entry["tier"],
                download_url=f"https://huggingface.co/{entry['name']}/resolve/main/{entry['filename']}",
                tags=["curated", "gguf"],
            ))
        # Largest / most capable first
        recs.sort(key=lambda m: m.vram_gb, reverse=True)
        return recs

    # -- download ---------------------------------------------------------

    def download_model(
        self, repo_id: str, filename: str,
        target_dir: Path | None = None, on_progress=None,
    ) -> Path:
        """Download a single GGUF file from Hugging Face."""
        target_dir = target_dir or self.models_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        url = f"https://huggingface.co/{repo_id}/resolve/main/{filename}"
        if not _REQUESTS_AVAILABLE:
            raise RuntimeError(
                "The 'requests' package is required to download models."
            )
        log.info("Downloading %s", url)
        resp = _requests().get(url, stream=True, timeout=30)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        temp_path = target_path.with_name(target_path.name + ".part")
        try:
            with open(temp_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if on_progress:
                            on_progress(downloaded, total, filename)
            os.replace(temp_path, target_path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
        log.info("Download complete: %s", target_path)
        self._catalog_cache = None  # invalidate cache
        return target_path

    def download_model_async(
        self, repo_id: str, filename: str,
        target_dir: Path | None = None,
        on_progress=None, on_complete=None,
    ) -> threading.Thread:
        """Download a model in a background thread."""
        def _worker():
            try:
                path = self.download_model(repo_id, filename, target_dir, on_progress)
                if on_complete:
                    on_complete(path, None)
            except Exception as e:
                log.error(f"Download failed: {e}")
                if on_complete:
                    on_complete(None, str(e))
        t = threading.Thread(target=_worker, daemon=True, name="vizier-download")
        t.start()
        return t

    # -- HuggingFace search ----------------------------------------------

    def search_hf(self, query: str, limit: int = 20) -> list[ModelInfo]:
        """Search Hugging Face for GGUF models matching *query*."""
        if not _REQUESTS_AVAILABLE:
            log.warning("'requests' is not installed; cannot search Hugging Face")
            return []
        try:
            params = {"search": query, "filter": "gguf", "limit": limit}
            resp = _requests().get(_HF_API, params=params, timeout=15)
            resp.raise_for_status()
            models = resp.json()
        except Exception as e:
            log.warning(f"HF search failed: {e}")
            return []
        results: list[ModelInfo] = []
        for m in models:
            sid = m.get("id", "")
            try:
                files_resp = _requests().get(
                    f"https://huggingface.co/api/models/{sid}", timeout=10)
                siblings = files_resp.json().get("siblings", []) if files_resp.status_code == 200 else []
            except Exception:
                siblings = []
            gguf_files = [s["rfilename"] for s in siblings if s.get("rfilename", "").endswith(".gguf")]
            if not gguf_files:
                continue
            results.append(ModelInfo(
                name=sid, display_name=sid.split("/")[-1],
                filename=gguf_files[0],
                download_url=f"https://huggingface.co/{sid}/resolve/main/{gguf_files[0]}",
                description=m.get("description", ""),
                tags=m.get("tags", []),
                source="huggingface",
            ))
        return results

