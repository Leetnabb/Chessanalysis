"""Tactical pattern detection for chess positions.

Detects common tactical motifs like forks, pins, skewers, hanging pieces,
discovered attacks, and back-rank weaknesses.
"""

import chess

# Piece values for evaluation
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,  # King can't be captured, but is relevant for checks
}


def detect_tactics_in_best_move(board: chess.Board, best_move: chess.Move) -> list[str]:
    """Detect what tactical patterns the best move exploits.

    Given a position and the engine's best move, determine what tactics
    are present. This helps explain WHY a move is best.

    Returns a list of tactical pattern tags.
    """
    if best_move is None:
        return []

    tags = []

    # Check tactics of the best move
    if _is_fork(board, best_move):
        tags.append("fork")
    if _is_pin_exploitation(board, best_move):
        tags.append("pin")
    if _is_skewer(board, best_move):
        tags.append("skewer")
    if _is_discovered_attack(board, best_move):
        tags.append("discovered_attack")
    if _is_back_rank_threat(board, best_move):
        tags.append("back_rank")
    if _is_removal_of_defender(board, best_move):
        tags.append("removing_defender")
    if _captures_hanging_piece(board, best_move):
        tags.append("hanging_piece")
    if _is_promotion_tactic(board, best_move):
        tags.append("promotion")

    return tags


def detect_position_weaknesses(board: chess.Board, side: chess.Color) -> list[str]:
    """Detect positional weaknesses for the given side.

    Returns a list of positional weakness tags.
    """
    tags = []

    if _has_isolated_pawns(board, side):
        tags.append("isolated_pawns")
    if _has_doubled_pawns(board, side):
        tags.append("doubled_pawns")
    if _has_weak_back_rank(board, side):
        tags.append("weak_back_rank")
    if _king_exposed(board, side):
        tags.append("king_exposed")
    if _has_trapped_piece(board, side):
        tags.append("trapped_piece")

    return tags


def categorize_error(board: chess.Board, played_move: chess.Move,
                     best_move: chess.Move, loss_cp: int) -> dict:
    """Categorize an error (mistake/blunder) by type.

    Returns a dict with:
      - error_type: 'tactical', 'positional', 'strategic'
      - tactics_missed: list of tactical patterns in the best move
      - description: human-readable description
    """
    if best_move is None:
        return {"error_type": "unknown", "tactics_missed": [], "description": ""}

    tactics = detect_tactics_in_best_move(board, best_move)

    if tactics:
        error_type = "tactical"
        desc = _describe_tactics(tactics, board, best_move)
    elif _is_piece_placement_error(board, played_move, best_move):
        error_type = "positional"
        desc = "Suboptimal piece placement"
    elif _is_pawn_structure_error(board, played_move):
        error_type = "positional"
        desc = "Pawn structure weakened"
    else:
        error_type = "strategic"
        desc = "Strategic inaccuracy"

    return {
        "error_type": error_type,
        "tactics_missed": tactics,
        "description": desc,
    }


# ── Fork detection ──────────────────────────────────────────────

def _is_fork(board: chess.Board, move: chess.Move) -> bool:
    """Check if the move creates a fork (attacks 2+ valuable pieces)."""
    test_board = board.copy()
    piece = test_board.piece_at(move.from_square)
    if piece is None:
        return False

    test_board.push(move)

    # Get all squares attacked by the moved piece
    attacked = test_board.attacks(move.to_square)
    valuable_targets = 0

    for sq in attacked:
        target = test_board.piece_at(sq)
        if target is not None and target.color != piece.color:
            # Count pieces more valuable than a pawn (or king = check)
            if target.piece_type == chess.KING:
                valuable_targets += 1
            elif PIECE_VALUES.get(target.piece_type, 0) >= 3:
                valuable_targets += 1
            elif piece.piece_type == chess.PAWN and target.piece_type != chess.PAWN:
                valuable_targets += 1

    return valuable_targets >= 2


