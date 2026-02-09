# Chess PGN Database

A command-line tool to import, store, search, and analyze chess games from PGN files using SQLite.

## Quick Start

```bash
# Import PGN files
python -m chess_db import pgn_files/

# View database summary
python -m chess_db summary

# Search games
python -m chess_db search --player "Kasparov"
python -m chess_db search --eco B06 --result 1-0

# Show a specific game
python -m chess_db show 1

# Player statistics
python -m chess_db stats "Kasparov, Garry"

# List top players
python -m chess_db players

# List common openings
python -m chess_db openings

# Export games back to PGN
python -m chess_db export -o output.pgn
python -m chess_db export --ids 1 3 5
```

## Commands

| Command    | Description                          |
|------------|--------------------------------------|
| `import`   | Import PGN files or directories      |
| `search`   | Search games by player, ECO, date... |
| `show`     | Display a single game by ID          |
| `players`  | List players ranked by game count    |
| `openings` | List most common openings            |
| `stats`    | Detailed statistics for a player     |
| `export`   | Export games back to PGN format      |
| `delete`   | Remove a game by ID                  |
| `summary`  | Show database overview               |

## Search Filters

- `--player` - Name appears as white or black
- `--white` / `--black` - Specific side
- `--event` - Event name
- `--eco` - ECO opening code (prefix match)
- `--result` - Game result (1-0, 0-1, 1/2-1/2)
- `--opening` - Opening name
- `--date-from` / `--date-to` - Date range
- `--min-elo` - Minimum rating
- `--limit` - Max results

## Importing Your Games

Place your `.pgn` files in the `pgn_files/` directory and run:

```bash
python -m chess_db import pgn_files/
```

Or import specific files:

```bash
python -m chess_db import game1.pgn game2.pgn
```

## Running Tests

```bash
pip install pytest
pytest tests/
```
