"""Phase 1 pick recommender: need-aware VOR with bye penalty and tier context.

score(p | roster) = VOR(p) * need_multiplier(pos, roster) - bye_penalty(p, roster)

Deterministic and fully interpretable. In Phase 2 the need_multiplier heuristic
is replaced by Monte Carlo lookahead (see docs/DRAFT_MODEL.md).
"""

from dataclasses import dataclass

from .league import LeagueConfig
from .value import vor

# Value retained by a player who does NOT fill an open starting slot
# (bench / injury insurance / handcuff). Elite value still matters, so > 0.
_BENCH_MULTIPLIER = 0.45
_FLEX_MULTIPLIER = 0.9

# Bye-week penalty (in per-game projected points) per conflicting starter.
# Public: lineup.py uses the same constants to score final rosters.
BYE_SAME_POS = 2.0      # heavy: two startable RBs off in the same week hurts
BYE_OTHER_POS = 0.5     # mild: general roster-wide bye congestion


@dataclass
class Recommendation:
    player: object
    score: float
    base_vor: float
    need_multiplier: float
    bye_penalty: float
    tier_players_left: int
    reasons: list


def _open_starting_needs(roster, config: LeagueConfig) -> dict:
    """Remaining unfilled starting slots after greedily placing the roster."""
    needs = dict(config.starters)
    flex_left = needs.get("FLEX", 0)
    for p in roster:
        if needs.get(p.pos, 0) > 0:
            needs[p.pos] -= 1
        elif p.pos in config.flex_positions and flex_left > 0:
            flex_left -= 1
    if "FLEX" in needs:
        needs["FLEX"] = flex_left
    return needs


def need_multiplier(pos: str, roster, config: LeagueConfig) -> float:
    needs = _open_starting_needs(roster, config)
    if needs.get(pos, 0) > 0:
        return 1.0
    if pos in config.flex_positions and needs.get("FLEX", 0) > 0:
        return _FLEX_MULTIPLIER
    return _BENCH_MULTIPLIER


def _likely_starters(roster, config: LeagueConfig) -> list:
    """Players who currently occupy a starting slot (for bye-conflict checks)."""
    needs = dict(config.starters)
    flex_left = needs.get("FLEX", 0)
    starters = []
    for p in roster:
        if needs.get(p.pos, 0) > 0:
            needs[p.pos] -= 1
            starters.append(p)
        elif p.pos in config.flex_positions and flex_left > 0:
            flex_left -= 1
            starters.append(p)
    return starters


def bye_penalty(player, roster, config: LeagueConfig) -> float:
    if not player.bye:
        return 0.0
    penalty = 0.0
    for s in _likely_starters(roster, config):
        if s.bye != player.bye:
            continue
        penalty += BYE_SAME_POS if s.pos == player.pos else BYE_OTHER_POS
    return penalty


def tier_players_left(player, available) -> int:
    """How many players remain in this player's position AND tier (scarcity)."""
    return sum(
        1 for p in available if p.pos == player.pos and p.tier == player.tier
    )


def _build_reasons(rec_pos, mult, byepen, tier_left, base_vor) -> list:
    reasons = []
    if mult >= 1.0:
        reasons.append(f"fills an open {rec_pos} starting slot")
    elif mult == _FLEX_MULTIPLIER:
        reasons.append("fills your FLEX")
    else:
        reasons.append(f"{rec_pos} starters full — bench/insurance value")
    if base_vor > 0:
        reasons.append(f"+{base_vor:.1f} pts/gm over replacement")
    if tier_left <= 2:
        reasons.append(f"tier cliff: only {tier_left} left in this tier")
    if byepen > 0:
        reasons.append(f"bye stack penalty -{byepen:.1f}")
    return reasons


def recommend(available, roster, config: LeagueConfig, top_k: int = 8) -> list:
    """Rank available players for the next pick. Returns Recommendations."""
    recs = []
    for p in available:
        base = vor(p.proj_points, p.pos, config)
        mult = need_multiplier(p.pos, roster, config)
        byepen = bye_penalty(p, roster, config)
        score = base * mult - byepen
        tier_left = tier_players_left(p, available)
        recs.append(
            Recommendation(
                player=p,
                score=score,
                base_vor=base,
                need_multiplier=mult,
                bye_penalty=byepen,
                tier_players_left=tier_left,
                reasons=_build_reasons(p.pos, mult, byepen, tier_left, base),
            )
        )
    recs.sort(key=lambda r: r.score, reverse=True)
    return recs[:top_k]
