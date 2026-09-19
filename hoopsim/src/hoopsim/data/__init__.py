"""Data layer: canonical schema, source adapters, play-by-play parsing."""

from .loaders import League, add_rest, aggregate_team_box
from .source import DataSource
from .csv_source import CSVSource
from .synthetic import SyntheticSource

__all__ = [
    "League",
    "DataSource",
    "SyntheticSource",
    "CSVSource",
    "add_rest",
    "aggregate_team_box",
]


def __getattr__(name):
    # NBAStatsSource pulls in `requests`; import it lazily so the rest of the
    # data layer works without a network stack installed.
    if name == "NBAStatsSource":
        from .nba_stats import NBAStatsSource

        return NBAStatsSource
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
