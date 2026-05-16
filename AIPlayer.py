import copy
import random
from collections import deque
from typing import List, Optional, Dict, Tuple

from Board import Board, PlayerId, Position, Wall, WallOrientation


class AIPlayer:
    """
    AI opponent for Quoridor with three difficulty levels.

    Easy   — lazy greedy: moves toward goal, occasionally drops a random wall.
    Medium — greedy: advance if winning, otherwise place the most blocking wall.
    Hard   — depth-3 minimax with alpha-beta pruning.

    Pathfinding split:
      Board.get_shortest_path()             → wall-graph BFS (no pawns).
                                              Used by place_wall() for trap detection.
      AIPlayer.get_shortest_path_with_pawns() → pawn-aware BFS (respects jump rules).
                                              Used by the AI heuristic / move ordering.
    """

    def __init__(self, difficulty: str = "easy"):
        self.difficulty = difficulty

    # =========================================================================
    # Public entry point
    # =========================================================================

    def choose_move(self, board: Board, player: PlayerId):
        """
        Returns ("move", Position) or ("wall", Wall).
        Returns None only if the board has no legal moves (should never happen).
        """
        if self.difficulty == "easy":
            return self._easy_move(board, player)
        elif self.difficulty == "medium":
            return self._medium_move(board, player)
        elif self.difficulty == "hard":
            return self._hard_move(board, player)
        return self._easy_move(board, player)

    # =========================================================================
    # Pawn-aware BFS  (lives here, NOT in Board)
    # =========================================================================

    def get_shortest_path_with_pawns(
        self, board: Board, player: PlayerId
    ) -> List[Position]:
        """
        BFS that respects full Quoridor pawn-movement rules:
          - Walls block edges (same as the wall-graph BFS).
          - The opponent's square cannot be a landing square.
          - When the opponent is adjacent, straight and diagonal jumps are allowed.

        This gives the AI an accurate distance-to-goal that accounts for the
        fact that jumping over an opponent can shorten or lengthen the path.

        Returns a list of Positions from start to goal, or [] if no path exists.
        """
        opponent_id = self._opponent(player)
        start = board.get_player_position(player)
        opp   = board.get_player_position(opponent_id)
        goal_row = 0 if player == PlayerId.PLAYER_1 else (board.BOARD_SIZE - 1)

        queue = deque([start])
        came_from: Dict[Tuple[int,int], Optional[Tuple[int,int]]] = {
            (start.row, start.col): None
        }

        while queue:
            cur = queue.popleft()
            cur_t = (cur.row, cur.col)

            if cur.row == goal_row:
                path, node = [], cur_t
                while node is not None:
                    path.append(Position(node[0], node[1]))
                    node = came_from[node]
                path.reverse()
                return path

            for nb in self._pawn_neighbours(board, cur, opp, board.BOARD_SIZE):
                nb_t = (nb.row, nb.col)
                if nb_t not in came_from:
                    came_from[nb_t] = cur_t
                    queue.append(nb)

        return []

    # =========================================================================
    # Easy AI
    # =========================================================================

    def _easy_move(self, board: Board, player: PlayerId):
        """
        'Lazy Greedy' — usually moves toward the goal, 
        occasionally drops a random wall near the opponent.
        """
        my_path = self.get_shortest_path_with_pawns(board, player)
        opponent = self._opponent(player)

        # 20% chance to place a wall if they have any
        if random.random() < 0.2 and board.get_player_wall_count(player) > 0:
            candidates = self._wall_candidates(board, opponent)
            valid_candidates = [w for w in candidates if board.is_valid_wall_placement(player, w)]
            if valid_candidates:
                return ("wall", random.choice(valid_candidates))

        # Otherwise, just move toward the goal
        if my_path and len(my_path) > 1:
            return ("move", my_path[1])
        
        # Fallback to random if no path found (shouldn't happen)
        moves = [("move", p) for p in board.get_valid_pawn_moves(player)]
        return random.choice(moves) if moves else None

    # =========================================================================
    # Medium AI — greedy
    # =========================================================================

    def _medium_move(self, board: Board, player: PlayerId):
        opponent = self._opponent(player)

        my_path  = self.get_shortest_path_with_pawns(board, player)
        opp_path = self.get_shortest_path_with_pawns(board, opponent)

        if not my_path:
            return None

        # Advance if already equal or ahead
        if len(my_path) <= len(opp_path):
            return ("move", my_path[1])

        # Try to find the wall that lengthens the opponent's path the most
        best_wall, best_gain = None, 0

        if board.get_player_wall_count(player) > 0:
            for wall in self._wall_candidates(board, opponent):
                if not board.is_valid_wall_placement(player, wall):
                    continue

                # Simulate without a full deepcopy — add, measure, remove
                board._add_wall_edges(wall)
                new_opp = self.get_shortest_path_with_pawns(board, opponent)
                new_me  = self.get_shortest_path_with_pawns(board, player)
                board._remove_wall_edges(wall)

                # Skip if this traps either player
                if not new_opp or not new_me:
                    continue

                gain = len(new_opp) - len(opp_path)
                if gain > best_gain:
                    best_gain = gain
                    best_wall = wall

        if best_wall and best_gain > 0:
            return ("wall", best_wall)

        return ("move", my_path[1])

    # =========================================================================
    # Hard AI — depth-3 minimax with alpha-beta pruning
    # =========================================================================

    def _hard_move(self, board: Board, player: PlayerId):
        best_score = float("-inf")
        best_move  = None
        alpha = float("-inf")
        beta  = float("inf")

        # Create one working copy of the board to explore state space fast
        working_board = copy.deepcopy(board)

        for move in self._candidate_moves(working_board, player, max_walls=20):
            undo_data = self._apply_move(working_board, player, move)
            score = self._minimax(working_board, depth=3, is_max=False,
                                  ai_player=player, alpha=alpha, beta=beta)
            self._undo_move(working_board, player, move, undo_data)
            if score > best_score:
                best_score = score
                best_move  = move
            alpha = max(alpha, best_score)

        return best_move if best_move else self._medium_move(board, player)

    def _minimax(self, board: Board, depth: int, is_max: bool,
                 ai_player: PlayerId, alpha: float, beta: float) -> float:
        current_player = ai_player if is_max else self._opponent(ai_player)

        if board.has_player_won(ai_player):
            return 10000 + depth        # Prefer faster wins
        if board.has_player_won(self._opponent(ai_player)):
            return -10000 - depth       # Prefer slower losses
        if depth == 0:
            return self._evaluate(board, ai_player)

        moves = self._candidate_moves(board, current_player, max_walls=10)
        if not moves:
            return self._evaluate(board, ai_player)

        if is_max:
            best = float("-inf")
            for move in moves:
                undo_data = self._apply_move(board, current_player, move)
                val = self._minimax(board, depth - 1, False, ai_player, alpha, beta)
                self._undo_move(board, current_player, move, undo_data)
                best  = max(best, val)
                alpha = max(alpha, best)
                if beta <= alpha:
                    break
            return best
        else:
            best = float("inf")
            for move in moves:
                undo_data = self._apply_move(board, current_player, move)
                val = self._minimax(board, depth - 1, True, ai_player, alpha, beta)
                self._undo_move(board, current_player, move, undo_data)
                best = min(best, val)
                beta = min(beta, best)
                if beta <= alpha:
                    break
            return best

    # =========================================================================
    # Evaluation
    # =========================================================================

    def _evaluate(self, board: Board, player: PlayerId) -> float:
        """
        Score from `player`'s perspective.
        Uses pawn-aware BFS distances so jump opportunities are valued correctly.
        """
        opponent = self._opponent(player)

        my_path  = self.get_shortest_path_with_pawns(board, player)
        opp_path = self.get_shortest_path_with_pawns(board, opponent)

        if not my_path:  return -10000
        if not opp_path: return  10000

        path_score = len(opp_path) - len(my_path)
        wall_score = (board.get_player_wall_count(player) -
                      board.get_player_wall_count(opponent)) * 0.1

        return path_score + wall_score

    # =========================================================================
    # Move generation
    # =========================================================================

    def _candidate_moves(self, board: Board, player: PlayerId, max_walls=20) -> list:
        """Ordered candidate moves: path-advancing pawn moves first, then best walls."""
        opponent = self._opponent(player)
        moves = []

        pawn_moves = board.get_valid_pawn_moves(player)
        my_path = self.get_shortest_path_with_pawns(board, player)
        path_set = {(p.row, p.col) for p in my_path} if my_path else set()

        # Path-advancing moves first, others after
        pawn_moves.sort(key=lambda p: (0 if (p.row, p.col) in path_set else 1))
        moves.extend(("move", p) for p in pawn_moves)

        # Only add the top N wall candidates to keep search fast
        if board.get_player_wall_count(player) > 0:
            valid_walls = []
            for wall in self._wall_candidates(board, opponent):
                if board.is_valid_wall_placement(player, wall):
                    valid_walls.append(wall)
            
            # score each wall by how much it lengthens opponent path
            opp_path_len = len(self.get_shortest_path_with_pawns(board, opponent))
            scored = []
            # Check up to 40 walls for heuristic to keep it very hard
            for wall in valid_walls[:min(40, max_walls * 2)]:  
                board._add_wall_edges(wall)
                new_opp = self.get_shortest_path_with_pawns(board, opponent)
                board._remove_wall_edges(wall)
                if new_opp:
                    gain = len(new_opp) - opp_path_len
                    scored.append((gain, wall))
            
            # sort by gain descending, take the best ones
            scored.sort(key=lambda x: -x[0])
            for gain, wall in scored[:max_walls]:
                moves.append(("wall", wall))

        return moves

    def _wall_candidates(self, board: Board, opponent: PlayerId) -> List[Wall]:
        """
        Returns walls near the opponent's path.
        Restored vision to 2 squares to capture long-range strategic blocks.
        """
        opp_path = board.get_shortest_path(opponent)
        if not opp_path:
            return []

        path_cells = {(p.row, p.col) for p in opp_path}
        candidates = []
        for r in range(8):
            for c in range(8):
                # Restored to 2 squares for better strategic depth
                near_path = any(abs(r - pr) <= 2 and abs(c - pc) <= 2 
                               for pr, pc in path_cells)
                if not near_path:
                    continue
                for orientation in WallOrientation:
                    candidates.append(Wall(Position(r, c), orientation))
        return candidates

    # =========================================================================
    # Pawn-neighbour helper (core of pawn-aware BFS)
    # =========================================================================

    @staticmethod
    def _pawn_neighbours(
        board: Board,
        pos: Position,
        opp: Position,
        size: int
    ) -> List[Position]:
        """
        Returns all squares reachable in one move from `pos`, given the opponent
        is at `opp`.  Mirrors Quoridor rules exactly:
          - Normal step to any adjacent non-opponent square not blocked by a wall.
          - Straight jump over the opponent if adjacent and path is clear.
          - Diagonal jump if adjacent, straight is wall-blocked or off-board,
            and the diagonal edge is clear.
        Does NOT mutate any board state.
        """
        result = []
        opp_adjacent = abs(pos.row - opp.row) + abs(pos.col - opp.col) == 1

        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nb = Position(pos.row + dr, pos.col + dc)

            if not (0 <= nb.row < size and 0 <= nb.col < size):
                continue
            if board._is_wall_blocking(pos, nb):
                continue

            if nb.row == opp.row and nb.col == opp.col:
                # Opponent is here — attempt a jump instead of landing
                if not opp_adjacent:
                    continue  # Shouldn't happen, but guard anyway

                # Straight jump
                straight = Position(opp.row + dr, opp.col + dc)
                if (0 <= straight.row < size and 0 <= straight.col < size and
                        not board._is_wall_blocking(opp, straight)):
                    result.append(straight)
                else:
                    # Diagonal jumps (both perpendicular directions)
                    for ddr, ddc in [(-dc, dr), (dc, -dr)]:  # 90-degree rotations
                        diag = Position(opp.row + ddr, opp.col + ddc)
                        if (0 <= diag.row < size and 0 <= diag.col < size and
                                not board._is_wall_blocking(opp, diag)):
                            result.append(diag)
            else:
                result.append(nb)

        return result

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _opponent(player: PlayerId) -> PlayerId:
        return PlayerId.PLAYER_2 if player == PlayerId.PLAYER_1 else PlayerId.PLAYER_1

    @staticmethod
    def _apply_move(board: Board, player: PlayerId, move):
        move_type, action = move
        if move_type == "move":
            old_pos = board.get_player_position(player)
            board.move_pawn(player, action)
            return old_pos
        else:
            board.place_wall(player, action)
            return None

    @staticmethod
    def _undo_move(board: Board, player: PlayerId, move, undo_data) -> None:
        move_type, action = move
        if move_type == "move":
            if player == PlayerId.PLAYER_1:
                board._p1_pos = undo_data
            else:
                board._p2_pos = undo_data
            board._move_history.pop()
        else:
            board._remove_wall_edges(action)
            if player == PlayerId.PLAYER_1:
                board._p1_walls += 1
            else:
                board._p2_walls += 1
            board._placed_walls.pop()
            board._move_history.pop()
