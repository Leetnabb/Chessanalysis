"""SQLite database layer for the chess game database."""

import json
import sqlite3
from pathlib import Path

from .parser import ChessGame

DEFAULT_DB_PATH = Path("chess_games.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event       TEXT NOT NULL DEFAULT '?',
    site        TEXT NOT NULL DEFAULT '?',
    date        TEXT NOT NULL DEFAULT '????.??.??',
    round       TEXT NOT NULL DEFAULT '?',
    white       TEXT NOT NULL DEFAULT '?',
    black       TEXT NOT NULL DEFAULT '?',
    result      TEXT NOT NULL DEFAULT '*',
    white_elo   INTEGER,
    black_elo   INTEGER,
    eco         TEXT DEFAULT '',
    opening     TEXT DEFAULT '',
    time_control TEXT DEFAULT '',
    termination TEXT DEFAULT '',
    variant     TEXT DEFAULT 'Standard',
    moves       TEXT NOT NULL DEFAULT '',
    total_plies INTEGER DEFAULT 0,
    source_file TEXT DEFAULT '',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_white ON games(white);
CREATE INDEX IF NOT EXISTS idx_black ON games(black);
CREATE INDEX IF NOT EXISTS idx_date ON games(date);
CREATE INDEX IF NOT EXISTS idx_eco ON games(eco);
CREATE INDEX IF NOT EXISTS idx_result ON games(result);
CREATE INDEX IF NOT EXISTS idx_event ON games(event);

CREATE TABLE IF NOT EXISTS move_analysis (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    ply         INTEGER NOT NULL,
    move_number INTEGER NOT NULL,
    side        TEXT NOT NULL,
    move_san    TEXT NOT NULL,
    move_uci    TEXT NOT NULL,
    score_cp    INTEGER,
    score_mate  INTEGER,
    best_move_san TEXT,
    best_move_uci TEXT,
    best_score_cp INTEGER,
    best_score_mate INTEGER,
    classification TEXT NOT NULL,
    error_type  TEXT DEFAULT '',
    tactics_missed TEXT DEFAULT '',
    clock_seconds REAL,
    UNIQUE(game_id, ply)
);

CREATE TABLE IF NOT EXISTS game_analysis (
    game_id         INTEGER PRIMARY KEY REFERENCES games(id) ON DELETE CASCADE,
    depth           INTEGER NOT NULL,
    white_accuracy  REAL,
    black_accuracy  REAL,
    white_blunders  INTEGER DEFAULT 0,
    white_mistakes  INTEGER DEFAULT 0,
    white_inaccuracies INTEGER DEFAULT 0,
    black_blunders  INTEGER DEFAULT 0,
    black_mistakes  INTEGER DEFAULT 0,
    black_inaccuracies INTEGER DEFAULT 0,
    analyzed_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ma_game ON move_analysis(game_id);
CREATE INDEX IF NOT EXISTS idx_ma_class ON move_analysis(classification);
CREATE INDEX IF NOT EXISTS idx_ma_side ON move_analysis(side);
"""


class ChessDatabase:
    """SQLite-backed chess game database."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA)
        # Migrate: add new columns if they don't exist yet
        try:
            self.conn.execute("SELECT error_type FROM move_analysis LIMIT 1")
        except sqlite3.OperationalError:
            self.conn.execute("ALTER TABLE move_analysis ADD COLUMN error_type TEXT DEFAULT ''")
            self.conn.execute("ALTER TABLE move_analysis ADD COLUMN tactics_missed TEXT DEFAULT ''")
            self.conn.execute("ALTER TABLE move_analysis ADD COLUMN clock_seconds REAL")
        self.conn.commit()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ── Import ────────────────────────────────────────────────────────

    def import_game(self, game: ChessGame, source_file: str = "") -> int:
        """Import a single game into the database. Returns the new row id."""
        cur = self.conn.execute(
            """INSERT INTO games
               (event, site, date, round, white, black, result,
                white_elo, black_elo, eco, opening, time_control,
                termination, variant, moves, total_plies, source_file)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                game.event,
                game.site,
                game.date,
                game.round,
                game.white,
                game.black,
                game.result,
                game.white_elo,
                game.black_elo,
                game.eco,
                game.opening,
                game.time_control,
                game.termination,
                game.variant,
                game.moves,
                game.total_moves(),
                source_file,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def import_games(self, games: list[ChessGame], source_file: str = "") -> int:
        """Import multiple games. Returns the number of games imported."""
        count = 0
        for game in games:
            self.import_game(game, source_file)
            count += 1
        return count

    # ── Queries ───────────────────────────────────────────────────────

    def count(self) -> int:
        """Return total number of games in the database."""
        row = self.conn.execute("SELECT COUNT(*) FROM games").fetchone()
        return row[0]

    def get_game(self, game_id: int) -> dict | None:
        """Get a single game by id."""
        row = self.conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
        return dict(row) if row else None

    def search(
        self,
        player: str | None = None,
        white: str | None = None,
        black: str | None = None,
        event: str | None = None,
        eco: str | None = None,
        result: str | None = None,
        opening: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        min_elo: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Search games with flexible filters. Returns list of game dicts."""
        conditions = []
        params: list = []

        if player:
            conditions.append("(white LIKE ? OR black LIKE ?)")
            params.extend([f"%{player}%", f"%{player}%"])
        if white:
            conditions.append("white LIKE ?")
            params.append(f"%{white}%")
        if black:
            conditions.append("black LIKE ?")
            params.append(f"%{black}%")
        if event:
            conditions.append("event LIKE ?")
            params.append(f"%{event}%")
        if eco:
            conditions.append("eco LIKE ?")
            params.append(f"{eco}%")
        if result:
            conditions.append("result = ?")
            params.append(result)
        if opening:
            conditions.append("opening LIKE ?")
            params.append(f"%{opening}%")
        if date_from:
            conditions.append("date >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("date <= ?")
            params.append(date_to)
        if min_elo:
            conditions.append("(white_elo >= ? OR black_elo >= ?)")
            params.extend([min_elo, min_elo])

        where = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM games WHERE {where} ORDER BY date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def players(self, limit: int = 50) -> list[dict]:
        """List players ranked by number of games played."""
        query = """
            SELECT name, COUNT(*) as games,
                   SUM(CASE WHEN won = 1 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN drawn = 1 THEN 1 ELSE 0 END) as draws,
                   SUM(CASE WHEN lost = 1 THEN 1 ELSE 0 END) as losses,
                   MAX(elo) as peak_elo
            FROM (
                SELECT white as name, white_elo as elo,
                       CASE WHEN result = '1-0' THEN 1 ELSE 0 END as won,
                       CASE WHEN result = '1/2-1/2' THEN 1 ELSE 0 END as drawn,
                       CASE WHEN result = '0-1' THEN 1 ELSE 0 END as lost
                FROM games
                UNION ALL
                SELECT black as name, black_elo as elo,
                       CASE WHEN result = '0-1' THEN 1 ELSE 0 END as won,
                       CASE WHEN result = '1/2-1/2' THEN 1 ELSE 0 END as drawn,
                       CASE WHEN result = '1-0' THEN 1 ELSE 0 END as lost
                FROM games
            )
            GROUP BY name
            ORDER BY games DESC
            LIMIT ?
        """
        rows = self.conn.execute(query, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def openings(self, limit: int = 50) -> list[dict]:
        """List most common openings (by ECO code)."""
        query = """
            SELECT eco, opening,
                   COUNT(*) as games,
                   SUM(CASE WHEN result = '1-0' THEN 1 ELSE 0 END) as white_wins,
                   SUM(CASE WHEN result = '0-1' THEN 1 ELSE 0 END) as black_wins,
                   SUM(CASE WHEN result = '1/2-1/2' THEN 1 ELSE 0 END) as draws
            FROM games
            WHERE eco != ''
            GROUP BY eco
            ORDER BY games DESC
            LIMIT ?
        """
        rows = self.conn.execute(query, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def player_stats(self, name: str) -> dict:
        """Get detailed statistics for a player."""
        games = self.search(player=name, limit=10000)
        total = len(games)
        if total == 0:
            return {"player": name, "games": 0}

        wins = draws = losses = 0
        elos = []
        opponents = set()
        eco_counts: dict[str, int] = {}

        for g in games:
            is_white = name.lower() in g["white"].lower()
            is_black = name.lower() in g["black"].lower()

            if is_white:
                opponents.add(g["black"])
                if g["white_elo"]:
                    elos.append(g["white_elo"])
            if is_black:
                opponents.add(g["white"])
                if g["black_elo"]:
                    elos.append(g["black_elo"])

            if g["result"] == "1-0" and is_white:
                wins += 1
            elif g["result"] == "0-1" and is_black:
                wins += 1
            elif g["result"] == "1/2-1/2":
                draws += 1
            elif g["result"] != "*":
                losses += 1

            if g["eco"]:
                eco_counts[g["eco"]] = eco_counts.get(g["eco"], 0) + 1

        top_openings = sorted(eco_counts.items(), key=lambda x: -x[1])[:5]

        return {
            "player": name,
            "games": total,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "win_rate": round(wins / total * 100, 1) if total else 0,
            "peak_elo": max(elos) if elos else None,
            "unique_opponents": len(opponents),
            "top_openings": top_openings,
        }

    def delete_game(self, game_id: int) -> bool:
        """Delete a game by id. Returns True if a row was deleted."""
        cur = self.conn.execute("DELETE FROM games WHERE id = ?", (game_id,))
        self.conn.commit()
        return cur.rowcount > 0

    # ── Analysis storage ─────────────────────────────────────────────

    def is_analyzed(self, game_id: int) -> bool:
        """Check if a game has already been analyzed."""
        row = self.conn.execute(
            "SELECT 1 FROM game_analysis WHERE game_id = ?", (game_id,)
        ).fetchone()
        return row is not None

    def unanalyzed_game_ids(self, player: str | None = None, limit: int = 0) -> list[int]:
        """Return IDs of games not yet analyzed, optionally filtered by player."""
        conditions = ["g.id NOT IN (SELECT game_id FROM game_analysis)"]
        params: list = []
        if player:
            conditions.append("(g.white LIKE ? OR g.black LIKE ?)")
            params.extend([f"%{player}%", f"%{player}%"])
        where = " AND ".join(conditions)
        query = f"SELECT g.id FROM games g WHERE {where} ORDER BY g.date DESC"
        if limit > 0:
            query += " LIMIT ?"
            params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [r[0] for r in rows]

    def save_analysis(self, game_id: int, depth: int, move_results: list[dict]):
        """Save analysis results for a game (move-by-move + summary)."""
        # Clear any previous analysis
        self.conn.execute("DELETE FROM move_analysis WHERE game_id = ?", (game_id,))
        self.conn.execute("DELETE FROM game_analysis WHERE game_id = ?", (game_id,))

        for r in move_results:
            tactics_json = json.dumps(r.get("tactics_missed", []))
            self.conn.execute(
                """INSERT INTO move_analysis
                   (game_id, ply, move_number, side, move_san, move_uci,
                    score_cp, score_mate, best_move_san, best_move_uci,
                    best_score_cp, best_score_mate, classification,
                    error_type, tactics_missed, clock_seconds)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    game_id, r["ply"], r["move_number"], r["side"],
                    r["move_san"], r["move_uci"], r["score_cp"], r["score_mate"],
                    r["best_move_san"], r["best_move_uci"],
                    r["best_score_cp"], r["best_score_mate"], r["classification"],
                    r.get("error_type", ""), tactics_json, r.get("clock_seconds"),
                ),
            )

        # Compute summary
        counts = {"white": {}, "black": {}}
        totals = {"white": 0, "black": 0}
        for r in move_results:
            side = r["side"]
            cls = r["classification"]
            counts[side][cls] = counts[side].get(cls, 0) + 1
            totals[side] += 1

        def accuracy(side_counts, total):
            if total == 0:
                return None
            good = (side_counts.get("best", 0) + side_counts.get("excellent", 0)
                    + side_counts.get("good", 0) + side_counts.get("book", 0))
            return round(good / total * 100, 1)

        self.conn.execute(
            """INSERT INTO game_analysis
               (game_id, depth, white_accuracy, black_accuracy,
                white_blunders, white_mistakes, white_inaccuracies,
                black_blunders, black_mistakes, black_inaccuracies)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                game_id, depth,
                accuracy(counts["white"], totals["white"]),
                accuracy(counts["black"], totals["black"]),
                counts["white"].get("blunder", 0),
                counts["white"].get("mistake", 0),
                counts["white"].get("inaccuracy", 0),
                counts["black"].get("blunder", 0),
                counts["black"].get("mistake", 0),
                counts["black"].get("inaccuracy", 0),
            ),
        )
        self.conn.commit()

    def get_analysis_summary(self, game_id: int) -> dict | None:
        """Get the analysis summary for a game."""
        row = self.conn.execute(
            "SELECT * FROM game_analysis WHERE game_id = ?", (game_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_move_analysis(self, game_id: int) -> list[dict]:
        """Get all move analysis rows for a game."""
        rows = self.conn.execute(
            "SELECT * FROM move_analysis WHERE game_id = ? ORDER BY ply", (game_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def analyzed_count(self) -> int:
        """Return how many games have been analyzed."""
        row = self.conn.execute("SELECT COUNT(*) FROM game_analysis").fetchone()
        return row[0]

    def get_blunders(
        self, player: str, limit: int = 20, classifications: tuple = ("blunder", "mistake")
    ) -> list[dict]:
        """Get worst moves for a player across all analyzed games."""
        placeholders = ",".join("?" * len(classifications))
        query = f"""
            SELECT ma.*, g.white, g.black, g.date, g.eco, g.opening, g.result
            FROM move_analysis ma
            JOIN games g ON g.id = ma.game_id
            WHERE ma.classification IN ({placeholders})
              AND (
                (ma.side = 'white' AND g.white LIKE ?)
                OR (ma.side = 'black' AND g.black LIKE ?)
              )
            ORDER BY
                CASE ma.classification
                    WHEN 'blunder' THEN 0
                    WHEN 'mistake' THEN 1
                    WHEN 'inaccuracy' THEN 2
                    ELSE 3
                END,
                ABS(COALESCE(ma.best_score_cp, 0) - COALESCE(ma.score_cp, 0)) DESC
            LIMIT ?
        """
        params = list(classifications) + [f"%{player}%", f"%{player}%", limit]
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def get_player_report(self, player: str) -> dict | None:
        """Generate a comprehensive report for a player from analyzed games."""
        # Get all analyzed games for this player
        rows = self.conn.execute(
            """SELECT ga.*, g.white, g.black, g.eco, g.opening, g.result,
                      g.date, g.total_plies
               FROM game_analysis ga
               JOIN games g ON g.id = ga.game_id
               WHERE g.white LIKE ? OR g.black LIKE ?
               ORDER BY g.date DESC""",
            (f"%{player}%", f"%{player}%"),
        ).fetchall()
        if not rows:
            return None

        games = [dict(r) for r in rows]
        total = len(games)

        # Per-game accuracy for the player
        accuracies = []
        total_blunders = total_mistakes = total_inaccuracies = 0
        eco_stats: dict[str, dict] = {}  # eco -> {games, acc_sum, blunders, ...}

        # Phase analysis: opening (ply 1-20), middlegame (21-60), endgame (61+)
        phase_errors: dict[str, dict[str, int]] = {
            "opening": {"blunder": 0, "mistake": 0, "inaccuracy": 0, "total": 0},
            "middlegame": {"blunder": 0, "mistake": 0, "inaccuracy": 0, "total": 0},
            "endgame": {"blunder": 0, "mistake": 0, "inaccuracy": 0, "total": 0},
        }

        for g in games:
            is_white = player.lower() in g["white"].lower()
            acc = g["white_accuracy"] if is_white else g["black_accuracy"]
            if acc is not None:
                accuracies.append(acc)

            bl = g["white_blunders"] if is_white else g["black_blunders"]
            mi = g["white_mistakes"] if is_white else g["black_mistakes"]
            ina = g["white_inaccuracies"] if is_white else g["black_inaccuracies"]
            total_blunders += bl
            total_mistakes += mi
            total_inaccuracies += ina

            eco = g["eco"] or "?"
            if eco not in eco_stats:
                eco_stats[eco] = {"games": 0, "acc_sum": 0.0, "blunders": 0, "opening": g["opening"] or eco}
            eco_stats[eco]["games"] += 1
            if acc is not None:
                eco_stats[eco]["acc_sum"] += acc
            eco_stats[eco]["blunders"] += bl

            # Get move-level data for phase analysis
            side = "white" if is_white else "black"
            move_rows = self.conn.execute(
                """SELECT ply, classification FROM move_analysis
                   WHERE game_id = ? AND side = ?""",
                (g["game_id"], side),
            ).fetchall()
            for mr in move_rows:
                ply = mr[0]
                cls = mr[1]
                if ply <= 20:
                    phase = "opening"
                elif ply <= 60:
                    phase = "middlegame"
                else:
                    phase = "endgame"
                phase_errors[phase]["total"] += 1
                if cls in ("blunder", "mistake", "inaccuracy"):
                    phase_errors[phase][cls] += 1

        avg_accuracy = round(sum(accuracies) / len(accuracies), 1) if accuracies else None

        # Top worst openings by average accuracy
        opening_report = []
        for eco, s in eco_stats.items():
            if s["games"] >= 1:
                avg = round(s["acc_sum"] / s["games"], 1) if s["games"] > 0 else 0
                opening_report.append({
                    "eco": eco,
                    "opening": s["opening"],
                    "games": s["games"],
                    "avg_accuracy": avg,
                    "blunders": s["blunders"],
                })

        opening_report.sort(key=lambda x: x["avg_accuracy"])

        return {
            "player": player,
            "analyzed_games": total,
            "avg_accuracy": avg_accuracy,
            "total_blunders": total_blunders,
            "total_mistakes": total_mistakes,
            "total_inaccuracies": total_inaccuracies,
            "phase_errors": phase_errors,
            "weakest_openings": opening_report[:10],
            "strongest_openings": list(reversed(opening_report[-10:])),
        }

    def get_player_insights(self, player: str, recent_months: int = 24) -> dict:
        """Generate comprehensive improvement insights for a player.

        Returns detailed analysis including:
          - Accuracy trends over time
          - Error type breakdown (tactical/positional/strategic)
          - Missed tactics frequency
          - Phase weaknesses
          - Opening performance
          - Win patterns
        """
        # Get all analyzed games for this player, ordered by date
        rows = self.conn.execute(
            """SELECT ga.*, g.id as gid, g.white, g.black, g.eco, g.opening,
                      g.result, g.date, g.total_plies, g.time_control,
                      g.white_elo, g.black_elo
               FROM game_analysis ga
               JOIN games g ON g.id = ga.game_id
               WHERE g.white LIKE ? OR g.black LIKE ?
               ORDER BY g.date ASC""",
            (f"%{player}%", f"%{player}%"),
        ).fetchall()
        if not rows:
            return None

        games = [dict(r) for r in rows]

        # ── Accuracy trend ─────────────────────────────
        accuracy_trend = []
        for g in games:
            is_white = player.lower() in g["white"].lower()
            acc = g["white_accuracy"] if is_white else g["black_accuracy"]
            if acc is not None:
                accuracy_trend.append({
                    "date": g["date"],
                    "accuracy": acc,
                    "game_id": g["gid"],
                    "opponent": g["black"] if is_white else g["white"],
                    "result": g["result"],
                    "color": "white" if is_white else "black",
                })

        # ── Error type breakdown ───────────────────────
        error_types = {"tactical": 0, "positional": 0, "strategic": 0, "unknown": 0}
        tactics_missed = {}
        phase_errors = {
            "opening": {"total": 0, "errors": 0, "tactical": 0, "positional": 0},
            "middlegame": {"total": 0, "errors": 0, "tactical": 0, "positional": 0},
            "endgame": {"total": 0, "errors": 0, "tactical": 0, "positional": 0},
        }

        for g in games:
            is_white = player.lower() in g["white"].lower()
            side = "white" if is_white else "black"

            move_rows = self.conn.execute(
                """SELECT ply, classification, error_type, tactics_missed
                   FROM move_analysis WHERE game_id = ? AND side = ?""",
                (g["gid"], side),
            ).fetchall()

            for mr in move_rows:
                ply = mr[0]
                cls = mr[1]
                err_type = mr[2] or ""
                tactics_json = mr[3] or "[]"

                # Phase
                if ply <= 20:
                    phase = "opening"
                elif ply <= 60:
                    phase = "middlegame"
                else:
                    phase = "endgame"

                phase_errors[phase]["total"] += 1

                if cls in ("inaccuracy", "mistake", "blunder"):
                    phase_errors[phase]["errors"] += 1

                    if err_type:
                        error_types[err_type] = error_types.get(err_type, 0) + 1
                        if err_type == "tactical":
                            phase_errors[phase]["tactical"] += 1
                        elif err_type == "positional":
                            phase_errors[phase]["positional"] += 1

                    # Count missed tactics
                    try:
                        tactics = json.loads(tactics_json)
                        for t in tactics:
                            tactics_missed[t] = tactics_missed.get(t, 0) + 1
                    except (json.JSONDecodeError, TypeError):
                        pass

        # Sort missed tactics by frequency
        tactics_missed_sorted = sorted(tactics_missed.items(), key=lambda x: -x[1])

        # ── Opening performance ────────────────────────
        opening_stats = {}
        for g in games:
            is_white = player.lower() in g["white"].lower()
            eco = g["eco"] or "?"
            key = eco

            if key not in opening_stats:
                opening_stats[key] = {
                    "eco": eco, "opening": g["opening"] or eco,
                    "games": 0, "wins": 0, "draws": 0, "losses": 0,
                    "acc_sum": 0.0,
                }

            opening_stats[key]["games"] += 1
            acc = g["white_accuracy"] if is_white else g["black_accuracy"]
            if acc is not None:
                opening_stats[key]["acc_sum"] += acc

            result = g["result"]
            if (result == "1-0" and is_white) or (result == "0-1" and not is_white):
                opening_stats[key]["wins"] += 1
            elif result == "1/2-1/2":
                opening_stats[key]["draws"] += 1
            elif result != "*":
                opening_stats[key]["losses"] += 1

        opening_list = []
        for s in opening_stats.values():
            s["avg_accuracy"] = round(s["acc_sum"] / s["games"], 1) if s["games"] > 0 else 0
            s["win_rate"] = round(s["wins"] / s["games"] * 100, 1) if s["games"] > 0 else 0
            s["score"] = round((s["wins"] + s["draws"] * 0.5) / s["games"] * 100, 1) if s["games"] > 0 else 0
            del s["acc_sum"]
            opening_list.append(s)

        best_openings = sorted(opening_list, key=lambda x: (-x["score"], -x["games"]))
        worst_openings = sorted(opening_list, key=lambda x: (x["score"], -x["games"]))

        # ── Win/loss patterns ──────────────────────────
        total_games = len(games)
        wins = draws = losses = 0
        win_as_white = win_as_black = 0
        games_as_white = games_as_black = 0

        for g in games:
            is_white = player.lower() in g["white"].lower()
            if is_white:
                games_as_white += 1
            else:
                games_as_black += 1

            result = g["result"]
            if (result == "1-0" and is_white) or (result == "0-1" and not is_white):
                wins += 1
                if is_white:
                    win_as_white += 1
                else:
                    win_as_black += 1
            elif result == "1/2-1/2":
                draws += 1
            elif result != "*":
                losses += 1

        # ── Time control performance ───────────────────
        tc_stats = {}
        for g in games:
            tc = g["time_control"] or "?"
            # Categorize time control
            tc_cat = _categorize_time_control(tc)
            if tc_cat not in tc_stats:
                tc_stats[tc_cat] = {"games": 0, "wins": 0, "acc_sum": 0.0, "acc_count": 0}
            tc_stats[tc_cat]["games"] += 1
            is_white = player.lower() in g["white"].lower()
            result = g["result"]
            if (result == "1-0" and is_white) or (result == "0-1" and not is_white):
                tc_stats[tc_cat]["wins"] += 1
            acc = g["white_accuracy"] if is_white else g["black_accuracy"]
            if acc is not None:
                tc_stats[tc_cat]["acc_sum"] += acc
                tc_stats[tc_cat]["acc_count"] += 1

        tc_report = []
        for cat, s in tc_stats.items():
            tc_report.append({
                "category": cat,
                "games": s["games"],
                "win_rate": round(s["wins"] / s["games"] * 100, 1) if s["games"] > 0 else 0,
                "avg_accuracy": round(s["acc_sum"] / s["acc_count"], 1) if s["acc_count"] > 0 else None,
            })

        return {
            "player": player,
            "total_analyzed": total_games,
            "accuracy_trend": accuracy_trend,
            "error_types": error_types,
            "tactics_missed": tactics_missed_sorted,
            "phase_errors": phase_errors,
            "best_openings": [o for o in best_openings if o["games"] >= 2][:10],
            "worst_openings": [o for o in worst_openings if o["games"] >= 2][:10],
            "all_openings": sorted(opening_list, key=lambda x: -x["games"]),
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "games_as_white": games_as_white,
            "games_as_black": games_as_black,
            "win_as_white": win_as_white,
            "win_as_black": win_as_black,
            "time_control_stats": tc_report,
        }

    def export_pgn(self, game_ids: list[int] | None = None) -> str:
        """Export games as PGN text. If game_ids is None, export all."""
        if game_ids:
            placeholders = ",".join("?" * len(game_ids))
            rows = self.conn.execute(
                f"SELECT * FROM games WHERE id IN ({placeholders})", game_ids
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM games ORDER BY date").fetchall()

        parts = []
        for row in rows:
            g = dict(row)
            pgn = f'[Event "{g["event"]}"]\n'
            pgn += f'[Site "{g["site"]}"]\n'
            pgn += f'[Date "{g["date"]}"]\n'
            pgn += f'[Round "{g["round"]}"]\n'
            pgn += f'[White "{g["white"]}"]\n'
            pgn += f'[Black "{g["black"]}"]\n'
            pgn += f'[Result "{g["result"]}"]\n'
            if g["white_elo"]:
                pgn += f'[WhiteElo "{g["white_elo"]}"]\n'
            if g["black_elo"]:
                pgn += f'[BlackElo "{g["black_elo"]}"]\n'
            if g["eco"]:
                pgn += f'[ECO "{g["eco"]}"]\n'
            if g["opening"]:
                pgn += f'[Opening "{g["opening"]}"]\n'
            if g["time_control"]:
                pgn += f'[TimeControl "{g["time_control"]}"]\n'
            pgn += f"\n{g['moves']}\n"
            parts.append(pgn)

        return "\n".join(parts)


def _categorize_time_control(tc: str) -> str:
    """Categorize a time control string into bullet/blitz/rapid/classical."""
    if not tc or tc == "?" or tc == "-":
        return "Unknown"
    try:
        # Format: "base+increment" or "base"
        parts = tc.replace("+", "/").split("/")
        base = int(parts[0])
        inc = int(parts[1]) if len(parts) > 1 else 0
        total = base + 40 * inc  # Estimated game time
        if total < 180:
            return "Bullet"
        elif total < 600:
            return "Blitz"
        elif total < 1800:
            return "Rapid"
        else:
            return "Classical"
    except (ValueError, IndexError):
        return "Unknown"
