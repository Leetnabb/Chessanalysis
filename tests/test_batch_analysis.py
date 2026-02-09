"""Tests for batch analysis, report, and blunders functionality."""

import shutil
import tempfile
from pathlib import Path

import pytest

from chess_db.database import ChessDatabase
from chess_db.parser import parse_pgn
from chess_db.engine import StockfishAnalyzer

# Skip all tests if Stockfish is not installed
pytestmark = pytest.mark.skipif(
    not shutil.which("stockfish") and not shutil.which("/usr/games/stockfish"),
    reason="Stockfish not installed",
)

SAMPLE_PGN = """
[Event "Test Tournament"]
[Site "Online"]
[Date "2024.06.01"]
[White "TestPlayer"]
[Black "Opponent1"]
[Result "1-0"]
[ECO "C50"]
[Opening "Italian Game"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 1-0

[Event "Test Tournament"]
[Site "Online"]
[Date "2024.06.02"]
[White "Opponent2"]
[Black "TestPlayer"]
[Result "0-1"]
[ECO "D30"]
[Opening "Queen's Gambit"]

1. d4 d5 2. c4 e6 0-1
"""


def _make_db_with_games():
    """Create a temp database with sample games."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db = ChessDatabase(tmp.name)
    games = parse_pgn(SAMPLE_PGN)
    db.import_games(games, source_file="test.pgn")
    return db, tmp.name


def test_schema_has_analysis_tables():
    db, path = _make_db_with_games()
    # Check that the new tables exist
    tables = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    table_names = [t[0] for t in tables]
    assert "game_analysis" in table_names
    assert "move_analysis" in table_names
    db.close()
    Path(path).unlink()


def test_is_analyzed_false_initially():
    db, path = _make_db_with_games()
    assert db.is_analyzed(1) is False
    assert db.is_analyzed(2) is False
    db.close()
    Path(path).unlink()


def test_unanalyzed_game_ids():
    db, path = _make_db_with_games()
    ids = db.unanalyzed_game_ids()
    assert len(ids) == 2
    assert 1 in ids
    assert 2 in ids

    # Filter by player
    ids_tp = db.unanalyzed_game_ids(player="TestPlayer")
    assert len(ids_tp) == 2

    ids_opp = db.unanalyzed_game_ids(player="Opponent1")
    assert len(ids_opp) == 1

    db.close()
    Path(path).unlink()


def test_save_and_retrieve_analysis():
    db, path = _make_db_with_games()
    game = db.get_game(1)

    with StockfishAnalyzer() as analyzer:
        results = analyzer.analyze_game(game["moves"], depth=8)

    db.save_analysis(1, 8, results)

    assert db.is_analyzed(1) is True
    assert db.is_analyzed(2) is False

    # Summary
    summary = db.get_analysis_summary(1)
    assert summary is not None
    assert summary["depth"] == 8
    assert summary["white_accuracy"] is not None
    assert summary["black_accuracy"] is not None

    # Move data
    moves = db.get_move_analysis(1)
    assert len(moves) == len(results)
    assert moves[0]["ply"] == 1
    assert moves[0]["move_san"] == "e4"

    # Analyzed count
    assert db.analyzed_count() == 1

    db.close()
    Path(path).unlink()


def test_save_analysis_overwrites():
    """Re-analyzing a game should replace old data."""
    db, path = _make_db_with_games()
    game = db.get_game(1)

    with StockfishAnalyzer() as analyzer:
        results = analyzer.analyze_game(game["moves"], depth=6)

    db.save_analysis(1, 6, results)
    first_summary = db.get_analysis_summary(1)

    # Re-analyze at different depth
    with StockfishAnalyzer() as analyzer:
        results2 = analyzer.analyze_game(game["moves"], depth=8)

    db.save_analysis(1, 8, results2)
    second_summary = db.get_analysis_summary(1)

    assert first_summary["depth"] == 6
    assert second_summary["depth"] == 8
    # Should still be just 1 analyzed game
    assert db.analyzed_count() == 1

    db.close()
    Path(path).unlink()


def test_unanalyzed_excludes_done():
    db, path = _make_db_with_games()
    game = db.get_game(1)

    with StockfishAnalyzer() as analyzer:
        results = analyzer.analyze_game(game["moves"], depth=6)

    db.save_analysis(1, 6, results)

    ids = db.unanalyzed_game_ids()
    assert 1 not in ids
    assert 2 in ids
    assert len(ids) == 1

    db.close()
    Path(path).unlink()


def test_get_blunders():
    db, path = _make_db_with_games()

    # Analyze both games
    with StockfishAnalyzer() as analyzer:
        for gid in [1, 2]:
            game = db.get_game(gid)
            results = analyzer.analyze_game(game["moves"], depth=8)
            db.save_analysis(gid, 8, results)

    # Get blunders - might be empty if all moves are good at this depth
    blunders = db.get_blunders("TestPlayer", limit=10)
    # Just verify it returns a list with the right structure
    assert isinstance(blunders, list)
    for b in blunders:
        assert "move_san" in b
        assert "best_move_san" in b
        assert "classification" in b
        assert b["classification"] in ("blunder", "mistake")

    db.close()
    Path(path).unlink()


def test_get_player_report():
    db, path = _make_db_with_games()

    # Analyze both games
    with StockfishAnalyzer() as analyzer:
        for gid in [1, 2]:
            game = db.get_game(gid)
            results = analyzer.analyze_game(game["moves"], depth=8)
            db.save_analysis(gid, 8, results)

    report = db.get_player_report("TestPlayer")
    assert report is not None
    assert report["analyzed_games"] == 2
    assert report["avg_accuracy"] is not None
    assert report["total_blunders"] >= 0
    assert "phase_errors" in report
    assert "opening" in report["phase_errors"]
    assert "middlegame" in report["phase_errors"]
    assert "endgame" in report["phase_errors"]
    assert "weakest_openings" in report
    assert "strongest_openings" in report

    db.close()
    Path(path).unlink()


def test_report_none_for_unknown_player():
    db, path = _make_db_with_games()
    report = db.get_player_report("UnknownPlayer")
    assert report is None
    db.close()
    Path(path).unlink()
