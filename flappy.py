import serial
from itertools import cycle
import random
import sys
import time
import threading
import matplotlib
from matplotlib import pyplot as plt
from matplotlib.figure import Figure
import matplotlib.backends.backend_tkagg as FigureCanvasTkAgg
import numpy as np
import matplotlib.animation as animation
from threading import Thread
from threading import Lock
import pygame
from pygame.locals import *
from queue import *
import shelve
import re
import RPi.GPIO as GPIO

sensor = list(range(450,500))
threshold = 50
dataAvg = 510 #average or midpoint of the EMG signal

#Locks are used when multiple threads may be using the same variable
#to ensure only one thread can access it at a time
calib_lock = threading.Lock()
calib_finished = False
jump_lock = threading.Lock()
sensor_lock = threading.Lock()


gold = [194,142,14]
black = [0,0,0]
FPS = 60
#SCREENWIDTH  = 288
#SCREENHEIGHT = 512

SCREENWIDTH  = 288
SCREENHEIGHT = 512
# amount by which base can maximum shift to left
PIPEGAPSIZE  = 110 # gap between upper and lower part of pipe
#BASEY        = SCREENHEIGHT * 0.79
BASEY        = SCREENHEIGHT
# image, sound and hitjump = 0mask  dicts
IMAGES, SOUNDS, HITMASKS = {}, {}, {}
s=[0]

#passes data from serialread to either jumpthread or calibthread
dataq = Queue()
#Jumpthread will put a '1' in jumpq if the bird should jump, the game will read
#from jumpq when needed
jumpq = Queue(maxsize=1)

# list of all possible players (tuple of 3 positions of flap)
PLAYERS_LIST = (
    # red bird
    (
        'assets/sprites/train_8bit.png',
        'assets/sprites/train_8bit.png',
        'assets/sprites/train_8bit.png',
    ),
    # blue bird
    (
        # amount by which base can maximum shift to left
        'assets/sprites/train_8bit.png',
        'assets/sprites/train_8bit.png',
        'assets/sprites/train_8bit.png',
    ),
    # yellow bird
    (
        'assets/sprites/train_8bit.png',
        'assets/sprites/train_8bit.png',
        'assets/sprites/train_8bit.png',
    ),
)

# list of backgrounds
BACKGROUNDS_LIST = (
    #'assets/sprites/Bell_Tower_8bit.png',
    'assets/sprites/Bell_Tower_8bit.png',
    #'assets/sprites/spider.jpg',
    
)

# list of pipes
PIPES_LIST = (
    'assets/sprites/pipe-green.png',
    'assets/sprites/pipe-green.png',
)

try:
    xrange
except NameError:
    xrange = range

#reads the incoming EMG data from the serial connection
def serialread():
    global sensor_lock
    global sensor
    global dataq
    while True:
        time.sleep(.005)
        if ser.read(1) == b'z':
            s = ser.read(3)
            #read_serial = (float(ser.read(3))*10)/9
            read_serial = (float(s)*10)/9
            dataq.put(read_serial)
            sensor_lock.acquire(True)
            sensor.pop(0)
            sensor.append(read_serial)
            sensor_lock.release()

def jumpThread():
    global jump
    global threshold
    global dataAvg
    global dataq
    global calib_lock
    counter = 0
    state = 0
    read = 1
    data = 500
    while True:
        if counter >= 6:
            state = 0
            counter = 0

        #acquire lock before accessing q
        calib_lock.acquire(True)
        data = dataq.get()
        calib_lock.release()

        #essentially abs(data - average_data_value)
        #the average_data_value of the signal has been observed to be 510
        if data >= dataAvg:
            data = data - dataAvg
        else:
            data = dataAvg- data

        if int(data/threshold)>=1:
            if state == 1:
                time.sleep(0.005)
            else:
                state = 1
                try:
                    jumpq.put_nowait(1)
                except:
                    pass
                time.sleep(0.005)
        else:
            counter += 1
            time.sleep(0.005)
     
def calibrate():
    global dataq
    global calib_lock
    global calib_finished
    global dataAvg
    calib_lock.acquire(True)
    #time.sleep(1.5)
    global threshold
    count = 0
    valuemaxc1 = 50
    valuemaxc2 = 50
    valuemaxc3 = 50
    for i in range(150):
        valueabsc = 0
        valuec = dataq.get()

        #take abs of data around the average
        if valuec <= dataAvg:
            valueabsc = dataAvg - valuec
        else :
            valueabsc = valuec - dataAvg

        #ignore large values
        if valueabsc >= 130:
            pass

        #keep track of the 3 highest values
        elif valueabsc > valuemaxc1:
            valuemaxc3 = valuemaxc2
            valuemaxc2 = valuemaxc1
            valuemaxc1 = valueabsc
            time.sleep(0.005)
            count += 1
        elif (valueabsc > valuemaxc2):
            valuemaxc3 = valuemaxc2
            valuemaxc2 = valueabsc
            time.sleep(0.005)
            count += 1
        elif (valueabsc > valuemaxc3):
            valuemaxc3 = valueabsc
            time.sleep(0.005)
            count += 1
    
    #set threshold to default 
    if valuemaxc1 == 50:
        pass

    elif  (valuemaxc1-valuemaxc2)>=40 and (count>=2) :

        if (valuemaxc1-valuemaxc3)>60:
            if valuemaxc2-valuemaxc3<20 :
                threshold = 0.55*(valuemaxc2+valuemaxc3)/2
            else:
                threshold = 0.55*valuemaxc2

        else:
            threshold = 0.55*valuemaxc2

    elif count == 1:
        threshold = 0.55*valuemaxc1
    elif count == 2:
        threshold = 0.55*valuemaxc1
    elif count == 3:
        threshold = 0.55*((valuemaxc1+valuemaxc2)/2)
    elif count >= 4:

        if (valuemaxc1-valuemaxc3)>60 :
            threshold = 0.55*( (valuemaxc1+valuemaxc2+valuemaxc3)/3 )
        else:
            threshold = 0.55*( (valuemaxc1+valuemaxc2+(valuemaxc3+20))/3 )

    else:
        threshold = 0.55*valuemaxc1
    print ("threshold") #used for debugging, can be removed
    print (threshold) #used for debugging, can be removed
    calib_finished = True
    calib_lock.release()

