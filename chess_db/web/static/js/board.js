/**
 * Chess board renderer with SVG pieces.
 */

const PIECE_FILES = {
    'K': 'wK', 'Q': 'wQ', 'R': 'wR', 'B': 'wB', 'N': 'wN', 'P': 'wP',
    'k': 'bK', 'q': 'bQ', 'r': 'bR', 'b': 'bB', 'n': 'bN', 'p': 'bP',
};

const PIECES_PATH = '/static/pieces/';
const START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

class ChessBoard {
    constructor(boardEl, options = {}) {
        this.el = boardEl;
        this.flipped = options.flipped || false;
        this.position = this.fenToBoard(START_FEN);
        this.lastMove = null;
        this.render();
    }

    fenToBoard(fen) {
        const board = [];
        const rows = fen.split(' ')[0].split('/');
        for (const row of rows) {
            const rank = [];
            for (const ch of row) {
                if (ch >= '1' && ch <= '8') {
                    for (let i = 0; i < parseInt(ch); i++) rank.push('');
                } else {
                    rank.push(ch);
                }
            }
            board.push(rank);
        }
        return board;
    }

    setPosition(fen) {
        this.position = this.fenToBoard(fen);
        this.render();
    }

    setHighlight(fromSq, toSq) {
        this.lastMove = { from: fromSq, to: toSq };
        this.render();
    }

    render() {
        this.el.innerHTML = '';
        const grid = document.createElement('div');
        grid.className = 'chess-board';

        for (let r = 0; r < 8; r++) {
            for (let f = 0; f < 8; f++) {
                const dispR = this.flipped ? 7 - r : r;
                const dispF = this.flipped ? 7 - f : f;
                const sq = document.createElement('div');
                const isLight = (dispR + dispF) % 2 === 0;
                sq.className = 'sq ' + (isLight ? 'sq-light' : 'sq-dark');

                const sqName = String.fromCharCode(97 + dispF) + (8 - dispR);
                if (this.lastMove &&
                    (sqName === this.lastMove.from || sqName === this.lastMove.to)) {
                    sq.classList.add('sq-highlight');
                }

                // Coordinate labels on the edges
                if (f === 0) {
                    const rankLabel = document.createElement('span');
                    rankLabel.className = 'coord coord-rank';
                    rankLabel.textContent = 8 - dispR;
                    sq.appendChild(rankLabel);
                }
                if (r === 7) {
                    const fileLabel = document.createElement('span');
                    fileLabel.className = 'coord coord-file';
                    fileLabel.textContent = String.fromCharCode(97 + dispF);
                    sq.appendChild(fileLabel);
                }

                const piece = this.position[dispR][dispF];
                if (piece && PIECE_FILES[piece]) {
                    const img = document.createElement('img');
                    img.src = PIECES_PATH + PIECE_FILES[piece] + '.svg';
                    img.className = 'piece-img';
                    img.draggable = false;
                    sq.appendChild(img);
                }
                grid.appendChild(sq);
            }
        }
        this.el.appendChild(grid);
    }
}

/**
 * Minimal chess logic to replay moves from SAN.
 * Enough to play through a game and get FEN at each position.
 */
class ChessGame {
    constructor() {
        this.reset();
    }

    reset() {
        this.board = [
            ['r','n','b','q','k','b','n','r'],
            ['p','p','p','p','p','p','p','p'],
            ['','','','','','','',''],
            ['','','','','','','',''],
            ['','','','','','','',''],
            ['','','','','','','',''],
            ['P','P','P','P','P','P','P','P'],
            ['R','N','B','Q','K','B','N','R'],
        ];
        this.turn = 'w';
        this.castling = 'KQkq';
        this.enPassant = '-';
        this.halfmove = 0;
        this.fullmove = 1;
        this.positions = [this.fen()];
        this.moveUcis = [null];
    }

    fen() {
        let fen = '';
        for (let r = 0; r < 8; r++) {
            let empty = 0;
            for (let f = 0; f < 8; f++) {
                if (this.board[r][f] === '') {
                    empty++;
                } else {
                    if (empty > 0) { fen += empty; empty = 0; }
                    fen += this.board[r][f];
                }
            }
            if (empty > 0) fen += empty;
            if (r < 7) fen += '/';
        }
        fen += ` ${this.turn} ${this.castling || '-'} ${this.enPassant} ${this.halfmove} ${this.fullmove}`;
        return fen;
    }

    isWhite(piece) { return piece >= 'A' && piece <= 'Z'; }
    isBlack(piece) { return piece >= 'a' && piece <= 'z'; }

