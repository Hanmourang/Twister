
# File: tsclogging.py ; This file is part of Twister.

# version: 3.004

# Copyright (C) 2012 , Luxoft

# Authors:
#    Andrei Costachi <acostachi@luxoft.com>
#    Andrei Toma <atoma@luxoft.com>
#    Cristian Constantin <crconstantin@luxoft.com>
#    Daniel Cioata <dcioata@luxoft.com>

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at:

# http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

'''
This module is used by the Central Engine and the Resource Allocator,
to print debug and error messages.
It shouldn't be used anywhere else.
'''

import os
import datetime

import cherrypy
import logging as log

TWISTER_PATH = os.getenv('TWISTER_PATH')
if not TWISTER_PATH:
    print('TWISTER_PATH environment variable is not set! Exiting!')
    exit(1)

LOGS_PATH = TWISTER_PATH + '/logs/'
if not os.path.exists(LOGS_PATH):
    os.makedirs(LOGS_PATH)

formatter = log.Formatter('%(asctime)s  %(levelname)-8s %(message)s',
            datefmt='%y-%m-%d %H:%M:%S')

# CherryPy logging
cherry_log = cherrypy.log.error_log

# Config file logging
dateTag = datetime.datetime.now().strftime("%Y-%b-%d %H-%M-%S")
LOG_FILE = LOGS_PATH + 'Log %s.txt' % dateTag
filehnd = log.FileHandler(LOG_FILE, mode='w')
filehnd.setLevel(log.NOTSET)
filehnd.setFormatter(formatter)
cherry_log.addHandler(filehnd)

# Config console logging
console = log.StreamHandler()
console.setLevel(log.NOTSET)
console.setFormatter(formatter)
cherry_log.addHandler(console)


__all__ = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'LOG_FILE',
            'logMsg', 'logDebug', 'logInfo', 'logWarning', 'logError', 'logCritical']

DEBUG    = 1
INFO     = 2
WARNING  = 3
ERROR    = 4
CRITICAL = 5


def getLogLevel():
    logInfo('tsclogging:getLogLevel')
    #
    lvl = cherry_log.getEffectiveLevel()
    return lvl / 10
    #

def setLogLevel(Level):
    logInfo('tsclogging:setLogLevel')
    #
    if Level not in (DEBUG, INFO, WARNING, ERROR, CRITICAL):
        cherry_log.error('LOG: Invalid error level `%s`!' % str(Level))
        return
    #
    global filehnd, console
    cherry_log.setLevel(Level * 10)
    filehnd.setLevel(Level * 10)
    console.setLevel(Level * 10)
    #

def logMsg(Level, *args):
    logInfo('tsclogging:logMsg')
    #
    if Level not in (DEBUG, INFO, WARNING, ERROR, CRITICAL):
        cherry_log.error('LOG: Invalid error level `{}`!'.format(Level))
        return
    #
    stack = cherry_log.findCaller()
    msg = '{}: {}: {}  {}'.format(os.path.split(stack[0])[1], str(stack[1]), stack[2],
          ' '.join([str(i) for i in args]))
    #
    if Level == 1:
        cherry_log.debug(msg)
    elif Level == 2:
        cherry_log.info(msg)
    elif Level == 3:
        cherry_log.warning(msg)
    elif Level == 4:
        cherry_log.error(msg)
    else:
        cherry_log.critical(msg)
    #

def logDebug(*args):
    logInfo('tsclogging:logDebug')
    logMsg(DEBUG, *args)

def logInfo(*args):
    logInfo('tsclogging:logInfo')
    logMsg(INFO, *args)

def logWarning(*args):
    logInfo('tsclogging:logWarning')
    logMsg(WARNING, *args)

def logError(*args):
    logInfo('tsclogging:logError')
    logMsg(ERROR, *args)

def logCritical(*args):
    logInfo('tsclogging:logCritical')
    logMsg(CRITICAL, *args)