def flappyGame():
    global SCREEN, FPSCLOCK, size
    pygame.init()
    FPSCLOCK = pygame.time.Clock()

    #SCREEN = pygame.display.set_mode((1000, 1000,), pygame.FULLSCREEN)
    #SCREEN = pygame.display.set_mode((SCREENWIDTH, SCREENHEIGHT,), pygame.FULLSCREEN)
    SCREEN = pygame.display.set_mode((SCREENWIDTH, SCREENHEIGHT))


    
    pygame.display.set_caption('Flappy Bird')

    # numbers sprites for score display
    IMAGES['numbers'] = (
        pygame.image.load('assets/sprites/0.png').convert_alpha(),
        pygame.image.load('assets/sprites/1.png').convert_alpha(),
        pygame.image.load('assets/sprites/2.png').convert_alpha(),
        pygame.image.load('assets/sprites/3.png').convert_alpha(),
        pygame.image.load('assets/sprites/4.png').convert_alpha(),
        pygame.image.load('assets/sprites/5.png').convert_alpha(),
        pygame.image.load('assets/sprites/6.png').convert_alpha(),
        pygame.image.load('assets/sprites/7.png').convert_alpha(),
        pygame.image.load('assets/sprites/8.png').convert_alpha(),
        pygame.image.load('assets/sprites/9.png').convert_alpha()
    )

    IMAGES['letters'] = (
        pygame.image.load('assets/letters/A.png').convert_alpha(),
        pygame.image.load('assets/letters/B.png').convert_alpha(),
        pygame.image.load('assets/letters/C.png').convert_alpha(),
        pygame.image.load('assets/letters/D.png').convert_alpha(),
        pygame.image.load('assets/letters/E.png').convert_alpha(),
        pygame.image.load('assets/letters/F.png').convert_alpha(),
        pygame.image.load('assets/letters/G.png').convert_alpha(),
        pygame.image.load('assets/letters/H.png').convert_alpha(),
        pygame.image.load('assets/letters/I.png').convert_alpha(),
        pygame.image.load('assets/letters/J.png').convert_alpha(),
        pygame.image.load('assets/letters/K.png').convert_alpha(),
        pygame.image.load('assets/letters/L.png').convert_alpha(),
        pygame.image.load('assets/letters/M.png').convert_alpha(),
        pygame.image.load('assets/letters/N.png').convert_alpha(),
        pygame.image.load('assets/letters/O.png').convert_alpha(),
        pygame.image.load('assets/letters/P.png').convert_alpha(),
        pygame.image.load('assets/letters/Q.png').convert_alpha(),
        pygame.image.load('assets/letters/R.png').convert_alpha(),
        pygame.image.load('assets/letters/S.png').convert_alpha(),
        pygame.image.load('assets/letters/T.png').convert_alpha(),
        pygame.image.load('assets/letters/U.png').convert_alpha(),
        pygame.image.load('assets/letters/V.png').convert_alpha(),
        pygame.image.load('assets/letters/W.png').convert_alpha(),
        pygame.image.load('assets/letters/X.png').convert_alpha(),
        pygame.image.load('assets/letters/Y.png').convert_alpha(),
        pygame.image.load('assets/letters/Z.png').convert_alpha()
    )

  
    # game over sprite
    IMAGES['gameover'] = pygame.image.load('assets/sprites/gameover.png').convert_alpha()
    # message sprite for welcome screen
    IMAGES['message'] = pygame.image.load('assets/sprites/message.png').convert_alpha()
    # message sprite for calibration screen
    IMAGES['calib'] = pygame.image.load('assets/sprites/calib.png').convert_alpha()
    # base (ground) sprite
    IMAGES['base'] = pygame.image.load('assets/sprites/base.png').convert_alpha()

    # sounds
    soundExt = '.wav'

    SOUNDS['die']    = pygame.mixer.Sound('assets/audio/die' + soundExt)
    SOUNDS['hit']    = pygame.mixer.Sound('assets/audio/smack' + soundExt)
    SOUNDS['point']  = pygame.mixer.Sound('assets/audio/score_bell' + soundExt)
    SOUNDS['swoosh'] = pygame.mixer.Sound('assets/audio/swoosh.ogg')
    SOUNDS['wing']   = pygame.mixer.Sound('assets/audio/Real_choo_choo' + soundExt)

    while True:
        # select random background sprites
        randBg = random.randint(0, len(BACKGROUNDS_LIST) - 1)
        IMAGES['background'] = pygame.image.load(BACKGROUNDS_LIST[randBg]).convert()

        # select random player sprites
        randPlayer = random.randint(0, len(PLAYERS_LIST) - 1)
        IMAGES['player'] = (
            pygame.image.load(PLAYERS_LIST[randPlayer][0]).convert_alpha(),
            pygame.image.load(PLAYERS_LIST[randPlayer][1]).convert_alpha(),
            pygame.image.load(PLAYERS_LIST[randPlayer][2]).convert_alpha(),
        )

        # select random pipe sprites
        pipeindex = random.randint(0, len(PIPES_LIST) - 1)
        IMAGES['pipe'] = (
            pygame.transform.rotate(
                pygame.image.load(PIPES_LIST[pipeindex]).convert_alpha(), 180),
            pygame.image.load(PIPES_LIST[pipeindex]).convert_alpha(),
        )

        # hismask for pipes
        HITMASKS['pipe'] = (
            getHitmask(IMAGES['pipe'][0]),
            getHitmask(IMAGES['pipe'][1]),
        )

        # hitmask for player
        HITMASKS['player'] = (
            getHitmask(IMAGES['player'][0]),
            getHitmask(IMAGES['player'][1]),
            getHitmask(IMAGES['player'][2]),
        )
       
        movementInfo = showWelcomeAnimation()
        showCalibrationScreen()
        crashInfo = mainGame(movementInfo)
        score = showGameOverScreen(crashInfo)
        
        #d = shelve.open('scores.dat')
        scoreArray = [None] * 10
        f = open("scores.txt", "r")
        i = 0
        for x in f:
            scoreArray[i] = x
            i = i + 1

        print (scoreArray[0])
        print (scoreArray[1])
        print (scoreArray[2])
        print (scoreArray[3])
        print (scoreArray[4])
        print (scoreArray[5])
        print (scoreArray[6])
        print (scoreArray[7])
        print (scoreArray[8])
        print (scoreArray[9])
        
        #scoreArray = [d['s1'], d['s2'], d['s3'], d['s4'], d['s5'], d['s6'], d['s7'], d['s8'], d['s9'], d['s10']]
        
        last = int(scoreArray[9].split()[1])
        print ("last: " + str(last))
        if ((score/2) > last):
            highScoreInput(score)
        #highScoreInput(score)
        #d.close()

        showHighScoreScreen()
        
        #ser.write('C')

