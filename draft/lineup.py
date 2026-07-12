"""The draft objective: value of a finished roster's best starting lineup.

This is what the Monte Carlo lookahead maximizes (docs/DRAFT_MODEL.md):

    TeamValue(roster) = sum of proj_points over the best legal starting lineup
                        - bye-congestion penalty among those starters

Bench players contribute nothing directly — their value shows up only by
upgrading a starter. Unfilled starting slots contribute 0 points, so rollout
policies are naturally pressured to complete a legal lineup (QB/DST/K included).
"""

from .league import LeagueConfig
from .scorer import BYE_OTHER_POS, BYE_SAME_POS


def best_lineup(roster, config: LeagueConfig) -> list:
    """Pick the best legal starting lineup from a roster.

    Dedicated slots take the top players at their position; FLEX then takes
    the best remaining flex-eligible player. Greedy is optimal here because
    dedicated slots and FLEX want players in the same descending order.
    """
    by_pos = {}
    for p in roster:
        by_pos.setdefault(p.pos, []).append(p)
    for lst in by_pos.values():
        lst.sort(key=lambda p: p.proj_points, reverse=True)

    starters, used = [], set()
    for pos, count in config.starters.items():
        if pos == "FLEX":
            continue
        for p in by_pos.get(pos, [])[:count]:
            starters.append(p)
            used.add(id(p))

    flex_pool = [
        p
        for pos in config.flex_positions
        for p in by_pos.get(pos, [])
        if id(p) not in used
    ]
    flex_pool.sort(key=lambda p: p.proj_points, reverse=True)
    starters.extend(flex_pool[: config.starters.get("FLEX", 0)])
    return starters


def lineup_value(roster, config: LeagueConfig) -> float:
    """TeamValue: starting-lineup points minus bye congestion among starters."""
    starters = best_lineup(roster, config)
    value = sum(p.proj_points for p in starters)
    for i, a in enumerate(starters):
        for b in starters[i + 1 :]:
            if a.bye and a.bye == b.bye:
                value -= BYE_SAME_POS if a.pos == b.pos else BYE_OTHER_POS
    return value
