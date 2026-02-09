"""Command-line interface for the chess PGN database."""

import argparse
import sys
from pathlib import Path

from .database import ChessDatabase
from .engine import StockfishAnalyzer, format_score, format_eval_bar
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

    # ── analyze ──────────────────────────────────────────────────────
    p_analyze = subparsers.add_parser("analyze", help="Analyze a game with Stockfish")
    p_analyze.add_argument("id", type=int, help="Game ID to analyze")
    p_analyze.add_argument("--depth", type=int, default=18, help="Search depth (default: 18)")
    p_analyze.add_argument("--moves", help="Move range to analyze, e.g. 1-20 (full move numbers)")
    p_analyze.add_argument("--multipv", type=int, default=1, help="Number of lines to show per position")
    p_analyze.add_argument("--stockfish", help="Path to Stockfish binary")

    # ── eval ─────────────────────────────────────────────────────────
    p_eval = subparsers.add_parser("eval", help="Evaluate a FEN position with Stockfish")
    p_eval.add_argument("fen", help="FEN string to evaluate")
    p_eval.add_argument("--depth", type=int, default=20, help="Search depth (default: 20)")
    p_eval.add_argument("--multipv", type=int, default=3, help="Number of lines (default: 3)")
    p_eval.add_argument("--stockfish", help="Path to Stockfish binary")

    # ── batch-analyze ────────────────────────────────────────────────
    p_batch = subparsers.add_parser("batch-analyze", help="Batch-analyze games with Stockfish")
    p_batch.add_argument("--player", help="Only analyze games for this player")
    p_batch.add_argument("--limit", type=int, default=50, help="Max games to analyze (default: 50)")
    p_batch.add_argument("--depth", type=int, default=14, help="Search depth (default: 14)")
    p_batch.add_argument("--stockfish", help="Path to Stockfish binary")

    # ── report ───────────────────────────────────────────────────────
    p_report = subparsers.add_parser("report", help="Show learning report from analyzed games")
    p_report.add_argument("player", help="Player name")

    # ── blunders ─────────────────────────────────────────────────────
    p_blunders = subparsers.add_parser("blunders", help="Show worst moves for learning")
    p_blunders.add_argument("player", help="Player name")
    p_blunders.add_argument("--limit", type=int, default=20, help="Number of blunders (default: 20)")

    # ── web ─────────────────────────────────────────────────────────
    p_web = subparsers.add_parser("web", help="Start the web interface")
    p_web.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    p_web.add_argument("--port", type=int, default=5000, help="Port (default: 5000)")

    args = parser.parse_args(argv)

    if args.command == "web":
        from .web.app import run_server
        run_server(db_path=args.db, host=args.host, port=args.port)
        return

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
        elif args.command == "analyze":
            cmd_analyze(db, args)
        elif args.command == "eval":
            cmd_eval(args)
        elif args.command == "batch-analyze":
            cmd_batch_analyze(db, args)
        elif args.command == "report":
            cmd_report(db, args)
        elif args.command == "blunders":
            cmd_blunders(db, args)


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


