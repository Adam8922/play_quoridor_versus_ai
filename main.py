# handle initialization and main game loop
import pygame
from game_screen import GameScreen #custom game screen class 

pygame.init() #initialize pygame
screen = pygame.display.set_mode((800, 700)) #set width & height 
pygame.display.set_caption("Quoridor Game") #set window title
clock = pygame.time.Clock() #create clock object to control frame rate

game_screen = GameScreen(screen) #instance of GameScreen class

running = True #flag to keep game loop running
while running:
    for event in pygame.event.get(): #event loop to handle events
        if event.type == pygame.QUIT:  #x button clicked
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r: #reset game when R pressed
                game_screen = GameScreen(screen)
        game_screen.handle_event(event) #pass event to game screen for processing

    game_screen.draw() #redraw game screen after handling event

    clock.tick(60) #limit frame rate to 60 frames per second 
pygame.quit()