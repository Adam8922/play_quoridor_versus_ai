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

        self._placed_walls: List[Wall] = []
        self._move_history: List[GameMove] = []

        # Horizontal edges: (BOARD_SIZE-1) rows x BOARD_SIZE cols
        self._horizontal_edges = [
            [False] * self.BOARD_SIZE for _ in range(self.BOARD_SIZE - 1)
        ]
        # Vertical edges: BOARD_SIZE rows x (BOARD_SIZE-1) cols
        self._vertical_edges = [
            [False] * (self.BOARD_SIZE - 1) for _ in range(self.BOARD_SIZE)
        ]
        # Peg grid to prevent cross-walls: (BOARD_SIZE-1) x (BOARD_SIZE-1)
        self._crosses_blocked = [
            [False] * (self.BOARD_SIZE - 1) for _ in range(self.BOARD_SIZE - 1)
        ]

    # =========================================================================
    # State Modifiers
    # =========================================================================

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

        # Speculative write then path check, then rollback or commit
        self._add_wall_edges(wall)

        if not self.get_shortest_path(PlayerId.PLAYER_1) or \
           not self.get_shortest_path(PlayerId.PLAYER_2):
            self._remove_wall_edges(wall)
            return MoveResult.TRAPS_PLAYER

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

    # =========================================================================
    # Pawn Move Logic
    # =========================================================================

    def get_valid_pawn_moves(self, player: PlayerId) -> List[Position]:
        """Returns all legally reachable squares for a player this turn."""
        current = self.get_player_position(player)
        offsets = [
            (-1, 0), (1, 0), (0, -1), (0, 1),   # Normal
            (-2, 0), (2, 0), (0, -2), (0, 2),    # Straight jumps
            (-1, -1), (-1, 1), (1, -1), (1, 1)   # Diagonal jumps
        ]
        valid_moves = []
        for dr, dc in offsets:
            target = Position(current.row + dr, current.col + dc)
            if self.is_valid_pawn_move(player, target):
                valid_moves.append(target)
        return valid_moves

    def is_opponent_adjacent(self, player: PlayerId) -> bool:
        """Returns True if the opponent is exactly 1 square away (orthogonally)."""
        current = self.get_player_position(player)
        opponent = self._p2_pos if player == PlayerId.PLAYER_1 else self._p1_pos
        return abs(current.row - opponent.row) + abs(current.col - opponent.col) == 1

    def is_valid_pawn_move(self, player: PlayerId, new_pos: Position) -> bool:
        """
        The absolute source of truth for pawn movement.
        Validates boundaries, normal steps, straight jumps, and diagonal jumps.
        """
        current = self.get_player_position(player)

        if not (0 <= new_pos.row < self.BOARD_SIZE and
                0 <= new_pos.col < self.BOARD_SIZE):
            return False

        if current == new_pos:
            return False

        opponent_id = PlayerId.PLAYER_2 if player == PlayerId.PLAYER_1 else PlayerId.PLAYER_1
        opponent = self.get_player_position(opponent_id)

        row_diff = new_pos.row - current.row
        col_diff = new_pos.col - current.col
        abs_r = abs(row_diff)
        abs_c = abs(col_diff)

        # Normal Move
        if abs_r + abs_c == 1 and new_pos != opponent:
            return not self._is_wall_blocking(current, new_pos)

        # Jump Maneuvers (only when opponent is adjacent)
        if self.is_opponent_adjacent(player):

            # Straight Jump
            if (abs_r == 2 and col_diff == 0) or (abs_c == 2 and row_diff == 0):
                mid = Position(current.row + row_diff // 2, current.col + col_diff // 2)
                if mid != opponent:
                    return False
                if self._is_wall_blocking(current, opponent):
                    return False
                if self._is_wall_blocking(opponent, new_pos):
                    return False
                return True

            # Diagonal Jump
            elif abs_r == 1 and abs_c == 1:
                if abs(new_pos.row - opponent.row) + abs(new_pos.col - opponent.col) != 1:
                    return False
                if not (current.row == opponent.row or current.col == opponent.col):
                    return False

                jump_row = opponent.row + (opponent.row - current.row)
                jump_col = opponent.col + (opponent.col - current.col)
                jump_pos = Position(jump_row, jump_col)

                is_straight_blocked = (
                    jump_row < 0 or jump_row >= self.BOARD_SIZE or
                    jump_col < 0 or jump_col >= self.BOARD_SIZE or
                    self._is_wall_blocking(opponent, jump_pos)
                )
                if not is_straight_blocked:
                    return False
                if self._is_wall_blocking(current, opponent):
                    return False
                if self._is_wall_blocking(opponent, new_pos):
                    return False
                return True

        return False

    # =========================================================================
    # Wall Placement Logic
    # =========================================================================

    def is_valid_wall_placement(self, wall: Wall) -> bool:
        """
        Validates if a wall can physically be placed on the board.
        Checks board limits, cross-intersections, and overlapping segments.
        Wall count check is the caller's responsibility.
        """
        r = wall.top_left.row
        c = wall.top_left.col

        if r < 0 or r >= 8 or c < 0 or c >= 8:
            return False

        if self._crosses_blocked[r][c]:
            return False

        if wall.orientation == WallOrientation.HORIZONTAL:
            if self._horizontal_edges[r][c] or self._horizontal_edges[r][c + 1]:
                return False
        elif wall.orientation == WallOrientation.VERTICAL:
            if self._vertical_edges[r][c] or self._vertical_edges[r + 1][c]:
                return False

        return True

    # =========================================================================
    # Pathfinding — Wall Graph Only (no pawn awareness)
    # =========================================================================

    def get_shortest_path(self, player: PlayerId) -> List[Position]:
        """
        BFS on the WALL GRAPH ONLY.

        Pawns are completely invisible — every square is passable as long as
        no wall blocks the edge.  This is intentionally simple:
          - Used by place_wall() to check a wall doesn't trap anyone.
          - A wall is only illegal if it cuts ALL wall-graph paths.
          - Pawn-aware pathfinding (with jump rules) lives in AIPlayer.

        Returns the shortest path as a list of Positions, or [] if none exists.
        """
        start = self.get_player_position(player)
        goal_row = 0 if player == PlayerId.PLAYER_1 else (self.BOARD_SIZE - 1)

        queue = deque([start])
        came_from: Dict[tuple, Optional[tuple]] = {(start.row, start.col): None}

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

            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nb = Position(cur.row + dr, cur.col + dc)
                nb_t = (nb.row, nb.col)

                if not (0 <= nb.row < self.BOARD_SIZE and 0 <= nb.col < self.BOARD_SIZE):
                    continue
                if nb_t in came_from:
                    continue
                if self._is_wall_blocking(cur, nb):
                    continue

                came_from[nb_t] = cur_t
                queue.append(nb)

        return []

    # =========================================================================
    # Getters
    # =========================================================================

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

    def has_player_won(self, player: PlayerId) -> bool:
        if player == PlayerId.PLAYER_1:
            return self._p1_pos.row == 0
        else:
            return self._p2_pos.row == (self.BOARD_SIZE - 1)

    # =========================================================================
    # Private Helpers
    # =========================================================================

    def _is_wall_blocking(self, current_pos: Position, target_pos: Position) -> bool:
        """Checks the edge matrix between two adjacent squares for a blocking wall."""
        if target_pos.row < current_pos.row:    # Moving UP
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