def cmd_analyze(db: ChessDatabase, args):
    game = db.get_game(args.id)
    if not game:
        print(f"Game #{args.id} not found.")
        return

    print(f"Analyzing game #{game['id']}: {game['white']} vs {game['black']}")
    print(f"  Opening: {game['opening'] or game['eco'] or '?'}")
    print(f"  Result:  {game['result']}")
    print(f"  Depth:   {args.depth}")
    print()

    move_range = None
    if args.moves:
        parts = args.moves.split("-")
        start_full = int(parts[0])
        end_full = int(parts[1]) if len(parts) > 1 else start_full
        # Convert full move numbers to ply
        start_ply = (start_full - 1) * 2 + 1
        end_ply = end_full * 2
        move_range = (start_ply, end_ply)

    try:
        with StockfishAnalyzer(stockfish_path=args.stockfish) as analyzer:
            results = analyzer.analyze_game(
                game["moves"], depth=args.depth, move_range=move_range
            )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return

    if not results:
        print("No moves to analyze.")
        return

    # Print move-by-move analysis
    _CLASSIFICATION_SYMBOLS = {
        "best": "!!",
        "excellent": "!",
        "good": "",
        "inaccuracy": "?!",
        "mistake": "?",
        "blunder": "??",
    }

    counts = {"white": {}, "black": {}}
    for r in results:
        cls = r["classification"]
        side = r["side"]
        counts[side][cls] = counts[side].get(cls, 0) + 1

    print(f"{'Move':<8} {'Played':<12} {'Eval':>8}  {'Bar':<22} {'Best':<12} {'Class'}")
    print("-" * 80)

    for r in results:
        score_str = format_score(r["score_cp"], r["score_mate"])
        bar = format_eval_bar(r["score_cp"], r["score_mate"])
        sym = _CLASSIFICATION_SYMBOLS.get(r["classification"], "")
        move_label = f"{r['move_number']}." if r["side"] == "white" else f"{r['move_number']}..."

        best_str = ""
        if r["classification"] not in ("best", "excellent", "good"):
            best_str = r["best_move_san"]

        played = f"{r['move_san']}{sym}"
        print(f"{move_label:<8} {played:<12} {score_str:>8}  {bar}  {best_str:<12} {r['classification']}")

    # Summary
    print()
    print("Summary:")
    for side in ("white", "black"):
        name = game["white"] if side == "white" else game["black"]
        side_counts = counts[side]
        total = sum(side_counts.values())
        if total == 0:
            continue
        parts = []
        for cls in ("best", "excellent", "good", "inaccuracy", "mistake", "blunder"):
            c = side_counts.get(cls, 0)
            if c > 0:
                parts.append(f"{c} {cls}")
        accuracy = (
            side_counts.get("best", 0) + side_counts.get("excellent", 0) + side_counts.get("good", 0)
        ) / total * 100
        print(f"  {name} ({side}): accuracy {accuracy:.0f}% - {', '.join(parts)}")


def cmd_eval(args):
    print(f"Evaluating position: {args.fen}")
    print(f"  Depth: {args.depth}  Lines: {args.multipv}")
    print()

    try:
        with StockfishAnalyzer(stockfish_path=args.stockfish) as analyzer:
            results = analyzer.analyze_fen(args.fen, depth=args.depth, multipv=args.multipv)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return

    for i, r in enumerate(results, 1):
        score_str = format_score(r["score_cp"], r["score_mate"])
        bar = format_eval_bar(r["score_cp"], r["score_mate"])
        pv_str = " ".join(r["pv_san"][:10])
        if len(r["pv_san"]) > 10:
            pv_str += " ..."
        print(f"Line {i}: {score_str}  {bar}")
        print(f"  PV: {pv_str}")
        print()


def cmd_batch_analyze(db: ChessDatabase, args):
    game_ids = db.unanalyzed_game_ids(player=args.player, limit=args.limit)
    already = db.analyzed_count()
    total_games = db.count()

    if not game_ids:
        print(f"All matching games already analyzed ({already}/{total_games}).")
        return

    print(f"Batch analysis: {len(game_ids)} game(s) to analyze (depth {args.depth})")
    print(f"  Already analyzed: {already}/{total_games}")
    if args.player:
        print(f"  Filter: {args.player}")
    print()

    try:
        with StockfishAnalyzer(stockfish_path=args.stockfish) as analyzer:
            for i, gid in enumerate(game_ids, 1):
                game = db.get_game(gid)
                if not game or not game["moves"].strip():
                    continue

                white = game["white"][:15]
                black = game["black"][:15]
                print(f"  [{i}/{len(game_ids)}] #{gid} {white} vs {black} ", end="", flush=True)

                try:
                    results = analyzer.analyze_game(game["moves"], depth=args.depth)
                    db.save_analysis(gid, args.depth, results)

                    # Quick summary
                    summary = db.get_analysis_summary(gid)
                    w_acc = f"{summary['white_accuracy']:.0f}%" if summary["white_accuracy"] is not None else "?"
                    b_acc = f"{summary['black_accuracy']:.0f}%" if summary["black_accuracy"] is not None else "?"
                    errs = summary["white_blunders"] + summary["black_blunders"]
                    print(f"  W:{w_acc} B:{b_acc} ({errs} blunder(s))")
                except Exception as e:
                    print(f"  ERROR: {e}")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return

    new_total = db.analyzed_count()
    print(f"\nDone. {new_total}/{total_games} games analyzed.")