def showCalibrationScreen():
    """Shows welcome screen animation of flappy bird"""
    global calib_finished
    calib_finished = False
    # index of player to blit on screen
    playerIndex = 0
    playerIndexGen = cycle([0, 1, 2, 1])
    # iterator used to change playerIndex after every 5th iteration
    loopIter = 0

    playerx = int(SCREENWIDTH * 0.2)
    playery = int((SCREENHEIGHT - IMAGES['player'][0].get_height()) / 2)

    messagex = int((SCREENWIDTH - IMAGES['calib'].get_width()) / 2)
    messagey = int(SCREENHEIGHT * 0.12)

    basex = 0
    # amount by which base can maximum shift to left
    baseShift = IMAGES['base'].get_width() - IMAGES['background'].get_width()

    # player shm for up-down motion on welcome screen
    playerShmVals = {'val': 0, 'dir': 1}
    start = time.time()
    end = start + 5
    progress = 10
    pygame.draw.rect(SCREEN, gold, [100,100,204,49])
    pygame.draw.rect(SCREEN, black, [101,101,202,47])
    pygame.display.flip()
    t = Thread(target = calibrate, args = ())
    t.start()
    while True:
        if time.time() > end and calib_finished == True:
            calib_finished = False
            return
        # adjust playery, playerIndex, basex
        if (loopIter + 1) % 5 == 0:
            playerIndex = next(playerIndexGen)
        loopIter = (loopIter + 1) % 30
        basex = -((-basex + 4) % baseShift)
        playerShm(playerShmVals)

        # draw sprites
        SCREEN.blit(IMAGES['background'], (0,0))
        SCREEN.blit(IMAGES['player'][playerIndex],
                    (playerx, playery + playerShmVals['val']))
        SCREEN.blit(IMAGES['calib'], (messagex, messagey))
        SCREEN.blit(IMAGES['base'], (basex, BASEY))

        pygame.draw.rect(SCREEN, gold, [55, 152, progress, 45])
        progress = progress + 0.6;

        pygame.display.update()
        FPSCLOCK.tick(FPS)
        
        

def showWelcomeAnimation():
    """Shows welcome screen animation of flappy bird"""
    # index of player to blit on screen
    playerIndex = 0
    playerIndexGen = cycle([0, 1, 2, 1])
    # iterator used to change playerIndex after every 5th iteration
    loopIter = 0

    playerx = int(SCREENWIDTH * 0.2)
    playery = int((SCREENHEIGHT - IMAGES['player'][0].get_height()) / 2)

    messagex = int((SCREENWIDTH - IMAGES['message'].get_width()) / 2)
    messagey = int(SCREENHEIGHT * 0.12)

    basex = 0
    # amount by which base can maximum shift to left
    baseShift = IMAGES['base'].get_width() - IMAGES['background'].get_width()

    # player shm for up-down motion on welcome screen
    playerShmVals = {'val': 0, 'dir': 1}
    global jumpq
    j = 0
    
    while True:
        
        try:
            j = jumpq.get_nowait()
        except:
            j = 0
        if j == 1 or j == 2:
            SOUNDS['wing'].play()

            return {
                    'playery': playery + playerShmVals['val'],
                    'basex': basex,
                    'playerIndexGen': playerIndexGen,
                    }
        else:
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                    pygame.quit()
                    sys.exit()
                if (event.type == KEYDOWN and (event.key == K_SPACE or event.key == K_UP)):
                    # make first flap sound and return values for mainGame
                    SOUNDS['wing'].play()
                    return {
                        'playery': playery + playerShmVals['val'],
                        'basex': basex,
                        'playerIndexGen': playerIndexGen,
                    }
        # adjust playery, playerIndex, basex
        if (loopIter + 1) % 5 == 0:
            playerIndex = next(playerIndexGen)
        loopIter = (loopIter + 1) % 30
        basex = -((-basex + 4) % baseShift)
        playerShm(playerShmVals)

        # draw sprites
        SCREEN.blit(IMAGES['background'], (0,0))
        SCREEN.blit(IMAGES['player'][playerIndex],
                    (playerx, playery + playerShmVals['val']))
        SCREEN.blit(IMAGES['message'], (messagex, messagey))
        SCREEN.blit(IMAGES['base'], (basex, BASEY))

        pygame.display.update()
        FPSCLOCK.tick(FPS)
        

