"""Splits: cut any metric by any vertical."""

from .engine import DIMENSIONS, Dimension, SplitEngine, available, register

__all__ = ["SplitEngine", "Dimension", "DIMENSIONS", "available", "register"]
