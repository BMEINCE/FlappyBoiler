import serial
from itertools import cycle
import random
import sys
import serial
import time
import mutex
import threading
import matplotlib
from matplotlib import pyplot as plt
import numpy as np
import matplotlib.animation as animation
from threading import Thread
from threading import Lock
import pygame
from pygame.locals import *
from Queue import *


fig = plt.figure()
ax1 = fig.add_subplot(1,1,1)
y_range = [100,1000]
sensor = list(range(450,500))
threshold = 50
timeAxis = list(range(0,50))
ax1.set_ylim(y_range)
line, = ax1.plot(timeAxis,sensor)
calib_lock = threading.Lock()
calib_finished = False
jump_lock = threading.Lock()
sensor_lock = threading.Lock()
jump = 0
jumpstat = 0
gold = [194,142,14]
black = [0,0,0]
FPS = 60
SCREENWIDTH  = 288
SCREENHEIGHT = 512
# amount by which base can maximum shift to left
PIPEGAPSIZE  = 110 # gap between upper and lower part of pipe
BASEY        = SCREENHEIGHT * 0.79
# image, sound and hitjump = 0mask  dicts
IMAGES, SOUNDS, HITMASKS = {}, {}, {}
s=[0]

q = Queue()
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
    'assets/sprites/Bell_Tower_8bit.png',
    'assets/sprites/Bell_Tower_8bit.png',
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

def serialread():
    global sensor_lock
    global sensor
    global q
    jdata = 0
    while True:
        time.sleep(.005)
        if ser.read(1) == 'z':
            read_serial = float(ser.read(3)) * (10/9)
            q.put(read_serial)
            if q.qsize() > 5:
                print (q.qsize())
            sensor_lock.acquire(True)
            sensor.pop(0)
            sensor.append(read_serial)
            sensor_lock.release()


def jumpThread():
    global jump
    global threshold
    global datajump
    global q
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
        data = q.get()
        calib_lock.release()

        #essentially abs(data - average_data_value)
        #the average_data_value of the signal has been observed to be 510
        if data >= 500:
            data = data - 500
        else:
            data = 500 - data

        if int(data/threshold)>=1:
            if state == 1:
                time.sleep(0.005)
            else:
                state = 1
                jumpcheck(2)
                time.sleep(0.005)
        else:
            counter += 1
            time.sleep(0.005)
        '''
        if read == 0:
            time.sleep(0.01)
            read = 1
        elif int(data/threshold) >= 1:
            counter = 0
            if state == 1:
                time.sleep(0.005)
            else:
                state = 1
                jumpcheck(2)
                read = 0
                time.sleep(0.005)
        else:
            counter += 1
        '''

def graphStart():
    ani = animation.FuncAnimation(fig, graphFunc,fargs=(), interval=35, blit = True)
    plt.show()
    
def graphFunc(i):
    global sensor
    global sensor_lock
    sensor_lock.acquire(True)
    line.set_ydata(sensor)
    sensor_lock.release()
    return line,

#1 returns value, 2 sets to jump
#Used to control communication of jumps to ensure thread safety

def jumpcheck(i):
    global jumpstat
    global jump_lock
    jump_lock.acquire(True)
    retval = 0
    if i == 1:
        if jumpstat == 1:
            jumpstat = 0
            retval = 1
        else :
            retval = 0
    else :
        jumpstat = 1
    jump_lock.release()
    return retval

def calibrate():
    global q
    print "calibrating"
    global calib_lock
    global calib_finished
    calib_lock.acquire(True)
    #time.sleep(1.5)
    global threshold
    count = 0
    valuemaxc1 = 50
    valuemaxc2 = 50
    valuemaxc3 = 50
    for i in range(150):
        valueabsc = 0
        valuec = q.get()

        #take abs of data around the average
        if valuec <= 500:
            valueabsc = 500 - valuec
        else :
            valueabsc = valuec - 500

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
                threshold = 0.75*(valuemaxc2+valuemaxc3)/2
            else:
                threshold = 0.75*valuemaxc2

        else:
            threshold = 0.75*valuemaxc2

    elif count == 1:
        threshold = 0.75*valuemaxc1
    elif count == 2:
        threshold = 0.75*valuemaxc1
    elif count == 3:
        threshold = 0.75*((valuemaxc1+valuemaxc2)/2)
    elif count >= 4:

        if (valuemaxc1-valuemaxc3)>60 :
            threshold = 0.75*( (valuemaxc1+valuemaxc2+valuemaxc3)/3 )
        else:
            threshold = 0.75*( (valuemaxc1+valuemaxc2+(valuemaxc3+20))/3 )

    else:
        threshold = 0.75*valuemaxc1
    print ("threshold")
    print (threshold)
    calib_finished = True
    calib_lock.release()

def flappyGame():
    global SCREEN, FPSCLOCK
    pygame.init()
    FPSCLOCK = pygame.time.Clock()
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

    # game over sprite
    IMAGES['gameover'] = pygame.image.load('assets/sprites/gameover.png').convert_alpha()
    # message sprite for welcome screen
    IMAGES['message'] = pygame.image.load('assets/sprites/message.png').convert_alpha()
    # message sprite for calibration screen
    IMAGES['calib'] = pygame.image.load('assets/sprites/calib.png').convert_alpha()
    # base (ground) sprite
    IMAGES['base'] = pygame.image.load('assets/sprites/base.png').convert_alpha()

    # sounds
    if 'win' in sys.platform:
        soundExt = '.wav'
    else:
        soundExt = '.ogg'

    SOUNDS['die']    = pygame.mixer.Sound('assets/audio/die' + soundExt)
    SOUNDS['hit']    = pygame.mixer.Sound('assets/audio/smack' + soundExt)
    SOUNDS['point']  = pygame.mixer.Sound('assets/audio/score_bell' + soundExt)
    SOUNDS['swoosh'] = pygame.mixer.Sound('assets/audio/swoosh' + soundExt)
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
        showGameOverScreen(crashInfo)
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
    
    while True:

        j = jumpcheck(1)
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
    
    while True:

        j = jumpcheck(1)
        if j == 1 or j == 2:
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
    global q
    q.queue.clear()
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

        #
        j = jumpcheck(1)
        if j == 1 or j == 2:
            if playery + playerHeight >= BASEY - 1:
                #jump = 0
                return
        
        else:
        
            for event in pygame.event.get():
                if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                    pygame.quit()
                    sys.exit()
                if event.type == KEYDOWN and (event.key == K_SPACE or event.key == K_UP):
                    if playery + playerHeight >= BASEY - 1:
                        return
    
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
    pipeX = SCREENWIDTH + 10

    return [
        {'x': pipeX, 'y': gapY - pipeHeight - 50},  # upper pipe
        {'x': pipeX, 'y': gapY + PIPEGAPSIZE + 80}, # lower pipe
    ]


def showScore(score):
    """displays score in center of screen"""
    scoreDigits = [int(x) for x in list(str(score))]
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
t2 = Thread(target=graphStart, args=())
t2.start()
t3 = Thread(target=flappyGame, args=())
t3.start()