def mainGame(movementInfo):
    score = playerIndex = loopIter = 0
    playerIndexGen = movementInfo['playerIndexGen']
    playerx, playery = int(SCREENWIDTH * 0.2), movementInfo['playery']

    basex = movementInfo['basex']
    baseShift = IMAGES['base'].get_width() - IMAGES['background'].get_width()

    # get 2 new pipes to add to upperPipes lowerPipes list
    newPipe1 = getRandomPipe()
    newPipe2 = getRandomPipe()

    # list of upper pipes
    upperPipes = [
        {'x': SCREENWIDTH + 200, 'y': newPipe1[0]['y']},
        {'x': SCREENWIDTH + 200 + (SCREENWIDTH / 2), 'y': newPipe2[0]['y']},
    ]

    # list of lowerpipe
    lowerPipes = [
        {'x': SCREENWIDTH + 200, 'y': newPipe1[1]['y']},
        {'x': SCREENWIDTH + 200 + (SCREENWIDTH / 2), 'y': newPipe2[1]['y']},
    ]

    pipeVelX = -2

    # player velocity, max velocity, downward accleration, accleration on flap
    playerVelY    =  -3   # player's velocity along Y, default same as playerFlapped
    playerMaxVelY =  6   # max vel along Y, max descend speed
    playerMinVelY =  -4   # min vel along Y, max ascend speed
    playerAccY    =   0.175   # players downward accleration
    playerRot     =  45   # player's rotation
    playerVelRot  =   1.5   # angular speed
    playerRotThr  =  40   # rotation threshold
    playerFlapAcc =  -4.5   # players speed on flapping
    playerFlapped = False # True when player flaps

    cooldownBuffer = time.time()    #coolDownBuffer is initially set to the current time

    f = open("scores.txt", "w+")
    f.write("1:14:1   123\n")
    f.write("19:8:12  099\n")
    f.write("9:0:23   087\n")
    f.write("3:8:11   050\n")
    f.write("12:0:23  041\n")
    f.write("9:8:11   040\n")
    f.write("15:14:7  037\n")
    f.write("23:14:23 035\n")
    f.write("13:8:10  011\n")
    f.write("15:4:19  003\n")

    f.close()

    
    #d = shelve.open('scores.dat')
    #d['s1']  = "1:14:1   123"
    #d['s2']  = "19:8:12  099"
    #d['s3']  = "9:0:23   087"
    #d['s4']  = "3:8:11   050"
    #d['s5']  = "12:0:23  041"
    #d['s6']  = "9:8:11   040"
    #d['s7']  = "15:14:7  037"
    #d['s8']  = "23:14:23 035"
    #d['s9']  = "13:8:10  011"
    #d['s10'] = "15:4:19  008"

    #d.close()
    while True:
        try:
            j = jumpq.get_nowait()
        except:
            j = 0
        if (j == 1 or j == 2) and (time.time() > cooldownBuffer):   #jump can only occur when current time > buffer
            cooldownBuffer = time.time() + .65                   #Every jump, buffer is set to .65 seconds in the future
            if playery > -2 * IMAGES['player'][0].get_height():
                    playerVelY = playerFlapAcc
                    playerFlapped = True
                    SOUNDS['wing'].play()
        else:
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                    pygame.quit()
                    sys.exit()
                if event.type == KEYDOWN and (event.key == K_SPACE or event.key == K_UP):
                    if playery > -2 * IMAGES['player'][0].get_height():
                        playerVelY = playerFlapAcc
                        playerFlapped = True
                        SOUNDS['wing'].play()

        # check for crash here
        crashTest = checkCrash({'x': playerx, 'y': playery, 'index': playerIndex},
                               upperPipes, lowerPipes)
        if crashTest[0]:
            return {
                'y': playery,
                'groundCrash': crashTest[1],
                'basex': basex,
                'upperPipes': upperPipes,
                'lowerPipes': lowerPipes,
                'score': score,
                'playerVelY': playerVelY,
                'playerRot': playerRot
            }

        # check for score
        playerMidPos = playerx + IMAGES['player'][0].get_width() / 2
        for pipe in upperPipes:
            pipeMidPos = pipe['x'] + IMAGES['pipe'][0].get_width() / 2
            if pipeMidPos <= playerMidPos < pipeMidPos + 4:
                score += 1
                SOUNDS['point'].play()

        # playerIndex basex change
        if (loopIter + 1) % 3 == 0:
            playerIndex = next(playerIndexGen)
        loopIter = (loopIter + 1) % 30
        basex = -((-basex + 50) % baseShift)

        # rotate the player
        if playerRot > -90:
            playerRot -= playerVelRot

        # player's movement
        if playerVelY < playerMaxVelY and not playerFlapped:
            playerVelY += playerAccY
        if playerFlapped:
            playerFlapped = False

            # more rotation to cover the threshold (calculated in visible rotation)
            playerRot = 45

        playerHeight = IMAGES['player'][playerIndex].get_height()
        playery += min(playerVelY, BASEY - playery - playerHeight)

        # move pipes to left
        for uPipe, lPipe in zip(upperPipes, lowerPipes):
            uPipe['x'] += pipeVelX
            lPipe['x'] += pipeVelX

        # add new pipe when first pipe is about to touch left of screen
        if 0 < upperPipes[0]['x'] < 3:
            newPipe = getRandomPipe()
            upperPipes.append(newPipe[0])
            lowerPipes.append(newPipe[1])

        # remove first pipe if its out of the screen
        if upperPipes[0]['x'] < -IMAGES['pipe'][0].get_width():
            upperPipes.pop(0)
            lowerPipes.pop(0)

        # draw sprites
        SCREEN.blit(IMAGES['background'], (0,0))

        for uPipe, lPipe in zip(upperPipes, lowerPipes):
            SCREEN.blit(IMAGES['pipe'][0], (uPipe['x'], uPipe['y']))
            SCREEN.blit(IMAGES['pipe'][1], (lPipe['x'], lPipe['y']))

        SCREEN.blit(IMAGES['base'], (basex, BASEY))
        # print score so player overlaps the score
        showScore(score/2)

        # Player rotation has a threshold
        visibleRot = playerRotThr
        if playerRot <= playerRotThr:
            visibleRot = playerRot
        
        playerSurface = pygame.transform.rotate(IMAGES['player'][playerIndex], visibleRot)
        SCREEN.blit(playerSurface, (playerx, playery))

        pygame.display.update()
        FPSCLOCK.tick(FPS)