def cmd_report(db: ChessDatabase, args):
    report = db.get_player_report(args.player)
    if report is None:
        print(f"No analyzed games found for '{args.player}'.")
        print("Run 'batch-analyze' first to analyze your games.")
        return

    print(f"=== Learning Report: {report['player']} ===")
    print(f"  Analyzed games: {report['analyzed_games']}")
    if report["avg_accuracy"] is not None:
        print(f"  Average accuracy: {report['avg_accuracy']}%")
    print(f"  Total blunders: {report['total_blunders']}")
    print(f"  Total mistakes: {report['total_mistakes']}")
    print(f"  Total inaccuracies: {report['total_inaccuracies']}")

    # Phase breakdown
    print(f"\n--- Errors by game phase ---")
    print(f"{'Phase':<15} {'Moves':>6} {'Blunders':>9} {'Mistakes':>9} {'Inacc.':>7} {'Error%':>7}")
    print("-" * 58)
    for phase_name in ("opening", "middlegame", "endgame"):
        p = report["phase_errors"][phase_name]
        total = p["total"]
        if total == 0:
            continue
        errors = p["blunder"] + p["mistake"] + p["inaccuracy"]
        err_pct = round(errors / total * 100, 1)
        print(
            f"{phase_name:<15} {total:>6} {p['blunder']:>9} {p['mistake']:>9} "
            f"{p['inaccuracy']:>7} {err_pct:>6.1f}%"
        )

    # Weakest openings
    if report["weakest_openings"]:
        print(f"\n--- Weakest openings (lowest accuracy) ---")
        print(f"{'ECO':<6} {'Opening':<30} {'Games':>6} {'Acc%':>6} {'Blunders':>9}")
        print("-" * 62)
        for o in report["weakest_openings"][:7]:
            name = (o["opening"] or o["eco"])[:29]
            print(f"{o['eco']:<6} {name:<30} {o['games']:>6} {o['avg_accuracy']:>5.1f}% {o['blunders']:>9}")

    # Strongest openings
    if report["strongest_openings"]:
        print(f"\n--- Strongest openings (highest accuracy) ---")
        print(f"{'ECO':<6} {'Opening':<30} {'Games':>6} {'Acc%':>6} {'Blunders':>9}")
        print("-" * 62)
        for o in report["strongest_openings"][:7]:
            name = (o["opening"] or o["eco"])[:29]
            print(f"{o['eco']:<6} {name:<30} {o['games']:>6} {o['avg_accuracy']:>5.1f}% {o['blunders']:>9}")

    print(f"\nTip: Run 'blunders {args.player}' to see your worst moves and learn from them.")


def cmd_blunders(db: ChessDatabase, args):
    moves = db.get_blunders(args.player, limit=args.limit)
    if not moves:
        print(f"No blunders/mistakes found for '{args.player}'.")
        print("Run 'batch-analyze' first to analyze your games.")
        return

    print(f"=== Worst moves: {args.player} ===\n")
    print(f"{'#':>3} {'Game':>6} {'Move':<8} {'Played':<10} {'Best':<10} {'Eval':>8} {'Best Eval':>10} {'Type':<10} {'Opening'}")
    print("-" * 95)

    for i, m in enumerate(moves, 1):
        move_label = f"{m['move_number']}." if m["side"] == "white" else f"{m['move_number']}..."
        score_str = format_score(m["score_cp"], m["score_mate"])
        best_score_str = format_score(m["best_score_cp"], m["best_score_mate"])
        opening = (m.get("opening") or m.get("eco") or "?")[:20]

        print(
            f"{i:>3} #{m['game_id']:<5} {move_label:<8} {m['move_san']:<10} "
            f"{m['best_move_san']:<10} {score_str:>8} {best_score_str:>10} "
            f"{m['classification']:<10} {opening}"
        )

    print(f"\nUse 'analyze <game-id>' to see the full game analysis.")


if __name__ == "__main__":
    main()
