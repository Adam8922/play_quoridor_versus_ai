import random
import copy
from typing import List, Tuple, Optional

from Board import Board, PlayerId, Position, Wall, WallOrientation, MoveResult


class AIPlayer:
    """
    AI opponent for Quoridor with three difficulty levels.

    Easy  — random legal move.
    Medium — greedy: advance if winning, otherwise place the most blocking wall.
    Hard  — depth-3 minimax with alpha-beta pruning and smart move generation.
    """

    def __init__(self, difficulty: str = "easy"):
        self.difficulty = difficulty

    # ==========================================================================
    # PUBLIC ENTRY POINT
    # ==========================================================================
    def choose_move(self, board: Board, player: PlayerId):
        """
        Returns a tuple: ("move", Position) or ("wall", Wall).
        Returns None only if the board has no legal moves (should never happen).
        """
        if self.difficulty == "easy":
            return self._easy_move(board, player)
        elif self.difficulty == "medium":
            return self._medium_move(board, player)
        elif self.difficulty == "hard":
            return self._hard_move(board, player)
        return self._easy_move(board, player)

    # ==========================================================================
    # EASY AI — random legal move
    # ==========================================================================
    def _easy_move(self, board: Board, player: PlayerId):
        moves = [("move", pos) for pos in board.get_valid_pawn_moves(player)]

        if board.get_player_wall_count(player) > 0:
            for r in range(8):
                for c in range(8):
                    for orientation in WallOrientation:
                        wall = Wall(Position(r, c), orientation)
                        if board.is_valid_wall_placement(wall):
                            moves.append(("wall", wall))

        return random.choice(moves) if moves else None

    # ==========================================================================
    # MEDIUM AI — greedy path-length heuristic
    # ==========================================================================
    def _medium_move(self, board: Board, player: PlayerId):
        opponent = self._opponent(player)

        my_path = board.get_shortest_path(player)
        opp_path = board.get_shortest_path(opponent)

        if not my_path:
            return None  # Shouldn't happen in a valid game state

        # Advance if already ahead or equal
        if len(my_path) <= len(opp_path):
            return ("move", my_path[1])

        # Try to find the wall that lengthens the opponent's path the most
        best_wall = None
        best_gain = 0

        if board.get_player_wall_count(player) > 0:
            for wall in self._wall_candidates(board, opponent):
                if not board.is_valid_wall_placement(wall):
                    continue

                # Simulate placement without full board copy
                board._add_wall_edges(wall)
                new_opp_path = board.get_shortest_path(opponent)
                new_my_path = board.get_shortest_path(player)
                board._remove_wall_edges(wall)

                # Must not trap either player (is_valid_wall_placement +
                # place_wall already enforce this, but we're simulating manually)
                if not new_opp_path or not new_my_path:
                    continue

                gain = len(new_opp_path) - len(opp_path)
                if gain > best_gain:
                    best_gain = gain
                    best_wall = wall

        if best_wall and best_gain > 0:
            return ("wall", best_wall)

        # Fallback: just advance
        return ("move", my_path[1])

    # ==========================================================================
    # HARD AI — depth-3 minimax with alpha-beta pruning
    # ==========================================================================
    def _hard_move(self, board: Board, player: PlayerId):
        best_score = float("-inf")
        best_move = None
        alpha = float("-inf")
        beta = float("inf")

        for move in self._candidate_moves(board, player):
            child = copy.deepcopy(board)
            self._apply_move(child, player, move)

            score = self._minimax(child, depth=2, is_max=False,
                                  ai_player=player, alpha=alpha, beta=beta)

            if score > best_score:
                best_score = score
                best_move = move

            alpha = max(alpha, best_score)

        # Fallback to medium if minimax found nothing (edge case)
        return best_move if best_move else self._medium_move(board, player)

    def _minimax(self, board: Board, depth: int, is_max: bool,
                 ai_player: PlayerId, alpha: float, beta: float) -> float:
        """Alpha-beta minimax. ai_player is always the maximising side."""
        current_player = ai_player if is_max else self._opponent(ai_player)

        # Terminal / horizon check
        if depth == 0:
            return self._evaluate(board, ai_player)

        if board.has_player_won(ai_player):
            return 10000 + depth   # Prefer faster wins
        if board.has_player_won(self._opponent(ai_player)):
            return -10000 - depth  # Prefer slower losses

        moves = self._candidate_moves(board, current_player)
        if not moves:
            return self._evaluate(board, ai_player)

        if is_max:
            best = float("-inf")
            for move in moves:
                child = copy.deepcopy(board)
                self._apply_move(child, current_player, move)
                val = self._minimax(child, depth - 1, False, ai_player, alpha, beta)
                best = max(best, val)
                alpha = max(alpha, best)
                if beta <= alpha:
                    break  # Beta cut-off
            return best
        else:
            best = float("inf")
            for move in moves:
                child = copy.deepcopy(board)
                self._apply_move(child, current_player, move)
                val = self._minimax(child, depth - 1, True, ai_player, alpha, beta)
                best = min(best, val)
                beta = min(beta, best)
                if beta <= alpha:
                    break  # Alpha cut-off
            return best

    # ==========================================================================
    # EVALUATION FUNCTION
    # ==========================================================================
    def _evaluate(self, board: Board, player: PlayerId) -> float:
        """
        Heuristic score from `player`'s perspective.
        Primary factor: path length difference (positive = player is ahead).
        Secondary factor: slight bonus for having more walls in reserve.
        """
        opponent = self._opponent(player)

        my_path = board.get_shortest_path(player)
        opp_path = board.get_shortest_path(opponent)

        if not my_path:
            return -10000
        if not opp_path:
            return 10000

        path_score = len(opp_path) - len(my_path)

        # Small wall-reserve bonus: walls are options, options are good
        wall_score = (board.get_player_wall_count(player) -
                      board.get_player_wall_count(opponent)) * 0.1

        return path_score + wall_score

    # ==========================================================================
    # MOVE GENERATION
    # ==========================================================================
    def _candidate_moves(self, board: Board, player: PlayerId) -> list:
        """
        Generates a focused, ordered list of candidate moves for minimax.
        Pawn moves come first (they're usually best), then strategic walls.
        """
        opponent = self._opponent(player)
        moves = []

        # --- Pawn moves (always include all of them) ---
        pawn_moves = board.get_valid_pawn_moves(player)
        my_path = board.get_shortest_path(player)

        # Sort pawn moves: path-advancing moves first
        path_set = set()
        if my_path and len(my_path) > 1:
            path_set = {(p.row, p.col) for p in my_path}

        pawn_moves.sort(key=lambda p: (0 if (p.row, p.col) in path_set else 1))
        moves.extend(("move", p) for p in pawn_moves)

        # --- Wall moves (only if we have walls and it's worth considering) ---
        if board.get_player_wall_count(player) > 0:
            for wall in self._wall_candidates(board, opponent):
                if board.is_valid_wall_placement(wall):
                    moves.append(("wall", wall))

        return moves

    def _wall_candidates(self, board: Board, opponent: PlayerId) -> List[Wall]:
        """
        Returns a focused list of wall candidates near the opponent's path.
        This keeps move generation fast without sacrificing too much quality.

        FIX: The original code broke out of the orientation loop early, meaning
        vertical walls were never generated. Both orientations are now always tried.
        """
        opp_path = board.get_shortest_path(opponent)

        if not opp_path:
            return []

        # Collect rows that appear in the opponent's path
        path_rows = {p.row for p in opp_path}

        candidates = []
        for r in range(8):
            # Focus on rows near the opponent's path
            if not any(abs(r - pr) <= 2 for pr in path_rows):
                continue
            for c in range(8):
                for orientation in WallOrientation:   # FIX: try BOTH orientations
                    wall = Wall(Position(r, c), orientation)
                    candidates.append(wall)

        return candidates

    # ==========================================================================
    # HELPERS
    # ==========================================================================
    @staticmethod
    def _opponent(player: PlayerId) -> PlayerId:
        return PlayerId.PLAYER_2 if player == PlayerId.PLAYER_1 else PlayerId.PLAYER_1

    @staticmethod
    def _apply_move(board: Board, player: PlayerId, move) -> None:
        """Applies a move tuple to a board in-place."""
        move_type, action = move
        if move_type == "move":
            board.move_pawn(player, action)
        else:
            board.place_wall(player, action)
