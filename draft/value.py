"""Player value: projected points and Value Over Replacement (VOR).

Projected points are the ONE input we don't have offline. In the real pipeline
they come from ESPN's `kona_player_info` view. Here we derive a transparent
proxy from positional rank so the prototype runs on real player/bye data today.

To go live: replace `proj_points_from_rank` with real projections and every
downstream number (VOR, need-adjusted score) becomes real. Nothing else changes.
"""

from .league import LeagueConfig

# Per-game PPR anchors: (points for pos_rank 1, per-rank decline, floor).
# Calibrated to rough real-world shapes so cross-position VOR is sane
# (elite RB/WR > elite QB in VOR because QB replacement level is high).
PROJECTION_ANCHORS = {
    "QB":   (24.0, 0.45, 14.0),
    "RB":   (21.0, 0.42, 6.0),
    "WR":   (20.0, 0.34, 6.0),
    "TE":   (15.0, 0.55, 4.0),
    "D/ST": (8.0,  0.15, 4.0),
    "K":    (9.0,  0.10, 6.0),
}
_DEFAULT_ANCHOR = (10.0, 0.30, 3.0)


def proj_points_from_rank(pos: str, pos_rank: int) -> float:
    """PROXY projection (per game) from positional rank. Replace with real data."""
    top, slope, floor = PROJECTION_ANCHORS.get(pos, _DEFAULT_ANCHOR)
    return max(floor, top - slope * (pos_rank - 1))


def replacement_points(pos: str, config: LeagueConfig) -> float:
    """Projection of the last startable player at `pos` (the VOR baseline)."""
    return proj_points_from_rank(pos, config.replacement_rank(pos))


def vor(proj_points: float, pos: str, config: LeagueConfig) -> float:
    """Value Over Replacement: points above a freely-available starter."""
    return proj_points - replacement_points(pos, config)