def showGameOverScreen(crashInfo):
    """crashes the player down and shows gameover image"""
    global dataq
    dataq.queue.clear()
    score = crashInfo['score']
    playerx = SCREENWIDTH * 0.2
    playery = crashInfo['y']
    playerHeight = IMAGES['player'][0].get_height()
    playerVelY = crashInfo['playerVelY']
    playerAccY = 2
    playerRot = crashInfo['playerRot']
    playerVelRot = 7

    basex = crashInfo['basex']

    upperPipes, lowerPipes = crashInfo['upperPipes'], crashInfo['lowerPipes']

    # play hit and die sounds
    SOUNDS['hit'].play()
    if not crashInfo['groundCrash']:
        SOUNDS['die'].play()

    messagex = int((SCREENWIDTH - IMAGES['gameover'].get_width()) / 2)
    messagey = int(SCREENHEIGHT * 0.12)
    global jumpq

    while True:

        try:
            j = jumpq.get_nowait()
        except:
            j = 0 #no jump was in the queue
        if j == 1 or j == 2:
            if playery + playerHeight >= BASEY - 1:
                #jump = 0
                return score
        
        else:
        
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                    pygame.quit()
                    sys.exit()
                if event.type == KEYDOWN and (event.key == K_SPACE or event.key == K_UP):
                    if playery + playerHeight >= BASEY - 1:
                        return score
    
        # player y shift
        if playery + playerHeight < BASEY - 1:
            playery += min(playerVelY, BASEY - playery - playerHeight)

        # player velocity change
        if playerVelY < 15:
            playerVelY += playerAccY

        # rotate only when it's a pipe crash
        if not crashInfo['groundCrash']:
            if playerRot > -90:
                playerRot -= playerVelRot

        # draw sprites
        SCREEN.blit(IMAGES['background'], (0,0))
        SCREEN.blit(IMAGES['gameover'], (messagex, messagey*2))
        
        for uPipe, lPipe in zip(upperPipes, lowerPipes):
            SCREEN.blit(IMAGES['pipe'][0], (uPipe['x'], uPipe['y']))
            SCREEN.blit(IMAGES['pipe'][1], (lPipe['x'], lPipe['y']))

        SCREEN.blit(IMAGES['base'], (basex, BASEY))
        showScore(score/2)
        
        playerSurface = pygame.transform.rotate(IMAGES['player'][1], playerRot)
        SCREEN.blit(playerSurface, (playerx,playery))

        FPSCLOCK.tick(FPS)
        pygame.display.update()

