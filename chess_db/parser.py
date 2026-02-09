"""PGN (Portable Game Notation) parser for chess games."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ChessGame:
    """Represents a single parsed chess game."""

    # Standard Seven Tag Roster (STR)
    event: str = "?"
    site: str = "?"
    date: str = "????.??.??"
    round: str = "?"
    white: str = "?"
    black: str = "?"
    result: str = "*"

    # Common optional tags
    white_elo: int | None = None
    black_elo: int | None = None
    eco: str = ""
    opening: str = ""
    time_control: str = ""
    termination: str = ""
    variant: str = "Standard"

    # All tags (including non-standard ones)
    tags: dict = field(default_factory=dict)

    # Move text
    moves: str = ""

    def move_list(self) -> list[str]:
        """Return moves as a list of individual moves (e.g. ['e4', 'e5', 'Nf3', ...])."""
        text = self.moves
        # Remove comments
        text = re.sub(r"\{[^}]*\}", "", text)
        # Remove variations
        depth = 0
        clean = []
        for char in text:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif depth == 0:
                clean.append(char)
        text = "".join(clean)
        # Remove move numbers and NAGs
        text = re.sub(r"\d+\.+", "", text)
        text = re.sub(r"\$\d+", "", text)
        # Remove result
        text = re.sub(r"(1-0|0-1|1/2-1/2|\*)\s*$", "", text)
        # Split into individual moves
        return [m.strip() for m in text.split() if m.strip()]

    def total_moves(self) -> int:
        """Return total number of half-moves (plies)."""
        return len(self.move_list())

    def total_full_moves(self) -> int:
        """Return total number of full moves."""
        return (self.total_moves() + 1) // 2


_TAG_RE = re.compile(r'\[(\w+)\s+"([^"]*)"\]')


def parse_pgn(text: str) -> list[ChessGame]:
    """Parse PGN text and return a list of ChessGame objects.

    Handles multiple games in a single PGN string, comments, variations,
    and all standard/non-standard tags.
    """
    games: list[ChessGame] = []
    current_tags: dict[str, str] = {}
    move_lines: list[str] = []
    in_moves = False

    for line in text.splitlines():
        line_stripped = line.strip()

        # Empty line: if we were collecting moves, this ends the game
        if not line_stripped:
            if in_moves and move_lines:
                game = _build_game(current_tags, " ".join(move_lines))
                games.append(game)
                current_tags = {}
                move_lines = []
                in_moves = False
            continue

        # Tag line
        tag_match = _TAG_RE.match(line_stripped)
        if tag_match:
            if in_moves and move_lines:
                # New game starting - save previous
                game = _build_game(current_tags, " ".join(move_lines))
                games.append(game)
                current_tags = {}
                move_lines = []
                in_moves = False
            current_tags[tag_match.group(1)] = tag_match.group(2)
        else:
            # Move text line
            in_moves = True
            move_lines.append(line_stripped)

    # Handle last game
    if current_tags or move_lines:
        game = _build_game(current_tags, " ".join(move_lines))
        games.append(game)

    return games


def parse_pgn_file(path: str | Path) -> list[ChessGame]:
    """Parse a PGN file and return a list of ChessGame objects."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_pgn(text)


def _build_game(tags: dict[str, str], moves: str) -> ChessGame:
    """Build a ChessGame from parsed tags and move text."""
    white_elo = None
    if "WhiteElo" in tags:
        try:
            white_elo = int(tags["WhiteElo"])
        except ValueError:
            pass

    black_elo = None
    if "BlackElo" in tags:
        try:
            black_elo = int(tags["BlackElo"])
        except ValueError:
            pass

    return ChessGame(
        event=tags.get("Event", "?"),
        site=tags.get("Site", "?"),
        date=tags.get("Date", "????.??.??"),
        round=tags.get("Round", "?"),
        white=tags.get("White", "?"),
        black=tags.get("Black", "?"),
        result=tags.get("Result", "*"),
        white_elo=white_elo,
        black_elo=black_elo,
        eco=tags.get("ECO", ""),
        opening=tags.get("Opening", ""),
        time_control=tags.get("TimeControl", ""),
        termination=tags.get("Termination", ""),
        variant=tags.get("Variant", "Standard"),
        tags=tags,
        moves=moves,
    )
