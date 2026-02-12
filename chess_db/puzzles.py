"""Generate training puzzles from analyzed games.

Creates practice exercises from positions where the player made
mistakes, blunders, or inaccuracies. Puzzles are categorized as:
  - tactical: missed forks, pins, skewers, etc.
  - positional: piece placement and pawn structure errors
  - opening: mistakes in the first 20 plies (opening phase)
"""

import chess
import chess.pgn
import io
import json


def _reconstruct_fens(moves_text: str, target_plies: list[int]) -> dict[int, str]:
    """Reconstruct FEN positions at multiple plies from a game.

    Returns dict mapping ply -> FEN (position BEFORE that ply's move).
    """
    if not target_plies:
        return {}
    board = chess.Board()
    game_io = io.StringIO(f'[Result "*"]\n\n{moves_text}')
    pgn_game = chess.pgn.read_game(game_io)
    if not pgn_game:
        return {}

    fens = {}
    target_set = set(target_plies)
    max_ply = max(target_plies)

    for i, move in enumerate(pgn_game.mainline_moves()):
        ply = i + 1
        if ply in target_set:
            fens[ply] = board.fen()
        if ply > max_ply:
            break
        board.push(move)
    return fens


def generate_puzzles(
    db,
    player: str,
    categories: list[str] | None = None,
    limit: int = 200,
) -> list[dict]:
    """Generate training puzzles from analyzed games.

    Args:
        db: ChessDatabase instance
        player: player name
        categories: filter by category ('tactical', 'positional', 'opening')
                    None = all categories
        limit: max puzzles to return

    Returns list of puzzle dicts with keys:
        id, fen, correct_move_uci, correct_move_san, played_move_san,
        classification, category, error_type, tactics, cp_loss,
        game_id, ply, move_number, player_color, opponent, date,
        eco, opening, difficulty
    """
    if categories is None:
        categories = ["tactical", "positional", "opening"]

    # Query all mistakes/blunders for this player
    classifications = ("blunder", "mistake", "inaccuracy")
    blunders = db.get_blunders(
        player, limit=limit * 3, classifications=classifications
    )
    if not blunders:
        return []

    # Group by game_id for efficient FEN reconstruction
    game_groups: dict[int, list[dict]] = {}
    for b in blunders:
        gid = b["game_id"]
        if gid not in game_groups:
            game_groups[gid] = []
        game_groups[gid].append(b)

    puzzles = []
    for gid, mistake_list in game_groups.items():
        game = db.get_game(gid)
        if not game or not game["moves"].strip():
            continue

        target_plies = [m["ply"] for m in mistake_list]
        fens = _reconstruct_fens(game["moves"], target_plies)

        is_white = player.lower() in game["white"].lower()
        player_color = "white" if is_white else "black"
        opponent = game["black"] if is_white else game["white"]

        for m in mistake_list:
            ply = m["ply"]
            fen = fens.get(ply)
            if not fen:
                continue

            # Skip if the move is not by the player
            move_side = m.get("side", "")
            if move_side and move_side != player_color:
                continue

            # Parse tactics
            error_type = m.get("error_type", "") or ""
            tactics_json = m.get("tactics_missed", "[]") or "[]"
            try:
                tactics = (
                    json.loads(tactics_json)
                    if isinstance(tactics_json, str)
                    else tactics_json
                )
            except (json.JSONDecodeError, TypeError):
                tactics = []

            # Determine puzzle category
            if ply <= 20:
                category = "opening"
            elif error_type == "tactical" or tactics:
                category = "tactical"
            else:
                category = "positional"

            if category not in categories:
                continue

            # Calculate cp loss
            best_cp = m.get("best_score_cp")
            post_cp = m.get("score_cp")
            if best_cp is not None and post_cp is not None:
                cp_loss = abs(best_cp - post_cp)
            else:
                cp_loss = 0

            # Skip positions that are already lost before the mistake.
            # These give little training value - the game was already over.
            # best_score_cp is from white's perspective.
            if best_cp is not None:
                player_eval = best_cp if is_white else -best_cp
                if player_eval < -300:
                    continue  # Already losing badly, skip

            # Difficulty: 1=easy (big blunder), 2=medium, 3=hard (subtle)
            if m["classification"] == "blunder":
                difficulty = 1
            elif m["classification"] == "mistake":
                difficulty = 2
            else:
                difficulty = 3

            puzzles.append({
                "id": f"{gid}_{ply}",
                "fen": fen,
                "correct_move_uci": m["best_move_uci"],
                "correct_move_san": m["best_move_san"],
                "played_move_san": m["move_san"],
                "played_move_uci": m.get("move_uci", ""),
                "classification": m["classification"],
                "category": category,
                "error_type": error_type,
                "tactics": tactics,
                "cp_loss": cp_loss,
                "game_id": gid,
                "ply": ply,
                "move_number": m["move_number"],
                "player_color": player_color,
                "opponent": opponent,
                "date": game["date"],
                "eco": game.get("eco", ""),
                "opening": game.get("opening", ""),
                "difficulty": difficulty,
            })

    # Sort: blunders first (easiest to spot), then by cp loss
    puzzles.sort(key=lambda p: (p["difficulty"], -p["cp_loss"]))
    return puzzles[:limit]


def generate_opening_puzzles(db, player: str, limit: int = 100) -> list[dict]:
    """Generate opening-specific training puzzles.

    Focuses on mistakes in the first 20 plies, especially in
    openings where the player performs poorly.
    """
    return generate_puzzles(db, player, categories=["opening"], limit=limit)
