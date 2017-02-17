# uncompyle6 version 2.9.8
# Python bytecode 3.4 (3310)
# Decompiled from: Python 2.7.9 (default, Apr  7 2015, 07:58:25) 
# [GCC 4.2.1 Compatible Apple LLVM 6.0 (clang-600.0.57)]
# Embedded file name: mypi_server.py
# Compiled at: 2016-06-02 06:08:00
# Size of source mod 2**32: 4931 bytes
import socket
import sys
import RPi.GPIO as GPIO
import json
import threading
import configparser
import os
import time
print('MyPi TCP Server v1.4')
path = os.path.dirname(os.path.abspath(__file__)) + '/mypi.cfg'
print('Loading configuration file: ' + path)
config = configparser.ConfigParser()
config.read(path)
BUFFER_SIZE = 256
TCP_IP = '0.0.0.0'
PASSWORD = config.get('CONNECTION', 'PASSWORD')
PASSWORD = PASSWORD.strip('"')
TCP_PORT = config.getint('CONNECTION', 'TCP_PORT')
INIT_LEVEL = config.getint('GPIO', 'INIT_LEVEL')
DELAY = config.getfloat('GPIO', 'DELAY')
MAX_OUTPUT_PINS = 8
OUTPUTS = []
INPUTS = []
MODES = []
for x in range(1, MAX_OUTPUT_PINS + 1):
    outs = 'OUT' + str(x)
    ins = 'IN' + str(x)
    modes = outs + '-MODE'
    OUTPUTS.append(config.getint('GPIO', outs))
    INPUTS.append(config.getint('GPIO', ins))
    mode = config.get('GPIO', modes)
    mode = mode.strip('"')
    MODES.append(mode)

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
connectionsList = []
print('Init GPIO Output pins')
for pin in OUTPUTS:
    GPIO.setup(pin, GPIO.OUT, initial=INIT_LEVEL)

print('Init GPIO Input pins')
for pin in INPUTS:
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def flip(socket, x):
    GPIO.output(OUTPUTS[x], not GPIO.input(OUTPUTS[x]))
    print('Pin %d: level=%d' % (OUTPUTS[x], GPIO.input(OUTPUTS[x])))
    updateAllClients(socket)


def flipOutput(socket, index):
    flip(socket, index)
    if MODES[index] == 'M':
        time.sleep(DELAY)
        flip(socket, index)

def getInputs():
    status = []
    for x in range(0, MAX_OUTPUT_PINS):
        status.append(GPIO.input(OUTPUTS[x]))

    return status


def sendResponse(connection, ctx, status):
    response = {}
    response['ctx'] = ctx
    response['status'] = status
    connection.send(bytes(json.dumps(response), 'UTF-8'))


def updateAllClients(socket):
    global connectionsList
    status = getInputs()
    if socket == '':
        for currentConn in connectionsList:
            sendResponse(currentConn, 'update', status)

    else:
        sendResponse(socket, 'update', status)
        for currentConn in connectionsList:
            if currentConn != socket:
                sendResponse(currentConn, 'update', status)
                continue


def checkInputs():
    delay = 0.1
    for x in range(0, MAX_OUTPUT_PINS):
        if GPIO.input(INPUTS[x]) == 0:
            threading.Thread(target=flipOutput, args=('', x)).start()
            delay = 0.2
            continue

    threading.Timer(delay, checkInputs).start()


checkInputs()

class ClientThread(threading.Thread):

    def __init__(self, ip, port, clientsocket):
        threading.Thread.__init__(self)
        self.ip = ip
        self.port = port
        self.socket = clientsocket
        print('Connected to: ' + ip)

    def run(self):
        global BUFFER_SIZE
        auth = False
        sendResponse(self.socket, 'sendcode', '')
        while 1:
            data = self.socket.recv(BUFFER_SIZE)
            if not data:
                break
            info = data.decode('UTF-8')
            list = info.split()
            cmd = list[0]
            val = list[1]
            if cmd == 'password':
                if val == PASSWORD:
                    auth = True
                    sendResponse(self.socket, 'password', getInputs())
                    connectionsList.append(self.socket)
                else:
                    sendResponse(self.socket, 'password', 'codenotok')
                    self.socket.shutdown(0)
            if auth:
                if cmd == 'update':
                    index = int(val)
                    if 0 <= index < MAX_OUTPUT_PINS:
                        threading.Thread(target=flipOutput, args=(self.socket, index)).start()
                if cmd == 'get':
                    if val == 'status':
                        sendResponse(self.socket, 'update', status)
                else:
                    continue

        if self.socket in connectionsList:
            connectionsList.remove(self.socket)
        print(self.ip + ' Disconnected...')


tcpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcpsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
tcpsock.bind((TCP_IP, TCP_PORT))
print('Listening for incoming connections on Port ' + str(TCP_PORT))
while True:
    tcpsock.listen(5)
    clientsock, (TCP_IP, TCP_PORT) = tcpsock.accept()
    newthread = ClientThread(TCP_IP, TCP_PORT, clientsock)
    newthread.start()