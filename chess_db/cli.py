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

    # ── smart-analyze ──────────────────────────────────────────────
    p_smart = subparsers.add_parser("smart-analyze", help="Smart large-scale analysis with priority tiers")
    p_smart.add_argument("player", help="Player name to analyze")
    p_smart.add_argument("--threads", type=int, default=0, help="Stockfish threads (0=auto)")
    p_smart.add_argument("--hash", type=int, default=256, help="Stockfish hash MB (default: 256)")
    p_smart.add_argument("--stockfish", help="Path to Stockfish binary")
    p_smart.add_argument("--tier", choices=["recent", "older", "all"], default="all",
                         help="Which tier to analyze (default: all)")
    p_smart.add_argument("--reanalyze", action="store_true",
                         help="Re-analyze already analyzed games at higher depth")
    p_smart.add_argument("--time-limit", type=float, default=0,
                         help="Override time limit per position in seconds (0=use tier defaults)")

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
        elif args.command == "smart-analyze":
            cmd_smart_analyze(db, args)
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


def cmd_smart_analyze(db: ChessDatabase, args):
    """Smart large-scale analysis with priority tiers and optimized settings.

    Tiers:
      - Recent (last 2 years): depth 18, full tactical detection
      - Older (2-5 years): depth 14
      - Ancient (5+ years): depth 10
    """
    import os
    import time

    player = args.player

    # Auto-detect threads
    threads = args.threads
    if threads <= 0:
        threads = max(1, os.cpu_count() - 1) if os.cpu_count() else 1
    hash_mb = args.hash

    # Get all games for this player
    all_games = db.search(player=player, limit=100000)
    if not all_games:
        print(f"No games found for '{player}'.")
        return

    # Split into tiers by date
    from datetime import datetime
    now = datetime.now()

    tiers = {"recent": [], "older": [], "ancient": []}
    tier_depths = {"recent": 18, "older": 14, "ancient": 10}
    # Time limit per position (seconds) - prevents positions from taking minutes
    user_tl = getattr(args, 'time_limit', 0)
    if user_tl > 0:
        tier_time_limits = {"recent": user_tl, "older": user_tl, "ancient": user_tl}
    else:
        tier_time_limits = {"recent": 0.5, "older": 0.3, "ancient": 0.2}
    tier_labels = {
        "recent": f"Recent (last 2 years) - depth 18, {tier_time_limits['recent']}s/pos",
        "older": f"Older (2-5 years) - depth 14, {tier_time_limits['older']}s/pos",
        "ancient": f"Ancient (5+ years) - depth 10, {tier_time_limits['ancient']}s/pos",
    }

    for g in all_games:
        gid = g["id"]
        date_str = g.get("date", "")

        # Parse year from date (format: YYYY.MM.DD)
        try:
            year = int(date_str[:4])
        except (ValueError, TypeError):
            year = 2000  # Unknown date -> ancient

        age = now.year - year

        if age <= 2:
            tiers["recent"].append(g)
        elif age <= 5:
            tiers["older"].append(g)
        else:
            tiers["ancient"].append(g)

    # Determine which games need analysis
    analyzed_ids = set()
    analyzed_depths = {}
    for tier_name, games in tiers.items():
        for g in games:
            summary = db.get_analysis_summary(g["id"])
            if summary:
                analyzed_ids.add(g["id"])
                analyzed_depths[g["id"]] = summary["depth"]

    print(f"=== Smart Analysis for {player} ===")
    print(f"  Total games: {len(all_games)}")
    print(f"  Already analyzed: {len(analyzed_ids)}")
    print(f"  Stockfish threads: {threads}, hash: {hash_mb}MB")
    print()

    for tier_name in ("recent", "older", "ancient"):
        games = tiers[tier_name]
        target_depth = tier_depths[tier_name]

        if args.tier != "all" and args.tier != tier_name:
            continue

        # Filter: unanalyzed, or reanalyze if current depth < target
        to_analyze = []
        for g in games:
            gid = g["id"]
            if gid not in analyzed_ids:
                to_analyze.append(g)
            elif args.reanalyze and analyzed_depths.get(gid, 0) < target_depth:
                to_analyze.append(g)

        total_in_tier = len(games)
        need_analysis = len(to_analyze)
        already = total_in_tier - need_analysis

        print(f"--- {tier_labels[tier_name]} ---")
        print(f"  {total_in_tier} games, {already} done, {need_analysis} remaining")

        if need_analysis == 0:
            print("  All done!")
            print()
            continue

        # Estimate time based on time limit per position
        pos_time = tier_time_limits[tier_name]
        avg_plies = sum(g.get("total_plies", 60) for g in to_analyze) / max(len(to_analyze), 1)
        # ~1 analysis per ply (single-analysis optimization), ~10 book plies are fast
        effective_plies = max(avg_plies - 10, 20)
        time_per_game = effective_plies * pos_time
        total_est = time_per_game * need_analysis
        if total_est < 3600:
            est_str = f"~{total_est / 60:.0f} minutes"
        elif total_est < 86400:
            est_str = f"~{total_est / 3600:.1f} hours"
        else:
            est_str = f"~{total_est / 86400:.1f} days"

        print(f"  Estimated time: {est_str}")
        print()

        # Sort: losses first (most to learn), then draws, then wins
        def sort_key(g):
            is_white = player.lower() in g["white"].lower()
            r = g["result"]
            if (r == "0-1" and is_white) or (r == "1-0" and not is_white):
                return 0  # losses first
            elif r == "1/2-1/2":
                return 1
            else:
                return 2
        to_analyze.sort(key=sort_key)

        try:
            with StockfishAnalyzer(
                stockfish_path=args.stockfish,
                threads=threads,
                hash_mb=hash_mb,
            ) as analyzer:
                start_time = time.time()
                for i, g in enumerate(to_analyze, 1):
                    gid = g["id"]
                    if not g["moves"].strip():
                        continue

                    white = g["white"][:15]
                    black = g["black"][:15]
                    elapsed = time.time() - start_time
                    rate = i / max(elapsed, 1) * 3600
                    eta = (need_analysis - i) / max(rate / 3600, 0.001)

                    print(
                        f"  [{i}/{need_analysis}] #{gid} {white} vs {black} "
                        f"({g['date']}) ",
                        end="", flush=True,
                    )

                    try:
                        results = analyzer.analyze_game(
                            g["moves"], depth=target_depth,
                            time_limit=tier_time_limits[tier_name],
                        )
                        db.save_analysis(gid, target_depth, results)

                        summary = db.get_analysis_summary(gid)
                        is_white = player.lower() in g["white"].lower()
                        acc = summary["white_accuracy"] if is_white else summary["black_accuracy"]
                        acc_str = f"{acc:.0f}%" if acc is not None else "?"
                        print(f"  {acc_str}  [{rate:.0f}/hr, ETA {eta:.1f}h]")

                    except KeyboardInterrupt:
                        print("\n\n  Stopped by user. Progress saved - run again to continue.")
                        return
                    except Exception as e:
                        print(f"  ERROR: {e}")

        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return

        print()

    total_analyzed = db.analyzed_count()
    total_games = db.count()
    print(f"Done. {total_analyzed}/{total_games} games analyzed total.")
    print(f"View insights at: http://localhost:8080/insights/{player}")


if __name__ == "__main__":
    main()
