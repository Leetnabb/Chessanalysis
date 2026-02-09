"""Tests for the PGN parser."""

import tempfile
from pathlib import Path

from chess_db.parser import ChessGame, parse_pgn, parse_pgn_file


SIMPLE_PGN = """
[Event "Test Game"]
[Site "Internet"]
[Date "2024.01.15"]
[Round "1"]
[White "Player1"]
[Black "Player2"]
[Result "1-0"]
[ECO "C50"]
[WhiteElo "1500"]
[BlackElo "1400"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. d3 d6 5. O-O Nf6 1-0
"""

MULTI_GAME_PGN = """
[Event "Game 1"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 e5 2. Nf3 1-0

[Event "Game 2"]
[White "Charlie"]
[Black "Dave"]
[Result "0-1"]

1. d4 d5 2. c4 0-1
"""

GAME_WITH_COMMENTS = """
[Event "Annotated"]
[White "A"]
[Black "B"]
[Result "*"]

1. e4 {Best by test} e5 2. Nf3 Nc6 (2... d6 {Philidor}) 3. Bb5 *
"""


def test_parse_single_game():
    games = parse_pgn(SIMPLE_PGN)
    assert len(games) == 1
    g = games[0]
    assert g.event == "Test Game"
    assert g.site == "Internet"
    assert g.date == "2024.01.15"
    assert g.white == "Player1"
    assert g.black == "Player2"
    assert g.result == "1-0"
    assert g.eco == "C50"
    assert g.white_elo == 1500
    assert g.black_elo == 1400


def test_parse_multiple_games():
    games = parse_pgn(MULTI_GAME_PGN)
    assert len(games) == 2
    assert games[0].white == "Alice"
    assert games[0].result == "1-0"
    assert games[1].white == "Charlie"
    assert games[1].result == "0-1"


def test_move_list():
    games = parse_pgn(SIMPLE_PGN)
    moves = games[0].move_list()
    assert moves[0] == "e4"
    assert moves[1] == "e5"
    assert "1-0" not in moves


def test_move_list_with_comments():
    games = parse_pgn(GAME_WITH_COMMENTS)
    moves = games[0].move_list()
    assert "Best" not in " ".join(moves)
    assert "Philidor" not in " ".join(moves)
    assert moves[0] == "e4"


def test_total_moves():
    games = parse_pgn(SIMPLE_PGN)
    g = games[0]
    assert g.total_moves() == 10  # 5 full moves = 10 half-moves
    assert g.total_full_moves() == 5


def test_parse_pgn_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pgn", delete=False) as f:
        f.write(SIMPLE_PGN)
        f.flush()
        games = parse_pgn_file(f.name)
        assert len(games) == 1
        assert games[0].white == "Player1"
    Path(f.name).unlink()


def test_default_values():
    g = ChessGame()
    assert g.event == "?"
    assert g.white_elo is None
    assert g.moves == ""
    assert g.move_list() == []
    assert g.total_moves() == 0
