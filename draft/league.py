"""League configuration: size, starting lineup, flex eligibility.

Defaults match the user's league (10-team PPR) per the original notebook and
Current_Roster.csv. In the real pipeline these come from the ESPN `mSettings`
view instead of being hardcoded.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LeagueConfig:
    n_teams: int = 10
    scoring: str = "PPR"
    # Starting-lineup slots (excludes bench). FLEX handled separately.
    starters: dict = field(
        default_factory=lambda: {
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 1,
            "D/ST": 1,
            "K": 1,
        }
    )
    flex_positions: tuple = ("RB", "WR", "TE")

    def dedicated_starters(self, pos: str) -> int:
        """Starting slots reserved for `pos`, ignoring flex."""
        return self.starters.get(pos, 0)

    def flex_share(self, pos: str) -> float:
        """Fraction of the league's flex slots that tend to go to `pos`.

        Split flex evenly across flex-eligible positions as a first
        approximation; used only to place the replacement baseline.
        """
        if pos not in self.flex_positions:
            return 0.0
        return 1.0 / len(self.flex_positions)

    def replacement_rank(self, pos: str) -> int:
        """Positional rank of the last 'startable' player leaguewide.

        e.g. 10 teams x 2 starting RB + flex share -> ~RB25 is replacement.
        """
        flex_slots = self.starters.get("FLEX", 0)
        starters_at_pos = self.dedicated_starters(pos) + self.flex_share(pos) * flex_slots
        rank = round(self.n_teams * starters_at_pos)
        return max(rank, 1)
