"""model + gpu smoke test: the exact Phase 1 baseline model
(BAAI/bge-small-en-v1.5) still loads and runs through sentence-transformers
on CUDA. Must never download - local_files_only=True plus HF_HUB_OFFLINE=1
as a second, independent guard, and an explicit pre-check via
huggingface_hub.try_to_load_from_cache() to distinguish "not cached" (skip)
from "cached but broken" (fail)."""

import pytest
import torch
from huggingface_hub import try_to_load_from_cache

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EXPECTED_DIM = 384


@pytest.mark.model
@pytest.mark.gpu
def test_bge_small_offline_cuda_inference(monkeypatch):
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")

    if not torch.cuda.is_available():
        pytest.skip("CUDA not available on this machine")

    if try_to_load_from_cache(MODEL_NAME, "config.json") is None:
        pytest.skip(
            f"{MODEL_NAME} not available in local cache; network downloads are disabled in tests"
        )

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME, device="cuda", local_files_only=True)
    param_device = next(model.parameters()).device
    assert param_device.type == "cuda"

    texts = [
        "The company reported revenue for fiscal 2024.",
        "Item 1A describes material risk factors.",
    ]
    embeddings = model.encode(texts, device="cuda", convert_to_tensor=True)

    assert embeddings.shape == (2, EXPECTED_DIM)
    assert torch.isfinite(embeddings).all().item()
    assert embeddings.device.type == "cuda"
