"""Tests for the database layer."""

import tempfile
from pathlib import Path

from chess_db.database import ChessDatabase
from chess_db.parser import ChessGame, parse_pgn


SAMPLE_PGN = """
[Event "Test Tournament"]
[Site "Online"]
[Date "2024.06.01"]
[Round "1"]
[White "Alpha"]
[Black "Beta"]
[Result "1-0"]
[ECO "C50"]
[WhiteElo "2000"]
[BlackElo "1900"]
[Opening "Italian Game"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 1-0

[Event "Test Tournament"]
[Site "Online"]
[Date "2024.06.02"]
[Round "2"]
[White "Beta"]
[Black "Gamma"]
[Result "0-1"]
[ECO "D30"]
[WhiteElo "1900"]
[BlackElo "1850"]
[Opening "Queen's Gambit Declined"]

1. d4 d5 2. c4 e6 0-1

[Event "Test Tournament"]
[Site "Online"]
[Date "2024.06.03"]
[Round "3"]
[White "Alpha"]
[Black "Gamma"]
[Result "1/2-1/2"]
[ECO "C50"]
[WhiteElo "2010"]
[BlackElo "1860"]
[Opening "Italian Game"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 1/2-1/2
"""


def _make_db():
    """Create a temp database and populate it."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = ChessDatabase(tmp.name)
    games = parse_pgn(SAMPLE_PGN)
    db.import_games(games, source_file="test.pgn")
    return db, tmp.name


def test_import_and_count():
    db, path = _make_db()
    assert db.count() == 3
    db.close()
    Path(path).unlink()


def test_get_game():
    db, path = _make_db()
    g = db.get_game(1)
    assert g is not None
    assert g["white"] == "Alpha"
    assert g["black"] == "Beta"
    assert g["white_elo"] == 2000
    db.close()
    Path(path).unlink()


def test_search_by_player():
    db, path = _make_db()
    results = db.search(player="Alpha")
    assert len(results) == 2
    db.close()
    Path(path).unlink()


def test_search_by_eco():
    db, path = _make_db()
    results = db.search(eco="C50")
    assert len(results) == 2
    results = db.search(eco="D30")
    assert len(results) == 1
    db.close()
    Path(path).unlink()


def test_search_by_result():
    db, path = _make_db()
    results = db.search(result="1-0")
    assert len(results) == 1
    results = db.search(result="1/2-1/2")
    assert len(results) == 1
    db.close()
    Path(path).unlink()


def test_players():
    db, path = _make_db()
    players = db.players()
    names = [p["name"] for p in players]
    assert "Alpha" in names
    assert "Beta" in names
    # Alpha played 2 games
    alpha = next(p for p in players if p["name"] == "Alpha")
    assert alpha["games"] == 2
    db.close()
    Path(path).unlink()


def test_openings():
    db, path = _make_db()
    openings = db.openings()
    eco_codes = [o["eco"] for o in openings]
    assert "C50" in eco_codes
    c50 = next(o for o in openings if o["eco"] == "C50")
    assert c50["games"] == 2
    db.close()
    Path(path).unlink()


def test_player_stats():
    db, path = _make_db()
    stats = db.player_stats("Alpha")
    assert stats["games"] == 2
    assert stats["wins"] == 1
    assert stats["draws"] == 1
    assert stats["losses"] == 0
    assert stats["peak_elo"] == 2010
    db.close()
    Path(path).unlink()


def test_delete_game():
    db, path = _make_db()
    assert db.count() == 3
    assert db.delete_game(1) is True
    assert db.count() == 2
    assert db.get_game(1) is None
    assert db.delete_game(999) is False
    db.close()
    Path(path).unlink()


def test_export_pgn():
    db, path = _make_db()
    pgn = db.export_pgn()
    assert '[White "Alpha"]' in pgn
    assert '[White "Beta"]' in pgn
    # Export specific IDs
    pgn_one = db.export_pgn([1])
    assert '[White "Alpha"]' in pgn_one
    assert '[White "Beta"]' not in pgn_one
    db.close()
    Path(path).unlink()


def test_context_manager():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    with ChessDatabase(tmp.name) as db:
        assert db.count() == 0
    Path(tmp.name).unlink()
