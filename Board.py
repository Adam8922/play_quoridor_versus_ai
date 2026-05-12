from collections import deque
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict

# --- Enums ---
class PlayerId(Enum):
    PLAYER_1 = 1
    PLAYER_2 = 2

class WallOrientation(Enum):
    HORIZONTAL = 1
    VERTICAL = 2

class MoveType(Enum):
    PAWN_MOVE = 1
    WALL_PLACEMENT = 2

class MoveResult(Enum):
    SUCCESS = 1
    OUT_OF_WALLS = 2
    INVALID_PHYSICS = 3  # Overlaps or out of bounds
    TRAPS_PLAYER = 4     # Fails the BFS check
    INVALID_MOVE = 5     # Tried to jump a wall or move too far
    VICTORY = 6          # The player reached the opposite side!

# --- Core Data Structures ---
@dataclass
class Position:
    row: int = 0
    col: int = 0

@dataclass
class Wall:
    top_left: Position = field(default_factory=Position)
    orientation: WallOrientation = WallOrientation.HORIZONTAL

# --- History Tracking ---
@dataclass
class GameMove:
    player: PlayerId
    move_type: MoveType
    previous_pawn_pos: Optional[Position] = None
    new_pawn_pos: Optional[Position] = None
    placed_wall: Optional[Wall] = None

