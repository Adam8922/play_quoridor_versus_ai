from Board import Board, PlayerId, MoveResult
from AIPlayer import AIPlayer

class GameController:
    def __init__(self, game_mode="2players"):
        self.board = Board()   
        self._current_player = PlayerId.PLAYER_1
        self._game_over = False
        self._winner = None
        self.game_mode = game_mode  # "2players", "easy", "medium", "hard"

        # create AI player if needed (AI is always Player 2)
        if game_mode in ("easy", "medium", "hard"):
            self.ai = AIPlayer(difficulty=game_mode)
            self.ai_player = PlayerId.PLAYER_2  # AI controls player 2
        else:
            self.ai = None
            self.ai_player = None

    def current_player(self):       
        return self._current_player

    def game_over(self): #indicate whether game ended             
        return self._game_over

    def winner(self): #return the winner if game ended
        return self._winner

    def is_ai_turn(self):
        """Check if it's the AI's turn to move"""
        if self.ai is None:
            return False
        return self._current_player == self.ai_player and not self._game_over

    def ai_turn(self):
        """Let the AI make its move. Returns the result."""
        if not self.is_ai_turn():
            return None
        
        move = self.ai.choose_move(self.board, self.ai_player)
        if move is None:
            return None

        move_type, action = move
        if move_type == "move":
            return self.make_move(action)
        else:
            return self.place_wall(action)

    def switch_turn(self):
        if self._current_player == PlayerId.PLAYER_1:
            self._current_player = PlayerId.PLAYER_2
        else:
            self._current_player = PlayerId.PLAYER_1

    def make_move(self, new_pos): #make a move and check victory    
        result = self.board.move_pawn(self._current_player, new_pos)
        if result == MoveResult.VICTORY:
            self._game_over = True
            self._winner = self._current_player
        elif result == MoveResult.SUCCESS:
            self.switch_turn()
        return result

    def undo(self):
        if self.board.undo_last_move():
            self.switch_turn()
            self._game_over = False
            self._winner = None
            return True
        return False
    
    def redo(self):
        if self.board.redo_last_undo(self._current_player):
            self.switch_turn()
            # Check if redoing this move won the game
            # (Turn was just switched, so check the PREVIOUS player)
            prev_player = PlayerId.PLAYER_2 if self._current_player == PlayerId.PLAYER_1 else PlayerId.PLAYER_1
            if self.board.has_player_won(prev_player):
                self._game_over = True
                self._winner = prev_player
            return True
        return False
    
    def place_wall(self, wall):
        result = self.board.place_wall(self._current_player, wall)
        if result == MoveResult.SUCCESS:
            self.switch_turn()
        return result