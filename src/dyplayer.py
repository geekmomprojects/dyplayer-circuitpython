# ----------------------------------------------------------------------------
# CircuitPython driver library for the DY-SV5W Playback Module.
# Module manual at: https://grobotronics.com/images/companies/1/datasheets/DY-SV5W%20Voice%20Playback%20ModuleDatasheet.pdf?1559812879320
# May work for other versions of DYy player, but has not been tested.
#
# To use this library, DIP pins on DY-SV5W should be set to (1)Low (2)Low (3)High
# and set the IO0/TX to controller UART RX, and IO1/RX to controller UART TX
#
# Adapted (not all functionality present) from the Arduino API by SnijderC:
# https://github.com/SnijderC/dyplayer
#
# Author: Debra Ansell
# License: MIT
#
# Website:
#
# ----------------------------------------------------------------------------

import board
import time
import busio
import struct


class PlayState():
    FAIL    = -1
    STOPPED = 0
    PLAYING = 1
    PAUSED  = 2

class PlayMode():
    REPEAT          = 0x00  # Play all music in sequence, and repeat
    REPEAT_ONE      = 0x01  # Repeat current sound
    ONE_OFF         = 0x02  # Play sound file and stop
    RANDOM          = 0x03  # Play random sound file.
    REPEAT_DIR      = 0x04  # Repeat current directory
    RANDOM_DIR      = 0x05  # Play random sound file in current folder.
    SEQUENCE_DIR    = 0x06  # Play all sound files in current folder in sequence, and stop
    SEQUENCE        = 0X07  # Play all sound files on device in sequence, and stop

def clamp(x, minval, maxval):
    return max(min(maxval, x), minval)

