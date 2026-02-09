"""Tests for the web interface."""

import tempfile
from pathlib import Path

from chess_db.database import ChessDatabase
from chess_db.parser import parse_pgn
from chess_db.web.app import create_app

SAMPLE_PGN = """
[Event "Test"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]
[ECO "C50"]
[Opening "Italian Game"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 1-0
"""


def _make_app():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = ChessDatabase(tmp.name)
    games = parse_pgn(SAMPLE_PGN)
    db.import_games(games, source_file="test.pgn")
    db.close()
    app = create_app(tmp.name)
    app.config["TESTING"] = True
    return app, tmp.name


def test_index():
    app, path = _make_app()
    with app.test_client() as c:
        resp = c.get("/")
        assert resp.status_code == 200
        assert b"Dashboard" in resp.data
        assert b"1" in resp.data  # total games
    Path(path).unlink()


def test_games_list():
    app, path = _make_app()
    with app.test_client() as c:
        resp = c.get("/games")
        assert resp.status_code == 200
        assert b"Alice" in resp.data
        assert b"Bob" in resp.data
    Path(path).unlink()


def test_games_search():
    app, path = _make_app()
    with app.test_client() as c:
        resp = c.get("/games?player=Alice")
        assert resp.status_code == 200
        assert b"Alice" in resp.data
    Path(path).unlink()


def test_game_detail():
    app, path = _make_app()
    with app.test_client() as c:
        resp = c.get("/game/1")
        assert resp.status_code == 200
        assert b"Alice" in resp.data
        assert b"Bob" in resp.data
    Path(path).unlink()


def test_game_not_found():
    app, path = _make_app()
    with app.test_client() as c:
        resp = c.get("/game/999")
        assert resp.status_code == 404
    Path(path).unlink()


def test_report_no_analysis():
    app, path = _make_app()
    with app.test_client() as c:
        resp = c.get("/report/Alice")
        assert resp.status_code == 200
        assert b"No analyzed games" in resp.data
    Path(path).unlink()


def test_blunders_no_analysis():
    app, path = _make_app()
    with app.test_client() as c:
        resp = c.get("/blunders/Alice")
        assert resp.status_code == 200
        assert b"No blunders" in resp.data
    Path(path).unlink()
