"""Shared pytest fixtures for foam_gnn smoke tests.

The 5 committed sample frames (``tests/fixtures/samples/``) stand in for the full
198-frame folder during development. Expensive steps (loading, segmentation) are
session-scoped so the suite stays fast.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from foam_gnn.config import DataConfig, PipelineConfig
from foam_gnn.io_utils import load_frame
from foam_gnn.segmentation import build_segmenter

FIXTURE_ROOT = Path(__file__).parent / "fixtures"
SAMPLE_DIR = FIXTURE_ROOT / "samples"


@pytest.fixture(scope="session")
def cfg() -> PipelineConfig:
    # data_root = fixtures/, experiments = ("samples",)  -> exercises list_experiment_frames too
    return PipelineConfig(data=DataConfig(data_root=FIXTURE_ROOT, experiments=("samples",)))


@pytest.fixture(scope="session")
def sample_paths() -> list[Path]:
    paths = sorted(SAMPLE_DIR.glob("*.jpg"))
    assert len(paths) == 5, f"expected 5 sample frames, found {len(paths)} in {SAMPLE_DIR}"
    return paths


@pytest.fixture(scope="session")
def frames(sample_paths: list[Path], cfg: PipelineConfig) -> list[np.ndarray]:
    return [load_frame(p, cfg.data) for p in sample_paths]


@pytest.fixture(scope="session")
def results(frames: list[np.ndarray], cfg: PipelineConfig):
    seg = build_segmenter(cfg)
    return [seg.segment(f) for f in frames]
