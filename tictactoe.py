class TicTacToe:
    def __init__(self, player1, player2):
        self.players = [player1, player2]
        self.current_turn = 0
        self.board = [[' ' for _ in range(3)] for _ in range(3)]

    def __str__(self):
        board_lines = ['|'.join(row) for row in self.board[::-1]]
        return '\n'.join(board_lines)



    def check_winner(self):
        for row in self.board:
            if row[0] == row[1] == row[2] != ' ':
                return True
        for col in range(3):
            if self.board[0][col] == self.board[1][col] == self.board[2][col] != ' ':
                return True
        if self.board[0][0] == self.board[1][1] == self.board[2][2] != ' ':
            return True
        if self.board[0][2] == self.board[1][1] == self.board[2][0] != ' ':
            return True
        return False

    def make_move(self, x, y):
        x -= 1
        y = 3 - y  # Map the input value to the correct row
        if self.board[y][x] == ' ':
            self.board[y][x] = 'X' if self.current_turn == 0 else 'O'
            if self.check_winner():
                return f"{self.players[self.current_turn].mention} has won!", True
            if all(cell != ' ' for row in self.board for cell in row):
                return "It's a draw!", True
            self.current_turn = 1 - self.current_turn
            return None, True
        else:
            return "Invalid move. Try again.", False