class DYPlayer(object):

  # --- commands from DY-SV5W datasheet)  ----------------

  # --- control commands (no return value) ------------------
  CMD_PLAY          = b'\xaa\x02\x00\xac'    # - PLAY
  CMD_PAUSE         = b'\xaa\x03\x00\xad'    # - PAUSE
  CMD_STOP          = b'\xaa\x04\x00\xae'    # - STOP
  CMD_PREV          = b'\xaa\x05\x00\xaf'    # - PREVIOUS MUSIC
  CMD_NEXT          = b'\xaa\x06\x00\xb0'    # - NEXT MUSIC
  CMD_VOL_UP        = b'\xaa\x14\x00\xbe'
  CMD_VOL_DOWN      = b'\xaa\x15\x00\xbf'
  CMD_PREV_FILE     = b'\xaa\x0e\x00\xb8'
  CMD_NEXT_FILE     = b'\xaa\x0f\x00\xb9'
  CMD_STOP_PLAYING  = b'\xaa\x10\x00\xba'

  # --- control commands with parameters -------------------------------
  CMD_PLAY_BY_NUMBER = b'\xaa\x07\x02'  # +SNH +SNL (low, high bits from 0x00-0xff)
  CMD_PLAY_BY_PATH   = b'\xaa\x08'      # +LENGTH +DRIVE +PATH (length, drive, path all from 0x00 to 0xff)

  # --- query commands (with return value format) --------------
  QUERY_PLAY_STATUS      = b'\xaa\x01\x00\xab'  #aa 01 01, play status, SM   - CHECK PLAY STATUS
  QUERY_ONLINE_DRIVE     = b'\xaa\x09\x00\xb3'  #aa 09 01, drive, SM         -
  QUERY_PLAY_DRIVE       = b'\xaa\x0a\x00\xb4'  #aa 0a 01, drive, SM         - CHECK CURRENT PLAYING DEVICE
  QUERY_NUM_SONGS        = b'\xaa\x0c\x00\xb6'  #aa 0c 02 S.N.H S.N.L SM     - CHECK NUMBER OF ALL MUSIC
  QUERY_CURRENT_SONG     = b'\xaa\x0d\x00\xb7'  #aa 0d 02 S.N.H S.N.L SM     - CHECK CURRENT MUSIC
  QUERY_FOLDER_DIR_SONG  = b'\xaa\x11\x00\xbb'  #aa 11 02 S.N.H S.N.L SM     - CHECK FIRST MUSIC IN FOLDER
  QUERY_FOLDER_NUM_SONG  = b'\xaa\x12\x00\xbc'  #aa 12 02 S.N.H S.N.L SM     - CHECK NUMBER OF MUSIC IN FOLDER

  # --- set commands (with parameter notes from datasheet)
  SET_VOLUME        = b'\xaa\x13\x01' # + VOL SM (vol: 0x00-0xFF)
  SET_CYCLE_MODE    = b'\xaa\x18\x01' # + LOOP-MODE SM (LOOP-MODE 0X00-0X07)
  SET_CYCLE_TIMES   = b'\xaa\x19\x01' # + H L SM (H: 0x00-0xFF, L:0x00-0xFF)
  SET_EQ            = b'\xaa\x01'     # + EQ SM (EQ: 0X00-0X04)

  #TBD - Specified Song by Path

  # --- constructor   --------------------------------------------------------

  def __init__(self,uart=None,media=None,volume=50,eq=None,latency=0.100):
    if uart is None:
      self._uart = busio.UART(board.TX,board.RX,baudrate=9600)
    else:
      self._uart = uart
    self._latency = latency

  # --- transfer data to device   ---------------------------------------------
  def _write_data(self, buf):
    self._uart.write(buf)

  # --- read data from device   ------------------------------------------------
  def _read_data(self, buf):
    index = 0
    while self._uart.in_waiting:
      readbuf = self._uart.read(32)
      print(readbuf)
      if readbuf is not None:
        for i in range(len(readbuf)):
          buf[index] = readbuf[i]
          index = index + 1
    return index

  # --- data validation   ------------------------------------------------------
  def checksum(self, data, length):
    val = 0
    for i in range(length):
      val = (val + data[i]) % 255
    return val

  # --- takes bytearray and appends checksum byte ------------------------------
  def appendChecksum(self, data, length):
      return data + bytes([self.checksum(data, length)])

  def appendChecksum(self, data):
      return data + bytes([self.checksum(data, len(data))])

  def validateCrc(self, data, length):
    return self.checksum(data[0:length-1], length-1) == data[length-1]

  # --- send/read commands -----------------------------------------------------
  def sendCommand(self, cmd):
    if isinstance(cmd, bytearray):
        self._write_data(cmd)
    else:
        self._write_data(bytearray(cmd))

  # --- TBD path commands not yet functional
  def sendPathCommand(self, cmd, path):
    device = 1
    path = path.upper()
    print(path)
    bytepath = str.encode(path)
    print(bytepath)
    pathlen = len(path)
    if pathlen < 1:
        return
    # Count "/" in path, except root slash and determine new length
    num_slash = path[1:].count('/')
    print(num_slash, " slashes")
    bytecmd = bytearray(len(cmd) + pathlen + num_slash + 2)
    cmdlen = len(cmd)
    for i in range(cmdlen):
        bytecmd[i] = cmd[i]

    print(bytecmd)
    print(pathlen + num_slash)
    bytecmd[cmdlen]        = pathlen + num_slash
    print(bytecmd)
    bytecmd[cmdlen + 1]    = device
    bytecmd[cmdlen + 2]    = ord(path[0])
    idx = 3
    for i in range(1, pathlen):
      ch = path[i]
      bytech = bytepath[i]
      #print(ch, bytech)
      if ch == '.':
        #print("here")
        bytecmd[cmdlen + idx] = ord('*')
        idx = idx + 1
      else:
        if ch == '/':
          bytecmd[cmdlen + idx] = ord('*')
          idx = idx + 1
        bytecmd[cmdlen + idx] = bytech
        idx = idx + 1
    print("cmd = ", bytecmd)
    self._write_data(bytecmd,)
    self._write_data(bytes([self.checksum(bytecmd, len(bytecmd))]))

    #fullcmd = self.appendChecksum(bytecmd)
    #print("path command = ", fullcmd)
    #self.sendCommand(fullcmd)


  # Timeout determines how long to wait for response
  def getResponse(self, buffer, timeout = 1):
    nbytes = 0
    start = time.monotonic()
    while (nbytes == 0 and time.monotonic() - start < timeout):
        nbytes = self._read_data(buffer)
    if nbytes == 0:
      print("no data received")
      return 0
    if self.validateCrc(buffer, nbytes):
      return nbytes
    else:
      print("data not validated ", buffer)
      return 0


  # --- play current file ---------------------------------------------------------
  def play(self):
    self.sendCommand(DYPlayer.CMD_PLAY)

  # --- play the next file --------------------------------------------------------
  def next(self):
    self.sendCommand(DYPlayer.CMD_NEXT)

  # --- play the previous file -----------------------------------------------------
  def prev(self):
      self.sendCommand(DYPlayer.CMD_PREV)

  # --- stop ----------------
  def stop(self):
      self.sendCommand(DYPlayer.CMD_STOP)

  # --- stop playing --------------------------------------------------------------
  def stopPlaying(self):
      self.sendCommand(DYPlayer.CMD_STOP_PLAYING)

  # --- pause ----------------------------------------------------------------------
  def pause(self):
      self.sendCommand(DYPlayer.CMD_PAUSE)

  # --- find the current device ----------------------------------------------------
  def queryDevice(self):
      self.sendCommand(DYPlayer.QUERY_PLAY_DRIVE)
      resp = bytearray(10)
      print("waiting...")  # Need to give MP3 player time to respond
      time.sleep(2)
      val = self.getResponse(resp)
      if (val):
          #print("response was: ", resp)
          return resp[3]
      else:
          print("query failed to get response")
          return None

  # --- get the current play state, can be called any time. Returns value from PlayState class -----
  def queryPlayState(self):
      self.sendCommand(DYPlayer.QUERY_PLAY_STATUS)
      resp = bytearray(16)
      time.sleep(0.1)  #Don't know if this is necessary
      val = self.getResponse(resp)
      if val:
          #print("val = ", val, " response = ", resp[0:val])
          #print("response was:", resp[0:val])
          return resp[3]  # Play state is 4th byte of response
      else:
          #print("failed to get response")
          return None

  # --- get the number of the current song ------------------
  def queryCurrentSong(self):
      self.sendCommand(DYPlayer.QUERY_CURRENT_SONG)
      resp = bytearray(16)
      time.sleep(0.5)
      val = self.getResponse(resp)
      if val:
        #print("val = ", val, " response = ", resp)
        return (resp[3] << 8) | resp[4]
      else:
        print("failed to get response")
        return None

  # --- get the number of songs available --------------------
  def queryNumSongs(self):
      self.sendCommand(DYPlayer.QUERY_NUM_SONGS)
      resp = bytearray(16)
      time.sleep(0.5)
      val = self.getResponse(resp)
      if val:
        #print("Query num songs val = ", val, " response = ", resp[0:val])
        return (resp[3] << 8) | resp[4]
      else:
        #print("failed to get response")
        return None

  # --- set the volume to a value between 0 and 30
  def setVolume(self, vol):
    vol = clamp(vol, 0, 30)
    cmd = self.appendChecksum( DYPlayer.SET_VOLUME + bytes([vol]) )
    self.sendCommand(cmd)

  def increaseVolume(self, vol):
    self.sendCommand(DYPlayer.CMD_VOL_UP)

  def decreaseVolume(self, vol):
    self.sendCommand(DYPlayer.CMD_VOL_DOWN)

  # --- play a song by number order ------
  def playByNumber(self, num):
    cmd = self.appendChecksum( DYPlayer.CMD_PLAY_BY_NUMBER + bytes([num >> 8]) + bytes([num & 0xff]) )
    self.sendCommand(cmd)

  # --- play a song specified by its path (assume device=1 is SD card) -----
  # NOT YET WORKING
  def playByPath(self, path):
    self.sendPathCommand(DYPlayer.CMD_PLAY_BY_PATH, path)



