
# SPDX-FileCopyrightText: 2020 Jeff Epler for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""CircuitPython Essentials Audio Out MP3 Example"""
import board
import busio
import time
import digitalio
from dyplayer import DYPlayer

# TX/RX pins to be connected to RX/TX on the MP3 player
# Pico UART2 TX (GP8) <-> MP3 Player RX
# Pico UART2 RX (GP9) <-> MP3 Player TX
player_uart = busio.UART(board.GP8, board.GP9, baudrate=9600)

# Create Player Object
player = DYPlayer(uart=player_uart)
time.sleep(0.4) #Leave time to initialize

# Query how many songs on SD card
numsongs = player.queryNumSongs()
print("number of songs in directory is ", numsongs)
time.sleep(0.2)

# Find current state. 0 is stopped, 1 is playing, 2 is paused
state = player.queryPlayState()
if state is not None:
    print("play state is ", state)
else:
    time.sleep(0.5)
    state = player.queryPlayState()
    print("second try play state is ", state)

# The current song is the song number which will play with the "play" command
curSong = player.queryCurrentSong()
print("Current song = ", curSong)
if curSong is None:
    curSong = 2

# Set volume takes a number from 0-30
print("Setting volume to 15")
player.setVolume(15)

# Play the current song for 3 seconds before stopping it
print("playing the current song")
player.play()
time.sleep(3)
player.stop()

# Try setting a higher volume
print("Setting volume to 10")
player.setVolume(10)

# If the current song is not the last one in the directory, play
# the next song, otherwise play the previous song
if numsongs is not None and curSong < numsongs:
    print("Playing the next song")
    player.next()
else:
    print("Playing the previous song")
    player.prev()

time.sleep(3) # let the song play for 3 seconds before stopping it
player.stop()

#  Play all songs in the directory numerically for a fixed
#  time interval. Note that first song is numbered 1, not 0
playTime = 2
for i in range(1,numsongs+1):
    print("Playing song ", i, " for ", playTime, " seconds")
    player.playByNumber(i)
    # Dont start the timer until the player has started
    while (player.queryPlayState() != 1):
        print("waiting to start playing...")
        time.sleep(0.1)
    time.sleep(playTime)  # Let each song play for two seconds before stopping it
    player.stop()

#  Play the entirety of each song in the directory
#  While each song is playing, query the play state to
#  find out when it is finsished. The play state values are
#  0 -> stopped, 1 -> playing, 2 -> paused
for i in range(1, numsongs+1):
    print("Playing song ", i)
    player.playByNumber(i)
    time.sleep(0.25)
    while(player.queryPlayState() == 1):
        time.sleep(0.1)




