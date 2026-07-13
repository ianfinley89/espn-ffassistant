"""Phase 2: Monte Carlo draft lookahead (docs/DRAFT_MODEL.md).

For each candidate pick, simulate the rest of the snake draft N times —
opponents sample from ADP with noise, our remaining picks use the fast Phase-1
greedy policy — and score the final roster with the lineup_value objective.
Recommend the candidate with the best expected final team.

Everything replans from the live board every pick, so "someone drafted off the
predicted path" costs nothing: there is no predicted path, only the current
state.

Design notes:
- Opponent model: real leagues draft close to ADP. We sample from the top
  OPP_WINDOW available (after positional-sanity filters) with exponentially
  decaying weight. Sharpening this with a learned pick-probability model is
  the designated Phase-3 upgrade and slots in at `opponent_pick`.
- Our rollout policy is the Phase-1 need-aware VOR score over a small ADP
  window: cheap, decent, and shared logic with the live recommender.
- Both policies are forced onto unfilled starting positions when a team's
  remaining picks run low, so simulated rosters end with legal lineups.
- Common random numbers: simulation `s` uses the same seed for every
  candidate, so candidates are compared under paired opponent behavior
  (variance reduction).
"""

import random
from dataclasses import dataclass
from math import exp, sqrt
from statistics import fmean, pstdev

from .league import LeagueConfig
from .lineup import lineup_value
from .scorer import _open_starting_needs, bye_penalty, need_multiplier, recommend
from .value import vor

# Opponents consider this many of the best available (post-filter) players...
OPP_WINDOW = 12
# ...with weight exp(-i / OPP_TEMP) on the i-th; lower = tighter to ADP.
OPP_TEMP = 3.0
# Our rollout policy scores this many of the best available by ADP.
MY_WINDOW = 20
# Sanity caps so simulated teams don't hoard onesie positions.
POSITION_CAPS = {"QB": 2, "TE": 2, "K": 1, "D/ST": 1}
# K/D:ST become draftable only in a team's last few picks (as humans do).
LATE_KDST_PICKS = 3


def team_for_pick(pick: int, n_teams: int) -> int:
    """Snake order: 0-based overall pick -> team index."""
    rnd, slot = divmod(pick, n_teams)
    return slot if rnd % 2 == 0 else n_teams - 1 - slot


@dataclass
class DraftState:
    config: LeagueConfig
    available: list        # Players still on the board, sorted by ADP
    rosters: list          # list[list[Player]], one per team
    next_pick: int         # 0-based overall pick number
    n_rounds: int = 16     # total roster size per team

    @property
    def total_picks(self) -> int:
        return self.config.n_teams * self.n_rounds

    @property
    def done(self) -> bool:
        return self.next_pick >= self.total_picks

    def clone(self) -> "DraftState":
        return DraftState(
            self.config,
            list(self.available),
            [list(r) for r in self.rosters],
            self.next_pick,
            self.n_rounds,
        )

    def picks_left(self, team: int) -> int:
        """How many picks `team` still has, including the current one if on
        the clock. O(1) via snake structure."""
        n = self.config.n_teams
        rnd, pos_in_round = divmod(self.next_pick, n)
        idx_in_round = team if rnd % 2 == 0 else n - 1 - team
        still_this_round = 1 if idx_in_round >= pos_in_round else 0
        return still_this_round + (self.n_rounds - rnd - 1)

    def next_pick_for(self, team: int) -> int:
        """Overall pick number of `team`'s next turn after the current pick."""
        for pick in range(self.next_pick + 1, self.total_picks):
            if team_for_pick(pick, self.config.n_teams) == team:
                return pick
        return self.total_picks


def _eligible_indices(state: DraftState, team: int, window: int) -> list:
    """Indices (into state.available) a team would realistically consider.

    Applies: forced-need mode when remaining picks barely cover unfilled
    starting slots; positional caps; and no K/D:ST until the late rounds.
    """
    roster = state.rosters[team]
    config = state.config
    picks_left = state.picks_left(team)
    needs = _open_starting_needs(roster, config)
    must = sum(needs.values())
    force = picks_left <= must

    counts = {}
    for p in roster:
        counts[p.pos] = counts.get(p.pos, 0) + 1

    out = []
    for i, p in enumerate(state.available):
        if force:
            ok = needs.get(p.pos, 0) > 0 or (
                needs.get("FLEX", 0) > 0 and p.pos in config.flex_positions
            )
            if not ok:
                continue
        else:
            if counts.get(p.pos, 0) >= POSITION_CAPS.get(p.pos, 99):
                continue
            if p.pos in ("K", "D/ST") and picks_left > LATE_KDST_PICKS:
                continue
        out.append(i)
        if len(out) >= window:
            break
    # Degenerate board (filters excluded everything): take best available.
    return out or list(range(min(window, len(state.available))))


