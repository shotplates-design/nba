# NBA Box Score Explorer

Streamlit app for the box scores in `data/nba_box_scores.json`.

The file is nested as `{TEAM_ABBR: {game_N: {home_team: [player rows], away_team: [player rows]}}}`. Counting stats are numeric strings, and shooting fields are made-attempted strings such as `5-10`. `loader.py` (`BoxScoreLoader`) turns those into numbers, including values wrapped in an extra pair of quotes.

## Run

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

Streamlit prints a local URL, usually http://localhost:8501.

The sidebar switches between three views:

- **Leaderboard** — per-game averages for points, rebounds, assists, steals, and blocks, plus FG%, 3P%, and FT%. Sort from the control (or the column header) and filter by team. Shooting percentages are total makes divided by total attempts.
- **Player** — one player's season line, game log, and a trend chart.
- **Game** — both teams' box scores for a single game.

## Tests

```bash
python3 -m pytest
```
