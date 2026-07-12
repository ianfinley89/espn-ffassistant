"""Phase 2 demo: Monte Carlo lookahead vs Phase-1 greedy on the same board.

    python -m draft.demo_mc [n_sims]

Rebuilds the Phase-1 demo state (10-team PPR, ~round 5, we have zero RBs) and
shows how simulating the rest of the draft changes the recommendation —
including P(player survives to your next pick) for every candidate.
"""

import sys
import time

from .league import LeagueConfig
from .lineup import best_lineup, lineup_value
from .players import load_players
from .scorer import recommend
from .simulate import DraftState, mc_recommend, play_out, team_for_pick
import random

CSV = "Expert_Picks/FantasyPros_2024_Draft_ALL_Rankings.csv"

# Same interesting state as draft/demo.py: WR/QB/TE filled, zero RBs.
MY_ROSTER_NAMES = ["CeeDee Lamb", "Josh Allen", "Mark Andrews", "Drake London"]
MY_TEAM = 0
PICKS_MADE = 40  # 10 teams x 4 rounds done; pick 41 (ours) is on the clock


def build_state():
    config = LeagueConfig()
    universe = load_players(CSV)
    by_name = {p.name: p for p in universe}

    missing = [n for n in MY_ROSTER_NAMES if n not in by_name]
    if missing:
        raise SystemExit(f"Not in {CSV}: {missing}")
    mine = [by_name[n] for n in MY_ROSTER_NAMES]
    taken = {p.name for p in mine}

    # Opponents drafted the best of the rest: top 36 by ADP, dealt round-robin.
    rosters = [[] for _ in range(config.n_teams)]
    rosters[MY_TEAM] = list(mine)
    opp_teams = [t for t in range(config.n_teams) if t != MY_TEAM]
    i = 0
    for p in universe:
        if len(taken) >= PICKS_MADE:
            break
        if p.name in taken:
            continue
        rosters[opp_teams[i % len(opp_teams)]].append(p)
        taken.add(p.name)
        i += 1

    available = [p for p in universe if p.name not in taken]
    state = DraftState(config, available, rosters, next_pick=PICKS_MADE)
    assert team_for_pick(state.next_pick, config.n_teams) == MY_TEAM
    return state


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    state = build_state()
    config = state.config
    roster = state.rosters[MY_TEAM]

    rnd = state.next_pick // config.n_teams + 1
    print(f"League: {config.n_teams}-team {config.scoring} | "
          f"Round {rnd}, overall pick {state.next_pick + 1} (you)")
    print("Your roster:", ", ".join(f"{p.name} ({p.pos})" for p in roster))

    greedy = recommend(state.available, roster, config, top_k=5)
    print("\nPhase 1 (greedy VOR) top 5:")
    for i, r in enumerate(greedy, 1):
        print(f"  {i}. {r.player.name:<22} {r.player.pos}{r.player.pos_rank:<3}"
              f" score {r.score:5.1f}")

    t0 = time.perf_counter()
    evals = mc_recommend(state, MY_TEAM, n_sims=n_sims, seed=42)
    dt = time.perf_counter() - t0

    print(f"\nPhase 2 (Monte Carlo lookahead, {n_sims} sims/candidate, "
          f"{dt:.1f}s):")
    print(f"{'':3}{'player':<22}{'pos':<6}{'E[team value]':>14}"
          f"{'  ±SE':>7}{'  survives to next pick':>24}")
    for i, e in enumerate(evals, 1):
        p = e.player
        print(f"{i:>2}. {p.name:<22}{p.pos}{p.pos_rank:<4}"
              f"{e.mean_value:>12.1f}{e.std_err:>7.2f}"
              f"{e.survival_pct:>18.0f}%")

    g1, m1 = greedy[0].player, evals[0].player
    print()
    if g1.name == m1.name:
        print(f"Greedy and lookahead agree: {m1.name}.")
    else:
        gname = g1.name
        g_in_mc = next((e for e in evals if e.player.name == gname), None)
        print(f"Lookahead OVERRULES greedy: {m1.name} over {gname}.")
        if g_in_mc:
            print(f"  {gname}: E[team] {g_in_mc.mean_value:.1f} vs "
                  f"{evals[0].mean_value:.1f}, and survives to your next "
                  f"pick in {g_in_mc.survival_pct:.0f}% of sims "
                  f"(vs {evals[0].survival_pct:.0f}% for {m1.name}).")

    # Show one representative completed draft for trust in the rollouts.
    sim = state.clone()
    idx = next(i for i, p in enumerate(sim.available)
               if p.name == evals[0].player.name)
    sim.rosters[MY_TEAM].append(sim.available.pop(idx))
    sim.next_pick += 1
    play_out(sim, MY_TEAM, random.Random(7))
    final = sim.rosters[MY_TEAM]
    starters = best_lineup(final, config)
    starter_ids = {id(p) for p in starters}
    print(f"\nOne simulated end-state roster (TeamValue "
          f"{lineup_value(final, config):.1f}):")
    print("  starters:", ", ".join(f"{p.name} ({p.pos})" for p in starters))
    print("  bench:   ", ", ".join(p.name for p in final
                                   if id(p) not in starter_ids))


if __name__ == "__main__":
    main()
