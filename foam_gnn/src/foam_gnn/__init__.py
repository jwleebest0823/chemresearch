"""
foam_gnn
========
Physics-informed Graph Neural Network pipeline for modelling the evolution of a
quasi-2D evaporating soap foam.

Modules (built incrementally, each with a smoke test):
    config          - all configuration dataclasses (single source of truth)
    guards          - shape / dtype / finiteness validators (fail loud)
    io_utils        - frame discovery + loading
    segmentation    - MODULE 1: image -> labelled bubble masks  (implemented)
    tracking        - MODULE 2: persistent bubble IDs + T1/T2    (planned)
    graph           - MODULE 3: bubbles -> NetworkX / PyG graphs (planned)
    models/         - MODULE 4: spatio-temporal GNN + baselines  (planned)
    evaluate        - MODULE 5: metrics, beta, radial test       (planned)
    train           - MODULE 6: leave-one-experiment-out CV      (planned)

This package is self-contained and has no dependency on anything outside the
``foam_gnn/`` project root.
"""
from __future__ import annotations

from . import config, guards, io_utils, segmentation

__version__ = "0.1.0"

__all__ = ["config", "guards", "io_utils", "segmentation", "__version__"]
