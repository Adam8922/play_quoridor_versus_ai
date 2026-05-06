import random
import copy
from typing import Tuple, Optional
from collections import deque

# Import from your base file
from Board import Board, PlayerId, Position, Wall, WallOrientation


class AIPlayer:
    def __init__(self, difficulty="easy"):
        self.difficulty = difficulty

    # =========================
    # MAIN ENTRY
    # =========================
    def choose_move(self, board: Board, player: PlayerId):
        if self.difficulty == "easy":
            return self._easy_move(board, player)
        elif self.difficulty == "medium":
            return self._medium_move(board, player)
        elif self.difficulty == "hard":
            return self._hard_move(board, player)

    # =========================
    # EASY AI
    # =========================
    def _easy_move(self, board: Board, player: PlayerId):
        moves = []

        # pawn moves
        for pos in board.get_valid_pawn_moves(player):
            moves.append(("move", pos))

        # wall placements (random sampling)
        if board.get_player_wall_count(player) > 0:
            for r in range(8):
                for c in range(8):
                    for orientation in [WallOrientation.HORIZONTAL, WallOrientation.VERTICAL]:
                        wall = Wall(Position(r, c), orientation)
                        if board.is_valid_wall_placement(player, wall):
                            moves.append(("wall", wall))

        return random.choice(moves) if moves else None

    # =========================
    # MEDIUM AI
    # =========================
    def _medium_move(self, board: Board, player: PlayerId):
        opponent = PlayerId.PLAYER_2 if player == PlayerId.PLAYER_1 else PlayerId.PLAYER_1

        my_path = board.get_shortest_path(player)
        opp_path = board.get_shortest_path(opponent)

        # If no path is found for any reason
        if not my_path:
            return None

        # 1. If I am close to winning -> Move pawn
        if len(my_path) <= len(opp_path):
            return ("move", my_path[1])

        # 2. Try to block the opponent with a wall
        if board.get_player_wall_count(player) > 0:
            best_wall = None
            best_block = 0

            for r in range(8):
                for c in range(8):
                    for orientation in [WallOrientation.HORIZONTAL, WallOrientation.VERTICAL]:
                        wall = Wall(Position(r, c), orientation)

                        if not board.is_valid_wall_placement(player, wall):
                            continue

                        # simulate
                        board._add_wall_edges(wall)
                        new_path = board.get_shortest_path(opponent)
                        board._remove_wall_edges(wall)

                        if not new_path:
                            continue

                        block_value = len(new_path) - len(opp_path)

                        if block_value > best_block:
                            best_block = block_value
                            best_wall = wall

            if best_wall:
                return ("wall", best_wall)

        # fallback
        return ("move", my_path[1])

    # =========================
    # HARD AI (MINIMAX with Alpha-Beta Pruning)
    # =========================
    def _hard_move(self, board: Board, player: PlayerId):
        opponent = PlayerId.PLAYER_2 if player == PlayerId.PLAYER_1 else PlayerId.PLAYER_1
        
        # Get best moves using alpha-beta pruning
        best_score = float("-inf")
        best_move = None
        
        for move in self._get_all_moves_limited(board, player):
            new_board = copy.deepcopy(board)
            self._apply_move(new_board, player, move)
            score = self._minimax_alphabeta(new_board, 1, False, player, float("-inf"), float("inf"))
            
            if score > best_score:
                best_score = score
                best_move = move
        
        return best_move if best_move else self._medium_move(board, player)
    
    def _get_all_moves_limited(self, board: Board, player: PlayerId):
        """Get moves with aggressive limiting for speed"""
        moves = []
        
        for pos in board.get_valid_pawn_moves(player):
            moves.append(("move", pos))
        
        # Only add walls if we have few moves
        pawn_moves = board.get_valid_pawn_moves(player)
        if board.get_player_wall_count(player) > 0 and len(pawn_moves) <= 2:
            opponent = PlayerId.PLAYER_2 if player == PlayerId.PLAYER_1 else PlayerId.PLAYER_1
            opp_pos = board.get_player_position(opponent)
            
            # Only check very limited range near opponent
            for r in [opp_pos.row - 1, opp_pos.row, opp_pos.row + 1]:
                if 0 <= r < 8:
                    for c in range(8):
                        for orientation in [WallOrientation.HORIZONTAL, WallOrientation.VERTICAL]:
                            wall = Wall(Position(r, c), orientation)
                            if board.is_valid_wall_placement(player, wall):
                                moves.append(("wall", wall))
                                break  # Limit to 1 wall per position
        
        return moves if moves else [("move", pawn_moves[0])] if pawn_moves else []
    
    def _minimax_alphabeta(self, board: Board, depth: int, is_max: bool, player: PlayerId, alpha, beta):
        """Minimax with alpha-beta pruning"""
        opponent = PlayerId.PLAYER_2 if player == PlayerId.PLAYER_1 else PlayerId.PLAYER_1
        
        if depth == 0:
            return self._evaluate(board, player)
        
        if is_max:
            best = float("-inf")
            for move in self._get_all_moves_limited(board, player):
                new_board = copy.deepcopy(board)
                self._apply_move(new_board, player, move)
                val = self._minimax_alphabeta(new_board, depth - 1, False, player, alpha, beta)
                best = max(best, val)
                alpha = max(alpha, best)
                if beta <= alpha:
                    break  # Beta cutoff
            return best
        else:
            best = float("inf")
            for move in self._get_all_moves_limited(board, opponent):
                new_board = copy.deepcopy(board)
                self._apply_move(new_board, opponent, move)
                val = self._minimax_alphabeta(new_board, depth - 1, True, player, alpha, beta)
                best = min(best, val)
                beta = min(beta, best)
                if beta <= alpha:
                    break  # Alpha cutoff
            return best

    # =========================
    # EVALUATION FUNCTION
    # =========================
    def _evaluate(self, board: Board, player: PlayerId):
        opponent = PlayerId.PLAYER_2 if player == PlayerId.PLAYER_1 else PlayerId.PLAYER_1

        my_path = board.get_shortest_path(player)
        opp_path = board.get_shortest_path(opponent)

        if not my_path:
            return -1000
        if not opp_path:
            return 1000

        return len(opp_path) - len(my_path)

    # =========================
    # HELPERS
    # =========================
    def _get_all_moves(self, board: Board, player: PlayerId):
        moves = []

        for pos in board.get_valid_pawn_moves(player):
            moves.append(("move", pos))

        if board.get_player_wall_count(player) > 0:
            # Limit to strategic positions instead of all 64
            opponent = PlayerId.PLAYER_2 if player == PlayerId.PLAYER_1 else PlayerId.PLAYER_1
            opp_pos = board.get_player_position(opponent)
            
            # Check positions near opponent and between players
            search_range = range(max(0, opp_pos.row - 3), min(9, opp_pos.row + 4))
            
            for r in search_range:
                for c in range(8):
                    for orientation in [WallOrientation.HORIZONTAL, WallOrientation.VERTICAL]:
                        wall = Wall(Position(r, c), orientation)
                        if board.is_valid_wall_placement(player, wall):
                            moves.append(("wall", wall))

        return moves
    
    def _apply_move(self, board: Board, player: PlayerId, move):
        if move[0] == "move":
            board.move_pawn(player, move[1])
        else:
            board.place_wall(player, move[1])