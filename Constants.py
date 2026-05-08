BOARD_SIZE = 9 #no of cells
CELL_SIZE = 60 #width, height of each cell 
WALL_THICKNESS = 8 #width of gaps where walls will be placed 
MARGIN = 40 #offsset from the window edge 

BOARD_PIXEL_SIZE = BOARD_SIZE * CELL_SIZE #total size of grid

COLORS = {
    "background":  (30, 30, 30),
    "cell":        (240, 217, 181),
    "grid_line":   (180, 140, 100),
    "player1":     (70, 130, 200),
    "player2":     (220, 80,  80),
    "wall":        (80,  50,  20),
    "highlight":   (100, 220, 100, 120), 
    "wall_preview":(200, 200, 50,  150),
}