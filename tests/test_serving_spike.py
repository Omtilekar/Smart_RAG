"""Tests for the deterministic helper logic in scripts/serving_spike.py.

Deliberately does NOT run the full corpus/embedding/benchmark pipeline -
that is a many-minute manual benchmark run, not a pytest suite. Only the
pure, cheap helper functions (config hashing, percentile stats) are tested
here, per task_0.10 Step 39.
"""

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "serving_spike.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("serving_spike", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


spike = _load_module()


def test_config_hash_deterministic_for_same_config():
    config = spike.default_config(1000)
    assert spike.spike_config_hash(config) == spike.spike_config_hash(config)


def test_config_hash_differs_for_different_target_chunks():
    hash_a = spike.spike_config_hash(spike.default_config(1000))
    hash_b = spike.spike_config_hash(spike.default_config(2000))
    assert hash_a != hash_b


def test_config_hash_stable_under_key_reordering():
    config = spike.default_config(500)
    reordered = dict(reversed(list(config.items())))
    assert spike.spike_config_hash(config) == spike.spike_config_hash(reordered)


def test_percentile_stats_empty_input():
    assert spike.percentile_stats([]) == {"count": 0}


def test_percentile_stats_basic_values():
    samples = [float(i) for i in range(1, 101)]  # 1..100
    stats = spike.percentile_stats(samples)
    assert stats["count"] == 100
    assert stats["min"] == 1.0
    assert stats["max"] == 100.0
    assert stats["median"] == 50.5
    assert stats["p50"] == 50.0 or stats["p50"] == 51.0


def test_percentile_stats_p99_none_below_20_samples():
    stats = spike.percentile_stats([1.0, 2.0, 3.0])
    assert stats["p99"] is None


def test_default_config_has_required_top_level_keys():
    config = spike.default_config(100000)
    required = {
        "schema_version", "corpus", "chunking", "embedding", "lancedb",
        "retrieval", "reranker", "queries", "warmup", "measurement",
        "resource_controls",
    }
    assert required.issubset(config.keys())
