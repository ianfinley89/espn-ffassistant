# ESPN JSON API Spike

Proves we can read your league — settings, rosters, player pool, and draft
picks — straight from ESPN's internal JSON API. No Selenium, no XPath, no
copy/paste. This replaces the entire brittle scraping layer from the original
notebook.

## Why a completed season?

It's the off-season, so there's no live draft to poll. A **completed** draft
returns the same `mDraftDetail` shape a live one does, so running this against
last year validates auth, endpoints, and parsing today. The only thing it
can't exercise until draft night is real-time polling cadence.

## Setup

```bash
pip install requests python-dotenv
cp .env.example .env      # then edit .env
python spike/espn_api_spike.py
```

## Finding your LEAGUE_ID

Open your league on fantasy.espn.com. The URL contains it:

```
https://fantasy.espn.com/football/league?leagueId=123456
                                                  ^^^^^^  <- this
```

## Getting the cookies (private leagues only)

If your league is private you need two auth cookies. **These are sensitive —
treat them like a password.** They let anyone read (and potentially act in)
your league. Notes on where to run this are below.

1. Log into https://fantasy.espn.com in Chrome/Firefox.
2. Open DevTools (F12) → **Application** (Chrome) or **Storage** (Firefox) →
   **Cookies** → `https://fantasy.espn.com`.
3. Copy the **`espn_s2`** value (a long URL-encoded string) into `ESPN_S2`.
4. Copy the **`SWID`** value (a GUID in `{...}` braces — keep the braces) into
   `SWID`.

## A note on where to run this

`.env` is gitignored so your cookies won't be committed. But this repo can run
in a cloud container — if you'd rather not place real ESPN cookies in a shared
remote environment, run this spike **locally** on your own machine instead.
For a **public** league no cookies are needed at all, which is the safest way
to smoke-test the endpoints.

## What success looks like

You should see your league name, a list of draft picks with real player names,
and sample rosters. If so, the JSON-API approach is validated and we can build
the real "press go" assistant on top of it.
