"""Load the player universe from the FantasyPros rankings CSV.

Gives us real names, positions, positional ranks, tiers, and bye weeks. The
projected-points field is filled by the value-model proxy (see value.py).
"""

import csv
import re
from dataclasses import dataclass

from .value import proj_points_from_rank

_POS_RE = re.compile(r"([A-Za-z/]+?)(\d+)?$")


@dataclass
class Player:
    name: str
    pos: str            # RB, WR, QB, TE, D/ST, K
    pos_rank: int       # 1-based rank within position (from "RB1" etc.)
    overall_rank: int   # overall board rank (doubles as ADP proxy)
    tier: int
    bye: int
    proj_points: float  # per-game; proxy offline, real ESPN projection live

    def __repr__(self):
        return f"{self.name} ({self.pos}{self.pos_rank}, bye {self.bye})"


def _parse_pos(raw: str):
    """'RB1' -> ('RB', 1); 'D/ST' -> ('D/ST', None)."""
    raw = raw.strip()
    m = _POS_RE.match(raw)
    if not m:
        return raw, None
    pos, rank = m.group(1), m.group(2)
    return pos, (int(rank) if rank else None)


def _to_int(value, default=0):
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return default


def load_players(csv_path: str) -> list:
    """Parse the FantasyPros CSV into Player objects, ordered by board rank."""
    players = []
    pos_counters = {}
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            pos, pos_rank = _parse_pos(row.get("POS", ""))
            if not pos:
                continue
            # Some rows lack an explicit positional rank; assign by appearance.
            pos_counters[pos] = pos_counters.get(pos, 0) + 1
            if pos_rank is None:
                pos_rank = pos_counters[pos]
            players.append(
                Player(
                    name=row["PLAYER NAME"].strip(),
                    pos=pos,
                    pos_rank=pos_rank,
                    overall_rank=_to_int(row.get("RK"), default=999),
                    tier=_to_int(row.get("TIERS"), default=99),
                    bye=_to_int(row.get("BYE WEEK"), default=0),
                    proj_points=proj_points_from_rank(pos, pos_rank),
                )
            )
    players.sort(key=lambda p: p.overall_rank)
    return players
