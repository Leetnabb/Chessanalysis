"""Stockfish engine integration for position and game analysis."""

import shutil
import chess
import chess.engine
import chess.pgn
import io

from .openings import is_book_move
from .tactics import categorize_error


DEFAULT_STOCKFISH_PATH = "stockfish"
STOCKFISH_SEARCH_PATHS = [
    "stockfish",
    "/usr/games/stockfish",
    "/usr/local/bin/stockfish",
    "/usr/bin/stockfish",
]


def find_stockfish() -> str:
    """Locate the Stockfish binary on the system."""
    for path in STOCKFISH_SEARCH_PATHS:
        if shutil.which(path):
            return path
    raise FileNotFoundError(
        "Stockfish not found. Install it with: apt install stockfish (or brew install stockfish on macOS)"
    )


class StockfishAnalyzer:
    """Wrapper around the Stockfish engine for chess position analysis."""

    def __init__(self, stockfish_path: str | None = None, threads: int = 1, hash_mb: int = 64):
        self.path = stockfish_path or find_stockfish()
        self.threads = threads
        self.hash_mb = hash_mb
        self._engine: chess.engine.SimpleEngine | None = None

    def _get_engine(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
            self._engine.configure({"Threads": self.threads, "Hash": self.hash_mb})
        return self._engine

    def close(self):
        if self._engine is not None:
            self._engine.quit()
            self._engine = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def analyze_fen(self, fen: str, depth: int = 20, multipv: int = 1) -> list[dict]:
        """Analyze a FEN position and return evaluation results.

        Returns a list of dicts (one per PV line) with keys:
          - score_cp: centipawn score (from white's perspective), or None if mate
          - score_mate: mate-in-N (positive = white mates), or None
          - pv: list of moves in UCI notation
          - pv_san: list of moves in SAN notation
          - depth: search depth reached
        """
        engine = self._get_engine()
        board = chess.Board(fen)

        results = engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)

        if not isinstance(results, list):
            results = [results]

        output = []
        for info in results:
            score = info["score"].white()
            pv_moves = info.get("pv", [])

            pv_san = []
            temp_board = board.copy()
            for move in pv_moves:
                pv_san.append(temp_board.san(move))
                temp_board.push(move)

            entry = {
                "score_cp": score.score(),
                "score_mate": score.mate(),
                "pv": [m.uci() for m in pv_moves],
                "pv_san": pv_san,
                "depth": info.get("depth", depth),
            }
            output.append(entry)

        return output

    def analyze_game(
        self,
        moves_text: str,
        depth: int = 18,
        move_range: tuple[int, int] | None = None,
    ) -> list[dict]:
        """Analyze a game given its move text (SAN).

        Args:
            moves_text: PGN move text (e.g. "1. e4 e5 2. Nf3 Nc6 ...")
            depth: analysis depth per move
            move_range: optional (start_ply, end_ply) to analyze a subset (1-indexed)

        Returns a list of dicts per ply with:
          - ply: half-move number (1-indexed)
          - move_number: full move number
          - side: 'white' or 'black'
          - move_san: the move played in SAN
          - move_uci: the move played in UCI
          - score_cp: centipawn eval after the move (white's perspective)
          - score_mate: mate score or None
          - best_move_san: engine's best move in SAN
          - best_move_uci: engine's best move in UCI
          - best_score_cp: eval of the best move
          - best_score_mate: mate score of best move or None
          - classification: 'best', 'excellent', 'good', 'inaccuracy', 'mistake', 'blunder'
        """
        engine = self._get_engine()
        board = chess.Board()

        # Parse the move text by building a game
        game_io = io.StringIO(f"[Result \"*\"]\n\n{moves_text}")
        pgn_game = chess.pgn.read_game(game_io)
        if pgn_game is None:
            return []

        all_moves = list(pgn_game.mainline_moves())
        results = []
        prev_score_cp = 0  # starting eval

        # Extract clock times from PGN comments
        clock_times = _extract_clocks(pgn_game)

        start_ply = (move_range[0] if move_range else 1)
        end_ply = (move_range[1] if move_range else len(all_moves))

        in_book = True  # Track whether we're still in book territory

        for ply_idx, move in enumerate(all_moves):
            ply = ply_idx + 1

            if ply < start_ply:
                if in_book and not is_book_move(board, move):
                    in_book = False
                board.push(move)
                # Update prev_score for continuity if close to range
                if ply == start_ply - 1:
                    info = _analyse_single(engine, board, depth)
                    score = info["score"].white()
                    prev_score_cp = score.score() if score.score() is not None else 0
                continue
            if ply > end_ply:
                break

            # Check if this move is a book move
            move_is_book = in_book and is_book_move(board, move)
            if not move_is_book:
                in_book = False

            move_san = board.san(move)
            move_uci = move.uci()

            if move_is_book:
                # Book move: skip engine analysis, use lightweight eval
                board.push(move)
                post_info = _analyse_single(engine, board, depth)
                post_score = post_info["score"].white()
                score_cp = post_score.score()
                score_mate = post_score.mate()

                move_number = (ply + 1) // 2
                side = "white" if ply % 2 == 1 else "black"

                results.append({
                    "ply": ply,
                    "move_number": move_number,
                    "side": side,
                    "move_san": move_san,
                    "move_uci": move_uci,
                    "score_cp": score_cp,
                    "score_mate": score_mate,
                    "best_move_san": move_san,
                    "best_move_uci": move_uci,
                    "best_score_cp": score_cp,
                    "best_score_mate": score_mate,
                    "classification": "book",
                    "clock_seconds": clock_times.get(ply),
                })

                prev_score_cp = score_cp if score_cp is not None else 0
                continue

            # Get best move BEFORE playing the move
            pre_info = _analyse_single(engine, board, depth)
            pre_score = pre_info["score"].white()
            best_pv = pre_info.get("pv", [])
            best_move = best_pv[0] if best_pv else None

            best_move_san = board.san(best_move) if best_move else "?"
            best_move_uci = best_move.uci() if best_move else "?"
            best_score_cp = pre_score.score()
            best_score_mate = pre_score.mate()

            # Play the actual move
            board.push(move)

            # Evaluate position AFTER the move
            post_info = _analyse_single(engine, board, depth)
            post_score = post_info["score"].white()
            score_cp = post_score.score()
            score_mate = post_score.mate()

            # Classify the move
            classification = _classify_move(
                move, best_move, prev_score_cp, score_cp, best_score_cp,
                score_mate, best_score_mate, board.turn  # board.turn is now opponent's turn
            )

            # Detect tactical patterns for mistakes/blunders
            error_type = ""
            tactics_missed = []
            if classification in ("inaccuracy", "mistake", "blunder") and best_move:
                # Use pre-move board (pop, analyze, push back)
                board.pop()
                error_info = categorize_error(board, move, best_move, 0)
                error_type = error_info["error_type"]
                tactics_missed = error_info["tactics_missed"]
                board.push(move)

            move_number = (ply + 1) // 2
            side = "white" if ply % 2 == 1 else "black"

            results.append({
                "ply": ply,
                "move_number": move_number,
                "side": side,
                "move_san": move_san,
                "move_uci": move_uci,
                "score_cp": score_cp,
                "score_mate": score_mate,
                "best_move_san": best_move_san,
                "best_move_uci": best_move_uci,
                "best_score_cp": best_score_cp,
                "best_score_mate": best_score_mate,
                "classification": classification,
                "error_type": error_type,
                "tactics_missed": tactics_missed,
                "clock_seconds": clock_times.get(ply),
            })

            prev_score_cp = score_cp if score_cp is not None else 0

        return results