def highScoreInput(score):
    """checks to see if score breaks leaderboard"""

    # index of player to blit on screen
    playerIndex = 0
    playerIndexGen = cycle([0, 1, 2, 1])
    # iterator used to change playerIndex after every 5th iteration
    loopIter = 0

    playerx = int(SCREENWIDTH * 0.2)
    playery = int((SCREENHEIGHT - IMAGES['player'][0].get_height()) / 2)

    messagex = int((SCREENWIDTH - IMAGES['message'].get_width()) / 2)
    messagey = int(SCREENHEIGHT * 0.12)

    basex = 0
    # amount by which base can maximum shift to left
    baseShift = IMAGES['base'].get_width() - IMAGES['background'].get_width()

    # player shm for up-down motion on welcome screen
    playerShmVals = {'val': 0, 'dir': 1}
    global jumpq
    j = 0

    GPIO.setmode(GPIO.BCM)

    GPIO.setup(17,GPIO.IN, pull_up_down=GPIO.PUD_UP)

    GPIO.setup(27,GPIO.IN, pull_up_down=GPIO.PUD_UP)

    GPIO.setup(22,GPIO.IN, pull_up_down=GPIO.PUD_UP)

    GPIO.setup(23,GPIO.IN, pull_up_down=GPIO.PUD_UP)

    GPIO.setwarnings(False)

    GPIO.setup(16,GPIO.IN, pull_up_down=GPIO.PUD_UP)
    
    initial = [0, 0, 0]
    x = 0
    while True:
        input_state = GPIO.input(17)
        input_state2 = GPIO.input(27)
        input_state3 = GPIO.input(22)
        input_state4 = GPIO.input(23)
        input_state5 = GPIO.input(16)
        
        if input_state == False:
            print("Up")
        
        if input_state2 == False:
            print("Down")
       
        if input_state3 == False:
            print("Left")
            
        if input_state4 == True:
            print("Right")

        try:
            j = jumpq.get_nowait()
        except:
            j = 0
        if input_state5 == False:
            print ("in if")    
            SOUNDS['wing'].play()
            time.sleep(.2)

            scoreArray = [None] * 10
            f = open("scores.txt", "r")
            i = 0
            for x in f:
                scoreArray[i] = x
                i = i + 1
            f.close()
            #d = shelve.open('scores.dat')

            #scoreArray = [d['s1'], d['s2'], d['s3'], d['s4'], d['s5'], d['s6'], d['s7'], d['s8'], d['s9'], d['s10']]

            first = int(scoreArray[0].split()[1])
            second = int(scoreArray[1].split()[1])
            third = int(scoreArray[2].split()[1])
            fourth = int(scoreArray[3].split()[1])
            fifth = int(scoreArray[4].split()[1])
            sixth = int(scoreArray[5].split()[1])
            seventh = int(scoreArray[6].split()[1])
            eighth = int(scoreArray[7].split()[1])
            ninth = int(scoreArray[8].split()[1])
            last = int(scoreArray[9].split()[1])

            if(score/2) < 10:
                scoreString = "00" + str(int(score/2))
            elif(score/2) < 100:
                scoreString = "0" + str(int(score/2))
            else:
                scoreString = str(int(score/2))


            if ((score/2 > last)):
                scoreArray[9] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString + '\n'

            print(scoreArray[9])
            
            f = open("scores.txt", "w")
            f.write(scoreArray[0])
            f.write(scoreArray[1])
            f.write(scoreArray[2])
            f.write(scoreArray[3])
            f.write(scoreArray[4])
            f.write(scoreArray[5])
            f.write(scoreArray[6])
            f.write(scoreArray[7])
            f.write(scoreArray[8])
            f.write(scoreArray[9])
            f.close()
            
            """
            if ((score/2) > first):
                d['s10'] = d['s9']
                d['s9'] = d['s8']
                d['s8'] = d['s7']
                d['s7'] = d['s6']
                d['s6'] = d['s5']
                d['s5'] = d['s4']
                d['s4'] = d['s3']
                d['s3'] = d['s2']
                d['s2'] = d['s1']
                d['s1'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
            elif ((score/2) > second):
                d['s10'] = d['s9']
                d['s9'] = d['s8']
                d['s8'] = d['s7']
                d['s7'] = d['s6']
                d['s6'] = d['s5']
                d['s5'] = d['s4']
                d['s4'] = d['s3']
                d['s3'] = d['s2']
                d['s2'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
            elif ((score/2) > third):
                d['s10'] = d['s9']
                d['s9'] = d['s8']
                d['s8'] = d['s7']
                d['s7'] = d['s6']
                d['s6'] = d['s5']
                d['s5'] = d['s4']
                d['s4'] = d['s3']
                d['s3'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
            elif ((score/2) > fourth):
                d['s10'] = d['s9']
                d['s9'] = d['s8']
                d['s8'] = d['s7']
                d['s7'] = d['s6']
                d['s6'] = d['s5']
                d['s5'] = d['s4']
                d['s4'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
            elif ((score/2) > fifth):
                d['s10'] = d['s9']
                d['s9'] = d['s8']
                d['s8'] = d['s7']
                d['s7'] = d['s6']
                d['s6'] = d['s5']
                d['s5'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
            elif ((score/2) > sixth):
                d['s10'] = d['s9']
                d['s9'] = d['s8']
                d['s8'] = d['s7']
                d['s7'] = d['s6']
                d['s6'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
            elif ((score/2) > seventh):
                d['s10'] = d['s9']
                d['s9'] = d['s8']
                d['s8'] = d['s7']
                d['s7'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
            elif ((score/2) > eighth):
                d['s10'] = d['s9']
                d['s9'] = d['s8']
                d['s8'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
            elif ((score/2) > ninth):
                d['s10'] = d['s9']
                d['s9'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
            elif ((score/2) > last):
                d['s10'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
            
            f.close()
            """
            return {
                    'playery': playery + playerShmVals['val'],
                    'basex': basex,
                    'playerIndexGen': playerIndexGen,
                    }
        else:
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                    pygame.quit()
                    sys.exit()
                #if (event.type == KEYDOWN and (event.key == K_SPACE or event.key == K_UP)):
                if input_state5 == False:
                    print ("in else")
                    # make first flap sound and return values for mainGame
                    SOUNDS['wing'].play()
                    time.sleep(.2)

                    d = shelve.open('scores.dat')

                    scoreArray = [d['s1'], d['s2'], d['s3'], d['s4'], d['s5'], d['s6'], d['s7'], d['s8'], d['s9'], d['s10']]

                    first = int(scoreArray[0].split()[1])
                    second = int(scoreArray[1].split()[1])
                    third = int(scoreArray[2].split()[1])
                    fourth = int(scoreArray[3].split()[1])
                    fifth = int(scoreArray[4].split()[1])
                    sixth = int(scoreArray[5].split()[1])
                    seventh = int(scoreArray[6].split()[1])
                    eighth = int(scoreArray[7].split()[1])
                    ninth = int(scoreArray[8].split()[1])
                    last = int(scoreArray[9].split()[1])

                    if(score/2) < 10:
                        scoreString = "00" + str(score/2)
                    elif(score/2) < 100:
                        scoreString = "0" + str(score/2)
                    else:
                        scoreString = str(score/2)


                    if ((score/2) > first):
                        d['s10'] = d['s9']
                        d['s9'] = d['s8']
                        d['s8'] = d['s7']
                        d['s7'] = d['s6']
                        d['s6'] = d['s5']
                        d['s5'] = d['s4']
                        d['s4'] = d['s3']
                        d['s3'] = d['s2']
                        d['s2'] = d['s1']
                        d['s1'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
                    elif ((score/2) > second):
                        d['s10'] = d['s9']
                        d['s9'] = d['s8']
                        d['s8'] = d['s7']
                        d['s7'] = d['s6']
                        d['s6'] = d['s5']
                        d['s5'] = d['s4']
                        d['s4'] = d['s3']
                        d['s3'] = d['s2']
                        d['s2'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
                    elif ((score/2) > third):
                        d['s10'] = d['s9']
                        d['s9'] = d['s8']
                        d['s8'] = d['s7']
                        d['s7'] = d['s6']
                        d['s6'] = d['s5']
                        d['s5'] = d['s4']
                        d['s4'] = d['s3']
                        d['s3'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
                    elif ((score/2) > fourth):
                        d['s10'] = d['s9']
                        d['s9'] = d['s8']
                        d['s8'] = d['s7']
                        d['s7'] = d['s6']
                        d['s6'] = d['s5']
                        d['s5'] = d['s4']
                        d['s4'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
                    elif ((score/2) > fifth):
                        d['s10'] = d['s9']
                        d['s9'] = d['s8']
                        d['s8'] = d['s7']
                        d['s7'] = d['s6']
                        d['s6'] = d['s5']
                        d['s5'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
                    elif ((score/2) > sixth):
                        d['s10'] = d['s9']
                        d['s9'] = d['s8']
                        d['s8'] = d['s7']
                        d['s7'] = d['s6']
                        d['s6'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
                    elif ((score/2) > seventh):
                        d['s10'] = d['s9']
                        d['s9'] = d['s8']
                        d['s8'] = d['s7']
                        d['s7'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
                    elif ((score/2) > eighth):
                        d['s10'] = d['s9']
                        d['s9'] = d['s8']
                        d['s8'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
                    elif ((score/2) > ninth):
                        d['s10'] = d['s9']
                        d['s9'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
                    elif ((score/2) > last):
                        d['s10'] = str(initial[0]) + ":" + str(initial[1]) + ":" + str(initial[2]) + " " + scoreString
                    
                    d.close()
                    
                    return {
                        'playery': playery + playerShmVals['val'],
                        'basex': basex,
                        'playerIndexGen': playerIndexGen,
                    }
        # adjust playery, playerIndex, basex
        if (loopIter + 1) % 5 == 0:
            playerIndex = next(playerIndexGen)
        loopIter = (loopIter + 1) % 30
        basex = -((-basex + 4) % baseShift)
        playerShm(playerShmVals)

        # draw sprites
        SCREEN.blit(IMAGES['background'], (0,0))
        SCREEN.blit(pygame.image.load('assets/letters/highScore.png').convert_alpha(), (int((SCREENWIDTH - pygame.image.load('assets/letters/highScore.png').convert_alpha().get_width()) / 2),int(SCREENHEIGHT * 0.12)))
        #SCREEN.blit(IMAGES['base'], (basex, BASEY))

        y = 150
        SCREEN.blit(IMAGES['letters'][initial[0]], (107,y))
        SCREEN.blit(IMAGES['letters'][initial[1]], (107 + 27,y))
        SCREEN.blit(IMAGES['letters'][initial[2]], (107 + 27 + 27,y))
        if input_state == False:
            initial[x] = initial[x] - 1
            if initial[x] < 0:
                initial[x] = 25
            time.sleep(.1)
                
        if input_state2 == False:
            initial[x] = initial[x] + 1
            if initial[x] > 25:
                initial[x] = 0
            time.sleep(.1)
                
        if input_state3 == True:
            x = x - 1
            if x < 0:
                x = 0
            time.sleep(.1)
                
        if input_state4 == False:
            x = x + 1
            if x > 2:
                x = 2
            time.sleep(.1)

        pygame.display.update()
        FPSCLOCK.tick(FPS)
    
def showHighScoreScreen():
    # index of player to blit on screen
    playerIndex = 0
    playerIndexGen = cycle([0, 1, 2, 1])
    # iterator used to change playerIndex after every 5th iteration
    loopIter = 0

    playerx = int(SCREENWIDTH * 0.2)
    playery = int((SCREENHEIGHT - IMAGES['player'][0].get_height()) / 2)

    messagex = int((SCREENWIDTH - IMAGES['message'].get_width()) / 2)
    messagey = int(SCREENHEIGHT * 0.12)

    basex = 0
    # amount by which base can maximum shift to left
    baseShift = IMAGES['base'].get_width() - IMAGES['background'].get_width()

    # player shm for up-down motion on welcome screen
    playerShmVals = {'val': 0, 'dir': 1}
    global jumpq
    j = 0
    GPIO.setmode(GPIO.BCM)

    GPIO.setwarnings(False)

    GPIO.setup(16,GPIO.IN, pull_up_down=GPIO.PUD_UP)
    while True:
        input_state5 = GPIO.input(16)
        try:
            j = jumpq.get_nowait()
        except:
            j = 0
        if input_state5 == False:
            SOUNDS['wing'].play()

            return {
                    'playery': playery + playerShmVals['val'],
                    'basex': basex,
                    'playerIndexGen': playerIndexGen,
                    }
        else:
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                    pygame.quit()
                    sys.exit()
                if input_state5 == False:
                    # make first flap sound and return values for mainGame
                    SOUNDS['wing'].play()
                    return {
                        'playery': playery + playerShmVals['val'],
                        'basex': basex,
                        'playerIndexGen': playerIndexGen,
                    }
        # adjust playery, playerIndex, basex
        if (loopIter + 1) % 5 == 0:
            playerIndex = next(playerIndexGen)
        loopIter = (loopIter + 1) % 30
        basex = -((-basex + 4) % baseShift)
        playerShm(playerShmVals)

        # draw sprites
        SCREEN.blit(IMAGES['background'], (0,0))

        #d = shelve.open('scores.dat')
        #scoreArray = [d['s1'], d['s2'], d['s3'], d['s4'], d['s5'], d['s6'], d['s7'], d['s8'], d['s9'], d['s10']]

        scoreArray = [None] * 10
        f = open("scores.txt", "r")
        i = 0
        for x in f:
            scoreArray[i] = x
            i = i + 1
        
        counter = 0
        y = 30
        iterate = 0
        while counter < 10:
            SCREEN.blit(IMAGES['letters'][int(scoreArray[iterate].split()[0].split(':')[0])], (56,y))
            SCREEN.blit(IMAGES['letters'][int(scoreArray[iterate].split()[0].split(':')[1])], (56 + 27,y))
            SCREEN.blit(IMAGES['letters'][int(scoreArray[iterate].split()[0].split(':')[2])], (56 + 27 + 27,y))

            #print(int(scoreArray[iterate].split()[1]) / 100)
            #print(int(scoreArray[iterate].split()[1]) // 100)

            SCREEN.blit(IMAGES['numbers'][int(scoreArray[iterate].split()[1]) // 100], (56 + 27 + 27 + 27 + 27,y))
            SCREEN.blit(IMAGES['numbers'][int(scoreArray[iterate].split()[1]) // 10 % 10], (56 + 27 + 27 + 27 + 27 + 27,y))
            SCREEN.blit(IMAGES['numbers'][int(scoreArray[iterate].split()[1]) % 10], (56 + 27 + 27 + 27 + 27 + 27 + 27,y))
            
            counter += 1
            y += 38
            iterate += 1

        f.close()
        
        SCREEN.blit(IMAGES['base'], (basex, BASEY))

        pygame.display.update()
        FPSCLOCK.tick(FPS)
    
def playerShm(playerShm):
    """oscillates the value of playerShm['val'] between 8 and -8"""
    if abs(playerShm['val']) == 8:
        playerShm['dir'] *= -1

    if playerShm['dir'] == 1:
         playerShm['val'] += 1
    else:
        playerShm['val'] -= 1


def getRandomPipe():
    """returns a randomly generated pipe"""
    # y of gap between upper and lower pipe
    gapY = random.randrange(0, int(BASEY * 0.5 - PIPEGAPSIZE))
    gapY += int(BASEY * 0.175)
    pipeHeight = IMAGES['pipe'][0].get_height()
    pipeX = SCREENWIDTH + 2

    return [
        {'x': pipeX, 'y': gapY - pipeHeight - 50},  # upper pipe
        {'x': pipeX, 'y': gapY + PIPEGAPSIZE + 80}, # lower pipe
    ]


def showScore(score):
    """displays score in center of screen"""
    scoreDigits = [int(x) for x in list(str(int(score)))]
    #print((score))
    #scoreDigits = [1,2]
    totalWidth = 0 # total width of all numbers to be printed

    for digit in scoreDigits:
        totalWidth += IMAGES['numbers'][digit].get_width()

    Xoffset = (SCREENWIDTH - totalWidth) / 2

    for digit in scoreDigits:
        SCREEN.blit(IMAGES['numbers'][digit], (Xoffset, SCREENHEIGHT * 0.1))
        Xoffset += IMAGES['numbers'][digit].get_width()


def checkCrash(player, upperPipes, lowerPipes):
    """returns True if player collders with base or pipes."""
    pi = player['index']
    player['w'] = IMAGES['player'][0].get_width()
    player['h'] = IMAGES['player'][0].get_height()

    # if player crashes into ground
    if player['y'] + player['h'] >= BASEY - 1:
        return [True, True]
    else:

        playerRect = pygame.Rect(player['x'], player['y'],
                      player['w'], player['h'])
        pipeW = IMAGES['pipe'][0].get_width()
        pipeH = IMAGES['pipe'][0].get_height()

        for uPipe, lPipe in zip(upperPipes, lowerPipes):
            # upper and lower pipe rects
            uPipeRect = pygame.Rect(uPipe['x'], uPipe['y'], pipeW, pipeH)
            lPipeRect = pygame.Rect(lPipe['x'], lPipe['y'], pipeW, pipeH)

            # player and upper/lower pipe hitmasks
            pHitMask = HITMASKS['player'][pi]
            uHitmask = HITMASKS['pipe'][0]
            lHitmask = HITMASKS['pipe'][1]

            # if bird collided with upipe or lpipe
            uCollide = pixelCollision(playerRect, uPipeRect, pHitMask, uHitmask)
            lCollide = pixelCollision(playerRect, lPipeRect, pHitMask, lHitmask)

            if uCollide or lCollide:
                return [True, False]

    return [False, False]

def pixelCollision(rect1, rect2, hitmask1, hitmask2):
    """Checks if two objects collide and not just their rects"""
    rect = rect1.clip(rect2)

    if rect.width == 0 or rect.height == 0:
        return False

    x1, y1 = rect.x - rect1.x, rect.y - rect1.y
    x2, y2 = rect.x - rect2.x, rect.y - rect2.y

    for x in xrange(rect.width):
        for y in xrange(rect.height):
            if hitmask1[x1+x][y1+y] and hitmask2[x2+x][y2+y]:
                return True
    return False

def getHitmask(image):
    """returns a hitmask using an image's alpha."""
    mask = []
    for x in xrange(image.get_width()):
        mask.append([])
        for y in xrange(image.get_height()):
            mask[x].append(bool(image.get_at((x,y))[3]))
    return mask

ser = serial.Serial('/dev/ttyACM0', baudrate=115200, bytesize = 8, parity = 'N',stopbits = 1)
t1 = Thread(target=serialread, args=())
t1.start()
t4 = Thread(target=jumpThread, args=())
t4.start()
t2 = Thread(target=flappyGame, args=())
t2.start()