# ── Pin detection ───────────────────────────────────────────────

def _is_pin_exploitation(board: chess.Board, move: chess.Move) -> bool:
    """Check if the move exploits a pin."""
    piece = board.piece_at(move.from_square)
    if piece is None:
        return False

    opponent = not piece.color

    # Check if any opponent piece is pinned
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p is not None and p.color == opponent:
            if board.is_pinned(opponent, sq):
                # Check if our move targets this pinned piece or the square behind
                if move.to_square == sq:
                    return True
    return False


# ── Skewer detection ────────────────────────────────────────────

def _is_skewer(board: chess.Board, move: chess.Move) -> bool:
    """Check if the move creates a skewer (attacks a valuable piece
    which, when moved, exposes a less valuable one)."""
    piece = board.piece_at(move.from_square)
    if piece is None:
        return False

    # Only line pieces can skewer
    if piece.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return False

    test_board = board.copy()
    test_board.push(move)

    # Check if we're giving check or attacking a high-value piece in a line
    attacked = test_board.attacks(move.to_square)
    for sq in attacked:
        target = test_board.piece_at(sq)
        if target is not None and target.color != piece.color:
            if target.piece_type in (chess.KING, chess.QUEEN, chess.ROOK):
                # Check if there's a piece behind in the same line
                direction = _direction(move.to_square, sq)
                if direction is not None:
                    behind_sq = sq
                    while True:
                        behind_sq = _step(behind_sq, direction)
                        if behind_sq is None:
                            break
                        behind_piece = test_board.piece_at(behind_sq)
                        if behind_piece is not None:
                            if behind_piece.color != piece.color:
                                return True
                            break
    return False


# ── Discovered attack ───────────────────────────────────────────

def _is_discovered_attack(board: chess.Board, move: chess.Move) -> bool:
    """Check if moving the piece reveals an attack from another piece."""
    piece = board.piece_at(move.from_square)
    if piece is None:
        return False

    # Find line pieces of the same color that might be behind
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p is None or p.color != piece.color or sq == move.from_square:
            continue
        if p.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
            continue

        # Check if the from_square was blocking this piece's attack
        attacks_before = board.attacks(sq)
        test_board = board.copy()
        # Remove the piece temporarily
        test_board.remove_piece_at(move.from_square)
        attacks_after = test_board.attacks(sq)

        new_attacks = attacks_after & ~attacks_before
        for target_sq in new_attacks:
            target = board.piece_at(target_sq)
            if target is not None and target.color != piece.color:
                if PIECE_VALUES.get(target.piece_type, 0) >= 3 or target.piece_type == chess.KING:
                    return True
    return False


# ── Back rank ───────────────────────────────────────────────────

def _is_back_rank_threat(board: chess.Board, move: chess.Move) -> bool:
    """Check if the move threatens or delivers a back-rank mate."""
    piece = board.piece_at(move.from_square)
    if piece is None:
        return False

    if piece.piece_type not in (chess.ROOK, chess.QUEEN):
        return False

    test_board = board.copy()
    test_board.push(move)

    # Check if this gives check on the back rank
    if test_board.is_check():
        opponent_king_sq = test_board.king(not piece.color)
        if opponent_king_sq is not None:
            rank = chess.square_rank(opponent_king_sq)
            if (piece.color == chess.WHITE and rank == 7) or \
               (piece.color == chess.BLACK and rank == 0):
                return True

    return False


def _has_weak_back_rank(board: chess.Board, side: chess.Color) -> bool:
    """Check if the side has a weak back rank."""
    king_sq = board.king(side)
    if king_sq is None:
        return False

    rank = chess.square_rank(king_sq)
    back_rank = 0 if side == chess.WHITE else 7

    if rank != back_rank:
        return False

    # Check if pawns block king escape
    king_file = chess.square_file(king_sq)
    escape_files = [f for f in [king_file - 1, king_file, king_file + 1] if 0 <= f <= 7]
    escape_rank = 1 if side == chess.WHITE else 6

    blocked = 0
    for f in escape_files:
        sq = chess.square(f, escape_rank)
        p = board.piece_at(sq)
        if p is not None and p.color == side and p.piece_type == chess.PAWN:
            blocked += 1

    return blocked >= 2


