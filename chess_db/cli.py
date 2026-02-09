"""Command-line interface for the chess PGN database."""

import argparse
import sys
from pathlib import Path

from .database import ChessDatabase
from .parser import parse_pgn_file


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        prog="chess-db",
        description="Chess PGN Database - Import, search, and analyze your chess games.",
    )
    parser.add_argument(
        "--db",
        default="chess_games.db",
        help="Path to the SQLite database file (default: chess_games.db)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── import ────────────────────────────────────────────────────────
    p_import = subparsers.add_parser("import", help="Import PGN files into the database")
    p_import.add_argument("files", nargs="+", help="PGN file(s) or directories to import")

    # ── search ────────────────────────────────────────────────────────
    p_search = subparsers.add_parser("search", help="Search games")
    p_search.add_argument("--player", help="Player name (white or black)")
    p_search.add_argument("--white", help="White player name")
    p_search.add_argument("--black", help="Black player name")
    p_search.add_argument("--event", help="Event name")
    p_search.add_argument("--eco", help="ECO opening code (e.g. B90)")
    p_search.add_argument("--result", choices=["1-0", "0-1", "1/2-1/2", "*"], help="Game result")
    p_search.add_argument("--opening", help="Opening name")
    p_search.add_argument("--date-from", help="Games from date (YYYY.MM.DD)")
    p_search.add_argument("--date-to", help="Games until date (YYYY.MM.DD)")
    p_search.add_argument("--min-elo", type=int, help="Minimum Elo rating")
    p_search.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")

    # ── show ──────────────────────────────────────────────────────────
    p_show = subparsers.add_parser("show", help="Show a game by ID")
    p_show.add_argument("id", type=int, help="Game ID")

    # ── players ───────────────────────────────────────────────────────
    p_players = subparsers.add_parser("players", help="List players by number of games")
    p_players.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")

    # ── openings ──────────────────────────────────────────────────────
    p_openings = subparsers.add_parser("openings", help="List most common openings")
    p_openings.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")

    # ── stats ─────────────────────────────────────────────────────────
    p_stats = subparsers.add_parser("stats", help="Show stats for a player")
    p_stats.add_argument("name", help="Player name")

    # ── export ────────────────────────────────────────────────────────
    p_export = subparsers.add_parser("export", help="Export games as PGN")
    p_export.add_argument("--ids", nargs="*", type=int, help="Game IDs to export (omit for all)")
    p_export.add_argument("-o", "--output", help="Output file (default: stdout)")

    # ── delete ────────────────────────────────────────────────────────
    p_delete = subparsers.add_parser("delete", help="Delete a game by ID")
    p_delete.add_argument("id", type=int, help="Game ID")

    # ── summary ───────────────────────────────────────────────────────
    subparsers.add_parser("summary", help="Show database summary")

    args = parser.parse_args(argv)

    with ChessDatabase(args.db) as db:
        if args.command == "import":
            cmd_import(db, args)
        elif args.command == "search":
            cmd_search(db, args)
        elif args.command == "show":
            cmd_show(db, args)
        elif args.command == "players":
            cmd_players(db, args)
        elif args.command == "openings":
            cmd_openings(db, args)
        elif args.command == "stats":
            cmd_stats(db, args)
        elif args.command == "export":
            cmd_export(db, args)
        elif args.command == "delete":
            cmd_delete(db, args)
        elif args.command == "summary":
            cmd_summary(db)


# ── Command implementations ──────────────────────────────────────────


def cmd_import(db: ChessDatabase, args):
    total = 0
    for file_arg in args.files:
        path = Path(file_arg)
        if path.is_dir():
            pgn_files = sorted(path.glob("**/*.pgn"))
            if not pgn_files:
                print(f"No PGN files found in {path}")
                continue
            for pgn_file in pgn_files:
                count = _import_file(db, pgn_file)
                total += count
        elif path.is_file():
            count = _import_file(db, path)
            total += count
        else:
            print(f"Not found: {path}", file=sys.stderr)

    print(f"\nImported {total} game(s). Database now contains {db.count()} game(s).")


def _import_file(db: ChessDatabase, path: Path) -> int:
    try:
        games = parse_pgn_file(path)
    except Exception as e:
        print(f"Error parsing {path}: {e}", file=sys.stderr)
        return 0
    count = db.import_games(games, source_file=str(path))
    print(f"  {path.name}: {count} game(s)")
    return count


def cmd_search(db: ChessDatabase, args):
    results = db.search(
        player=args.player,
        white=args.white,
        black=args.black,
        event=args.event,
        eco=args.eco,
        result=args.result,
        opening=args.opening,
        date_from=args.date_from,
        date_to=args.date_to,
        min_elo=args.min_elo,
        limit=args.limit,
    )
    if not results:
        print("No games found.")
        return

    print(f"Found {len(results)} game(s):\n")
    print(f"{'ID':>5}  {'Date':<12} {'White':<20} {'Black':<20} {'Result':<8} {'ECO':<5} {'Event'}")
    print("-" * 95)
    for g in results:
        print(
            f"{g['id']:>5}  {g['date']:<12} {g['white']:<20} {g['black']:<20} "
            f"{g['result']:<8} {g['eco']:<5} {g['event']}"
        )


def cmd_show(db: ChessDatabase, args):
    game = db.get_game(args.id)
    if not game:
        print(f"Game #{args.id} not found.")
        return

    print(f"Game #{game['id']}")
    print(f"  Event:    {game['event']}")
    print(f"  Site:     {game['site']}")
    print(f"  Date:     {game['date']}")
    print(f"  Round:    {game['round']}")
    print(f"  White:    {game['white']}" + (f" ({game['white_elo']})" if game["white_elo"] else ""))
    print(f"  Black:    {game['black']}" + (f" ({game['black_elo']})" if game["black_elo"] else ""))
    print(f"  Result:   {game['result']}")
    if game["eco"]:
        print(f"  ECO:      {game['eco']}")
    if game["opening"]:
        print(f"  Opening:  {game['opening']}")
    if game["time_control"]:
        print(f"  Time:     {game['time_control']}")
    print(f"  Plies:    {game['total_plies']}")
    print(f"\nMoves:\n{game['moves']}")


def cmd_players(db: ChessDatabase, args):
    players = db.players(limit=args.limit)
    if not players:
        print("No players found.")
        return

    print(f"{'Player':<25} {'Games':>6} {'Wins':>6} {'Draws':>6} {'Losses':>6} {'Peak Elo':>9}")
    print("-" * 70)
    for p in players:
        elo = str(p["peak_elo"]) if p["peak_elo"] else "-"
        print(
            f"{p['name']:<25} {p['games']:>6} {p['wins']:>6} "
            f"{p['draws']:>6} {p['losses']:>6} {elo:>9}"
        )


def cmd_openings(db: ChessDatabase, args):
    openings = db.openings(limit=args.limit)
    if not openings:
        print("No opening data found.")
        return

    print(f"{'ECO':<6} {'Opening':<35} {'Games':>6} {'W Wins':>7} {'B Wins':>7} {'Draws':>6}")
    print("-" * 75)
    for o in openings:
        name = (o["opening"] or "-")[:34]
        print(
            f"{o['eco']:<6} {name:<35} {o['games']:>6} "
            f"{o['white_wins']:>7} {o['black_wins']:>7} {o['draws']:>6}"
        )


def cmd_stats(db: ChessDatabase, args):
    stats = db.player_stats(args.name)
    if stats["games"] == 0:
        print(f"No games found for '{args.name}'.")
        return

    print(f"Player: {stats['player']}")
    print(f"  Games:      {stats['games']}")
    print(f"  Wins:       {stats['wins']}")
    print(f"  Draws:      {stats['draws']}")
    print(f"  Losses:     {stats['losses']}")
    print(f"  Win rate:   {stats['win_rate']}%")
    if stats["peak_elo"]:
        print(f"  Peak Elo:   {stats['peak_elo']}")
    print(f"  Opponents:  {stats['unique_opponents']}")
    if stats["top_openings"]:
        print("  Top openings:")
        for eco, count in stats["top_openings"]:
            print(f"    {eco}: {count} game(s)")


def cmd_export(db: ChessDatabase, args):
    pgn_text = db.export_pgn(args.ids)
    if args.output:
        Path(args.output).write_text(pgn_text)
        print(f"Exported to {args.output}")
    else:
        print(pgn_text)


def cmd_delete(db: ChessDatabase, args):
    if db.delete_game(args.id):
        print(f"Game #{args.id} deleted.")
    else:
        print(f"Game #{args.id} not found.")


def cmd_summary(db: ChessDatabase):
    total = db.count()
    print(f"Database: {db.db_path}")
    print(f"Total games: {total}")
    if total > 0:
        players = db.players(limit=5)
        if players:
            print(f"\nTop players:")
            for p in players:
                print(f"  {p['name']}: {p['games']} games")
        openings = db.openings(limit=5)
        if openings:
            print(f"\nTop openings:")
            for o in openings:
                name = o["opening"] or o["eco"]
                print(f"  {name}: {o['games']} games")


if __name__ == "__main__":
    main()