def opponent_pick(state: DraftState, team: int, rng: random.Random) -> int:
    """ADP-with-noise opponent model. Returns an index into state.available."""
    idxs = _eligible_indices(state, team, OPP_WINDOW)
    weights = [exp(-j / OPP_TEMP) for j in range(len(idxs))]
    return rng.choices(idxs, weights=weights, k=1)[0]


def my_rollout_pick(state: DraftState, team: int,
                    exclude_name: str = None) -> int:
    """Our fast in-simulation policy: Phase-1 greedy score over an ADP window.

    `exclude_name` supports the survival question "what do I take if I pass
    on this player?" — the excluded player stays on the board.
    """
    roster = state.rosters[team]
    config = state.config
    best_i, best_score = None, float("-inf")
    for i in _eligible_indices(state, team, MY_WINDOW):
        p = state.available[i]
        if exclude_name is not None and p.name == exclude_name:
            continue
        score = (
            vor(p.proj_points, p.pos, config)
            * need_multiplier(p.pos, roster, config)
            - bye_penalty(p, roster, config)
        )
        if score > best_score:
            best_i, best_score = i, score
    if best_i is None:  # window contained only the excluded player
        best_i = next(
            i for i, p in enumerate(state.available) if p.name != exclude_name
        )
    return best_i


def play_out(state: DraftState, my_team: int, rng: random.Random,
             stop_at_pick: int = None) -> DraftState:
    """Advance the draft in place until completion (or `stop_at_pick`)."""
    stop = state.total_picks if stop_at_pick is None else min(
        stop_at_pick, state.total_picks
    )
    while state.next_pick < stop and state.available:
        team = team_for_pick(state.next_pick, state.config.n_teams)
        if team == my_team:
            idx = my_rollout_pick(state, team)
        else:
            idx = opponent_pick(state, team, rng)
        state.rosters[team].append(state.available.pop(idx))
        state.next_pick += 1
    return state


@dataclass
class CandidateEval:
    player: object
    mean_value: float     # E[final TeamValue | take this player now]
    std_err: float
    survival_pct: float   # P(still available at my next pick if I pass now)


def _candidates(state: DraftState, my_team: int, top_k: int,
                extra_adp: int) -> list:
    """Greedy shortlist plus the very top of the ADP board (coverage)."""
    recs = recommend(state.available, state.rosters[my_team], state.config,
                     top_k=top_k)
    cands = [r.player for r in recs]
    names = {p.name for p in cands}
    for p in state.available[:extra_adp]:
        if p.name not in names:
            cands.append(p)
            names.add(p.name)
    return cands


def _survival(state: DraftState, my_team: int, cands: list, n_sims: int,
              seed: int) -> dict:
    """P(candidate survives to my next pick) given I pass on him now.

    Per candidate: my current pick becomes my greedy choice *excluding* the
    candidate, opponents draft to my next turn, and we check whether the
    candidate is still on the board.
    """
    next_mine = state.next_pick_for(my_team)
    out = {}
    for cand in cands:
        survived = 0
        for s in range(n_sims):
            rng = random.Random((seed + 7919) * 100003 + s)
            sim = state.clone()
            idx = my_rollout_pick(sim, my_team, exclude_name=cand.name)
            sim.rosters[my_team].append(sim.available.pop(idx))
            sim.next_pick += 1
            play_out(sim, my_team, rng, stop_at_pick=next_mine)
            if any(p.name == cand.name for p in sim.available):
                survived += 1
        out[cand.name] = 100.0 * survived / n_sims
    return out


def mc_recommend(state: DraftState, my_team: int, n_sims: int = 100,
                 seed: int = 0, top_k: int = 8, extra_adp: int = 3) -> list:
    """Monte Carlo lookahead. Returns CandidateEvals sorted best-first."""
    cands = _candidates(state, my_team, top_k, extra_adp)
    survival = _survival(state, my_team, cands, max(n_sims, 100), seed)

    results = []
    for cand in cands:
        values = []
        for s in range(n_sims):
            # Same seed across candidates for paired comparison.
            rng = random.Random(seed * 100003 + s)
            sim = state.clone()
            idx = next(
                i for i, p in enumerate(sim.available) if p.name == cand.name
            )
            sim.rosters[my_team].append(sim.available.pop(idx))
            sim.next_pick += 1
            play_out(sim, my_team, rng)
            values.append(lineup_value(sim.rosters[my_team], sim.config))
        results.append(
            CandidateEval(
                player=cand,
                mean_value=fmean(values),
                std_err=pstdev(values) / sqrt(len(values)),
                survival_pct=survival[cand.name],
            )
        )
    results.sort(key=lambda r: r.mean_value, reverse=True)
    return results
