"""Shared fixtures.

The synthetic league is built once per session because generating it costs a
few seconds, and every test that needs data needs the same data.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hoopsim.context import Analysis  # noqa: E402
from hoopsim.data import League, SyntheticSource  # noqa: E402


@pytest.fixture(scope="session")
def source():
    return SyntheticSource(n_teams=10, games_per_team=20, seed=424242)


@pytest.fixture(scope="session")
def league(source):
    return League.from_source(source, "2024-25")


@pytest.fixture(scope="session")
def analysis(league):
    return Analysis(league=league)


@pytest.fixture(scope="session")
def big_league():
    """Larger league for tests that need statistical power."""
    return League.from_source(
        SyntheticSource(n_teams=20, games_per_team=40, seed=99), "2024-25"
    )