    applyUci(uci) {
        const fromF = uci.charCodeAt(0) - 97;
        const fromR = 8 - parseInt(uci[1]);
        const toF = uci.charCodeAt(2) - 97;
        const toR = 8 - parseInt(uci[3]);
        const promo = uci.length > 4 ? uci[4] : null;

        const piece = this.board[fromR][fromF];
        const captured = this.board[toR][toF];

        // En passant capture
        if ((piece === 'P' || piece === 'p') && toF !== fromF && captured === '') {
            this.board[fromR][toF] = '';
        }

        this.board[toR][toF] = piece;
        this.board[fromR][fromF] = '';

        // Promotion
        if (promo) {
            this.board[toR][toF] = this.turn === 'w'
                ? promo.toUpperCase()
                : promo.toLowerCase();
        }

        // Castling - move rook
        if (piece === 'K' || piece === 'k') {
            if (fromF === 4 && toF === 6) { // Kingside
                this.board[fromR][5] = this.board[fromR][7];
                this.board[fromR][7] = '';
            } else if (fromF === 4 && toF === 2) { // Queenside
                this.board[fromR][3] = this.board[fromR][0];
                this.board[fromR][0] = '';
            }
        }

        // Update castling rights
        if (piece === 'K') this.castling = this.castling.replace(/[KQ]/g, '');
        if (piece === 'k') this.castling = this.castling.replace(/[kq]/g, '');
        if (fromR === 7 && fromF === 7 || toR === 7 && toF === 7) this.castling = this.castling.replace('K', '');
        if (fromR === 7 && fromF === 0 || toR === 7 && toF === 0) this.castling = this.castling.replace('Q', '');
        if (fromR === 0 && fromF === 7 || toR === 0 && toF === 7) this.castling = this.castling.replace('k', '');
        if (fromR === 0 && fromF === 0 || toR === 0 && toF === 0) this.castling = this.castling.replace('q', '');
        if (!this.castling) this.castling = '-';

        // En passant
        if ((piece === 'P' || piece === 'p') && Math.abs(fromR - toR) === 2) {
            const epR = (fromR + toR) / 2;
            this.enPassant = String.fromCharCode(97 + toF) + (8 - epR);
        } else {
            this.enPassant = '-';
        }

        // Turn
        if (this.turn === 'b') this.fullmove++;
        this.turn = this.turn === 'w' ? 'b' : 'w';

        this.positions.push(this.fen());
        this.moveUcis.push(uci);
    }

    loadMoves(moveData) {
        this.reset();
        for (const m of moveData) {
            this.applyUci(m.uci);
        }
    }

    getFen(ply) {
        if (ply < 0 || ply >= this.positions.length) return this.positions[0];
        return this.positions[ply];
    }

    getUci(ply) {
        if (ply < 1 || ply >= this.moveUcis.length) return null;
        return this.moveUcis[ply];
    }
}

/**
 * Game navigator - ties board, moves, and eval together.
 */
class GameNavigator {
    constructor(boardEl, moveData) {
        this.moveData = moveData || [];
        this.game = new ChessGame();
        this.board = new ChessBoard(boardEl);
        this.currentPly = 0;

        if (this.moveData.length > 0) {
            this.game.loadMoves(this.moveData);
        }

        this.setupControls();
        this.setupMoveTable();
        this.goto(0);
    }

