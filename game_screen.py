# handle visual representation of the game board 
import pygame
import threading
from Constants import *
from Board import Board, PlayerId, Position, MoveResult, Wall, WallOrientation
from controller import GameController

class GameScreen:

    def __init__(self, screen, game_mode="2players"): #constructor to initialize game screen
        self.screen = screen
        self.game_mode = game_mode
        self.controller = GameController(game_mode) 
        self.board = self.controller.board #instance from class Board
        self.font = pygame.font.SysFont("Arial", 20,bold=True) #for showing no.walls, turn info, win info, restart (status messages)
        self.big_font = pygame.font.SysFont("Arial", 40, bold=True) #for showing turn and win info
        self.selected = False #flag to indicate if a pawn selected
        self.valid_moves = [] #list of positions for valid moves
        self.status_message = "" #at bottom to show turn info, invalid moves, guide info
        self.mode = "move" #default move pawn 
        self.wall_preview = None #only if mode is wall
        self.btn_move = pygame.Rect(BOARD_PIXEL_SIZE + 20, 100, 120, 40) #button for move pawn  (x,y,w,h)
        self.btn_wall = pygame.Rect(BOARD_PIXEL_SIZE + 20, 160, 120, 40) #button for place wall 
        self.btn_undo = pygame.Rect(BOARD_PIXEL_SIZE + 20, 240, 120, 40) #button for undo
        self.btn_redo = pygame.Rect(BOARD_PIXEL_SIZE + 20, 300, 120, 40) #button for redo
        self.ai_delay = 0  # timer to delay AI move so player can see the board
        self.ai_thinking = False  # flag to track if AI is computing in background

    def draw(self): #draw entire game screen elements
        self.screen.fill(COLORS["background"])
        self.draw_grid() #9*9
        self.draw_mode_buttons() #switch bet wall and pawn
        self.draw_highlights() #highlight valid moves 
        self.draw_pawns() #player pawns 
        self.draw_ui() #status messages
        self.draw_walls() #placed walls
        self.draw_wall_preview() #hovering near edge for preview
        
        # handle AI turn with a small delay
        if self.controller.is_ai_turn() and not self.ai_thinking:
            self.ai_delay += 1
            if self.ai_delay > 30:  # wait ~0.5 seconds at 60fps
                self.ai_thinking = True
                self.status_message = "AI is thinking..."
                # run AI in a background thread so the window doesn't freeze
                thread = threading.Thread(target=self._run_ai_move)
                thread.start()

        pygame.display.update() #update the full display surface to the screen

    def _run_ai_move(self):
        """runs in a background thread so the game doesn't freeze"""
        self.controller.ai_turn()
        self.ai_delay = 0
        self.ai_thinking = False
        if self.controller.game_over():
            self.status_message = "AI wins!" if self.controller.winner() == PlayerId.PLAYER_2 else ""
        else:
            self.status_message = "Your turn"
    
    def draw_grid(self): #loop through each row and column to draw cells
        for row in range(BOARD_SIZE): 
            for col in range(BOARD_SIZE):
                padding = 4
                x = col * CELL_SIZE + padding
                y = row * CELL_SIZE + padding
                rect = pygame.Rect(x, y, CELL_SIZE - padding*2, CELL_SIZE - padding*2)
                pygame.draw.rect(self.screen, COLORS["cell"], rect, border_radius=8)
    
    def draw_pawns(self): #draw player pawns with a simple clean look
        radius = CELL_SIZE // 2 - 10
        for player, color in [(PlayerId.PLAYER_1, COLORS["player1"]),(PlayerId.PLAYER_2, COLORS["player2"])]:
            pos = self.board.get_player_position(player)
            x, y = self.cell_to_pixel(pos.row, pos.col)
            
            # Simple pawn with outline
            pygame.draw.circle(self.screen, color, (x, y), radius)
            pygame.draw.circle(self.screen, (255, 255, 255), (x, y), radius, 2)
            
            if self.selected and player == self.controller.current_player():
                pygame.draw.circle(self.screen, (255, 255, 255), (x, y), radius + 6, 2)

    def draw_highlights(self):
       for pos in self.valid_moves:
        x = pos.col * CELL_SIZE
        y = pos.row * CELL_SIZE
        highlight_surf = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA) #(width, height, flag for transparency)
        highlight_surf.fill(COLORS["highlight"])
        self.screen.blit(highlight_surf, (x, y))

    def draw_ui(self):
        p1_walls = self.board.get_player_wall_count(PlayerId.PLAYER_1)
        p2_walls = self.board.get_player_wall_count(PlayerId.PLAYER_2)

        # Draw turn information at the top of the UI area
        if not self.controller.game_over():
            turn_num = "1" if self.controller.current_player() == PlayerId.PLAYER_1 else "2"
            turn_color = COLORS["player1"] if turn_num == "1" else COLORS["player2"]
            turn_text = self.big_font.render(f"Player {turn_num}'s Turn", True, turn_color)
            # Add a small shadow/glow to turn text
            shadow = self.big_font.render(f"Player {turn_num}'s Turn", True, (0, 0, 0))
            self.screen.blit(shadow, (BOARD_PIXEL_SIZE // 2 - turn_text.get_width() // 2 + 2, BOARD_PIXEL_SIZE + 17))
            self.screen.blit(turn_text, (BOARD_PIXEL_SIZE // 2 - turn_text.get_width() // 2, BOARD_PIXEL_SIZE + 15))

        # Draw wall counts side-by-side in the middle
        p1_undo = self.board.p1_undo_count
        p2_undo = self.board.p2_undo_count
        
        p1_text = self.font.render(f"P1 Walls: {p1_walls} (Undo: {p1_undo})", True, COLORS["player1"])
        p2_text = self.font.render(f"P2 Walls: {p2_walls} (Undo: {p2_undo})", True, COLORS["player2"])
        self.screen.blit(p1_text, (40, BOARD_PIXEL_SIZE + 75))
        self.screen.blit(p2_text, (BOARD_PIXEL_SIZE - p2_text.get_width() - 40, BOARD_PIXEL_SIZE + 75))
        
        # Draw status messages at the bottom
        if self.status_message:
            msg = self.font.render(self.status_message, True, COLORS["ui_text"])
            self.screen.blit(msg, (BOARD_PIXEL_SIZE // 2 - msg.get_width() // 2, BOARD_PIXEL_SIZE + 115))

        if self.controller.game_over():
            overlay = pygame.Surface((800,700), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180)) #semi-transparent black background 
            self.screen.blit(overlay, (0, 0))
            
            winner_num= "1" if self.controller.winner() == PlayerId.PLAYER_1 else "2"
            winner_color = COLORS["player1"] if winner_num == "1" else COLORS["player2"]
            winner_text = self.big_font.render(f"Player {winner_num} Wins!", True, winner_color)
            restart_text = self.font.render("Click R to restart", True, (255, 255, 255))

            self.screen.blit(winner_text, winner_text.get_rect(center=(400, 300))) #center winner text
            self.screen.blit(restart_text, restart_text.get_rect(center=(400, 370))) #center restart text

    def draw_mode_buttons(self):
        move_color = (80,160,80) if self.mode == "move" else (60,60,60) #switch color bet green and gray
        pygame.draw.rect(self.screen, move_color, self.btn_move, border_radius=5)
        move_text = self.font.render("Move Pawn", True, (255, 255, 255)) 
        self.screen.blit(move_text, move_text.get_rect(center=self.btn_move.center))

        wall_color = (160, 100,40) if self.mode == "wall" else (60, 60, 60) #switch color bet orange and gray
        pygame.draw.rect(self.screen, wall_color, self.btn_wall, border_radius=5)
        wall_text = self.font.render("Place Wall", True, (255, 255, 255))
        self.screen.blit(wall_text, wall_text.get_rect(center=self.btn_wall.center))

        # Undo/Redo buttons
        pygame.draw.rect(self.screen, (60, 60, 60), self.btn_undo, border_radius=5)
        undo_text = self.font.render("Undo", True, (255, 255, 255))
        self.screen.blit(undo_text, undo_text.get_rect(center=self.btn_undo.center))

        pygame.draw.rect(self.screen, (60, 60, 60), self.btn_redo, border_radius=5)
        redo_text = self.font.render("Redo", True, (255, 255, 255))
        self.screen.blit(redo_text, redo_text.get_rect(center=self.btn_redo.center))

    def draw_walls(self):
        for wall in self.board.get_placed_walls():
            r = wall.top_left.row 
            c = wall.top_left.col
            if wall.orientation == WallOrientation.HORIZONTAL:
                x = c * CELL_SIZE + 2
                y = r * CELL_SIZE + CELL_SIZE - WALL_THICKNESS // 2
                width = CELL_SIZE * 2 - 4
                height = WALL_THICKNESS
            else: #vertical wall
                x = c * CELL_SIZE + CELL_SIZE - WALL_THICKNESS // 2
                y = r * CELL_SIZE + 2
                width = WALL_THICKNESS
                height = CELL_SIZE * 2 - 4
            
            rect = pygame.Rect(x, y, width, height)
            pygame.draw.rect(self.screen, COLORS["wall"], rect, border_radius=2)
    
    def get_wall_from_mouse(self, mouse_pos):
        mx, my = mouse_pos #pixel coordinates of mouse click
        if not (0 <= mx < BOARD_PIXEL_SIZE and 0 <= my < BOARD_PIXEL_SIZE): #mouse outside board
            return None
        
        col = mx // CELL_SIZE
        row = my // CELL_SIZE
        rx= mx % CELL_SIZE #how far from left edge of cell
        ry = my % CELL_SIZE #how far from top edge of cell
        threshold = 15

        if ry > CELL_SIZE - threshold and row < BOARD_SIZE -1 and col < BOARD_SIZE -1: #near bottom edge of cell and not on last row/col
            return Wall(top_left=Position(row, col), orientation=WallOrientation.HORIZONTAL)
        
        if rx > CELL_SIZE - threshold and col < BOARD_SIZE -1 and row < BOARD_SIZE -1: #near right edge of cell and not on last row/col
            return Wall(top_left=Position(row, col), orientation=WallOrientation.VERTICAL)
        return None
    
    def draw_wall_preview(self):
        if self.mode != "wall" or not self.wall_preview:
            return
        
        r = self.wall_preview.top_left.row
        c = self.wall_preview.top_left.col

        if self.wall_preview.orientation == WallOrientation.HORIZONTAL:
            x = c * CELL_SIZE
            y = r * CELL_SIZE + CELL_SIZE - WALL_THICKNESS // 2
            w = CELL_SIZE * 2
            h = WALL_THICKNESS
        else: 
            x = c * CELL_SIZE + CELL_SIZE - WALL_THICKNESS // 2
            y = r * CELL_SIZE
            w = WALL_THICKNESS
            h = CELL_SIZE * 2

        preview_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        preview_surf.fill(COLORS["wall_preview"])
        self.screen.blit(preview_surf, (x, y))
        
    
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.handle_click(event.pos) #pass position of click to handle_click method
        elif event.type == pygame.MOUSEMOTION:
            if self.mode == "wall":
                self.wall_preview = self.get_wall_from_mouse(event.pos) #update wall preview based on mouse position
    
    def handle_click(self, mouse_pos):
        if self.controller.game_over():
            return #ignore clicks if game ended
        
        if self.btn_move.collidepoint(mouse_pos):
            self.mode = "move"
            self.wall_preview = None
            self.selected = False
            self.valid_moves = []
            self.status_message = "Click your pawn to move"
            return
        
        if self.btn_wall.collidepoint(mouse_pos):
            self.mode = "wall"
            self.selected = False
            self.valid_moves = []  
            self.status_message = "Hover near a cell edge and click to place wall"
            return
        
        if self.btn_undo.collidepoint(mouse_pos):
            if self.controller.undo():
                self.status_message = "Move undone"
            else:
                self.status_message = "Cannot undo (no history or charges)"
            self.selected = False
            self.valid_moves = []
            return

        if self.btn_redo.collidepoint(mouse_pos):
            if self.controller.redo():
                self.status_message = "Move redone"
            else:
                self.status_message = "Nothing to redo"
            self.selected = False
            self.valid_moves = []
            return
        
        if self.mode == "wall":
            wall = self.get_wall_from_mouse(mouse_pos)
            if wall is None:
                self.status_message = "Click near a cell edge to place a wall"
                return
            result = self.controller.place_wall(wall)
            if result == MoveResult.SUCCESS:
                self.wall_preview = None
                self.status_message = f"Player {'1' if self.controller.current_player() ==PlayerId.PLAYER_1 else '2'}'s turn"
            elif result == MoveResult.OUT_OF_WALLS:
                self.status_message = "No walls left! Switch to move mode"
            elif result == MoveResult.INVALID_PHYSICS:
                self.status_message = "Wall overlaps an existing wall!"
            elif result == MoveResult.TRAPS_PLAYER:
                self.status_message = "Wall would trap a player!"
            return 
        
        clicked = self.pixel_to_cell(mouse_pos) #convert pixel position to board cell
        if clicked is None:
            return #click outside the board
        
        row,col = clicked
        clicked_pos = Position(row, col)
        current = self.controller.current_player() #get current player
        pawn_pos = self.board.get_player_position(current) #get current player's pawn position

        #no pawn selected yet, select it
        if not self.selected:
            if row == pawn_pos.row and col == pawn_pos.col:
                self.selected = True #select the pawn
                self.valid_moves = self.board.get_valid_pawn_moves(current) #get valid moves for the selected pawn
                self.status_message = "Select a highligted square to move"
            else:
                self.status_message = "Click on your pawn to select it"
        
        #pawn already selected, try to move
        else:
            if row == pawn_pos.row and col == pawn_pos.col: #click pawn again to deselect
                self.selected = False #deselect the pawn
                self.valid_moves = [] #clear valid moves
                self.status_message = ""
                return
            result = self.controller.make_move(clicked_pos) #attempt to make move to the clicked position
            self.selected = False #deselect after move attempt
            self.valid_moves = [] #clear valid moves

            if result == MoveResult.SUCCESS:
                self.status_message = f"Player {'1' if self.controller.current_player() == PlayerId.PLAYER_1 else '2'}'s turn"
            elif result == MoveResult.VICTORY:
                self.status_message = f"Player {'1' if self.controller.current_player() == PlayerId.PLAYER_1 else '2'} wins!"
            elif result == MoveResult.INVALID_MOVE:
                self.status_message = "Invalid move! Try again"
    
    def cell_to_pixel(self, row, col): #convert from board coordinates to screen pixel coordinates 
        x = col * CELL_SIZE + CELL_SIZE // 2
        y = row * CELL_SIZE + CELL_SIZE // 2
        return x, y
    
    def pixel_to_cell(self, pos): #convert from screen pixel coordinates to board coordinates 
        x, y = pos
        if 0 <= x < BOARD_PIXEL_SIZE and 0 <= y < BOARD_PIXEL_SIZE:
            col = x // CELL_SIZE
            row = y // CELL_SIZE
            return int(row), int(col)
        return None
