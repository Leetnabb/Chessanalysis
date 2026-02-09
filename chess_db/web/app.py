"""Flask web application for chess game analysis."""

import os
import sys
from pathlib import Path

from flask import Flask, render_template, request, jsonify, redirect, url_for

from ..database import ChessDatabase
from ..engine import StockfishAnalyzer, format_score, format_eval_bar

DEFAULT_DB = os.environ.get("CHESS_DB", "chess_games.db")


def create_app(db_path: str = DEFAULT_DB) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.config["DB_PATH"] = db_path

    def get_db() -> ChessDatabase:
        return ChessDatabase(app.config["DB_PATH"])

    # ── Dashboard ─────────────────────────────────────────────────

    @app.route("/")
    def index():
        with get_db() as db:
            total = db.count()
            analyzed = db.analyzed_count()
            top_players = db.players(limit=10)
            top_openings = db.openings(limit=10)
        return render_template(
            "index.html",
            total=total,
            analyzed=analyzed,
            top_players=top_players,
            top_openings=top_openings,
        )

    # ── Games list / search ───────────────────────────────────────

    @app.route("/games")
    def games():
        player = request.args.get("player", "")
        eco = request.args.get("eco", "")
        result = request.args.get("result", "")
        page = int(request.args.get("page", 1))
        per_page = 30
        offset = (page - 1) * per_page

        with get_db() as db:
            results = db.search(
                player=player or None,
                eco=eco or None,
                result=result or None,
                limit=per_page,
                offset=offset,
            )
            # Check which are analyzed
            for g in results:
                g["analyzed"] = db.is_analyzed(g["id"])

        return render_template(
            "games.html",
            games=results,
            player=player,
            eco=eco,
            result=result,
            page=page,
        )

    # ── Single game view ──────────────────────────────────────────

    @app.route("/game/<int:game_id>")
    def game_detail(game_id: int):
        with get_db() as db:
            game = db.get_game(game_id)
            if not game:
                return "Game not found", 404
            analysis = db.get_analysis_summary(game_id)
            moves = db.get_move_analysis(game_id)

        # Build move data for JS
        move_data = []
        for m in moves:
            move_data.append({
                "ply": m["ply"],
                "moveNumber": m["move_number"],
                "side": m["side"],
                "san": m["move_san"],
                "uci": m["move_uci"],
                "scoreCp": m["score_cp"],
                "scoreMate": m["score_mate"],
                "bestSan": m["best_move_san"],
                "bestScoreCp": m["best_score_cp"],
                "bestScoreMate": m["best_score_mate"],
                "classification": m["classification"],
                "scoreStr": format_score(m["score_cp"], m["score_mate"]),
                "bestScoreStr": format_score(m["best_score_cp"], m["best_score_mate"]),
            })

        return render_template(
            "game.html",
            game=game,
            analysis=analysis,
            moves=move_data,
        )

    # ── Analyze game (trigger) ────────────────────────────────────

    @app.route("/game/<int:game_id>/analyze", methods=["POST"])
    def analyze_game(game_id: int):
        depth = int(request.form.get("depth", 14))
        with get_db() as db:
            game = db.get_game(game_id)
            if not game:
                return "Game not found", 404
            try:
                with StockfishAnalyzer() as analyzer:
                    results = analyzer.analyze_game(game["moves"], depth=depth)
                db.save_analysis(game_id, depth, results)
            except FileNotFoundError:
                return "Stockfish not found on system", 500
        return redirect(url_for("game_detail", game_id=game_id))

    # ── Player report ─────────────────────────────────────────────

    @app.route("/report/<player>")
    def report(player: str):
        with get_db() as db:
            report_data = db.get_player_report(player)
            stats = db.player_stats(player)
        return render_template(
            "report.html",
            player=player,
            report=report_data,
            stats=stats,
        )

    # ── Blunders ──────────────────────────────────────────────────

    @app.route("/blunders/<player>")
    def blunders(player: str):
        limit = int(request.args.get("limit", 30))
        with get_db() as db:
            blunder_list = db.get_blunders(player, limit=limit)
        for b in blunder_list:
            b["score_str"] = format_score(b["score_cp"], b["score_mate"])
            b["best_score_str"] = format_score(b["best_score_cp"], b["best_score_mate"])
        return render_template(
            "blunders.html",
            player=player,
            blunders=blunder_list,
        )

    # ── Batch analyze (trigger) ───────────────────────────────────

    @app.route("/batch-analyze", methods=["POST"])
    def batch_analyze():
        player = request.form.get("player", "")
        limit = int(request.form.get("limit", 20))
        depth = int(request.form.get("depth", 14))

        with get_db() as db:
            game_ids = db.unanalyzed_game_ids(
                player=player or None, limit=limit
            )
            analyzed = 0
            try:
                with StockfishAnalyzer() as analyzer:
                    for gid in game_ids:
                        game = db.get_game(gid)
                        if not game or not game["moves"].strip():
                            continue
                        try:
                            results = analyzer.analyze_game(
                                game["moves"], depth=depth
                            )
                            db.save_analysis(gid, depth, results)
                            analyzed += 1
                        except Exception:
                            continue
            except FileNotFoundError:
                return "Stockfish not found", 500

        if player:
            return redirect(url_for("report", player=player))
        return redirect(url_for("index"))

    # ── API: game move data (for AJAX) ────────────────────────────

    @app.route("/api/game/<int:game_id>/moves")
    def api_game_moves(game_id: int):
        with get_db() as db:
            moves = db.get_move_analysis(game_id)
        data = []
        for m in moves:
            data.append({
                "ply": m["ply"],
                "moveNumber": m["move_number"],
                "side": m["side"],
                "san": m["move_san"],
                "uci": m["move_uci"],
                "scoreCp": m["score_cp"],
                "scoreMate": m["score_mate"],
                "bestSan": m["best_move_san"],
                "classification": m["classification"],
            })
        return jsonify(data)

    return app


def run_server(db_path: str = DEFAULT_DB, host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    app = create_app(db_path)
    print(f"Starting chess analysis web UI on http://{host}:{port}")
    print(f"Database: {db_path}")
    app.run(host=host, port=port, debug=debug)