    setupControls() {
        document.getElementById('btn-start')?.addEventListener('click', () => this.goto(0));
        document.getElementById('btn-prev')?.addEventListener('click', () => this.goto(this.currentPly - 1));
        document.getElementById('btn-next')?.addEventListener('click', () => this.goto(this.currentPly + 1));
        document.getElementById('btn-end')?.addEventListener('click', () => this.goto(this.moveData.length));

        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowLeft') { this.goto(this.currentPly - 1); e.preventDefault(); }
            if (e.key === 'ArrowRight') { this.goto(this.currentPly + 1); e.preventDefault(); }
            if (e.key === 'Home') { this.goto(0); e.preventDefault(); }
            if (e.key === 'End') { this.goto(this.moveData.length); e.preventDefault(); }
        });
    }

    setupMoveTable() {
        document.querySelectorAll('.move-cell').forEach(cell => {
            cell.addEventListener('click', () => {
                const ply = parseInt(cell.dataset.ply);
                this.goto(ply);
            });
        });
    }

    goto(ply) {
        ply = Math.max(0, Math.min(ply, this.moveData.length));
        this.currentPly = ply;

        // Update board
        this.board.setPosition(this.game.getFen(ply));
        const uci = this.game.getUci(ply);
        if (uci) {
            const from = uci.substring(0, 2);
            const to = uci.substring(2, 4);
            this.board.setHighlight(from, to);
        }

        // Update move table highlight
        document.querySelectorAll('.move-cell').forEach(cell => {
            cell.classList.remove('active');
            if (parseInt(cell.dataset.ply) === ply) {
                cell.classList.add('active');
                cell.scrollIntoView({ block: 'nearest' });
            }
        });

        // Update eval display
        this.updateEval(ply);

        // Update eval chart cursor
        this.updateChartCursor(ply);
    }

    updateEval(ply) {
        const evalEl = document.getElementById('current-eval');
        const barFill = document.getElementById('eval-bar-fill');
        const barLabel = document.getElementById('eval-bar-label');

        if (ply === 0 || !this.moveData[ply - 1]) {
            if (evalEl) evalEl.textContent = '0.00';
            if (barFill) barFill.style.width = '50%';
            if (barLabel) barLabel.textContent = '0.00';
            return;
        }

        const m = this.moveData[ply - 1];
        let scoreStr, pct;

        if (m.scoreMate !== null && m.scoreMate !== undefined) {
            scoreStr = '#' + (m.scoreMate > 0 ? '+' : '') + m.scoreMate;
            pct = m.scoreMate > 0 ? 100 : 0;
        } else if (m.scoreCp !== null && m.scoreCp !== undefined) {
            scoreStr = (m.scoreCp >= 0 ? '+' : '') + (m.scoreCp / 100).toFixed(2);
            pct = Math.max(2, Math.min(98, 50 + (m.scoreCp / 10)));
        } else {
            scoreStr = '?';
            pct = 50;
        }

        if (evalEl) evalEl.textContent = scoreStr;
        if (barFill) barFill.style.width = pct + '%';
        if (barLabel) barLabel.textContent = scoreStr;
    }

    updateChartCursor(ply) {
        const cursor = document.getElementById('chart-cursor');
        const chart = document.getElementById('eval-chart');
        if (!cursor || !chart || this.moveData.length === 0) return;
        const pct = (ply / this.moveData.length) * 100;
        cursor.style.left = pct + '%';
    }
}

/**
 * Draw evaluation chart on a canvas.
 */
function drawEvalChart(canvasId, moveData) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !moveData || moveData.length === 0) return;

    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.offsetWidth * 2;
    const H = canvas.height = canvas.offsetHeight * 2;
    ctx.scale(1, 1);

    const midY = H / 2;
    const maxCp = 500;

    // Background
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, W, H);

    // Center line
    ctx.strokeStyle = '#2a3a5e';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, midY);
    ctx.lineTo(W, midY);
    ctx.stroke();

    // Fill areas
    const stepX = W / moveData.length;

    // White advantage area
    ctx.beginPath();
    ctx.moveTo(0, midY);
    for (let i = 0; i < moveData.length; i++) {
        const m = moveData[i];
        let cp;
        if (m.scoreMate !== null && m.scoreMate !== undefined) {
            cp = m.scoreMate > 0 ? maxCp : -maxCp;
        } else {
            cp = Math.max(-maxCp, Math.min(maxCp, m.scoreCp || 0));
        }
        const y = midY - (cp / maxCp) * midY;
        ctx.lineTo(i * stepX + stepX / 2, y);
    }
    ctx.lineTo(W, midY);
    ctx.closePath();

    // Fill white advantage
    const grad = ctx.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, 'rgba(255,255,255,0.3)');
    grad.addColorStop(0.5, 'rgba(255,255,255,0.05)');
    grad.addColorStop(0.5, 'rgba(0,0,0,0.05)');
    grad.addColorStop(1, 'rgba(0,0,0,0.3)');
    ctx.fillStyle = grad;
    ctx.fill();

    // Line
    ctx.beginPath();
    for (let i = 0; i < moveData.length; i++) {
        const m = moveData[i];
        let cp;
        if (m.scoreMate !== null && m.scoreMate !== undefined) {
            cp = m.scoreMate > 0 ? maxCp : -maxCp;
        } else {
            cp = Math.max(-maxCp, Math.min(maxCp, m.scoreCp || 0));
        }
        const x = i * stepX + stepX / 2;
        const y = midY - (cp / maxCp) * midY;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = '#e94560';
    ctx.lineWidth = 2;
    ctx.stroke();

    // Blunder markers
    for (let i = 0; i < moveData.length; i++) {
        const m = moveData[i];
        if (m.classification === 'blunder' || m.classification === 'mistake') {
            const x = i * stepX + stepX / 2;
            let cp;
            if (m.scoreMate !== null && m.scoreMate !== undefined) {
                cp = m.scoreMate > 0 ? maxCp : -maxCp;
            } else {
                cp = Math.max(-maxCp, Math.min(maxCp, m.scoreCp || 0));
            }
            const y = midY - (cp / maxCp) * midY;
            ctx.beginPath();
            ctx.arc(x, y, 4, 0, Math.PI * 2);
            ctx.fillStyle = m.classification === 'blunder' ? '#f44336' : '#ff9800';
            ctx.fill();
        }
    }
}
