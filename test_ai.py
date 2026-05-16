import time
from Board import Board, PlayerId
from AIPlayer import AIPlayer

board = Board()
ai = AIPlayer("hard")

start = time.time()
move = ai.choose_move(board, PlayerId.PLAYER_2)
end = time.time()

print(f"Time taken: {end - start:.2f} seconds")
print(f"Move: {move}")
