"""Run the Phase 1 recommender on real player data with a simulated draft state.

    python -m draft.demo

Loads the FantasyPros universe, marks the top overall players as already
drafted by opponents, assigns us a plausible mid-draft roster, and prints the
ranked recommendation for our next pick — with the reasoning behind each.
"""

from .league import LeagueConfig
from .players import load_players
from .scorer import recommend

CSV = "Expert_Picks/FantasyPros_2024_Draft_ALL_Rankings.csv"

# A plausible mid-draft roster to make the decision interesting: we're WR/QB/TE
# heavy and have zero RBs, so RB need should dominate. Names exist in the 2024
# file. (Live pipeline identifies our roster by ESPN player ID, no name matching.)
MY_ROSTER_NAMES = ["CeeDee Lamb", "Josh Allen", "Mark Andrews"]


def _find(players, name):
    for p in players:
        if p.name.lower() == name.lower():
            return p
    raise SystemExit(f"'{name}' not found in {CSV}; adjust MY_ROSTER_NAMES.")


def main():
    config = LeagueConfig()
    universe = load_players(CSV)

    roster = [_find(universe, n) for n in MY_ROSTER_NAMES]
    roster_names = {p.name for p in roster}

    # Simulate opponents having taken the best remaining players: mark the top
    # ~40 overall (that aren't ours) as gone, so we're picking around round 5.
    drafted = set(roster_names)
    for p in universe:
        if len(drafted) >= 40:
            break
        drafted.add(p.name)
    available = [p for p in universe if p.name not in drafted]

    print(f"League: {config.n_teams}-team {config.scoring}")
    print("My roster:", ", ".join(f"{p.name} ({p.pos})" for p in roster))
    byes = ", ".join(f"{p.pos} {p.name} bye {p.bye}" for p in roster)
    print("Byes:    ", byes)
    print(f"\nTop available: {available[0].name}, {available[1].name}, "
          f"{available[2].name} ...\n")

    print("=" * 78)
    print("RECOMMENDED PICKS (score = VOR x need - bye penalty)")
    print("=" * 78)
    for i, r in enumerate(recommend(available, roster, config, top_k=8), 1):
        p = r.player
        print(f"{i}. {p.name:<22} {p.pos}{p.pos_rank:<3} "
              f"score {r.score:6.1f}  (VOR {r.base_vor:5.1f} x "
              f"need {r.need_multiplier:.2f})")
        print(f"     -> {'; '.join(r.reasons)}")
    print("=" * 78)
    print("Note: projected points are a rank-derived PROXY offline; the live "
          "pipeline\nswaps in real ESPN projections via value.proj_points.")


if __name__ == "__main__":
    main()
