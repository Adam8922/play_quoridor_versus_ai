# menu screen to choose game mode before starting
import pygame
from Constants import *

class MenuScreen:

    def __init__(self, screen):
        self.screen = screen
        self.font = pygame.font.SysFont("Arial", 30, bold=True)
        self.title_font = pygame.font.SysFont("Arial", 50, bold=True)
        self.small_font = pygame.font.SysFont("Arial", 20)
        self.chosen_mode = None  # will be set when user picks a mode

        # buttons for game modes
        btn_width = 250
        btn_height = 50
        center_x = WINDOW_WIDTH // 2 - btn_width // 2

        self.btn_2players = pygame.Rect(center_x, 250, btn_width, btn_height)
        self.btn_easy = pygame.Rect(center_x, 340, btn_width, btn_height)
        self.btn_medium = pygame.Rect(center_x, 410, btn_width, btn_height)
        self.btn_hard = pygame.Rect(center_x, 480, btn_width, btn_height)

    def draw(self):
        self.screen.fill(COLORS["background"])

        # title
        title = self.title_font.render("Quoridor", True, COLORS["ui_text"])
        self.screen.blit(title, title.get_rect(center=(WINDOW_WIDTH // 2, 100)))

        # subtitle
        subtitle = self.small_font.render("Choose Game Mode", True, COLORS["ui_text"])
        self.screen.blit(subtitle, subtitle.get_rect(center=(WINDOW_WIDTH // 2, 170)))

        # 2 players button
        pygame.draw.rect(self.screen, (80, 160, 80), self.btn_2players, border_radius=8)
        text = self.font.render("2 Players", True, (255, 255, 255))
        self.screen.blit(text, text.get_rect(center=self.btn_2players.center))

        # AI section label
        label = self.small_font.render("1 Player (vs AI)", True, COLORS["ui_text"])
        self.screen.blit(label, label.get_rect(center=(WINDOW_WIDTH // 2, 320)))

        # easy button
        pygame.draw.rect(self.screen, (60, 120, 60), self.btn_easy, border_radius=8)
        text = self.font.render("Easy AI", True, (255, 255, 255))
        self.screen.blit(text, text.get_rect(center=self.btn_easy.center))

        # medium button
        pygame.draw.rect(self.screen, (160, 130, 40), self.btn_medium, border_radius=8)
        text = self.font.render("Medium AI", True, (255, 255, 255))
        self.screen.blit(text, text.get_rect(center=self.btn_medium.center))

        # hard button
        pygame.draw.rect(self.screen, (180, 50, 50), self.btn_hard, border_radius=8)
        text = self.font.render("Hard AI", True, (255, 255, 255))
        self.screen.blit(text, text.get_rect(center=self.btn_hard.center))

        pygame.display.update()

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = event.pos
            if self.btn_2players.collidepoint(pos):
                self.chosen_mode = "2players"
            elif self.btn_easy.collidepoint(pos):
                self.chosen_mode = "easy"
            elif self.btn_medium.collidepoint(pos):
                self.chosen_mode = "medium"
            elif self.btn_hard.collidepoint(pos):
                self.chosen_mode = "hard"