def _extract_clocks(pgn_game) -> dict[int, float]:
    """Extract clock times from PGN comments like {[%clk H:MM:SS]}.

    Returns a dict mapping ply number (1-indexed) to remaining seconds.
    """
    import re
    clocks = {}
    node = pgn_game
    ply = 0
    while node.variations:
        node = node.variation(0)
        ply += 1
        comment = node.comment or ""
        match = re.search(r'\[%clk\s+(\d+):(\d+):(\d+)', comment)
        if match:
            h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
            clocks[ply] = h * 3600 + m * 60 + s
    return clocks


def _analyse_single(engine, board, depth):
    """Run engine.analyse and always return a single info dict."""
    result = engine.analyse(board, chess.engine.Limit(depth=depth))
    if isinstance(result, list):
        return result[0]
    return result


def _classify_move(
    played_move, best_move, prev_cp, post_cp, best_cp,
    post_mate, best_mate, opponent_turn
) -> str:
    """Classify a move as best/excellent/good/inaccuracy/mistake/blunder."""
    if played_move == best_move:
        return "best"

    # Handle mate scores: if the played move leads to forced mate in our favor
    if post_mate is not None and best_mate is not None:
        # Both are mate scores
        if post_mate == best_mate:
            return "best"
        return "good"

    if best_mate is not None and post_mate is None:
        # Best move was mate, we didn't play it
        return "mistake"

    if post_mate is not None and best_mate is None:
        # We found a mate the engine didn't initially show (unlikely but possible)
        return "excellent"

    if best_cp is None or post_cp is None:
        return "good"

    # board.turn after push = whose turn it is NOW (the opponent of who just moved)
    # chess.WHITE = True, chess.BLACK = False
    # So opponent_turn=True means WHITE to move = BLACK just moved
    # And opponent_turn=False means BLACK to move = WHITE just moved
    # Scores are always from white's perspective.
    if opponent_turn:
        # White to move = black just moved
        # Bad black move makes eval more positive (better for white)
        loss = post_cp - best_cp
    else:
        # Black to move = white just moved
        # Bad white move makes eval more negative (worse for white)
        loss = best_cp - post_cp

    if loss <= 10:
        return "best"
    elif loss <= 25:
        return "excellent"
    elif loss <= 50:
        return "good"
    elif loss <= 100:
        return "inaccuracy"
    elif loss <= 200:
        return "mistake"
    else:
        return "blunder"


def format_score(score_cp: int | None, score_mate: int | None) -> str:
    """Format an engine score for display."""
    if score_mate is not None:
        return f"#{'+'if score_mate > 0 else ''}{score_mate}"
    if score_cp is not None:
        value = score_cp / 100.0
        return f"{value:+.2f}"
    return "?"


def format_eval_bar(score_cp: int | None, score_mate: int | None, width: int = 20) -> str:
    """Create a simple text-based evaluation bar."""
    if score_mate is not None:
        filled = width if score_mate > 0 else 0
    elif score_cp is not None:
        # Clamp between -500 and +500 cp for the bar
        clamped = max(-500, min(500, score_cp))
        filled = int((clamped + 500) / 1000 * width)
    else:
        filled = width // 2

    bar = "W" * filled + "B" * (width - filled)
    return f"[{bar}]"
