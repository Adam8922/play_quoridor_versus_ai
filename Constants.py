BOARD_SIZE = 9 #no of cells
CELL_SIZE = 60 #width, height of each cell 
WALL_THICKNESS = 4 #width of gaps where walls will be placed 
MARGIN = 40 #offsset from the window edge 

BOARD_PIXEL_SIZE = BOARD_SIZE * CELL_SIZE #total size of grid

COLORS = {
    "background":  (13, 17, 23),    # Deep space black/blue
    "cell":        (22, 27, 34),    # Dark slate
    "grid_line":   (48, 54, 61),    # Subtle divider
    "player1":     (56, 139, 253),  # Electric Blue
    "player2":     (248, 81, 73),   # Neon Red
    "wall":        (210, 153, 34),  # Neon Gold/Orange
    "highlight":   (63, 185, 80, 100), # Neon Green (translucent)
    "wall_preview":(210, 153, 34, 150), # Wall preview (translucent)
    "ui_text":     (201, 209, 217), # Off-white for readability
}