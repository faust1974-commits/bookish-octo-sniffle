"""Projection: aging, regression to the mean, player forecasts, rotations."""

from .aging import aging_curve_table, aging_delta, aging_multiplier
from .player import ProjectionConfig, ProjectionResult, project_availability, project_players
from .regression import reliability, shrink, shrink_stat, stabilization_point, weighted_history
from .rotation import (RotationConstraints, allocate_minutes, build_rotation_plan,
                       evaluate_rotation, optimize_rotation)

__all__ = [
    "aging_multiplier", "aging_delta", "aging_curve_table",
    "shrink", "shrink_stat", "stabilization_point", "reliability", "weighted_history",
    "project_players", "ProjectionConfig", "ProjectionResult", "project_availability",
    "RotationConstraints", "allocate_minutes", "build_rotation_plan",
    "evaluate_rotation", "optimize_rotation",
]
