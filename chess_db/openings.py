"""Opening book database for detecting theory moves.

Uses chess.polyglot zobrist hashing to quickly check if a move
in a given position is part of known opening theory.
"""

import chess
import chess.polyglot
import io

# Comprehensive opening lines (SAN move sequences).
# Each line covers a well-known variation to reasonable depth.
OPENING_LINES = [
    # ── A: Flank openings ──────────────────────────────────────

    # English Opening
    "1.c4 e5 2.Nc3 Nf6 3.Nf3 Nc6 4.g3 d5 5.cxd5 Nxd5 6.Bg2 Nb6 7.O-O Be7 8.d3 O-O 9.Be3",
    "1.c4 e5 2.Nc3 Nf6 3.Nf3 Nc6 4.e3 Bb4 5.Qc2 O-O 6.Nd5 Re8 7.a3 Bf8",
    "1.c4 c5 2.Nf3 Nf6 3.Nc3 d5 4.cxd5 Nxd5 5.e3 Nxc3 6.bxc3 g6 7.Bb5+ Bd7",
    "1.c4 c5 2.Nc3 Nc6 3.g3 g6 4.Bg2 Bg7 5.Nf3 Nf6 6.O-O O-O 7.d3 d6",
    "1.c4 Nf6 2.Nc3 e6 3.e4 d5 4.e5 d4 5.exf6 dxc3 6.bxc3 Qxf6",
    "1.c4 Nf6 2.Nc3 g6 3.e4 d6 4.d4 Bg7 5.Nf3 O-O 6.Be2 e5 7.O-O Nc6 8.d5 Ne7",
    "1.c4 e6 2.Nc3 d5 3.d4 Nf6 4.Bg5 Be7 5.e3 O-O 6.Nf3 h6 7.Bh4 b6",

    # Reti Opening
    "1.Nf3 d5 2.g3 Nf6 3.Bg2 g6 4.O-O Bg7 5.d3 O-O 6.Nbd2 Nc6",
    "1.Nf3 d5 2.c4 e6 3.g3 Nf6 4.Bg2 Be7 5.O-O O-O 6.b3 c5 7.Bb2 Nc6",
    "1.Nf3 d5 2.c4 c6 3.b3 Nf6 4.Bb2 Bg4 5.g3 e6 6.Bg2",
    "1.Nf3 Nf6 2.g3 g6 3.Bg2 Bg7 4.O-O O-O 5.d3 d6 6.c4 Nc6",

    # Bird Opening
    "1.f4 d5 2.Nf3 Nf6 3.e3 g6 4.Be2 Bg7 5.O-O O-O 6.d3",
    "1.f4 d5 2.Nf3 Nf6 3.g3 g6 4.Bg2 Bg7 5.O-O O-O 6.d3 c5",

    # Dutch Defense
    "1.d4 f5 2.g3 Nf6 3.Bg2 g6 4.Nf3 Bg7 5.O-O O-O 6.c4 d6 7.Nc3 Nc6",
    "1.d4 f5 2.c4 Nf6 3.g3 e6 4.Bg2 Be7 5.Nf3 O-O 6.O-O d5 7.Nc3 c6",
    "1.d4 f5 2.c4 Nf6 3.Nc3 g6 4.g3 Bg7 5.Bg2 O-O 6.Nf3 d6 7.O-O Nc6",

    # ── B: Semi-open games ─────────────────────────────────────

    # Sicilian Defense - Open
    "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 a6 6.Be3 e5 7.Nb3 Be6 8.f3 Be7 9.Qd2 O-O 10.O-O-O",
    "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 a6 6.Bg5 e6 7.f4 Be7 8.Qf3 Qc7 9.O-O-O Nbd7",
    "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 a6 6.Be2 e5 7.Nb3 Be7 8.O-O O-O 9.Be3 Be6",
    "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 a6 6.f3 e5 7.Nb3 Be6 8.Be3 Be7 9.Qd2 Nbd7",
    "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 g6 6.Be3 Bg7 7.f3 O-O 8.Qd2 Nc6 9.Bc4",
    "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 g6 6.Be2 Bg7 7.O-O O-O 8.Be3 Nc6",

    # Sicilian - Sveshnikov
    "1.e4 c5 2.Nf3 Nc6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 e5 6.Ndb5 d6 7.Bg5 a6 8.Na3 b5 9.Nd5 Be7 10.Bxf6 Bxf6 11.c3",

    # Sicilian - Classical
    "1.e4 c5 2.Nf3 Nc6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 d6 6.Be2 e5 7.Nf3 h6 8.O-O Be7 9.Re1 O-O",

    # Sicilian - Scheveningen
    "1.e4 c5 2.Nf3 d6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 e6 6.Be2 Be7 7.O-O O-O 8.f4 Nc6 9.Be3 a6",
    "1.e4 c5 2.Nf3 e6 3.d4 cxd4 4.Nxd4 Nf6 5.Nc3 d6 6.Be2 Be7 7.O-O O-O 8.f4 a6 9.Be3",

    # Sicilian - Kan
    "1.e4 c5 2.Nf3 e6 3.d4 cxd4 4.Nxd4 a6 5.Nc3 Qc7 6.Bd3 Nf6 7.O-O Bc5",
    "1.e4 c5 2.Nf3 e6 3.d4 cxd4 4.Nxd4 a6 5.Bd3 Nf6 6.O-O Qc7 7.Qe2 d6",

    # Sicilian - Taimanov
    "1.e4 c5 2.Nf3 e6 3.d4 cxd4 4.Nxd4 Nc6 5.Nc3 Qc7 6.Be3 a6 7.Bd3 Nf6 8.O-O Be7",
    "1.e4 c5 2.Nf3 e6 3.d4 cxd4 4.Nxd4 Nc6 5.Nc3 a6 6.Nxc6 bxc6 7.Bd3 d5 8.O-O Nf6",

    # Sicilian - Rossolimo / Moscow
    "1.e4 c5 2.Nf3 Nc6 3.Bb5 g6 4.O-O Bg7 5.Re1 e5 6.Bxc6 dxc6 7.d3 Nf6",
    "1.e4 c5 2.Nf3 Nc6 3.Bb5 e6 4.O-O Nge7 5.Re1 a6 6.Bf1 d5",
    "1.e4 c5 2.Nf3 d6 3.Bb5+ Bd7 4.Bxd7+ Qxd7 5.O-O Nc6 6.c3 Nf6 7.Re1",

    # Sicilian - Alapin
    "1.e4 c5 2.c3 Nf6 3.e5 Nd5 4.d4 cxd4 5.Nf3 Nc6 6.cxd4 d6 7.Bc4 Nb6 8.Bb5 dxe5 9.Nxe5",
    "1.e4 c5 2.c3 d5 3.exd5 Qxd5 4.d4 Nf6 5.Nf3 e6 6.Be2 cxd4 7.cxd4 Be7",

    # Sicilian - Closed
    "1.e4 c5 2.Nc3 Nc6 3.g3 g6 4.Bg2 Bg7 5.d3 d6 6.f4 e6 7.Nf3 Nge7 8.O-O O-O",

    # French Defense
    "1.e4 e6 2.d4 d5 3.Nc3 Bb4 4.e5 c5 5.a3 Bxc3+ 6.bxc3 Ne7 7.Qg4 O-O 8.Nf3",
    "1.e4 e6 2.d4 d5 3.Nc3 Nf6 4.Bg5 Be7 5.e5 Nfd7 6.Bxe7 Qxe7 7.f4 O-O 8.Nf3 c5",
    "1.e4 e6 2.d4 d5 3.Nc3 Nf6 4.e5 Nfd7 5.f4 c5 6.Nf3 Nc6 7.Be3 cxd4 8.Nxd4 Bc5",
    "1.e4 e6 2.d4 d5 3.Nd2 Nf6 4.e5 Nfd7 5.Bd3 c5 6.c3 Nc6 7.Ne2 cxd4 8.cxd4 f6",
    "1.e4 e6 2.d4 d5 3.Nd2 c5 4.exd5 exd5 5.Ngf3 Nc6 6.Bb5 Bd6 7.dxc5 Bxc5 8.O-O Nge7",
    "1.e4 e6 2.d4 d5 3.e5 c5 4.c3 Nc6 5.Nf3 Qb6 6.a3 c4 7.Nbd2",
    "1.e4 e6 2.d4 d5 3.Nc3 dxe4 4.Nxe4 Bd7 5.Nf3 Bc6 6.Bd3 Nd7 7.O-O Ngf6",

    # Caro-Kann Defense
    "1.e4 c6 2.d4 d5 3.Nc3 dxe4 4.Nxe4 Bf5 5.Ng3 Bg6 6.h4 h6 7.Nf3 Nd7 8.h5 Bh7 9.Bd3 Bxd3 10.Qxd3 e6",
    "1.e4 c6 2.d4 d5 3.Nc3 dxe4 4.Nxe4 Nd7 5.Nf3 Ngf6 6.Nxf6+ Nxf6 7.Bc4 Bf5",
    "1.e4 c6 2.d4 d5 3.e5 Bf5 4.Nf3 e6 5.Be2 c5 6.Be3 cxd4 7.Nxd4 Ne7 8.Nd2 Nbc6",
    "1.e4 c6 2.d4 d5 3.e5 Bf5 4.Nf3 e6 5.Be2 Nd7 6.O-O Ne7 7.Nbd2 h6",
    "1.e4 c6 2.d4 d5 3.exd5 cxd5 4.Bd3 Nc6 5.c3 Nf6 6.Bf4 Bg4 7.Qb3 Qd7",
    "1.e4 c6 2.d4 d5 3.Nd2 dxe4 4.Nxe4 Bf5 5.Ng3 Bg6 6.h4 h6 7.Nf3 Nd7",
    "1.e4 c6 2.Nf3 d5 3.d3 dxe4 4.dxe4 Qxd1+ 5.Kxd1 Nf6 6.Nbd2",

    # Pirc/Modern Defense
    "1.e4 d6 2.d4 Nf6 3.Nc3 g6 4.f4 Bg7 5.Nf3 O-O 6.Bd3 Na6 7.O-O c5",
    "1.e4 d6 2.d4 Nf6 3.Nc3 g6 4.Nf3 Bg7 5.Be2 O-O 6.O-O c6 7.a4 Nbd7",
    "1.e4 d6 2.d4 Nf6 3.Nc3 g6 4.Be3 Bg7 5.Qd2 O-O 6.Bh6 c6",
    "1.e4 g6 2.d4 Bg7 3.Nc3 d6 4.Nf3 Nf6 5.Be2 O-O 6.O-O c6",

    # Alekhine Defense
    "1.e4 Nf6 2.e5 Nd5 3.d4 d6 4.Nf3 g6 5.Be2 Bg7 6.O-O O-O 7.c4 Nb6 8.exd6 cxd6",
    "1.e4 Nf6 2.e5 Nd5 3.d4 d6 4.Nf3 Bg4 5.Be2 e6 6.O-O Be7 7.c4 Nb6",
    "1.e4 Nf6 2.e5 Nd5 3.c4 Nb6 4.d4 d6 5.exd6 cxd6 6.Nc3 g6 7.Be3 Bg7 8.Rc1 O-O 9.b3",

    # Scandinavian Defense
    "1.e4 d5 2.exd5 Qxd5 3.Nc3 Qa5 4.d4 Nf6 5.Nf3 Bf5 6.Bc4 e6 7.Bd2 c6",
    "1.e4 d5 2.exd5 Qxd5 3.Nc3 Qd6 4.d4 Nf6 5.Nf3 a6 6.Be2 Bg4",
    "1.e4 d5 2.exd5 Nf6 3.d4 Nxd5 4.c4 Nb6 5.Nf3 g6 6.Nc3 Bg7 7.Be2 O-O",

    # ── C: Open games ──────────────────────────────────────────

    # King's Gambit
    "1.e4 e5 2.f4 exf4 3.Nf3 g5 4.h4 g4 5.Ne5 Nf6 6.d4 d6",
    "1.e4 e5 2.f4 exf4 3.Nf3 d5 4.exd5 Nf6 5.Bc4 Nxd5 6.O-O Be7",
    "1.e4 e5 2.f4 Bc5 3.Nf3 d6 4.Nc3 Nf6 5.Bc4 O-O",

    # Vienna Game
    "1.e4 e5 2.Nc3 Nf6 3.f4 d5 4.fxe5 Nxe4 5.Nf3 Be7",
    "1.e4 e5 2.Nc3 Nc6 3.Bc4 Nf6 4.d3 Bb4 5.Nf3",

    # Italian Game
    "1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.c3 Nf6 5.d4 exd4 6.cxd4 Bb4+ 7.Bd2 Bxd2+ 8.Nbxd2 d5 9.exd5 Nxd5",
    "1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.d3 Nf6 5.O-O d6 6.c3 a6 7.a4 Ba7 8.Re1 O-O",
    "1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.O-O Nf6 5.d3 d6 6.c3 O-O 7.Re1 a6 8.a4 Ba7",
    "1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6 4.d3 Bc5 5.O-O d6 6.c3 O-O 7.Re1 a6",
    "1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6 4.d3 Be7 5.O-O O-O 6.Re1 d6 7.a4 Na5 8.Ba2",

    # Evans Gambit
    "1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.b4 Bxb4 5.c3 Ba5 6.d4 exd4 7.O-O d6",
    "1.e4 e5 2.Nf3 Nc6 3.Bc4 Bc5 4.b4 Bxb4 5.c3 Be7 6.d4 Na5 7.Be2 exd4 8.Qxd4 Nf6",

    # Two Knights Defense
    "1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6 4.Ng5 d5 5.exd5 Na5 6.Bb5+ c6 7.dxc6 bxc6 8.Be2 h6",
    "1.e4 e5 2.Nf3 Nc6 3.Bc4 Nf6 4.d4 exd4 5.O-O Nxe4 6.Re1 d5 7.Bxd5 Qxd5 8.Nc3",

    # Scotch Game
    "1.e4 e5 2.Nf3 Nc6 3.d4 exd4 4.Nxd4 Nf6 5.Nxc6 bxc6 6.e5 Qe7 7.Qe2 Nd5 8.c4 Ba6",
    "1.e4 e5 2.Nf3 Nc6 3.d4 exd4 4.Nxd4 Bc5 5.Nxc6 Qf6 6.Qd2 dxc6 7.Nc3",
    "1.e4 e5 2.Nf3 Nc6 3.d4 exd4 4.Nxd4 Nf6 5.Nc3 Bb4 6.Nxc6 bxc6 7.Bd3 d5 8.exd5",

    # Ruy Lopez / Spanish Game
    "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7 6.Re1 b5 7.Bb3 d6 8.c3 O-O 9.h3 Na5 10.Bc2 c5 11.d4",
    "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7 6.Re1 b5 7.Bb3 O-O 8.c3 d6 9.h3 Nb8 10.d4 Nbd7",
    "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Nxe4 6.d4 b5 7.Bb3 d5 8.dxe5 Be6 9.c3",
    "1.e4 e5 2.Nf3 Nc6 3.Bb5 Nf6 4.O-O Nxe4 5.d4 Nd6 6.Bxc6 dxc6 7.dxe5 Nf5 8.Qxd8+ Kxd8",
    "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 d6 5.c3 Bd7 6.d4 Nge7",
    "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Bxc6 dxc6 5.O-O Qd6 6.d3 Be7 7.Nbd2",
    "1.e4 e5 2.Nf3 Nc6 3.Bb5 f5 4.Nc3 fxe4 5.Nxe4 d5 6.Nxe5 dxe4",
    "1.e4 e5 2.Nf3 Nc6 3.Bb5 Bc5 4.c3 Nf6 5.O-O O-O 6.d4 Bb6",

    # Petroff Defense
    "1.e4 e5 2.Nf3 Nf6 3.Nxe5 d6 4.Nf3 Nxe4 5.d4 d5 6.Bd3 Nc6 7.O-O Be7 8.c4 Nb4 9.Be2",
    "1.e4 e5 2.Nf3 Nf6 3.Nxe5 d6 4.Nf3 Nxe4 5.d4 d5 6.Bd3 Be7 7.O-O Nc6 8.Re1 Bg4",
    "1.e4 e5 2.Nf3 Nf6 3.d4 Nxe4 4.Bd3 d5 5.Nxe5 Nd7 6.Nxd7 Bxd7 7.O-O Bd6",

    # Philidor Defense
    "1.e4 e5 2.Nf3 d6 3.d4 Nf6 4.Nc3 Nbd7 5.Bc4 Be7 6.O-O O-O 7.a4",
    "1.e4 e5 2.Nf3 d6 3.d4 exd4 4.Nxd4 Nf6 5.Nc3 Be7 6.Be2 O-O 7.O-O",

    # Four Knights
    "1.e4 e5 2.Nf3 Nc6 3.Nc3 Nf6 4.Bb5 Bb4 5.O-O O-O 6.d3 d6 7.Bg5",
    "1.e4 e5 2.Nf3 Nc6 3.Nc3 Nf6 4.d4 exd4 5.Nxd4 Bb4 6.Nxc6 bxc6 7.Bd3 d5",

    # ── D: Closed and semi-closed games ────────────────────────

    # Queen's Gambit Declined
    "1.d4 d5 2.c4 e6 3.Nc3 Nf6 4.cxd5 exd5 5.Bg5 c6 6.e3 Bf5 7.Qf3 Bg6 8.Bxf6 Qxf6 9.Qxf6 gxf6",
    "1.d4 d5 2.c4 e6 3.Nc3 Nf6 4.Bg5 Be7 5.e3 O-O 6.Nf3 Nbd7 7.Rc1 c6 8.Bd3 dxc4 9.Bxc4 Nd5",
    "1.d4 d5 2.c4 e6 3.Nc3 Nf6 4.Bg5 Be7 5.Nf3 h6 6.Bh4 O-O 7.e3 b6 8.Bd3",
    "1.d4 d5 2.c4 e6 3.Nc3 Be7 4.Nf3 Nf6 5.Bf4 O-O 6.e3 c5 7.dxc5 Bxc5",
    "1.d4 d5 2.c4 e6 3.Nf3 Nf6 4.Nc3 Be7 5.Bg5 h6 6.Bh4 O-O 7.e3 b6",
    "1.d4 d5 2.c4 e6 3.Nf3 Nf6 4.g3 Be7 5.Bg2 O-O 6.O-O dxc4 7.Qc2 a6 8.a4 Bd7",

    # Queen's Gambit Accepted
    "1.d4 d5 2.c4 dxc4 3.Nf3 Nf6 4.e3 e6 5.Bxc4 c5 6.O-O a6 7.Qe2 b5 8.Bb3 Bb7",
    "1.d4 d5 2.c4 dxc4 3.Nf3 Nf6 4.e3 e6 5.Bxc4 c5 6.O-O a6 7.dxc5 Bxc5 8.Qxd8+ Kxd8",
    "1.d4 d5 2.c4 dxc4 3.e4 Nf6 4.e5 Nd5 5.Bxc4 Nb6 6.Bd3 Nc6 7.Be3",

    # Slav Defense
    "1.d4 d5 2.c4 c6 3.Nf3 Nf6 4.Nc3 dxc4 5.a4 Bf5 6.e3 e6 7.Bxc4 Bb4 8.O-O O-O",
    "1.d4 d5 2.c4 c6 3.Nf3 Nf6 4.Nc3 e6 5.e3 Nbd7 6.Bd3 dxc4 7.Bxc4 b5 8.Bd3 Bb7",
    "1.d4 d5 2.c4 c6 3.Nf3 Nf6 4.e3 Bg4 5.Nc3 e6 6.h3 Bh5 7.cxd5 exd5",
    "1.d4 d5 2.c4 c6 3.Nc3 Nf6 4.e3 e6 5.Nf3 Nbd7 6.Qc2 Bd6 7.Bd3 O-O 8.O-O dxc4 9.Bxc4",

    # Semi-Slav
    "1.d4 d5 2.c4 c6 3.Nf3 Nf6 4.Nc3 e6 5.Bg5 h6 6.Bxf6 Qxf6 7.e3 Nd7 8.Bd3 dxc4 9.Bxc4 g6",
    "1.d4 d5 2.c4 c6 3.Nf3 Nf6 4.Nc3 e6 5.e3 Nbd7 6.Bd3 dxc4 7.Bxc4 b5 8.Bd3 a6 9.e4 c5",

    # London System
    "1.d4 d5 2.Bf4 Nf6 3.e3 c5 4.c3 Nc6 5.Nd2 e6 6.Ngf3 Bd6 7.Bg3 O-O",
    "1.d4 Nf6 2.Bf4 d5 3.e3 e6 4.Nf3 c5 5.c3 Nc6 6.Nbd2 Bd6 7.Bg3 O-O",
    "1.d4 d5 2.Bf4 Nf6 3.Nf3 c5 4.e3 Nc6 5.Nbd2 e6 6.c3 Bd6 7.Bg3",
    "1.d4 Nf6 2.Bf4 g6 3.e3 Bg7 4.Nf3 O-O 5.Be2 d6 6.O-O Nbd7 7.h3",

    # Catalan
    "1.d4 Nf6 2.c4 e6 3.g3 d5 4.Bg2 Be7 5.Nf3 O-O 6.O-O dxc4 7.Qc2 a6 8.a4",
    "1.d4 Nf6 2.c4 e6 3.g3 d5 4.Bg2 dxc4 5.Nf3 Be7 6.O-O O-O 7.Qc2 a6 8.a4",
    "1.d4 Nf6 2.c4 e6 3.g3 d5 4.Nf3 Be7 5.Bg2 O-O 6.O-O dxc4 7.Qc2 a6 8.Qxc4 b5 9.Qc2 Bb7",

    # Grunfeld Defense
    "1.d4 Nf6 2.c4 g6 3.Nc3 d5 4.cxd5 Nxd5 5.e4 Nxc3 6.bxc3 Bg7 7.Nf3 c5 8.Be3 Qa5 9.Qd2 O-O",
    "1.d4 Nf6 2.c4 g6 3.Nc3 d5 4.cxd5 Nxd5 5.e4 Nxc3 6.bxc3 Bg7 7.Bc4 O-O 8.Ne2 c5",
    "1.d4 Nf6 2.c4 g6 3.Nc3 d5 4.Nf3 Bg7 5.Qb3 dxc4 6.Qxc4 O-O 7.e4 Na6",
    "1.d4 Nf6 2.c4 g6 3.Nc3 d5 4.cxd5 Nxd5 5.Bd2 Bg7 6.e4 Nxc3 7.Bxc3 O-O 8.Qd2",

    # Trompowsky
    "1.d4 Nf6 2.Bg5 Ne4 3.Bf4 d5 4.e3 c5 5.Bd3 Nc6 6.Nf3",
    "1.d4 Nf6 2.Bg5 e6 3.e4 h6 4.Bxf6 Qxf6 5.Nc3 d6 6.Qd2",
    "1.d4 Nf6 2.Bg5 d5 3.e3 c5 4.Bxf6 gxf6 5.c4 dxc4 6.Bxc4 cxd4",

    # Torre Attack
    "1.d4 Nf6 2.Nf3 e6 3.Bg5 c5 4.e3 Be7 5.Nbd2 d5 6.c3",

    # Colle System
    "1.d4 d5 2.Nf3 Nf6 3.e3 e6 4.Bd3 c5 5.c3 Nc6 6.Nbd2 Bd6 7.O-O O-O",

    # Queen's Indian
    "1.d4 Nf6 2.c4 e6 3.Nf3 b6 4.g3 Ba6 5.b3 Bb4+ 6.Bd2 Be7 7.Bg2 c6 8.Bc3 d5 9.Ne5",
    "1.d4 Nf6 2.c4 e6 3.Nf3 b6 4.g3 Bb7 5.Bg2 Be7 6.O-O O-O 7.Nc3 Ne4 8.Qc2 Nxc3",
    "1.d4 Nf6 2.c4 e6 3.Nf3 b6 4.a3 Bb7 5.Nc3 d5 6.cxd5 Nxd5 7.Qc2",

    # Bogo-Indian
    "1.d4 Nf6 2.c4 e6 3.Nf3 Bb4+ 4.Bd2 Bxd2+ 5.Qxd2 O-O 6.g3 d5 7.Bg2 Nbd7",
    "1.d4 Nf6 2.c4 e6 3.Nf3 Bb4+ 4.Nbd2 O-O 5.a3 Be7 6.e4 d5 7.e5 Nfd7",

    # ── E: Indian defenses ─────────────────────────────────────

    # Nimzo-Indian Defense
    "1.d4 Nf6 2.c4 e6 3.Nc3 Bb4 4.Qc2 O-O 5.a3 Bxc3+ 6.Qxc3 b6 7.Bg5 Bb7 8.e3",
    "1.d4 Nf6 2.c4 e6 3.Nc3 Bb4 4.e3 O-O 5.Bd3 d5 6.Nf3 c5 7.O-O dxc4 8.Bxc4 Nbd7",
    "1.d4 Nf6 2.c4 e6 3.Nc3 Bb4 4.e3 O-O 5.Nf3 d5 6.Bd3 c5 7.O-O Nc6 8.a3 Bxc3 9.bxc3 dxc4 10.Bxc4",
    "1.d4 Nf6 2.c4 e6 3.Nc3 Bb4 4.f3 d5 5.a3 Bxc3+ 6.bxc3 c5 7.cxd5 exd5 8.e3 O-O",
    "1.d4 Nf6 2.c4 e6 3.Nc3 Bb4 4.Qb3 c5 5.dxc5 Nc6 6.Nf3 Ne4 7.Bd2 Nxd2",

    # King's Indian Defense
    "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.Nf3 O-O 6.Be2 e5 7.O-O Nc6 8.d5 Ne7 9.Ne1 Nd7 10.f3 f5",
    "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.f3 O-O 6.Be3 e5 7.d5 Nh5 8.Qd2 f5 9.O-O-O",
    "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.Nf3 O-O 6.Be2 e5 7.Be3 Ng4 8.Bg5 f6 9.Bh4 Nc6",
    "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.f4 O-O 6.Nf3 c5 7.d5 e6 8.Be2 exd5 9.cxd5",
    "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.e4 d6 5.Be2 O-O 6.Bg5 c5 7.d5 e6 8.Nf3",
    "1.d4 Nf6 2.c4 g6 3.Nc3 Bg7 4.g3 O-O 5.Bg2 d6 6.Nf3 Nbd7 7.O-O e5 8.e4 c6",
    "1.d4 Nf6 2.c4 g6 3.Nf3 Bg7 4.g3 O-O 5.Bg2 d6 6.O-O Nbd7 7.Nc3 e5 8.e4 c6",

    # King's Indian - Fianchetto
    "1.d4 Nf6 2.c4 g6 3.g3 Bg7 4.Bg2 O-O 5.Nc3 d6 6.Nf3 Nbd7 7.O-O e5 8.e4 c6",

    # Benoni Defense
    "1.d4 Nf6 2.c4 c5 3.d5 e6 4.Nc3 exd5 5.cxd5 d6 6.e4 g6 7.Nf3 Bg7 8.Be2 O-O 9.O-O",
    "1.d4 Nf6 2.c4 c5 3.d5 e6 4.Nc3 exd5 5.cxd5 d6 6.Nf3 g6 7.e4 Bg7 8.Be2 O-O 9.O-O Re8",

    # Budapest Gambit
    "1.d4 Nf6 2.c4 e5 3.dxe5 Ng4 4.Bf4 Nc6 5.Nf3 Bb4+ 6.Nbd2 Qe7",

    # Old Indian
    "1.d4 Nf6 2.c4 d6 3.Nc3 e5 4.Nf3 Nbd7 5.e4 Be7 6.Be2 O-O 7.O-O c6",

    # ── Common transpositions and misc ─────────────────────────

    # King's Indian Attack
    "1.Nf3 d5 2.g3 Nf6 3.Bg2 c6 4.O-O Bg4 5.d3 Nbd7 6.Nbd2 e5",
    "1.e4 e6 2.d3 d5 3.Nd2 Nf6 4.Ngf3 c5 5.g3 Nc6 6.Bg2 Be7 7.O-O O-O",

    # Symmetrical English
    "1.c4 c5 2.Nc3 Nc6 3.Nf3 Nf6 4.g3 d5 5.cxd5 Nxd5 6.Bg2 Nc7 7.O-O e5",

    # e4 e5 misc - Center Game
    "1.e4 e5 2.d4 exd4 3.Qxd4 Nc6 4.Qe3 Nf6 5.Nc3 Bb4 6.Bd2 O-O",

    # Bishop's Opening
    "1.e4 e5 2.Bc4 Nf6 3.d3 c6 4.Nf3 d5 5.Bb3 Bd6 6.O-O O-O",

    # Ponziani
    "1.e4 e5 2.Nf3 Nc6 3.c3 d5 4.Qa4 Nf6 5.Nxe5 Bd6",

    # d4 d5 misc
    "1.d4 d5 2.Nf3 Nf6 3.c4 e6 4.e3 Be7 5.Bd3 O-O 6.O-O c5 7.b3",
    "1.d4 d5 2.c4 e6 3.Nc3 c5 4.cxd5 exd5 5.Nf3 Nc6 6.g3 Nf6 7.Bg2 Be7 8.O-O O-O",

    # Misc openings
    "1.b3 e5 2.Bb2 Nc6 3.e3 d5 4.Bb5 Bd6 5.Nf3 Qe7",
    "1.g3 d5 2.Bg2 e5 3.d3 Nf6 4.Nf3 Nc6 5.O-O Be7",
]

