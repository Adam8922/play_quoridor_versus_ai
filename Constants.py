BOARD_SIZE = 9 #no of cells
CELL_SIZE = 60 #width, height of each cell 
WALL_THICKNESS = 4 #width of gaps where walls will be placed 
MARGIN = 40 #offsset from the window edge 

BOARD_PIXEL_SIZE = BOARD_SIZE * CELL_SIZE #total size of grid

COLORS = {
    "background":  (30, 30, 30), #black 
    "cell":        (240, 217, 181), #beige
    "grid_line":   (180, 140, 100), #light brown
    "player1":     (70, 130, 200), #blue
    "player2":     (220, 80,  80), #red
    "wall":        (80,  50,  20), #dark brown
    "highlight":   (100, 220, 100, 120), #green with alpha for transparency [0-255]
    "wall_preview":(200, 200, 50,  150), #yellow with alpha for transparency [0-255]
}