# ── Hanging piece ───────────────────────────────────────────────

def _captures_hanging_piece(board: chess.Board, move: chess.Move) -> bool:
    """Check if the move captures an undefended piece."""
    captured = board.piece_at(move.to_square)
    if captured is None:
        return False

    piece = board.piece_at(move.from_square)
    if piece is None:
        return False

    # Check if the captured piece is defended
    defenders = board.attackers(captured.color, move.to_square)
    if not defenders:
        return PIECE_VALUES.get(captured.piece_type, 0) >= 1
    return False


# ── Promotion ───────────────────────────────────────────────────

def _is_promotion_tactic(board: chess.Board, move: chess.Move) -> bool:
    """Check if the move involves or threatens promotion."""
    return move.promotion is not None


# ── Removal of defender ─────────────────────────────────────────

def _is_removal_of_defender(board: chess.Board, move: chess.Move) -> bool:
    """Check if the move removes a key defender."""
    captured = board.piece_at(move.to_square)
    if captured is None:
        return False

    piece = board.piece_at(move.from_square)
    if piece is None:
        return False

    # After capturing, check if any enemy piece becomes undefended
    test_board = board.copy()
    test_board.push(move)

    for sq in chess.SQUARES:
        p = test_board.piece_at(sq)
        if p is not None and p.color == captured.color:
            if PIECE_VALUES.get(p.piece_type, 0) >= 3:
                defenders = test_board.attackers(captured.color, sq)
                attackers = test_board.attackers(piece.color, sq)
                if attackers and not defenders:
                    return True
    return False


# ── Positional patterns ─────────────────────────────────────────

def _has_isolated_pawns(board: chess.Board, side: chess.Color) -> bool:
    """Check if the side has isolated pawns."""
    pawns = board.pieces(chess.PAWN, side)
    files_with_pawns = set()
    for sq in pawns:
        files_with_pawns.add(chess.square_file(sq))

    for f in files_with_pawns:
        adjacent = set()
        if f > 0:
            adjacent.add(f - 1)
        if f < 7:
            adjacent.add(f + 1)
        if not adjacent & files_with_pawns:
            return True
    return False


def _has_doubled_pawns(board: chess.Board, side: chess.Color) -> bool:
    """Check if the side has doubled pawns."""
    pawns = board.pieces(chess.PAWN, side)
    file_counts = {}
    for sq in pawns:
        f = chess.square_file(sq)
        file_counts[f] = file_counts.get(f, 0) + 1

    return any(c >= 2 for c in file_counts.values())


def _king_exposed(board: chess.Board, side: chess.Color) -> bool:
    """Check if the king is exposed (few pawn shields)."""
    king_sq = board.king(side)
    if king_sq is None:
        return False

    king_rank = chess.square_rank(king_sq)
    king_file = chess.square_file(king_sq)

    # Only check if king is on back ranks (castled position)
    if side == chess.WHITE and king_rank > 1:
        return False
    if side == chess.BLACK and king_rank < 6:
        return False

    shield_rank = king_rank + (1 if side == chess.WHITE else -1)
    shield_count = 0
    for f in range(max(0, king_file - 1), min(8, king_file + 2)):
        sq = chess.square(f, shield_rank)
        p = board.piece_at(sq)
        if p is not None and p.color == side and p.piece_type == chess.PAWN:
            shield_count += 1

    return shield_count <= 1


