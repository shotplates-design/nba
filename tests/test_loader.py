"""Parser tests for BoxScoreLoader."""

import json
from pathlib import Path

import pytest

from loader import BoxScoreLoader

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "nba_box_scores.json"


def raw_row(**overrides):
    base = {
        "game_id": 1,
        "player": "Test Player",
        "team": "Detroit Pistons",
        "minutes": "10",
        "points": "0",
        "field_goal_percentage": "0-0",
        "three_point_percentage": "0-0",
        "free_throw_percentage": "0-0",
        "rebounds": "0",
        "assists": "0",
        "turnovers": "0",
        "steals": "0",
        "blocks": "0",
        "o_rebounds": "0",
        "d_rebounds": "0",
        "fouls": "0",
        "plus_minus": "0",
        "Starter": False,
    }
    base.update(overrides)
    return base


def test_unwrap_strips_extra_quotes():
    assert BoxScoreLoader.unwrap("'21'") == "21"
    assert BoxScoreLoader.unwrap("\"'21'\"") == "21"
    assert BoxScoreLoader.unwrap("  '5-10'  ") == "5-10"
    assert BoxScoreLoader.unwrap("21") == "21"
    assert BoxScoreLoader.unwrap("'O'Brien'") == "O'Brien"


def test_parse_number_and_plus_minus():
    assert BoxScoreLoader.parse_number("'21'") == 21
    assert BoxScoreLoader.parse_number("21") == 21
    assert BoxScoreLoader.parse_number("+5") == 5
    assert BoxScoreLoader.parse_number("'-13'") == -13
    assert BoxScoreLoader.parse_number("0") == 0
    assert BoxScoreLoader.parse_number("--") is None
    assert BoxScoreLoader.parse_number("'--'") is None


def test_parse_shooting_made_attempted():
    assert BoxScoreLoader.parse_shooting("5-10") == (5, 10, 0.5)
    assert BoxScoreLoader.parse_shooting("'5-10'") == (5, 10, 0.5)
    assert BoxScoreLoader.parse_shooting("'0-3'") == (0, 3, 0.0)
    assert BoxScoreLoader.parse_shooting("0-0") == (0, 0, None)


def test_parse_row_accepts_quoted_strings():
    parsed = BoxScoreLoader.parse_row(
        raw_row(
            game_id="'1'",
            player="'Duncan Robinson'",
            team="'Detroit Pistons'",
            minutes="'28'",
            points="'21'",
            field_goal_percentage="'5-10'",
            three_point_percentage="'5-9'",
            free_throw_percentage="'6-8'",
            rebounds="'2'",
            assists="'2'",
            steals="'1'",
            blocks="'0'",
            plus_minus="'+5'",
            Starter="'True'",
        ),
        "home_team",
    )
    assert parsed["player"] == "Duncan Robinson"
    assert parsed["game_id"] == 1
    assert parsed["points"] == 21
    assert parsed["fg_made"] == 5
    assert parsed["fg_att"] == 10
    assert parsed["fg_pct"] == 0.5
    assert parsed["tp_made"] == 5
    assert parsed["tp_att"] == 9
    assert parsed["ft_made"] == 6
    assert parsed["plus_minus"] == 5
    assert parsed["starter"] is True
    assert parsed["side"] == "home"
    assert parsed["team_abbr"] == "DET"


def test_leaderboard_uses_attempt_weighted_percentages():
    first = BoxScoreLoader.parse_row(
        raw_row(
            game_id=1,
            points="10",
            rebounds="4",
            assists="3",
            steals="1",
            blocks="0",
            field_goal_percentage="1-2",
            three_point_percentage="0-1",
            free_throw_percentage="0-0",
        ),
        "home_team",
    )
    second = BoxScoreLoader.parse_row(
        raw_row(
            game_id=2,
            points="20",
            rebounds="6",
            assists="5",
            steals="3",
            blocks="2",
            field_goal_percentage="9-10",
            three_point_percentage="1-1",
            free_throw_percentage="2-2",
        ),
        "away_team",
    )
    entry = BoxScoreLoader.leaderboard([first, second])[0]
    assert entry["G"] == 2
    assert entry["PPG"] == 15
    assert entry["RPG"] == 5
    assert entry["APG"] == 4
    assert entry["SPG"] == 2
    assert entry["BPG"] == 1
    assert entry["FG%"] == pytest.approx(100 * 10 / 12)
    assert entry["FG%"] != pytest.approx(70)
    assert entry["3P%"] == pytest.approx(50)
    assert entry["FT%"] == pytest.approx(100)


def test_load_assigns_opponents(tmp_path):
    payload = {
        "DET": {
            "game_1": {
                "home_team": [raw_row(player="Home Guy", team="Detroit Pistons", points="10")],
                "away_team": [
                    raw_row(player="Away Guy", team="Boston Celtics", points="8", minutes="'--'")
                ],
            }
        }
    }
    path = tmp_path / "box.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = {row["player"]: row for row in BoxScoreLoader.load(path)}
    assert loaded["Home Guy"]["opponent"] == "Boston Celtics"
    assert loaded["Home Guy"]["side"] == "home"
    assert loaded["Away Guy"]["opponent"] == "Detroit Pistons"
    assert loaded["Away Guy"]["team_abbr"] == "BOS"
    assert loaded["Away Guy"]["minutes"] is None
    assert loaded["Away Guy"]["points"] == 8
    summary = BoxScoreLoader.game_summaries(list(loaded.values()))[0]
    assert summary["home_points"] == 10
    assert summary["away_points"] == 8
    assert summary["home_team"] == "Detroit Pistons"
    assert summary["away_team"] == "Boston Celtics"


def test_real_dataset_known_row():
    rows = BoxScoreLoader.load(DATA_PATH)
    assert len(rows) == 1533
    assert len({row["game_id"] for row in rows}) == 67
    duncan = next(
        row for row in rows if row["player"] == "Duncan Robinson" and row["game_id"] == 1
    )
    assert duncan["points"] == 21
    assert duncan["rebounds"] == 2
    assert duncan["assists"] == 2
    assert (duncan["fg_made"], duncan["fg_att"], duncan["fg_pct"]) == (5, 10, 0.5)
    assert duncan["plus_minus"] == 5
    assert duncan["starter"] is True
    assert duncan["side"] == "home"
    assert duncan["team"] == "Detroit Pistons"
    assert duncan["opponent"] == "Boston Celtics"
    dnp = [row for row in rows if row["minutes"] is None]
    assert len(dnp) == 2
    assert {row["player"] for row in dnp} == {"Pacome Dadiet"}
