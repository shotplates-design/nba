"""Parse nested NBA box scores into flat player-game rows."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path


class BoxScoreLoader:
    """Static parsers for the nested box-score file.

    Counting stats are numeric strings. Shooting fields are made-attempted
    strings such as ``5-10``, not percentages. Values may also be wrapped in
    an extra pair of quotes (``'21'``).
    """

    TEAM_ABBR = {
        "Atlanta Hawks": "ATL",
        "Boston Celtics": "BOS",
        "Brooklyn Nets": "BKN",
        "Charlotte Hornets": "CHA",
        "Chicago Bulls": "CHI",
        "Cleveland Cavaliers": "CLE",
        "Dallas Mavericks": "DAL",
        "Denver Nuggets": "DEN",
        "Detroit Pistons": "DET",
        "Golden State Warriors": "GSW",
        "Houston Rockets": "HOU",
        "Indiana Pacers": "IND",
        "LA Clippers": "LAC",
        "Los Angeles Clippers": "LAC",
        "Los Angeles Lakers": "LAL",
        "Memphis Grizzlies": "MEM",
        "Miami Heat": "MIA",
        "Milwaukee Bucks": "MIL",
        "Minnesota Timberwolves": "MIN",
        "New Orleans Pelicans": "NOP",
        "New York Knicks": "NYK",
        "Oklahoma City Thunder": "OKC",
        "Orlando Magic": "ORL",
        "Philadelphia 76ers": "PHI",
        "Phoenix Suns": "PHX",
        "Portland Trail Blazers": "POR",
        "Sacramento Kings": "SAC",
        "San Antonio Spurs": "SAS",
        "Toronto Raptors": "TOR",
        "Utah Jazz": "UTA",
        "Washington Wizards": "WAS",
    }

    COUNTING_FIELDS = (
        "points",
        "rebounds",
        "assists",
        "turnovers",
        "steals",
        "blocks",
        "o_rebounds",
        "d_rebounds",
        "fouls",
    )

    @staticmethod
    def unwrap(value):
        """Strip whitespace and matching quote layers from a string value."""
        if not isinstance(value, str):
            return value
        text = value.strip()
        while len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
            text = text[1:-1].strip()
        return text

    @staticmethod
    def parse_number(value):
        """Parse a counting stat or plus/minus. Non-numeric minutes (``--``) are None."""
        text = BoxScoreLoader.unwrap(value)
        if isinstance(text, bool) or text is None:
            return None
        if isinstance(text, int):
            return text
        if isinstance(text, float):
            return int(text) if text.is_integer() else text
        if not isinstance(text, str) or text in {"", "--", "DNP", "NA", "N/A"}:
            return None
        cleaned = text[1:] if text.startswith("+") else text
        if cleaned in {"", "--"}:
            return None
        try:
            number = float(cleaned)
        except ValueError:
            return None
        return int(number) if number.is_integer() else number

    @staticmethod
    def parse_shooting(value):
        """Split ``made-attempted`` into makes, attempts, and a rate.

        The rate is None when there are no attempts, including ``0-0``.
        """
        text = BoxScoreLoader.unwrap(value)
        if text is None or text in {"", "--"}:
            return 0, 0, None
        made_text, attempted_text = str(text).split("-", 1)
        made = int(made_text)
        attempted = int(attempted_text)
        percentage = None if attempted == 0 else made / attempted
        return made, attempted, percentage

    @staticmethod
    def parse_bool(value):
        if isinstance(value, bool):
            return value
        text = str(BoxScoreLoader.unwrap(value)).strip().lower()
        return text in {"true", "1", "yes"}

    @staticmethod
    def parse_row(raw, side):
        """Normalize one player row. ``side`` is ``home_team`` or ``away_team``."""
        team = BoxScoreLoader.unwrap(raw["team"])
        minutes = BoxScoreLoader.parse_number(raw["minutes"])
        fg_made, fg_att, fg_pct = BoxScoreLoader.parse_shooting(raw["field_goal_percentage"])
        tp_made, tp_att, tp_pct = BoxScoreLoader.parse_shooting(raw["three_point_percentage"])
        ft_made, ft_att, ft_pct = BoxScoreLoader.parse_shooting(raw["free_throw_percentage"])
        counting = {}
        for field in BoxScoreLoader.COUNTING_FIELDS:
            parsed = BoxScoreLoader.parse_number(raw[field])
            counting[field] = 0 if parsed is None else int(parsed)
        plus_minus = BoxScoreLoader.parse_number(raw["plus_minus"])
        location = "home" if str(side).startswith("home") else "away"
        return {
            "game_id": int(BoxScoreLoader.parse_number(raw["game_id"])),
            "player": BoxScoreLoader.unwrap(raw["player"]),
            "team": team,
            "team_abbr": BoxScoreLoader.TEAM_ABBR.get(team, team),
            "side": location,
            "opponent": None,
            "minutes": None if minutes is None else int(minutes),
            "plus_minus": None if plus_minus is None else int(plus_minus),
            "starter": BoxScoreLoader.parse_bool(raw.get("Starter", False)),
            "fg_made": fg_made,
            "fg_att": fg_att,
            "fg_pct": fg_pct,
            "tp_made": tp_made,
            "tp_att": tp_att,
            "tp_pct": tp_pct,
            "ft_made": ft_made,
            "ft_att": ft_att,
            "ft_pct": ft_pct,
            **counting,
        }

    @staticmethod
    def load(path):
        """Flatten the nested file into player-game dicts, one per box-score line."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        rows = []
        for games in raw.values():
            for sides in games.values():
                for side in ("home_team", "away_team"):
                    for player in sides.get(side, []):
                        rows.append(BoxScoreLoader.parse_row(player, side))
        teams_by_game = defaultdict(dict)
        for row in rows:
            teams_by_game[row["game_id"]][row["side"]] = row["team"]
        for row in rows:
            sides = teams_by_game[row["game_id"]]
            other = "away" if row["side"] == "home" else "home"
            row["opponent"] = sides.get(other)
        return rows

    @staticmethod
    def leaderboard(rows):
        """Per-game averages. Shooting percentages are total makes / total attempts."""
        grouped = defaultdict(list)
        for row in rows:
            grouped[(row["player"], row["team_abbr"])].append(row)
        board = []
        for (player, _team), games in grouped.items():
            played = len(games)
            made_attempts = {}
            for label, made_key, att_key in (
                ("FG%", "fg_made", "fg_att"),
                ("3P%", "tp_made", "tp_att"),
                ("FT%", "ft_made", "ft_att"),
            ):
                made = sum(game[made_key] for game in games)
                attempted = sum(game[att_key] for game in games)
                made_attempts[label] = None if attempted == 0 else 100.0 * made / attempted
            sample = games[0]
            board.append(
                {
                    "Player": player,
                    "Team": sample["team_abbr"],
                    "G": played,
                    "PPG": sum(game["points"] for game in games) / played,
                    "RPG": sum(game["rebounds"] for game in games) / played,
                    "APG": sum(game["assists"] for game in games) / played,
                    "SPG": sum(game["steals"] for game in games) / played,
                    "BPG": sum(game["blocks"] for game in games) / played,
                    **made_attempts,
                }
            )
        return board

    @staticmethod
    def game_summaries(rows):
        """One record per game with both teams and their point totals."""
        games = {}
        for row in rows:
            summary = games.setdefault(
                row["game_id"],
                {
                    "game_id": row["game_id"],
                    "home_team": None,
                    "away_team": None,
                    "home_abbr": None,
                    "away_abbr": None,
                    "home_points": 0,
                    "away_points": 0,
                },
            )
            prefix = row["side"]
            summary[f"{prefix}_team"] = row["team"]
            summary[f"{prefix}_abbr"] = row["team_abbr"]
            summary[f"{prefix}_points"] += row["points"]
        return [games[game_id] for game_id in sorted(games)]
