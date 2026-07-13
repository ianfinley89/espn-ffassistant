# Draft Model — Design

How the drafting assistant decides who to recommend. This is the "brain" that
sits behind the "press go" loop; the ESPN JSON API (see `spike/`) feeds it live
state, and the LLM sits on top to explain picks and absorb natural-language
preferences.

## The one idea that shapes everything

Separate the two problems. Fusing them is the classic mistake.

1. **Player value** — how many points will a player score? Regression, lots of
   clean data, and where real projections (ESPN/FantasyPros) or a tree model
   live. In v1 we just *consume* projections; we don't try to beat them.
2. **Pick strategy** — given values + scarcity + roster construction + how
   opponents behave, which pick maximizes my *final team's* value across the
   whole draft? Sequential, adversarial. This is the interesting part.

A single model that "predicts the next best pick" from historical drafts fails
at #2, because historical picks are just Average Draft Position (a model of the
*average drafter*, not of *optimal play*), and "which team won" is buried under
in-season variance (injuries, waivers, luck). So we use past-draft data as an
**opponent-behavior model**, never as optimality labels.

## Objective function

We optimize **expected season-long starting-lineup points, valued over
replacement**, at the end of the draft — not raw points, and not the value of
the players sitting on the bench.

```
TeamValue(roster) = Σ_{starting slots s}  proj_points( best_unused_player_for(s) )
                    − bye_conflict_penalty(roster)
```

The draft goal is to choose picks that maximize expected final `TeamValue`.
Everything the user asked for — scarcity, positional runs, not stacking byes,
roster balance — is a *consequence* of this objective, not a hand-coded rule.

## Phase 1 (shipping now): need-aware VOR, greedy

A fast, deterministic, fully interpretable score for each available player.
This is what `draft/scorer.py` implements today.

**Value Over Replacement (VOR / VBD):**

```
VOR(p) = proj_points(p) − replacement_points(pos(p))
```

`replacement_points(pos)` = the projection of the *last startable* player at
that position across the whole league, i.e. roughly the
`(n_teams × starters_per_team_at_pos)`-th best player at that position (flex
folded in). This is why an elite RB outscores an elite QB in VOR even though the
QB scores more raw points — QB replacement level is nearly as high as QB1.

**Need-aware adjustment** (a cheap stand-in for "what does this actually add to
my starting lineup?"):

```
score(p | roster) = VOR(p) × need_multiplier(pos, roster) − bye_penalty(p, roster)
```

- `need_multiplier` ≈ 1.0 if `p` fills an open starting slot, ~0.9 for flex,
  and a discount if the position's starting slots are already full (bench /
  injury insurance only).
- `bye_penalty` grows when `p` shares a bye week with players already
  penciled into my starting lineup — heavily for the same position.

We also surface a **tier-cliff** signal (how many players remain in `p`'s tier
at its position) so the assistant can say "grab RB now, the tier falls off a
cliff before your next pick."

Greedy VOR is already dramatically better than the old "dump every ranking into
the prompt" approach, and it grounds the LLM in real numbers.

## Phase 2 (the real brain): Monte Carlo lookahead

**Implemented:** `draft/lineup.py` (the TeamValue objective), `draft/simulate.py`
(DraftState, snake order, ADP-noise opponent model, rollout policies,
`mc_recommend`, survival probabilities), `draft/demo_mc.py` (side-by-side
greedy-vs-lookahead demo; ~150 sims/candidate runs in a few seconds, well
inside a pick clock).

Replace the `need_multiplier` heuristic with the genuine article: simulate the
rest of the draft and measure each candidate's *actual* effect on final
`TeamValue`.

```
for each candidate pick p at the current state:
    for i in 1..N simulations:
        take p, then play the draft to completion:
            - opponents pick by sampling ADP (with noise)      # opponent model
            - I fill my remaining picks with a fast rollout heuristic (Phase-1 VOR)
        record final TeamValue_i
    E[value | p] = mean(TeamValue_i)
recommend argmax_p E[value | p]
```

Why Monte Carlo, not RL, as the core engine:

- The **opponent model is nearly free**: real ESPN leagues (humans + auto-pick)
  draft close to ADP, so sampling ADP with noise is a genuinely good simulator.
- Scarcity, positional runs, bye balance, and roster construction all **emerge**
  from simulating to the end — no rules to maintain.
- **Off-path replanning is free**: we re-solve from the actual board every pick,
  so "someone drafted off the predicted path" just means we recompute. There is
  no fragile predicted path to break.
- With ~15 rounds and a 30–90s pick clock, inference-time simulation is fast
  enough. RL's payoff (amortize planning into one forward pass) isn't needed.

## Where trees and RL fit (later, optional)

- **Value tree (regression):** blend projection sources / build our own edge.
  Optional — expert projections are hard to beat.
- **Opponent tree (classification):** `P(player picked within next k picks |
  ADP, round, position-run state, …)`. This is the *correct* home for
  "learn from past drafts" — a well-posed problem with real labels (we observe
  who got picked) that sharpens the simulator's opponents.
- **Learned / RL policy:** distilled from the simulator, only if we want instant
  inference or want to *discover* non-obvious strategy (e.g. does Zero-RB beat
  balanced in our specific league settings?). We need the simulator either way,
  so it comes first.

## The LLM's job

The planner emits numbers and a ranked shortlist. The LLM (provider-swappable)
(1) explains the recommendation in plain language and (2) lets the user inject
soft preferences mid-draft ("go Zero-RB", "avoid anyone on the Jets", "I have
too many Week 9 byes") that reweight the objective. It does judgment and
communication; it does not do the arithmetic.

## Data sources

| Need                | Real pipeline (ESPN)                  | Offline prototype              |
| ------------------- | ------------------------------------- | ------------------------------ |
| Projected points    | `kona_player_info` view               | proxy from positional rank *   |
| Bye weeks           | player metadata / rankings            | FantasyPros CSV `BYE WEEK`     |
| Live board / picks  | `mDraftDetail` (polled)               | simulated mid-draft state      |
| ADP (opponent model)| `kona_player_info` draftRanks         | FantasyPros `RK` as ADP proxy  |
| League settings     | `mSettings`                           | hardcoded (10-team PPR)        |

\* The proxy is a transparent per-position decay curve in `draft/value.py`
(`PROJECTION_ANCHORS`). Replace `proj_points_from_rank` with real projections
and every downstream number becomes real — nothing else changes.
