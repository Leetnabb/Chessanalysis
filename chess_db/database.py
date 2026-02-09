"""SQLite database layer for the chess game database."""

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