# --- The Model (Engine) ---
# DESIGN NOTE: This class acts as a stateless Engine. It intentionally does NOT track turns.
# Turn enforcement is the responsibility of the external Game Controller, allowing this
# engine to be freely manipulated by AI algorithms exploring future gamestates.
class Board:
    BOARD_SIZE: int = 9
    INITIAL_WALLS: int = 10

    def __init__(self):
        """Initializes the board, pawns, walls, and edge matrices."""
        # Player 1 starts at the bottom middle (Row 8, Col 4)
        self._p1_pos = Position(self.BOARD_SIZE - 1, self.BOARD_SIZE // 2)
        # Player 2 starts at the top middle (Row 0, Col 4)
        self._p2_pos = Position(0, self.BOARD_SIZE // 2)

        self._p1_walls = self.INITIAL_WALLS
        self._p2_walls = self.INITIAL_WALLS

        # History
        self._placed_walls: List[Wall] = []
        self._move_history: List[GameMove] = []

        # Horizontal edges: between rows, so (BOARD_SIZE-1) x BOARD_SIZE
        self._horizontal_edges = [
            [False] * self.BOARD_SIZE for _ in range(self.BOARD_SIZE - 1)
        ]
        # Vertical edges: between cols, so BOARD_SIZE x (BOARD_SIZE-1)
        self._vertical_edges = [
            [False] * (self.BOARD_SIZE - 1) for _ in range(self.BOARD_SIZE)
        ]
        # Peg grid to prevent cross-walls: (BOARD_SIZE-1) x (BOARD_SIZE-1)
        self._crosses_blocked = [
            [False] * (self.BOARD_SIZE - 1) for _ in range(self.BOARD_SIZE - 1)
        ]

    # --- State Modifiers ---
    def move_pawn(self, player: PlayerId, new_pos: Position) -> MoveResult:
        """Executes a pawn movement. Returns a MoveResult to the Controller."""
        if not self.is_valid_pawn_move(player, new_pos):
            return MoveResult.INVALID_MOVE

        start_pos = self.get_player_position(player)

        if player == PlayerId.PLAYER_1:
            self._p1_pos = new_pos
        else:
            self._p2_pos = new_pos

        self._move_history.append(GameMove(
            player=player,
            move_type=MoveType.PAWN_MOVE,
            previous_pawn_pos=start_pos,
            new_pawn_pos=new_pos
        ))

        if self.has_player_won(player):
            return MoveResult.VICTORY

        return MoveResult.SUCCESS

    def place_wall(self, player: PlayerId, wall: Wall) -> MoveResult:
        """Places a wall. Returns specific error codes for UI feedback."""
        if self.get_player_wall_count(player) <= 0:
            return MoveResult.OUT_OF_WALLS

        if not self.is_valid_wall_placement(wall):
            return MoveResult.INVALID_PHYSICS

        # Speculative write — test pathfinding before committing
        self._add_wall_edges(wall)

        if not self.get_shortest_path(PlayerId.PLAYER_1) or \
           not self.get_shortest_path(PlayerId.PLAYER_2):
            self._remove_wall_edges(wall)
            return MoveResult.TRAPS_PLAYER

        # Commit
        if player == PlayerId.PLAYER_1:
            self._p1_walls -= 1
        else:
            self._p2_walls -= 1

        self._placed_walls.append(wall)
        self._move_history.append(GameMove(
            player=player,
            move_type=MoveType.WALL_PLACEMENT,
            placed_wall=wall
        ))

        return MoveResult.SUCCESS

    def undo_last_move(self) -> bool:
        """Reverses the most recent move. Returns True if successful."""
        if not self._move_history:
            return False

        last_move = self._move_history.pop()

        if last_move.move_type == MoveType.WALL_PLACEMENT:
            self._remove_wall_edges(last_move.placed_wall)
            if last_move.player == PlayerId.PLAYER_1:
                self._p1_walls += 1
            else:
                self._p2_walls += 1
            if self._placed_walls:
                self._placed_walls.pop()

        elif last_move.move_type == MoveType.PAWN_MOVE:
            if last_move.player == PlayerId.PLAYER_1:
                self._p1_pos = last_move.previous_pawn_pos
            else:
                self._p2_pos = last_move.previous_pawn_pos

        return True

    def get_valid_pawn_moves(self, player: PlayerId) -> List[Position]:
        """
        Calculates all legally accessible squares for a player.
        Evaluates normal steps, straight jumps, and diagonal jumps.
        """
        current = self.get_player_position(player)
        offsets = [
            (-1, 0), (1, 0), (0, -1), (0, 1),   # Normal moves
            (-2, 0), (2, 0), (0, -2), (0, 2),    # Straight jumps
            (-1, -1), (-1, 1), (1, -1), (1, 1)   # Diagonal jumps
        ]

        valid_moves = []
        for row_offset, col_offset in offsets:
            target_pos = Position(current.row + row_offset, current.col + col_offset)
            if self.is_valid_pawn_move(player, target_pos):
                valid_moves.append(target_pos)

        return valid_moves

    def is_opponent_adjacent(self, player: PlayerId) -> bool:
        """Returns True if the opponent is exactly 1 square away (orthogonally)."""
        current = self.get_player_position(player)
        opponent = self._p2_pos if player == PlayerId.PLAYER_1 else self._p1_pos
        return abs(current.row - opponent.row) + abs(current.col - opponent.col) == 1

    # --- Validation ---
    def is_valid_pawn_move(self, player: PlayerId, new_pos: Position) -> bool:
        """
        The absolute source of truth for pawn movement.
        Validates grid boundaries, normal steps, straight jumps, and diagonal jumps.
        """
        current = self.get_player_position(player)

        # Bounds check
        if not (0 <= new_pos.row < self.BOARD_SIZE and
                0 <= new_pos.col < self.BOARD_SIZE):
            return False

        # Cannot stay in place
        if current == new_pos:
            return False

        opponent_id = PlayerId.PLAYER_2 if player == PlayerId.PLAYER_1 else PlayerId.PLAYER_1
        opponent = self.get_player_position(opponent_id)

        row_diff = new_pos.row - current.row
        col_diff = new_pos.col - current.col
        abs_r = abs(row_diff)
        abs_c = abs(col_diff)

        # --- Normal Move (1 step, not occupied by opponent) ---
        if abs_r + abs_c == 1 and new_pos != opponent:
            return not self._is_wall_blocking(current, new_pos)

        # --- Jump Maneuvers (only when opponent is adjacent) ---
        if self.is_opponent_adjacent(player):

            # Straight Jump (distance 2 in one axis)
            if (abs_r == 2 and col_diff == 0) or (abs_c == 2 and row_diff == 0):
                mid = Position(current.row + row_diff // 2, current.col + col_diff // 2)
                if mid != opponent:
                    return False
                if self._is_wall_blocking(current, opponent):
                    return False
                if self._is_wall_blocking(opponent, new_pos):
                    return False
                return True

            # Diagonal Jump (distance 1 in each axis)
            elif abs_r == 1 and abs_c == 1:
                # Target must be adjacent to opponent
                if abs(new_pos.row - opponent.row) + abs(new_pos.col - opponent.col) != 1:
                    return False

                # Opponent must be orthogonally adjacent (not diagonal) to us
                if not (current.row == opponent.row or current.col == opponent.col):
                    return False

                # Straight-ahead square behind the opponent
                jump_row = opponent.row + (opponent.row - current.row)
                jump_col = opponent.col + (opponent.col - current.col)
                jump_pos = Position(jump_row, jump_col)

                # Diagonal is only legal if the straight path is blocked
                is_straight_blocked = (
                    jump_row < 0 or jump_row >= self.BOARD_SIZE or
                    jump_col < 0 or jump_col >= self.BOARD_SIZE or
                    self._is_wall_blocking(opponent, jump_pos)
                )
                if not is_straight_blocked:
                    return False

                # No walls clipping through on the diagonal path
                if self._is_wall_blocking(current, opponent):
                    return False
                if self._is_wall_blocking(opponent, new_pos):
                    return False

                return True

        return False

    def is_valid_wall_placement(self, wall: Wall) -> bool:
        """
        Validates if a wall can physically be placed on the board.
        Checks board limits, intersection collisions, and overlapping.

        NOTE: The player parameter was removed — wall validity is board-state only,
        not player-specific. The caller is responsible for checking wall counts.
        """
        r = wall.top_left.row
        c = wall.top_left.col

        # Walls live on the 8×8 peg grid (indices 0–7)
        if r < 0 or r >= 8 or c < 0 or c >= 8:
            return False

        # Prevent a horizontal and vertical wall from crossing at the same peg
        if self._crosses_blocked[r][c]:
            return False

        if wall.orientation == WallOrientation.HORIZONTAL:
            if self._horizontal_edges[r][c] or self._horizontal_edges[r][c + 1]:
                return False
        elif wall.orientation == WallOrientation.VERTICAL:
            if self._vertical_edges[r][c] or self._vertical_edges[r + 1][c]:
                return False

        return True

    def has_player_won(self, player: PlayerId) -> bool:
        """Checks if a player has reached their goal row."""
        if player == PlayerId.PLAYER_1:
            return self._p1_pos.row == 0
        else:
            return self._p2_pos.row == (self.BOARD_SIZE - 1)

    def get_shortest_path(self, player: PlayerId) -> List[Position]:
        """
        Finds the shortest path to the goal using BFS.
        
        FIX: Previously mutated board state to reuse get_valid_pawn_moves.
        Now uses a safe internal helper that accepts an explicit position,
        so the real board state is never touched during pathfinding.
        """
        start_pos = self.get_player_position(player)
        goal_row = 0 if player == PlayerId.PLAYER_1 else (self.BOARD_SIZE - 1)

        queue = deque([start_pos])
        start_tuple = (start_pos.row, start_pos.col)
        came_from: Dict[tuple, Optional[tuple]] = {start_tuple: None}

        # Identify the opponent's current position for jump logic
        opponent_id = PlayerId.PLAYER_2 if player == PlayerId.PLAYER_1 else PlayerId.PLAYER_1
        opponent_pos = self.get_player_position(opponent_id)

        while queue:
            current = queue.popleft()
            curr_tuple = (current.row, current.col)

            if current.row == goal_row:
                # Reconstruct path
                path = []
                node = curr_tuple
                while node is not None:
                    path.append(Position(node[0], node[1]))
                    node = came_from[node]
                path.reverse()
                return path

            # Safe move generation: pass position explicitly, no board mutation
            for next_pos in self._get_valid_moves_from(player, current, opponent_pos):
                next_tuple = (next_pos.row, next_pos.col)
                if next_tuple not in came_from:
                    came_from[next_tuple] = curr_tuple
                    queue.append(next_pos)

        return []  # No path found

    def _get_valid_moves_from(
        self,
        player: PlayerId,
        pos: Position,
        opponent_pos: Position
    ) -> List[Position]:
        """
        Returns valid moves for `player` if they were standing at `pos`,
        with the opponent at `opponent_pos`. 
        Pure query — does NOT mutate any board state.
        """
        offsets = [
            (-1, 0), (1, 0), (0, -1), (0, 1),
            (-2, 0), (2, 0), (0, -2), (0, 2),
            (-1, -1), (-1, 1), (1, -1), (1, 1)
        ]

        valid = []
        opp_adjacent = (abs(pos.row - opponent_pos.row) +
                        abs(pos.col - opponent_pos.col)) == 1

        for dr, dc in offsets:
            target = Position(pos.row + dr, pos.col + dc)

            if not (0 <= target.row < self.BOARD_SIZE and
                    0 <= target.col < self.BOARD_SIZE):
                continue
            if target == pos:
                continue

            abs_r, abs_c = abs(dr), abs(dc)

            # Normal move
            if abs_r + abs_c == 1 and target != opponent_pos:
                if not self._is_wall_blocking(pos, target):
                    valid.append(target)

            elif opp_adjacent:
                # Straight jump
                if (abs_r == 2 and dc == 0) or (abs_c == 2 and dr == 0):
                    mid = Position(pos.row + dr // 2, pos.col + dc // 2)
                    if mid == opponent_pos:
                        if not self._is_wall_blocking(pos, opponent_pos) and \
                           not self._is_wall_blocking(opponent_pos, target):
                            valid.append(target)

                # Diagonal jump
                elif abs_r == 1 and abs_c == 1:
                    if abs(target.row - opponent_pos.row) + \
                       abs(target.col - opponent_pos.col) != 1:
                        continue
                    if not (pos.row == opponent_pos.row or pos.col == opponent_pos.col):
                        continue

                    jump_row = opponent_pos.row + (opponent_pos.row - pos.row)
                    jump_col = opponent_pos.col + (opponent_pos.col - pos.col)
                    jump_pos = Position(jump_row, jump_col)

                    straight_blocked = (
                        jump_row < 0 or jump_row >= self.BOARD_SIZE or
                        jump_col < 0 or jump_col >= self.BOARD_SIZE or
                        self._is_wall_blocking(opponent_pos, jump_pos)
                    )
                    if not straight_blocked:
                        continue
                    if self._is_wall_blocking(pos, opponent_pos):
                        continue
                    if self._is_wall_blocking(opponent_pos, target):
                        continue
                    valid.append(target)

        return valid

    # --- Getters ---
    def get_player_position(self, player: PlayerId) -> Position:
        if player == PlayerId.PLAYER_1:
            return self._p1_pos
        elif player == PlayerId.PLAYER_2:
            return self._p2_pos
        return Position(-1, -1)

    def get_player_wall_count(self, player: PlayerId) -> int:
        if player == PlayerId.PLAYER_1:
            return self._p1_walls
        elif player == PlayerId.PLAYER_2:
            return self._p2_walls
        return 0

    def get_placed_walls(self) -> List[Wall]:
        return self._placed_walls

    def get_move_history(self) -> List[GameMove]:
        return self._move_history

    # --- Private Helpers ---
    def _is_wall_blocking(self, current_pos: Position, target_pos: Position) -> bool:
        """Checks the edge matrix between two adjacent squares for a blocking wall."""
        if target_pos.row < current_pos.row:   # Moving UP
            return self._horizontal_edges[target_pos.row][current_pos.col]
        elif target_pos.row > current_pos.row:  # Moving DOWN
            return self._horizontal_edges[current_pos.row][current_pos.col]
        elif target_pos.col < current_pos.col:  # Moving LEFT
            return self._vertical_edges[current_pos.row][target_pos.col]
        elif target_pos.col > current_pos.col:  # Moving RIGHT
            return self._vertical_edges[current_pos.row][current_pos.col]
        return False

    def _add_wall_edges(self, wall: Wall) -> None:
        """Writes a wall into the edge matrices and claims its center peg."""
        r, c = wall.top_left.row, wall.top_left.col
        self._crosses_blocked[r][c] = True
        if wall.orientation == WallOrientation.HORIZONTAL:
            self._horizontal_edges[r][c] = True
            self._horizontal_edges[r][c + 1] = True
        elif wall.orientation == WallOrientation.VERTICAL:
            self._vertical_edges[r][c] = True
            self._vertical_edges[r + 1][c] = True

    def _remove_wall_edges(self, wall: Wall) -> None:
        """Erases a wall from the edge matrices and releases its center peg."""
        r, c = wall.top_left.row, wall.top_left.col
        self._crosses_blocked[r][c] = False
        if wall.orientation == WallOrientation.HORIZONTAL:
            self._horizontal_edges[r][c] = False
            self._horizontal_edges[r][c + 1] = False
        elif wall.orientation == WallOrientation.VERTICAL:
            self._vertical_edges[r][c] = False
            self._vertical_edges[r + 1][c] = False