def _has_trapped_piece(board: chess.Board, side: chess.Color) -> bool:
    """Check if any piece (not pawn/king) has no safe squares."""
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p is None or p.color != side:
            continue
        if p.piece_type in (chess.PAWN, chess.KING):
            continue
        if PIECE_VALUES.get(p.piece_type, 0) < 3:
            continue

        # Check if piece has any safe move
        safe_moves = 0
        for move in board.legal_moves:
            if move.from_square == sq:
                # Check if the target square is safe
                test = board.copy()
                test.push(move)
                if not test.is_attacked_by(not side, move.to_square):
                    safe_moves += 1
                    break

        if safe_moves == 0:
            return True
    return False


def _is_piece_placement_error(board: chess.Board, played: chess.Move,
                              best: chess.Move) -> bool:
    """Check if the error is about piece placement (not tactical)."""
    played_piece = board.piece_at(played.from_square)
    best_piece = board.piece_at(best.from_square)

    if played_piece is None or best_piece is None:
        return False

    # Same piece, different square
    if played_piece.piece_type == best_piece.piece_type and \
       played.from_square == best.from_square:
        return True

    # No capture in either move
    if board.piece_at(played.to_square) is None and \
       board.piece_at(best.to_square) is None:
        return True

    return False


def _is_pawn_structure_error(board: chess.Board, played: chess.Move) -> bool:
    """Check if the played move weakens pawn structure."""
    piece = board.piece_at(played.from_square)
    if piece is None or piece.piece_type != chess.PAWN:
        return False

    test = board.copy()
    test.push(played)

    # Check if it creates doubled/isolated pawns
    side = piece.color
    return _has_doubled_pawns(test, side) and not _has_doubled_pawns(board, side)


# ── Helper functions ─────────────────────────────────────────────

def _direction(from_sq: int, to_sq: int):
    """Get direction vector (file_delta, rank_delta) between two squares on a line."""
    from_f, from_r = chess.square_file(from_sq), chess.square_rank(from_sq)
    to_f, to_r = chess.square_file(to_sq), chess.square_rank(to_sq)

    df = to_f - from_f
    dr = to_r - from_r

    if df == 0 and dr == 0:
        return None

    # Normalize to unit steps
    if df != 0:
        df = df // abs(df)
    if dr != 0:
        dr = dr // abs(dr)

    # Verify it's a straight or diagonal line
    fdiff = abs(to_f - from_f)
    rdiff = abs(to_r - from_r)
    if fdiff != 0 and rdiff != 0 and fdiff != rdiff:
        return None

    return (df, dr)


def _step(sq: int, direction: tuple) -> int | None:
    """Move one step in the given direction. Returns None if off-board."""
    f = chess.square_file(sq) + direction[0]
    r = chess.square_rank(sq) + direction[1]
    if 0 <= f <= 7 and 0 <= r <= 7:
        return chess.square(f, r)
    return None


def _describe_tactics(tactics: list[str], board: chess.Board, move: chess.Move) -> str:
    """Generate a human-readable description of tactical patterns."""
    descriptions = {
        "fork": "Fork opportunity",
        "pin": "Pin exploitation",
        "skewer": "Skewer",
        "discovered_attack": "Discovered attack",
        "back_rank": "Back rank threat",
        "hanging_piece": "Hanging piece capture",
        "removing_defender": "Removal of defender",
        "promotion": "Promotion threat",
    }
    parts = [descriptions.get(t, t) for t in tactics]
    return ", ".join(parts)


# ── Summary statistics ───────────────────────────────────────────

TACTIC_LABELS = {
    "fork": "Gaffel",
    "pin": "Binding",
    "skewer": "Spyd",
    "discovered_attack": "Avdekker",
    "back_rank": "Bakrekke",
    "hanging_piece": "Hengende brikke",
    "removing_defender": "Fjerne forsvarer",
    "promotion": "Bondeforvandling",
    "trapped_piece": "Fanget brikke",
    "isolated_pawns": "Isolerte bønder",
    "doubled_pawns": "Doble bønder",
    "weak_back_rank": "Svak bakrekke",
    "king_exposed": "Utsatt konge",
}
