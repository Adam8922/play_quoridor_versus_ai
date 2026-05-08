from Board import Board, PlayerId, MoveResult

class GameController:
    def __init__(self):
        self.board = Board()   
        self._current_player = PlayerId.PLAYER_1
        self._game_over = False
        self._winner = None

    def current_player(self):       
        return self._current_player

    def game_over(self):              
        return self._game_over

    def winner(self):
        return self._winner

    def switch_turn(self):
        if self._current_player == PlayerId.PLAYER_1:
            self._current_player = PlayerId.PLAYER_2
        else:
            self._current_player = PlayerId.PLAYER_1

    def make_move(self, new_pos):        
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
    
    def place_wall(self, wall):
        result = self.board.place_wall(self._current_player, wall)
        if result == MoveResult.SUCCESS:
            self.switch_turn()
        return result