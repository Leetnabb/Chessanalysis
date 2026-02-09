"""Tests for the Stockfish engine analysis module."""

import shutil
import pytest

from chess_db.engine import (
    StockfishAnalyzer,
    find_stockfish,
    format_score,
    format_eval_bar,
)

# Skip all tests if Stockfish is not installed
pytestmark = pytest.mark.skipif(
    not shutil.which("stockfish") and not shutil.which("/usr/games/stockfish"),
    reason="Stockfish not installed",
)

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
MATE_IN_ONE_FEN = "6k1/5ppp/8/8/8/8/8/4R1K1 w - - 0 1"  # Re1 can deliver mate patterns
SCHOLARS_MATE_FEN = "r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4"

SHORT_GAME_MOVES = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5"


def test_find_stockfish():
    path = find_stockfish()
    assert "stockfish" in path


def test_analyzer_context_manager():
    with StockfishAnalyzer() as analyzer:
        # Engine is lazily initialized, trigger it
        analyzer.analyze_fen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", depth=5)
        assert analyzer._engine is not None
    assert analyzer._engine is None


def test_analyze_fen_starting_position():
    with StockfishAnalyzer() as analyzer:
        results = analyzer.analyze_fen(STARTING_FEN, depth=10, multipv=1)
        assert len(results) == 1
        r = results[0]
        assert r["score_cp"] is not None or r["score_mate"] is not None
        assert len(r["pv"]) > 0
        assert len(r["pv_san"]) > 0
        assert r["depth"] >= 10


def test_analyze_fen_multipv():
    with StockfishAnalyzer() as analyzer:
        results = analyzer.analyze_fen(STARTING_FEN, depth=10, multipv=3)
        assert len(results) == 3
        for r in results:
            assert "score_cp" in r
            assert "pv_san" in r


def test_analyze_fen_mate_position():
    """Scholars mate - Black is mated (Qxf7#)."""
    with StockfishAnalyzer() as analyzer:
        results = analyzer.analyze_fen(SCHOLARS_MATE_FEN, depth=10, multipv=1)
        r = results[0]
        # Black is mated, score from white's perspective should be very high or mate
        assert r["score_mate"] is not None or (r["score_cp"] is not None and r["score_cp"] > 900)


def test_analyze_game():
    with StockfishAnalyzer() as analyzer:
        results = analyzer.analyze_game(SHORT_GAME_MOVES, depth=10)
        assert len(results) == 6  # 3 full moves = 6 half-moves
        for r in results:
            assert "ply" in r
            assert "move_san" in r
            assert "score_cp" in r or "score_mate" in r
            assert r["classification"] in (
                "best", "excellent", "good", "inaccuracy", "mistake", "blunder"
            )
        # Check ply ordering
        assert results[0]["ply"] == 1
        assert results[0]["side"] == "white"
        assert results[0]["move_san"] == "e4"
        assert results[1]["ply"] == 2
        assert results[1]["side"] == "black"


def test_analyze_game_move_range():
    with StockfishAnalyzer() as analyzer:
        # Only analyze moves 2-3 (full move numbers)
        results = analyzer.analyze_game(SHORT_GAME_MOVES, depth=10, move_range=(3, 6))
        assert len(results) == 4  # plies 3,4,5,6
        assert results[0]["ply"] == 3


def test_analyze_game_empty():
    with StockfishAnalyzer() as analyzer:
        results = analyzer.analyze_game("", depth=10)
        assert results == []


# ── Format helpers ───────────────────────────────────────────────────


def test_format_score_centipawns():
    assert format_score(50, None) == "+0.50"
    assert format_score(-120, None) == "-1.20"
    assert format_score(0, None) == "+0.00"


def test_format_score_mate():
    assert format_score(None, 3) == "#+3"
    assert format_score(None, -2) == "#-2"


def test_format_score_unknown():
    assert format_score(None, None) == "?"


def test_format_eval_bar():
    bar = format_eval_bar(0, None)
    assert len(bar) > 0
    # Equal position should have roughly equal W and B
    inner = bar.strip("[]")
    assert abs(inner.count("W") - inner.count("B")) <= 2

    # Winning for white
    bar_w = format_eval_bar(500, None)
    inner_w = bar_w.strip("[]")
    assert inner_w.count("W") > inner_w.count("B")

    # Mate for white
    bar_m = format_eval_bar(None, 3)
    inner_m = bar_m.strip("[]")
    assert inner_m.count("B") == 0
