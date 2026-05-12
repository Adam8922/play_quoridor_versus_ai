from collections import deque
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional

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
    INVALID_PHYSICS = 3 # Overlaps or out of bounds
    TRAPS_PLAYER = 4    # Fails the BFS check
    INVALID_MOVE = 5    # New: Tried to jump a wall or move too far
    VICTORY = 6         # New: The player reached the opposite side!
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
        # --- Protected Memory ---
        # Player 1 starts at the bottom middle (Row 8, Col 4)
        self._p1_pos = Position(self.BOARD_SIZE - 1, self.BOARD_SIZE // 2)
        # Player 2 starts at the top middle (Row 0, Col 4)
        self._p2_pos = Position(0, self.BOARD_SIZE // 2)
        
        self._p1_walls = self.INITIAL_WALLS
        self._p2_walls = self.INITIAL_WALLS
        
        # History
        self._placed_walls = []
        self._move_history = []
        
        # The Graph Edge Matrices
        # Horizontal walls go *between* the 9 rows, so there are 8 horizontal grooves.
        # Each groove is 9 squares wide. (8 rows x 9 cols)
        self._horizontal_edges = [[False for _ in range(self.BOARD_SIZE)] for _ in range(self.BOARD_SIZE - 1)]
        
        # Vertical walls go *between* the 9 columns, so there are 8 vertical grooves.
        # Each groove is 9 squares tall. (9 rows x 8 cols)
        self._vertical_edges = [[False for _ in range(self.BOARD_SIZE - 1)] for _ in range(self.BOARD_SIZE)]
        
        # And remember our brilliant "Top-Left Peg" logic to prevent crosses!
        # There are exactly 8x8 pegs on the board.
        self._crosses_blocked = [[False for _ in range(self.BOARD_SIZE - 1)] for _ in range(self.BOARD_SIZE - 1)]
    # --- State Modifiers (System Calls) ---
    def move_pawn(self, player: PlayerId, new_pos: Position) -> MoveResult:
        """
        Executes a pawn movement state transaction.
        Returns a MoveResult Enum to the Controller.
        """
        # --- PHASE 1: Fail-Fast Validation ---
        if not self.is_valid_pawn_move(player, new_pos):
            return MoveResult.INVALID_MOVE

        # --- PHASE 2: State Mutation ---
        # Capture the current position for the Undo ledger before overwriting it!
        start_pos = self.get_player_position(player)

        if player == PlayerId.PLAYER_1:
            self._p1_pos = new_pos
        else:
            self._p2_pos = new_pos

        # --- PHASE 3: Commit to Ledger ---
        new_move = GameMove(
            player=player, 
            move_type=MoveType.PAWN_MOVE, 
            previous_pawn_pos=start_pos,
            new_pawn_pos=new_pos
        )
        self._move_history.append(new_move)

        # --- PHASE 4: Win Condition Evaluation ---
        # Did this legal move land them on the finish line?
        if self.has_player_won(player):
            return MoveResult.VICTORY

        return MoveResult.SUCCESS


    def place_wall(self, player: PlayerId, wall: Wall) -> MoveResult:
        """
        Master controller. Returns specific error codes so the GUI 
        knows exactly which popup to display to the user.
        """
        # 1. Inventory Check
        if self.get_player_wall_count(player) <= 0:
            return MoveResult.OUT_OF_WALLS

        # 2. Physics Check (Your fast O(1) filter)
        if not self.is_valid_wall_placement(player, wall):
            return MoveResult.INVALID_PHYSICS

        # 3. Speculative Write
        self._add_wall_edges(wall)

        # 4. Pathfinding Check (The Referee)
        if not self.get_shortest_path(PlayerId.PLAYER_1) or not self.get_shortest_path(PlayerId.PLAYER_2):
            self._remove_wall_edges(wall)
            return MoveResult.TRAPS_PLAYER

        # 5. Commit State
        if player == PlayerId.PLAYER_1: self._p1_walls -= 1
        else: self._p2_walls -= 1

        self._placed_walls.append(wall)
        
        new_move = GameMove(player=player, move_type=MoveType.WALL_PLACEMENT, placed_wall=wall)
        self._move_history.append(new_move)

        return MoveResult.SUCCESS
    def undo_last_move(self) -> bool:
        """
        Reverses the most recent move made in the game.
        Returns True if a move was undone, False if the history is empty.
        """
        # 1. Is there actually anything to undo?
        if not self._move_history:
            return False

        # 2. Grab the most recent move from the top of the stack
        last_move = self._move_history.pop()

        # 3. Time-Travel Logic based on the move type
        if last_move.move_type == MoveType.WALL_PLACEMENT:
            # A. Erase the wall from the engine's raw memory matrices
            self._remove_wall_edges(last_move.placed_wall)
            
            # B. Give the physical wall back to the player's inventory
            if last_move.player == PlayerId.PLAYER_1:
                self._p1_walls += 1
            else:
                self._p2_walls += 1
                
            # C. Remove the wall from the UI's drawing list
            if self._placed_walls:
                # Note: Because the game history is a strict chronological stack (LIFO), 
                # popping the final item safely removes the exact wall associated with this move.
                self._placed_walls.pop()

        elif last_move.move_type == MoveType.PAWN_MOVE:
            # A. Teleport the pawn back to its starting square
            if last_move.player == PlayerId.PLAYER_1:
                self._p1_pos = last_move.previous_pawn_pos
            else:
                self._p2_pos = last_move.previous_pawn_pos

        return True
    def get_valid_pawn_moves(self, player: PlayerId) -> List[Position]:
        """
        Calculates all legally accessible squares for a player.
        Evaluates normal steps, straight jumps, and diagonal jumps.
        Used by the UI to draw highlighted 'ghost' pawns.
        """
        valid_moves = []
        current = self.get_player_position(player)

        # The 12 theoretical Quoridor landing zones
        offsets = [
            # 1. Normal Moves (Distance of 1)
            (-1, 0), (1, 0), (0, -1), (0, 1),
            
            # 2. Straight Jumps (Distance of 2)
            (-2, 0), (2, 0), (0, -2), (0, 2),
            
            # 3. Diagonal Jumps (Distance of 2, split)
            (-1, -1), (-1, 1), (1, -1), (1, 1)
        ]

        for row_offset, col_offset in offsets:
            target_pos = Position(current.row + row_offset, current.col + col_offset)

            # Let the engine's bulletproof validation pipeline do the heavy lifting!
            if self.is_valid_pawn_move(player, target_pos):
                valid_moves.append(target_pos)

        return valid_moves
    def is_opponent_adjacent(self, player: PlayerId) -> bool:

        current = self.get_player_position(player)
        opponent = self._p2_pos if player == PlayerId.PLAYER_1 else self._p1_pos

        row_diff = abs(current.row - opponent.row)
        col_diff = abs(current.col - opponent.col)

        return (row_diff + col_diff) == 1
    
    # --- State Queries (Validation) ---
    def is_valid_pawn_move(self, player: PlayerId, new_pos: Position) -> bool:
        """
        The absolute source of truth for pawn movement.
        Validates grid boundaries, normal steps, straight jumps, and conditional diagonal jumps.
        """
        current = self.get_player_position(player)

        # 1. Bounds Check: Prevent clicking off the grid
        if not (0 <= new_pos.row < self.BOARD_SIZE and
                0 <= new_pos.col < self.BOARD_SIZE):
            return False

        # 2. Pass Check: You cannot skip your turn by clicking your own square
        if current == new_pos:
            return False

        # 3. Securely identify the opponent's position
        opponent_id = PlayerId.PLAYER_2 if player == PlayerId.PLAYER_1 else PlayerId.PLAYER_1
        opponent = self.get_player_position(opponent_id)

        # Calculate mathematical distance (Manhattan vectors)
        row_diff = new_pos.row - current.row
        col_diff = new_pos.col - current.col
        abs_r = abs(row_diff)
        abs_c = abs(col_diff)

        # =====================================================
        # PHASE 1: NORMAL MOVE (1 Step)
        # =====================================================
        if abs_r + abs_c == 1 and new_pos != opponent:
            # Physics Check: Ensure no wooden wall severs this path
            if self._is_wall_blocking(current, new_pos):
                return False
            return True

        # =====================================================
        # PHASE 2: JUMP MANEUVERS
        # =====================================================
        # Jumps are ONLY considered if the opponent is standing right next to you.
        if self.is_opponent_adjacent(player):

            # --- SUB-ROUTINE A: THE STRAIGHT JUMP ---
            if (abs_r == 2 and col_diff == 0) or (abs_c == 2 and row_diff == 0):
                # 1. Math Check: Is the opponent exactly halfway between us and the target?
                mid = Position(
                    current.row + row_diff // 2,
                    current.col + col_diff // 2
                )
                if mid != opponent:
                    return False

                # 2. Physics Check: No walls on takeoff or landing
                if self._is_wall_blocking(current, opponent):
                    return False
                if self._is_wall_blocking(opponent, new_pos):
                    return False

                return True

            # --- SUB-ROUTINE B: THE DIAGONAL JUMP ---
            elif abs_r == 1 and abs_c == 1:
                # === THE FIX: The Anti-Teleport Lock ===
                # Prove the diagonal square is physically next to the opponent
                if abs(new_pos.row - opponent.row) + abs(new_pos.col - opponent.col) != 1:
                    return False

                # 1. Math Check: Ensure opponent is strictly adjacent (not already diagonal)
                if not (current.row == opponent.row or current.col == opponent.col):
                    return False

                # 2. Rule Check: Calculate the "Shadow Square" behind the opponent
                jump_row = opponent.row + (opponent.row - current.row)
                jump_col = opponent.col + (opponent.col - current.col)
                jump_pos = Position(jump_row, jump_col)

                # 3. Prove the straight path is blocked (by a wall or board edge)
                is_straight_blocked = (
                    jump_row < 0 or jump_row >= self.BOARD_SIZE or 
                    jump_col < 0 or jump_col >= self.BOARD_SIZE or 
                    self._is_wall_blocking(opponent, jump_pos)
                )

                # THE LOCK: If straight is open, diagonal is strictly illegal!
                if not is_straight_blocked:
                    return False 

                # 4. Physics Check: Ensure the diagonal slide doesn't clip through walls
                if self._is_wall_blocking(current, opponent):
                    return False
                if self._is_wall_blocking(opponent, new_pos):
                    return False

                return True

        # Catch-all: If it wasn't a normal move, and wasn't a legal jump, it is invalid.
        return False
    def is_valid_wall_placement(self, player: PlayerId, wall: Wall) -> bool:
        """
        Validates if a wall can physically be placed on the board.
        Checks board limits, intersection collisions, and overlapping.
        """
        r = wall.top_left.row
        c = wall.top_left.col

        # 1. Grid Limits
        # Walls are placed on the 8x8 "peg" grid. Indices must be 0 through 7.
        if r < 0 or r >= 8 or c < 0 or c >= 8:
            return False

        # 2. The Intersection Check (The "Peg" Lock)
        # Prevents a horizontal and vertical wall from forming a '+' cross.
        if self._crosses_blocked[r][c]:
            return False

        # 3. The Overlap Check
        # Prevents placing a wall directly on top of, or halfway over, an existing wall.
        if wall.orientation == WallOrientation.HORIZONTAL:
            # Check the two horizontal alleyways this wall needs
            if self._horizontal_edges[r][c] or self._horizontal_edges[r][c + 1]:
                return False
                
        elif wall.orientation == WallOrientation.VERTICAL:
            # Check the two vertical alleyways this wall needs
            if self._vertical_edges[r][c] or self._vertical_edges[r + 1][c]:
                return False

        # If it passed all physics checks, the placement is geometrically legal!
        return True

    def has_player_won(self, player: PlayerId) -> bool:
        """
        Checks if a player has reached their respective goal row.
        """
        if player == PlayerId.PLAYER_1:
            # Player 1 moves UP to reach Row 0
            return self._p1_pos.row == 0
        else:
            # Player 2 moves DOWN to reach Row 8
            return self._p2_pos.row == (self.BOARD_SIZE - 1)
    def get_shortest_path(self, player: PlayerId) -> List[Position]:
        """
        Uses BFS with a 'came_from' dictionary to find and return the 
        exact shortest path to the goal. 
        Returns an empty list [] if the player is trapped.
        """
        start_pos = self.get_player_position(player)
        
        # 1. Define the target row
        goal_row = 0 if player == PlayerId.PLAYER_1 else (self.BOARD_SIZE - 1)

        queue = deque([start_pos])
        
        # 2. The Breadcrumb Dictionary (The "Memory")
        # Format: { (Current_Row, Current_Col) : (Parent_Row, Parent_Col) }
        start_tuple = (start_pos.row, start_pos.col)
        came_from = {start_tuple: None} # The start position has no parent

        while queue:
            current = queue.popleft()

            # 3. GOAL REACHED! Time to trace the breadcrumbs backward.
            if current.row == goal_row:
                path = []
                curr_tuple = (current.row, current.col)
                
                # Walk backward until we hit 'None' (which is the start position)
                while curr_tuple is not None:
                    path.append(Position(curr_tuple[0], curr_tuple[1]))
                    curr_tuple = came_from[curr_tuple]
                    
                # The path was built backwards (Goal -> Start). 
                # Reverse it so it goes Start -> Goal.
                path.reverse() 
                return path

            # 4. Standard BFS Expansion
            directions = [
                Position(current.row - 1, current.col), # UP
                Position(current.row + 1, current.col), # DOWN
                Position(current.row, current.col - 1), # LEFT
                Position(current.row, current.col + 1)  # RIGHT
            ]

            for target in directions:
                if target.row < 0 or target.row >= self.BOARD_SIZE: continue
                if target.col < 0 or target.col >= self.BOARD_SIZE: continue
                if self._is_wall_blocking(current, target): continue

                target_tuple = (target.row, target.col)
                
                # If we haven't visited this square yet...
                if target_tuple not in came_from:
                    # Drop a breadcrumb pointing back to 'current'
                    came_from[target_tuple] = (current.row, current.col)
                    queue.append(target)

        # If the queue empties and we never found the goal, they are trapped.
        return []

    # --- Getters for the View / Controller ---
    def get_player_position(self, player: PlayerId) -> Position:
        """
        Safely returns the current (row, col) coordinates of the specified player.
        Used by the UI to draw pawns, and by the BFS to know where to start flooding.
        """
        if player == PlayerId.PLAYER_1:
            return self._p1_pos
        elif player == PlayerId.PLAYER_2:
            return self._p2_pos
            
        # Failsafe to prevent the engine from crashing if a bad ID is passed
        return Position(-1, -1)

    def get_player_wall_count(self, player: PlayerId) -> int:
        """
        Returns the number of walls the specified player has left.
        Used by the UI to render the wall counters.
        """
        if player == PlayerId.PLAYER_1:
            return self._p1_walls
        elif player == PlayerId.PLAYER_2:
            return self._p2_walls
            
        return 0 # Failsafe

    def get_placed_walls(self) -> List[Wall]:
        """
        Returns a list of all walls currently placed on the board.
        Used by the Pygame View every frame to draw the physical walls.
        """
        return self._placed_walls

    def get_move_history(self) -> List[GameMove]:
        """
        Returns the chronological list of all moves made in the game so far.
        Essential for the Undo/Redo system, AI analysis, and saving the game.
        """
        return self._move_history

    # --- Internal Private Helpers ---
    def _is_wall_blocking(self, current_pos: Position, target_pos: Position) -> bool:
        """
        Checks the exact memory index between two adjacent squares 
        to see if a wall is blocking the path.
        """
        # Moving UP (Row decreases)
        if target_pos.row < current_pos.row:
            # Check the horizontal fence below the target row
            return self._horizontal_edges[target_pos.row][current_pos.col]

        # Moving DOWN (Row increases)
        elif target_pos.row > current_pos.row:
            # Check the horizontal fence below the current row
            return self._horizontal_edges[current_pos.row][current_pos.col]

        # Moving LEFT (Col decreases)
        elif target_pos.col < current_pos.col:
            # Check the vertical fence to the right of the target col
            return self._vertical_edges[current_pos.row][target_pos.col]

        # Moving RIGHT (Col increases)
        elif target_pos.col > current_pos.col:
            # Check the vertical fence to the right of the current col
            return self._vertical_edges[current_pos.row][current_pos.col]

        return False # Failsafe

    def _add_wall_edges(self, wall: Wall) -> None:
        """
        Writes a newly placed wall into memory, claiming the center peg 
        and blocking the two corresponding alleyways.
        """
        r = wall.top_left.row
        c = wall.top_left.col

        # 1. Claim the central intersection peg to prevent crosses
        self._crosses_blocked[r][c] = True

        # 2. Block the physical alleyways
        if wall.orientation == WallOrientation.HORIZONTAL:
            self._horizontal_edges[r][c] = True
            self._horizontal_edges[r][c + 1] = True
            
        elif wall.orientation == WallOrientation.VERTICAL:
            self._vertical_edges[r][c] = True
            self._vertical_edges[r + 1][c] = True

    def _remove_wall_edges(self, wall: Wall) -> None:
        """
        Erases a wall from memory, freeing up the center peg and 
        reopening the alleyways. Used for Undo/Redo and AI simulations.
        """
        r = wall.top_left.row
        c = wall.top_left.col

        # 1. Release the central intersection peg
        self._crosses_blocked[r][c] = False

        # 2. Reopen the physical alleyways
        if wall.orientation == WallOrientation.HORIZONTAL:
            self._horizontal_edges[r][c] = False
            self._horizontal_edges[r][c + 1] = False
            
        elif wall.orientation == WallOrientation.VERTICAL:
            self._vertical_edges[r][c] = False
            self._vertical_edges[r + 1][c] = False
