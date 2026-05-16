# handle initialization and main game loop
import pygame
from game_screen import GameScreen #custom game screen class 
from menu_screen import MenuScreen #menu screen for mode selection

from Constants import *
pygame.init() #initialize pygame
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT)) #set width & height 
pygame.display.set_caption("Quoridor Game") #set window title
clock = pygame.time.Clock() #create clock object to control frame rate

# start with menu screen
menu = MenuScreen(screen)
game_screen = None  # will be created after mode is chosen
current_screen = "menu"  # track which screen we're on

running = True #flag to keep game loop running
while running:
    for event in pygame.event.get(): #event loop to handle events
        if event.type == pygame.QUIT:  #x button clicked
            running = False

        if current_screen == "menu":
            menu.handle_event(event)
            # check if a mode was chosen
            if menu.chosen_mode is not None:
                game_screen = GameScreen(screen, menu.chosen_mode)
                current_screen = "game"

        elif current_screen == "game":
            is_reset_key = event.type == pygame.KEYDOWN and event.key == pygame.K_r
            is_click_to_restart = event.type == pygame.MOUSEBUTTONDOWN and game_screen.controller.game_over()

            if is_reset_key or is_click_to_restart:
                menu = MenuScreen(screen)
                game_screen = None
                current_screen = "menu"
                continue
            game_screen.handle_event(event) #pass event to game screen for processing

    # draw the current screen
    if current_screen == "menu":
        menu.draw()
    elif current_screen == "game":
        game_screen.draw() #redraw game screen after handling event

    clock.tick(60) #limit frame rate to 60 frames per second 
pygame.quit()