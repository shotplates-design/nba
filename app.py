"""Streamlit explorer for the NBA box scores in data/nba_box_scores.json."""

from pathlib import Path

import pandas as pd
import streamlit as st

from loader import BoxScoreLoader

DATA_PATH = Path(__file__).resolve().parent / "data" / "nba_box_scores.json"
STAT_COLUMNS = ["PPG", "RPG", "APG", "SPG", "BPG", "FG%", "3P%", "FT%", "G"]
TREND_STATS = {
    "Points": "points",
    "Rebounds": "rebounds",
    "Assists": "assists",
    "Steals": "steals",
    "Blocks": "blocks",
}


class Dashboard:
    """Three views over rows produced by BoxScoreLoader."""

    @staticmethod
    def format_signed(value):
        if value is None:
            return ""
        return f"{int(value):+d}"

    @staticmethod
    def shot_line(made, attempted):
        return f"{made}-{attempted}"

    @staticmethod
    def percentage(rate):
        if rate is None:
            return None
        return round(100.0 * rate, 1)

    @staticmethod
    def leaderboard_frame(rows):
        frame = pd.DataFrame(BoxScoreLoader.leaderboard(rows))
        for column in ("FG%", "3P%", "FT%", "PPG", "RPG", "APG", "SPG", "BPG"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame

    @staticmethod
    def game_log_frame(player_rows):
        records = []
        for row in sorted(player_rows, key=lambda item: item["game_id"]):
            where = "vs" if row["side"] == "home" else "@"
            records.append(
                {
                    "Game": row["game_id"],
                    "Opponent": f"{where} {row['opponent']}",
                    "MIN": "—" if row["minutes"] is None else row["minutes"],
                    "PTS": row["points"],
                    "REB": row["rebounds"],
                    "AST": row["assists"],
                    "STL": row["steals"],
                    "BLK": row["blocks"],
                    "FG": Dashboard.shot_line(row["fg_made"], row["fg_att"]),
                    "3P": Dashboard.shot_line(row["tp_made"], row["tp_att"]),
                    "FT": Dashboard.shot_line(row["ft_made"], row["ft_att"]),
                    "+/-": Dashboard.format_signed(row["plus_minus"]),
                }
            )
        return pd.DataFrame(records)

    @staticmethod
    def box_frame(side_rows):
        ordered = sorted(side_rows, key=lambda row: not row["starter"])
        records = []
        for row in ordered:
            records.append(
                {
                    "Player": row["player"],
                    "GS": "Y" if row["starter"] else "",
                    "MIN": "—" if row["minutes"] is None else row["minutes"],
                    "PTS": row["points"],
                    "REB": row["rebounds"],
                    "AST": row["assists"],
                    "STL": row["steals"],
                    "BLK": row["blocks"],
                    "FG": Dashboard.shot_line(row["fg_made"], row["fg_att"]),
                    "FG%": Dashboard.percentage(row["fg_pct"]),
                    "3P": Dashboard.shot_line(row["tp_made"], row["tp_att"]),
                    "FT": Dashboard.shot_line(row["ft_made"], row["ft_att"]),
                    "+/-": Dashboard.format_signed(row["plus_minus"]),
                }
            )
        return pd.DataFrame(records)

    @staticmethod
    def show_leaderboard(rows):
        st.caption(
            "Per-game averages. FG%, 3P%, and FT% are total makes divided by total attempts."
        )
        teams = ["All teams"] + sorted({row["team"] for row in rows})
        filter_col, sort_col, order_col = st.columns([2, 1, 1])
        with filter_col:
            team = st.selectbox("Team", teams, key="leaderboard_team")
        with sort_col:
            sort_by = st.selectbox("Sort by", STAT_COLUMNS, key="leaderboard_sort")
        with order_col:
            ascending = st.checkbox("Ascending", key="leaderboard_ascending")
        scoped = rows if team == "All teams" else [row for row in rows if row["team"] == team]
        frame = Dashboard.leaderboard_frame(scoped)
        frame = frame.sort_values(sort_by, ascending=ascending, na_position="last")
        st.dataframe(
            frame,
            hide_index=True,
            use_container_width=True,
            height=640,
            column_config={
                "G": st.column_config.NumberColumn(format="%d"),
                "PPG": st.column_config.NumberColumn(format="%.1f"),
                "RPG": st.column_config.NumberColumn(format="%.1f"),
                "APG": st.column_config.NumberColumn(format="%.1f"),
                "SPG": st.column_config.NumberColumn(format="%.1f"),
                "BPG": st.column_config.NumberColumn(format="%.1f"),
                "FG%": st.column_config.NumberColumn(format="%.1f"),
                "3P%": st.column_config.NumberColumn(format="%.1f"),
                "FT%": st.column_config.NumberColumn(format="%.1f"),
            },
        )

    @staticmethod
    def show_player(rows):
        board = BoxScoreLoader.leaderboard(rows)
        ranked = sorted(board, key=lambda item: (item["PPG"], item["G"]), reverse=True)
        names = sorted(item["Player"] for item in board)
        if "player_name" not in st.session_state:
            st.session_state["player_name"] = ranked[0]["Player"]
        player = st.selectbox("Player", names, key="player_name")
        record = next(item for item in board if item["Player"] == player)
        player_rows = [row for row in rows if row["player"] == player]
        team_name = player_rows[0]["team"]
        st.subheader(f"{player} · {team_name}")
        metrics = st.columns(9)
        labels = [
            ("G", f"{record['G']}"),
            ("PPG", f"{record['PPG']:.1f}"),
            ("RPG", f"{record['RPG']:.1f}"),
            ("APG", f"{record['APG']:.1f}"),
            ("SPG", f"{record['SPG']:.1f}"),
            ("BPG", f"{record['BPG']:.1f}"),
            ("FG%", "—" if record["FG%"] is None else f"{record['FG%']:.1f}"),
            ("3P%", "—" if record["3P%"] is None else f"{record['3P%']:.1f}"),
            ("FT%", "—" if record["FT%"] is None else f"{record['FT%']:.1f}"),
        ]
        for column, (label, value) in zip(metrics, labels):
            column.metric(label, value)

        chosen = st.multiselect(
            "Trend",
            list(TREND_STATS),
            default=["Points", "Rebounds", "Assists"],
            key="player_trend",
        )
        log = sorted(player_rows, key=lambda item: item["game_id"])
        if chosen:
            chart = pd.DataFrame(
                {label: [row[TREND_STATS[label]] for row in log] for label in chosen},
                index=pd.Index([row["game_id"] for row in log], name="Game"),
            )
            st.line_chart(chart, height=280)
        st.markdown("**Game log**")
        st.dataframe(
            Dashboard.game_log_frame(player_rows),
            hide_index=True,
            use_container_width=True,
        )

    @staticmethod
    def show_game(rows):
        summaries = BoxScoreLoader.game_summaries(rows)
        labels = {
            (
                f"Game {game['game_id']}: "
                f"{game['away_abbr']} {game['away_points']} @ "
                f"{game['home_abbr']} {game['home_points']}"
            ): game
            for game in summaries
        }
        label = st.selectbox("Game", list(labels), key="game_label")
        game = labels[label]
        away_col, home_col = st.columns(2)
        panels = (
            (away_col, "away", "Away"),
            (home_col, "home", "Home"),
        )
        for column, side, title in panels:
            with column:
                st.markdown(f"### {game[f'{side}_abbr']} · {title}")
                st.caption(game[f"{side}_team"])
                st.metric("Points", game[f"{side}_points"])
                side_rows = [
                    row for row in rows if row["game_id"] == game["game_id"] and row["side"] == side
                ]
                st.dataframe(
                    Dashboard.box_frame(side_rows),
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "FG%": st.column_config.NumberColumn(format="%.1f"),
                    },
                )


def main():
    st.set_page_config(page_title="NBA Box Scores", layout="wide")
    st.title("NBA Box Scores")
    rows = BoxScoreLoader.load(DATA_PATH)
    games = len({row["game_id"] for row in rows})
    players = len({row["player"] for row in rows})
    st.caption(f"{games} games · {players} players · {len(rows):,} player lines")
    page = st.sidebar.radio("View", ["Leaderboard", "Player", "Game"], key="page")
    if page == "Leaderboard":
        Dashboard.show_leaderboard(rows)
    elif page == "Player":
        Dashboard.show_player(rows)
    else:
        Dashboard.show_game(rows)


if __name__ == "__main__":
    main()