# Module-level cache
_book_moves = None


def _build_book():
    """Parse all opening lines and build a set of (zobrist_hash, move) tuples."""
    global _book_moves
    if _book_moves is not None:
        return

    _book_moves = set()

    for line in OPENING_LINES:
        board = chess.Board()
        # Strip move numbers and parse SAN tokens
        tokens = line.split()
        for token in tokens:
            # Skip move numbers like "1.", "2.", "10."
            if token.endswith("."):
                continue
            # Remove move number prefix if attached like "1.e4"
            if "." in token:
                token = token.split(".")[-1]
            if not token:
                continue
            try:
                move = board.parse_san(token)
                zh = chess.polyglot.zobrist_hash(board)
                _book_moves.add((zh, move.from_square, move.to_square, move.promotion))
                board.push(move)
            except (chess.InvalidMoveError, chess.IllegalMoveError, ValueError):
                break  # Stop processing this line on error


def is_book_move(board: chess.Board, move: chess.Move) -> bool:
    """Check if a move in the given position is a known book move."""
    _build_book()
    zh = chess.polyglot.zobrist_hash(board)
    return (zh, move.from_square, move.to_square, move.promotion) in _book_moves


def book_moves_for_position(board: chess.Board) -> list[chess.Move]:
    """Return all book moves for the given position."""
    _build_book()
    zh = chess.polyglot.zobrist_hash(board)
    result = []
    for bh, from_sq, to_sq, promo in _book_moves:
        if bh == zh:
            result.append(chess.Move(from_sq, to_sq, promo))
    return result
