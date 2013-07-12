
# File: CentralEngineOthers.py ; This file is part of Twister.

# version: 2.009

# Copyright (C) 2012-2013 , Luxoft

# Authors:
#    Adrian Toader <adtoader@luxoft.com>
#    Andrei Costachi <acostachi@luxoft.com>
#    Andrei Toma <atoma@luxoft.com>
#    Cristi Constantin <crconstantin@luxoft.com>
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

"""
Project Class
*************

The **Project** class collects and organizes all the information for
 the Central Engine.

Information about *users*:

- user name
- user status (start, stop, pause)
- paths to logs and config files
- paths to script pre and script post
- parameters for this project like: libraries, tc delay, DB AutoSave
- global params for current user

Information about *EPs*:

- EP name
- EP status (start, stop, pause)
- EP OS
- EP IP

Information about *Suites*:

- suite name
- other info from Test-Suites.XML (eg: release, or build)
- test bed name
- panic detect

Information about *Test Files*:

- file name
- complete file path
- test title
- test description
- timeout value (if any)
- test status (pass, fail, skip, etc)
- crash detected
- test params
- test date started and finished
- test time elapsed
- test log

"""
from __future__ import with_statement

import os
import sys
import re
import time
import json
import thread
import subprocess
import socket
import platform
import smtplib
import MySQLdb


from string import Template
from collections import OrderedDict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


TWISTER_PATH = os.getenv('TWISTER_PATH')
if not TWISTER_PATH:
    print('$TWISTER_PATH environment variable is not set! Exiting!')
    exit(1)
sys.path.append(TWISTER_PATH)

from common.constants import *
from common.tsclogging import *
from common.xmlparser import *
from common.suitesmanager import *


class Project:

    """
    This class controls data about:

    - users
    - EPs
    - suites
    - test files

    """

    def __init__(self):

        self.users = {}
        self.parsers = {}
        self.plugins = {}
        self.test_ids = {}
        self.suite_ids = {}

        self.usr_lock = thread.allocate_lock()  # User change lock
        self.int_lock = thread.allocate_lock()  # Internal use lock
        self.glb_lock = thread.allocate_lock()  # Global variables lock
        self.eml_lock = thread.allocate_lock()  # E-mail lock
        self.db_lock  = thread.allocate_lock()  # Database lock

        # Panic Detect, load config for current user
        self.panicDetectConfigPath = TWISTER_PATH + '/config/PanicDetectData.json'
        if not os.path.exists(self.panicDetectConfigPath):
            config = open(self.panicDetectConfigPath, 'wb')
            config.write('{}')
            config.close()
        config = open(self.panicDetectConfigPath, 'rb')
        self.panicDetectRegularExpressions = json.load(config)
        config.close()


    def _common_user_reset(self, user, base_config, files_config):

        try:
            self.users[user]['eps'] = OrderedDict()
        except:
            pass

        # List with all EPs for this User
        epList = self.parsers[user].epnames
        if not epList:
            logCritical('Project ERROR: Cannot load the list of EPs for user `{}` !'.format(user))
            return False

        # Generate the list of EPs in order
        for epname in epList:
            self.users[user]['eps'][epname] = OrderedDict()
            self.users[user]['eps'][epname]['status']   = STATUS_STOP
            self.users[user]['eps'][epname]['test_bed'] = ''
            # Each EP has a SuitesManager, helper class for managing file and suite nodes!
            self.users[user]['eps'][epname]['suites'] = SuitesManager()

        # Information about ALL project suites
        # Some master-suites might have sub-suites, but all sub-suites must run on the same EP
        suitesInfo = self.parsers[user].getAllSuitesInfo()

        # Allocate each master-suite for one EP
        for s_id, suite in suitesInfo.items():
            epname = suite['ep']
            if epname not in self.users[user]['eps']:
                continue
            self.users[user]['eps'][epname]['test_bed'] = suite['tb']
            self.users[user]['eps'][epname]['suites'][s_id] = suite

        # Ordered list of file IDs, used for Get Status ALL
        self.test_ids[user] = suitesInfo.getFiles()
        # Ordered list with all suite IDs, for all EPs
        self.suite_ids[user] = suitesInfo.getSuites()

        # Add framework config info to default user
        self.users[user]['config_path']  = base_config
        self.users[user]['project_path'] = files_config

        # Get project global variables from XML:
        # Path to DB, E-mail XML, Globals, `Testcase Delay` value,
        # `Exit on test Fail` value, 'Libraries', `Database Autosave` value,
        # `Pre and Post` project Scripts, `Scripts mandatory` value
        for k, v in self.parsers[user].project_globals.iteritems():
            self.users[user][k] = v

        self.users[user]['log_types'] = {}

        for logType in self.parsers[user].getLogTypes():
            self.users[user]['log_types'][logType] = self.parsers[user].getLogFileForType(logType)

        # Global params for user
        self.users[user]['global_params'] = self.parsers[user].getGlobalParams()

        return True


    def createUser(self, user, base_config='', files_config=''):
        """
        Create or overwrite one user.\n
        This creates a master XML parser and a list with all user variables.
        """
        if not user:
            return False

        config_data = None
        # If config path is actually XML data
        if base_config and ( type(base_config)==type('') or type(base_config)==type(u'') )\
        and ( base_config[0] == '<' and base_config[-1] == '>' ):
            config_data, base_config = base_config, ''

        user_home = userHome(user)

        # If it's a valid path
        if base_config and not os.path.exists(base_config):
            logCritical('Project ERROR: Config path {}` does not exist !'.format(base_config))
            return False
        elif not os.path.exists( '{}/twister'.format(user_home) ):
            logCritical('Project ERROR: Cannot find Twister for user `{}`, '\
                'in path `{}/twister`!'.format(user, user_home))
            return False
        else:
            base_config = '{}/twister/config/fwmconfig.xml'.format(user_home)

        if not files_config:
            files_config = '{}/twister/config/testsuites.xml'.format(user_home)

        # User data + User parser
        # Parsers contain the list of all EPs and the list of all Project Globals
        self.users[user] = OrderedDict()
        self.users[user]['status'] = STATUS_STOP
        self.users[user]['eps'] = OrderedDict()

        if config_data:
            self.parsers[user] = TSCParser(user, config_data, files_config)
        else:
            self.parsers[user] = TSCParser(user, base_config, files_config)

        resp = self._common_user_reset(user, base_config, files_config)
        if not resp: return False

        # Save everything.
        self._dump()
        logDebug('Project: Created user `{}` ...'.format(user))

        return True


    def reset(self, user, base_config='', files_config=''):
        """
        Reset user parser, all EPs to STOP, all files to PENDING.
        """
        if not user or user not in self.users:
            logError('Project ERROR: Invalid user `{}` !'.format(user))
            return False

        if base_config and not os.path.isfile(base_config):
            logError('Project ERROR: Config path `{}` does not exist! Using default config!'.format(base_config))
            base_config = False

        r = self.changeUser(user)
        if not r: return False

        ti = time.clock()

        # User config XML files
        if not base_config:
            base_config = self.users[user]['config_path']
        if not files_config:
            files_config = self.users[user]['project_path']

        logDebug('Project: RESET configuration for user `{}`, using config files `{}` and `{}`.'
            ''.format(user, base_config, files_config))

        del self.parsers[user]
        self.parsers[user] = TSCParser(user, base_config, files_config)

        resp = self._common_user_reset(user, base_config, files_config)
        if not resp: return False

        # Save everything.
        self._dump()
        logDebug('Project: RESET operation took %.4f seconds.' % (time.clock()-ti))
        return True


    def renameUser(self, name, new_name):
        """
        Rename 1 user.
        """
        with self.usr_lock:

            self.users[new_name] = self.users[name]
            self.parsers[new_name] = self.parsers[name]
            self.test_ids[new_name] = self.test_ids[name]
            self.suite_ids[new_name] = self.suite_ids[name]

            del self.users[name]
            del self.parsers[name]
            del self.test_ids[name]
            del self.suite_ids[name]

        self._dump()
        logDebug('Project: Renamed user `{}` to `{}`...'.format(name, new_name))

        return True


    def deleteUser(self, user):
        """
        Delete 1 user.
        """
        with self.usr_lock:

            del self.users[user]
            del self.parsers[user]
            del self.test_ids[user]
            del self.suite_ids[user]

        self._dump()
        logDebug('Project: Deleted user `{}` ...'.format(user))

        return True


    def changeUser(self, user):
        """
        Switch user.\n
        This uses a lock, in order to create the user structure only once.
        If the lock is not present, on CE startup, all running EPs from one user will rush
        to create the memory structure.
        """
        with self.usr_lock:

            if not user:
                return False
            if user not in self.users:
                r = self.createUser(user)
                if not r: return False

        return True


    def listUsers(self, active=False):
        """
        All users that have Twister installer.\n
        If `active` is True, list only the users that are registered to Central Engine.
        """
        users = checkUsers()
        if active:
            users = [u for u in users if u in self.users]
        return sorted(users)


    def _dump(self):
        """
        Internal function. Save all data structure on HDD.\n
        This function must use a lock!
        """
        with self.int_lock:

            with open(TWISTER_PATH + '/config/project_users.json', 'w') as f:
                try: json.dump(self.users, f, indent=4)
                except: pass


# # #


    def _getConfigPath(self, user, _config):
        """
        Helper function.
        """
        config = _config.lower()

        if config in ['', 'fwmconfig', 'baseconfig']:
            return self.users[user]['config_path']

        elif config in ['project', 'testsuites']:
            return self.users[user]['project_path']

        elif config in ['db', 'database']:
            return self.users[user]['db_config']

        elif config in ['email', 'e-mail']:
            return self.users[user]['eml_config']

        elif config in ['glob', 'globals']:
            return self.users[user]['glob_params']

        else:
            # Unchanged config
            return _config


    def listSettings(self, user, config, x_filter):
        """
        List all available settings, for 1 config of a user.
        """
        r = self.changeUser(user)
        if not r: return False
        cfg_path = self._getConfigPath(user, config)
        return self.parsers[user].listSettings(cfg_path, x_filter)


    def getSettingsValue(self, user, config, key):
        """
        Fetch a value from 1 config of a user.
        """
        r = self.changeUser(user)
        if not r: return False
        cfg_path = self._getConfigPath(user, config)
        return self.parsers[user].getSettingsValue(cfg_path, key)


    def setSettingsValue(self, user, config, key, value):
        """
        Set a value for a key in the config of a user.
        """
        r = self.changeUser(user)
        if not r: return False
        cfg_path = self._getConfigPath(user, config)
        logDebug('Updating XML config `{0}`, `{1}` = `{2}`...'.format(config, key, value))
        return self.parsers[user].setSettingsValue(cfg_path, key, value)


    def delSettingsKey(self, user, config, key, index=0):
        """
        Del a key from the config of a user.
        """
        r = self.changeUser(user)
        if not r: return False
        cfg_path = self._getConfigPath(user, config)
        logDebug('Deleting XML config `{0}`, key `{1}`, index `{2}`...'.format(config, key, index))
        return self.parsers[user].delSettingsKey(cfg_path, key, index)


# # #


    def getUserInfo(self, user, key=None):
        """
        Returns data for the current user, including all EP info.
        If the key is not specified, it can be a huge dictionary.
        """
        r = self.changeUser(user)
        if not r:
            if key:
                return []
            else:
                return {}

        if key:
            return self.users[user].get(key)
        else:
            return self.users[user]


    def setUserInfo(self, user, key, value):
        """
        Create or overwrite a variable with a value, for the current user.
        """
        r = self.changeUser(user)
        if not r: return False

        if not key or key == 'eps':
            logDebug('Project: Invalid Key `%s` !' % str(key))
            return False

        self.users[user][key] = value
        self._dump()
        return True


    def getEpInfo(self, user, epname):
        """
        Retrieve all info available, about one EP.
        """
        r = self.changeUser(user)
        if not r: return {}

        return self.users[user]['eps'].get(epname, {})


    def getEpFiles(self, user, epname):
        """
        Return a list with all file IDs associated with one EP.
        The files are found recursive.
        """
        r = self.changeUser(user)
        if not r: return []

        files = self.users[user]['eps'][epname]['suites'].getFiles()
        return files


    def setEpInfo(self, user, epname, key, value):
        """
        Create or overwrite a variable with a value, for one EP.
        """
        r = self.changeUser(user)
        if not r: return False

        if epname not in self.users[user]['eps']:
            logDebug('Project: Invalid EP name `%s` !' % epname)
            return False
        if not key or key == 'suites':
            logDebug('Project: Invalid Key `%s` !' % str(key))
            return False

        self.users[user]['eps'][epname][key] = value
        self._dump()
        return True


    def getSuiteInfo(self, user, epname, suite_id):
        """
        Retrieve all info available, about one suite.
        The files are NOT recursive.
        """
        r = self.changeUser(user)
        if not r: return {}
        eps = self.users[user]['eps']

        if epname not in eps:
            logDebug('Project: Invalid EP name `%s` !' % epname)
            return False
        if suite_id not in eps[epname]['suites'].getSuites():
            logDebug( eps[epname]['suites'].getSuites() )
            logDebug('Project: Invalid Suite ID `%s` !' % suite_id)
            return False

        suite_node = eps[epname]['suites'].findId(suite_id)
        if not suite_node:
            logDebug('Project: Invalid Suite node `%s` !' % suite_id)
            return False
        return suite_node


    def getSuiteFiles(self, user, epname, suite_id):
        """
        Return a list with all file IDs associated with one Suite.
        """
        r = self.changeUser(user)
        if not r: return []
        eps = self.users[user]['eps']

        return eps[epname]['suites'].getFiles(suite_id)


    def setSuiteInfo(self, user, epname, suite_id, key, value):
        """
        Create or overwrite a variable with a value, for one Suite.
        """
        r = self.changeUser(user)
        if not r: return False
        eps = self.users[user]['eps']

        if epname not in eps:
            logDebug('Project: Invalid EP name `%s` !' % epname)
            return False
        if suite_id not in eps[epname]['suites'].getSuites():
            logDebug('Project: Invalid Suite ID `%s` !' % suite_id)
            return False
        if not key or key == 'children':
            logDebug('Project: Invalid Key `%s` !' % str(key))
            return False

        suite_node = eps[epname]['suites'].findId(suite_id)
        if not suite_node:
            logDebug('Project: Invalid Suite node `%s` !' % suite_id)
            return False
        suite_node[key] = value
        self._dump()
        return True


    def getFileInfo(self, user, epname, file_id):
        """
        Retrieve all info available, about one Test File.\n
        The file ID must be unique!
        """
        r = self.changeUser(user)
        if not r: return {}
        eps = self.users[user]['eps']

        if file_id not in eps[epname]['suites'].getFiles():
            logDebug('Project: Invalid File ID `%s` !' % file_id)
            return False

        file_node = eps[epname]['suites'].findId(file_id)
        if not file_node:
            logDebug('Project: Invalid File node `%s` !' % file_id)
            return False
        return file_node


    def setFileInfo(self, user, epname, file_id, key, value):
        """
        Create or overwrite a variable with a value, for one Test File.
        """
        r = self.changeUser(user)
        if not r: return False
        eps = self.users[user]['eps']

        if file_id not in eps[epname]['suites'].getFiles():
            logDebug('Project: Invalid File ID `%s` !' % file_id)
            return False
        if not key:
            logDebug('Project: Invalid Key `%s` !' % str(key))
            return False

        file_node = eps[epname]['suites'].findId(file_id)
        if not file_node:
            logDebug('Project: Invalid File node `%s` !' % file_id)
            return False
        file_node[key] = value
        self._dump()
        return True


    def getFileStatusAll(self, user, epname=None, suite_id=None):
        """
        Return the status of all files, in order.
        This can be filtered for an EP and a Suite.
        """
        r = self.changeUser(user)
        if not r: return []

        if suite_id and not epname:
            logError('Project: Must provide both EP and Suite!')
            return []

        statuses = {} # Unordered
        final = []    # Ordered
        eps = self.users[user]['eps']

        if epname:
            if suite_id:
                files = eps[epname]['suites'].getFiles(suite_id)
            else:
                files = eps[epname]['suites'].getFiles()
            for file_id in files:
                s = self.getFileInfo(user, epname, file_id).get('status', -1)
                statuses[file_id] = str(s)
        # Default case, no EP and no Suite
        else:
            for epname in eps:
                files = eps[epname]['suites'].getFiles()
                for file_id in files:
                    s = self.getFileInfo(user, epname, file_id).get('status', -1)
                    statuses[file_id] = str(s)

        for tcid in self.test_ids[user]:
            if tcid in statuses:
                final.append(statuses[tcid])

        return final


    def setFileStatusAll(self, user, epname=None, new_status=10):
        """
        Reset the status of all files, to value: x.
        """
        r = self.changeUser(user)
        if not r: return False
        eps = self.users[user]['eps']

        for epcycle in eps:
            if epname and epcycle != epname:
                continue
            files = eps[epcycle]['suites'].getFiles()
            for file_id in files:
                # This uses dump, after set file info
                self.setFileInfo(user, epcycle, file_id, 'status', new_status)

        return True


# # #


    def _findGlobalVariable(self, user, node_path):
        """
        Helper function.
        """
        var_pointer = self.users[user]['global_params']

        for node in node_path:
            if node in var_pointer:
                var_pointer = var_pointer[node]
            else:
                # Invalid variable path
                return False

        return var_pointer


    def getGlobalVariable(self, user, variable):
        """
        Sending a global variable, using a path.
        """
        r = self.changeUser(user)
        if not r: return False

        try: node_path = [v for v in variable.split('/') if v]
        except:
            logError('Global Variable: Invalid variable type `{0}`, for user `{1}`!'.format(variable, user))
            return False

        var_pointer = self._findGlobalVariable(user, node_path)

        if not var_pointer:
            logError('Global Variable: Invalid variable path `{0}`, for user `{1}`!'.format(node_path, user))
            return False

        return var_pointer


    def setGlobalVariable(self, user, variable, value):
        """
        Set a global variable path, for a user.\n
        The change is not persistent.
        """
        r = self.changeUser(user)
        if not r: return False

        try: node_path = [v for v in variable.split('/') if v]
        except:
            logError('Global Variable: Invalid variable type `{0}`, for user `{1}`!'.format(variable, user))
            return False

        if (not value) or (not str(value)):
            logError('Global Variable: Invalid value `{0}`, for global variable `{1}` from user `{2}`!'\
                ''.format(value, variable, user))
            return False

        # If the path is in ROOT, it's a root variable
        if len(node_path) == 1:
            with self.glb_lock:
                self.users[user]['global_params'][node_path[0]] = value
            return True

        # If the path is more complex, the pointer here will go to the parent
        var_pointer = self._findGlobalVariable(user, node_path[:-1])

        if not var_pointer:
            logError('Global Variable: Invalid variable path `{0}`, for user `{1}`!'.format(node_path, user))
            return False

        with self.glb_lock:
            var_pointer[node_path[-1]] = value
        return True


# # #


    def setPersistentSuite(self, user, suite, info={}, order=-1):
        """
        This function writes in TestSuites.XML file.
        """
        r = self.changeUser(user)
        if not r: return False
        cfg_path = self._getConfigPath(user, 'project')
        logDebug('Create Suite: Will create suite `{0}` for user `{1}` project.'.format(suite, user))
        return self.parsers[user].setPersistentSuite(cfg_path, suite, info, order)


    def delPersistentSuite(self, user, suite):
        """
        This function writes in TestSuites.XML file.
        """
        r = self.changeUser(user)
        if not r: return False
        xpath_suite = '/Root/TestSuite[tsName="{0}"]'.format(suite)
        logDebug('Del Suite: Will remove suite `{0}` from user `{1}` project.'.format(suite, user))
        return self.delSettingsKey(user, 'project', xpath_suite)


    def setPersistentFile(self, user, suite, fname, info={}, order=-1):
        """
        This function writes in TestSuites.XML file.
        """
        r = self.changeUser(user)
        if not r: return False
        cfg_path = self._getConfigPath(user, 'project')
        logDebug('Create File: Will create file `{0} - {1}` for user `{2}` project.'.format(suite, fname, user))
        return self.parsers[user].setPersistentFile(cfg_path, suite, fname, info, order)


    def delPersistentFile(self, user, suite, fname):
        """
        This function writes in TestSuites.XML file.
        """
        r = self.changeUser(user)
        if not r: return False
        xpath_file = '/Root/TestSuite[tsName="{0}"]/TestCase[tcName="{1}"]'.format(suite, fname)
        logDebug('Del File: Will remove file `{0} - {1}` from user `{2}` project.'.format(suite, fname, user))
        return self.delSettingsKey(user, 'project', xpath_file)


    def queueFile(self, user, suite, fname):
        """
        This function temporary adds a file at the end of the given suite, during runtime.
        """
        r = self.changeUser(user)
        if not r: return False

        # Try create a new file id
        try:
            file_id = str( int(max(self.test_ids[user])) + 1 )
        except:
            logError('Cannot queue file `{}`, because of internal error !'.format(fname))
            return False

        eps = self.users[user]['eps']
        suite_id = False
        SuitesManager = False

        # Try to find the suite name
        for epname in eps:
            manager = eps[epname]['suites']
            suites = manager.getSuites()
            for s_id in suites:
                if manager.findId(s_id)['name'] == suite:
                    suite_id = s_id
                    SuitesManager = manager
                    break
            if suite_id:
                break

        if not suite_id:
            logError('Cannot queue file `{}`, because suite `{}` doesn\'t exist !'.format(fname, suite))
            return False

        # This operation must be atomic !
        with self.usr_lock:

            # Add file in the ordered list of file IDs, used for Get Status ALL
            self.test_ids[user].append(file_id)

            finfo = OrderedDict()
            finfo['type']  = 'file'
            finfo['suite'] = suite_id
            finfo['file']  = fname
            finfo['Runnable']   = "true"

            # Add file for the user, in a specific suite
            suite = SuitesManager.findId(suite_id)
            suite['children'][file_id] = finfo

            # Add the file in suites.xml
            # self.setPersistentFile(self, user, suite, fname)

        return True


# # #


    def setFileOwner(self, user, path):
        """
        Update file ownership for 1 file.\n
        `Chown` function works ONLY in Linux.
        """
        try:
            from pwd import getpwnam
            uid = getpwnam(user)[2]
            gid = getpwnam(user)[3]
        except:
            return False

        if os.path.isdir(path):
            try:
                proc = subprocess.Popen(['chown', str(uid)+':'+str(gid), path, '-R'],)
                proc.wait()
            except:
                logWarning('Cannot set owner on folder! Cannot chown `{}:{}` on `{} -R`!'.format(uid, gid, path))
                return False

        else:
            try:
                os.chown(path, uid, gid)
            except:
                logWarning('Cannot set owner on file! Cannot chown `{}:{}` on `{}`!'.format(uid, gid, path))
                return False

        return True


    def execScript(self, script_path):
        """
        Execute a user script and return the text printed on the screen.
        """
        if not os.path.exists(script_path):
            logError('Exec script: The path `{0}` does not exist!'.format(script_path))
            return False

        try: os.system('chmod +x {0}'.format(script_path))
        except: pass

        logDebug('CE: Executing script `%s`...' % script_path)

        try:
            txt = subprocess.check_output(script_path, shell=True)
            return txt.strip()
        except Exception, e:
            logError('Exec script `%s`: Exception - %s' % (script_path, str(e)) )
            return False


# # #


    def sendMail(self, user):
        """
        Send e-mail function.
        """
        with self.eml_lock:

            r = self.changeUser(user)
            if not r: return False

            # This is updated every time.
            eMailConfig = self.parsers[user].getEmailConfig()
            if not eMailConfig:
                logWarning('E-mail: Nothing to do here.')
                return False

            try:
                logPath = self.users[user]['log_types']['logSummary']
                logSummary = open(logPath).read()
            except:
                logError('E-mail: Cannot open Summary Log `{0}` for reading !'.format(logPath))
                return False

            if not logSummary:
                logDebug('E-mail: Nothing to send!')
                return False

            logDebug('E-mail: Preparing... Server `{SMTPPath}`, user `{SMTPUser}`, from `{From}`, to `{To}`...'\
                ''.format(**eMailConfig))

            # Information that will be mapped into subject or message of the e-mail
            map_info = {'date': time.strftime("%Y-%m-%d %H:%M")}

            # Get all useful information, available for each EP
            for ep, ep_data in self.users[user]['eps'].iteritems():

                for k in ep_data:
                    if k in ['suites', 'status', 'last_seen_alive']: continue
                    if ep_data[k] == '': continue
                    # If the information is already in the mapping info
                    if k in map_info:
                        map_info[k] += ', ' + str(ep_data[k])
                        map_info[k] = ', '.join( list(set( map_info[k].split(', ') )) )
                        #map_info[k] = ', '.join(sorted( list(set(map_info[k].split(', '))) )) # Sorted ?
                    else:
                        map_info[k] = str(ep_data[k])

                # Get all useful information for each Suite
                for suite_id in ep_data['suites'].getSuites():
                    # All info about 1 Suite
                    suite_data = ep_data['suites'].findId(suite_id)

                    for k in suite_data:
                        if k in ['ep', 'children']: continue
                        if suite_data[k] == '': continue
                        # If the information is already in the mapping info
                        if k in map_info:
                            map_info[k] += ', ' + str(suite_data[k])
                            map_info[k] = ', '.join( list(set( map_info[k].split(', ') )) )
                            #map_info[k] = ', '.join(sorted( list(set(map_info[k].split(', '))) )) # Sorted ?
                        else:
                            map_info[k] = str(suite_data[k])

            # print 'E-mail map info::', map_info

            # Subject template string
            tmpl = Template(eMailConfig['Subject'])
            try:
                eMailConfig['Subject'] = tmpl.substitute(map_info)
            except Exception, e:
                logError('E-mail ERROR! Cannot build e-mail subject! Error: {0}!'.format(e))
                return False
            del tmpl

            # Message template string
            tmpl = Template(eMailConfig['Message'])
            try:
                eMailConfig['Message'] = tmpl.substitute(map_info)
            except Exception, e:
                logError('E-mail ERROR! Cannot build e-mail message! Error: {0}!'.format(e))
                return False
            del tmpl

            ROWS = []

            for line in logSummary.split('\n'):
                rows = line.replace('::', '|').split('|')
                if not rows[0]:
                    continue
                rclass = rows[3].strip().replace('*', '')

                rows = ['&nbsp;'+r.strip() for r in rows]
                ROWS.append( ('<tr class="%s"><td>' % rclass) + '</td><td>'.join(rows) + '</td></tr>\n')

            # Body string
            body_path = os.path.split(self.users[user]['config_path'])[0] +os.sep+ 'e-mail-tmpl.htm'
            if not os.path.exists(body_path):
                logError('CE ERROR! Cannot find e-mail template file `{0}`!'.format(body_path))
                return False

            body_tmpl = Template(open(body_path).read())
            body_dict = {
                'texec':  len(logSummary.strip().splitlines()),
                'tpass':  logSummary.count('*PASS*'),
                'tfail':  logSummary.count('*FAIL*'),
                'tabort': logSummary.count('*ABORTED*'),
                'tnexec': logSummary.count('*NO EXEC*'),
                'ttimeout': logSummary.count('*TIMEOUT*'),
                'rate'  : round( (float(logSummary.count('*PASS*'))/ len(logSummary.strip().splitlines())* 100), 2),
                'table' : ''.join(ROWS),
            }

            # Fix TO and CC
            eMailConfig['To'] = eMailConfig['To'].replace(';', ',')
            eMailConfig['To'] = eMailConfig['To'].split(',')

            msg = MIMEMultipart()
            msg['From'] = eMailConfig['From']
            msg['To'] = eMailConfig['To'][0]
            if len(eMailConfig['To']) > 1:
                # Carbon Copy recipients
                msg['CC'] = ','.join(eMailConfig['To'][1:])
            msg['Subject'] = eMailConfig['Subject']

            msg.attach(MIMEText(eMailConfig['Message'], 'plain'))
            msg.attach(MIMEText(body_tmpl.substitute(body_dict), 'html'))

            if (not eMailConfig['Enabled']) or (eMailConfig['Enabled'] in ['0', 'false']):
                e_mail_path = os.path.split(self.users[user]['config_path'])[0] +os.sep+ 'e-mail.htm'
                open(e_mail_path, 'w').write(msg.as_string())
                logDebug('E-mail.htm file written. The message will NOT be sent.')
                # Update file ownership
                self.setFileOwner(user, e_mail_path)
                return True

            try:
                server = smtplib.SMTP(eMailConfig['SMTPPath'])
            except:
                logError('SMTP: Cannot connect to SMTP server!')
                return False

            try:
                logDebug('SMTP: Preparing to login...')
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(eMailConfig['SMTPUser'], eMailConfig['SMTPPwd'])
                logDebug('SMTP: Connect success!')
            except:
                logError('SMTP: Cannot autentificate to SMTP server!')
                return False

            try:
                server.sendmail(eMailConfig['From'], eMailConfig['To'], msg.as_string())
                logDebug('SMTP: E-mail sent successfully!')
                server.quit()
                return True
            except:
                logError('SMTP: Cannot send e-mail!')
                return False


# # #


    def findLog(self, user, epname, file_id, file_name):
        '''
        Parses the log file of one EP and returns the log of one test file.
        '''
        logPath = self.getUserInfo(user, 'logs_path') + os.sep + epname + '_CLI.log'

        try:
            data = open(logPath, 'r').read()
        except:
            logError('Find Log: File `{0}` cannot be read!'.format(logPath))
            return '*no log*'

        fbegin = data.find('<<< START filename: `%s:%s' % (file_id, file_name))
        if fbegin == -1:
            logDebug('Find Log: Cannot find `{0}:{1}` in log `{2}`!'.format(file_id, file_name, logPath))

        fend = data.find('<<< END filename: `%s:%s' % (file_id, file_name))
        fend += len('<<< END filename: `%s:%s` >>>' % (file_id, file_name))

        return data[fbegin:fend]


    def saveToDatabase(self, user):
        """
        Save all data from a user: Ep, Suite, File, into database,
        using the DB.XML for the current project.
        """
        with self.db_lock:

            r = self.changeUser(user)
            if not r: return False

            # Database parser, fields, queries
            # This is created every time the Save is called
            db_parser = DBParser(user)
            db_config = db_parser.db_config
            queries = db_parser.getQueries() # List
            fields  = db_parser.getFields()  # Dictionary
            scripts = db_parser.getScripts() # List
            del db_parser

            if not queries:
                logDebug('Database: There are no queries defined! Nothing to do!')
                return False

            system = platform.machine() +' '+ platform.system() +', '+ ' '.join(platform.linux_distribution())

            #
            try:
                conn = MySQLdb.connect(host=db_config.get('server'), db=db_config.get('database'),
                    user=db_config.get('user'), passwd=db_config.get('password'))
                curs = conn.cursor()
            except MySQLdb.Error, e:
                logError('MySQL Error %d: %s!' % (e.args[0], e.args[1]))
                return False
            #

            conn.autocommit = False
            conn.begin()

            for epname, ep_info in self.users[user]['eps'].iteritems():
                SuitesManager = ep_info['suites']

                for file_id in SuitesManager.getFiles():

                    # Substitute data
                    subst_data = {'file_id': file_id}

                    # Add EP info
                    subst_data.update(ep_info)
                    del subst_data['suites']

                    # Add Suite info
                    file_info = SuitesManager.findId(file_id)
                    suite_id = file_info['suite']
                    suite_info = SuitesManager.findId(suite_id)
                    subst_data.update(suite_info)
                    del subst_data['children']

                    # Add file info
                    subst_data.update(file_info)

                    # Insert/ fix DB variables
                    subst_data['twister_rf_fname'] = '{}/config/resources.json'.format(TWISTER_PATH)
                    subst_data['twister_pf_fname'] = '{}/config/project_users.json'.format(TWISTER_PATH)
                    subst_data['twister_ce_os'] = system
                    subst_data['twister_ce_hostname'] = socket.gethostname()
                    subst_data['twister_ce_python_revision'] = '.'.join([str(v) for v in sys.version_info])
                    subst_data['twister_ep_name'] = epname
                    subst_data['twister_suite_name'] = suite_info['name']
                    subst_data['twister_tc_full_path'] = file_info['file']
                    subst_data['twister_tc_name'] = os.path.split(subst_data['twister_tc_full_path'])[1]
                    subst_data['twister_tc_title'] = ''
                    subst_data['twister_tc_description'] = ''

                    # Escape all unicodes variables before SQL Statements!
                    subst_data = {k: conn.escape_string(v) if isinstance(v, unicode) else v for k,v in subst_data.iteritems()}

                    try:
                        subst_data['twister_tc_log'] = self.findLog(user, epname, file_id, subst_data['twister_tc_full_path'])
                        subst_data['twister_tc_log'] = conn.escape_string( subst_data['twister_tc_log'].replace('\n', '<br>\n') )
                        subst_data['twister_tc_log'] = subst_data['twister_tc_log'].replace('<div', '&lt;div')
                        subst_data['twister_tc_log'] = subst_data['twister_tc_log'].replace('</div', '&lt;/div')
                    except:
                        subst_data['twister_tc_log'] = '*no log*'

                    # Setup and Teardown files will not be saved to database!
                    if subst_data.get('setup_file') or subst_data.get('teardown_file'):
                        continue
                    # Pre-Suite or Post-Suite files will not be saved to database
                    if subst_data.get('Pre-Suite') or subst_data.get('Post-Suite'):
                        continue

                    # For every insert SQL statement, build correct data...
                    for query in queries:

                        # All variables of type `UserScript` must be replaced with the script result
                        try: vars_to_replace = re.findall('(\$.+?)[,\.\'"\s]', query)
                        except: vars_to_replace = []

                        for field in vars_to_replace:
                            field = field[1:]

                            # If the field is not `UserScript`, ignore it
                            if field not in scripts:
                                continue

                            # Get Script Path, or null string
                            u_script = subst_data.get(field, '')

                            # Execute script and use result
                            r = self.execScript(u_script)
                            if r: subst_data[field] = r
                            else: subst_data[field] = ''

                        # All variables of type `DbSelect` must be replaced with the SQL result
                        try: vars_to_replace = re.findall('(@.+?@)', query)
                        except: vars_to_replace = []

                        for field in vars_to_replace:
                            # Delete the @ character
                            u_query = fields.get(field.replace('@', ''))

                            if not u_query:
                                logError('File: `{0}`, cannot build query! Field `{1}` is not defined in the fields section!'\
                                    ''.format(subst_data['file'], field))
                                conn.rollback()
                                return False

                            # Execute User Query
                            curs.execute(u_query)
                            q_value = curs.fetchone()[0]
                            # Replace @variables@ with real Database values
                            query = query.replace(field, str(q_value))

                        # String Template
                        tmpl = Template(query)

                        # Build complete query
                        try:
                            query = tmpl.substitute(subst_data)
                        except Exception, e:
                            logError('User `{0}`, file `{1}`: Cannot build query! Error on `{2}`!'\
                                ''.format(user, subst_data['file'], str(e)))
                            conn.rollback()
                            return False

                        # :: For DEBUG ::
                        #open(TWISTER_PATH + '/config/Query.debug', 'a').write('File Query:: `{0}` ::\n{1}\n\n\n'.format(subst_data['file'], query))

                        # Execute MySQL Query!
                        try:
                            curs.execute(query)
                        except MySQLdb.Error, e:
                            logError('Error in query ``{0}``'.format(query))
                            logError('MySQL Error %d: %s!' % (e.args[0], e.args[1]))
                            conn.rollback()
                            return False

            #
            conn.commit()
            curs.close()
            conn.close()
            #

            return True


    def panicDetectConfig(self, user, args):
        """ Panic Detect mechanism
        valid commands: list, add, update, remove regular expression;

        list command: args = {'command': 'list'}
        add command: args = {'command': 'add', 'data': {'expression': 'reg_exp_string'}}
        update command: args = {'command': 'update', 'data': {'id': 'reg_exp_id',
                                    expression': 'reg_exp_modified_string'}}
        remove command:  args = {'command': 'remove', 'data': 'reg_exp_id'}
        """

        panicDetectCommands = {
            'simple': [
                'list',
            ],
            'argumented': [
                'add', 'update', 'remove',
            ]
        }

        # response structure
        response = {
            'status': {
                'success': True,
                'message': 'None', # error message
            },
            'type': 'reply', # reply type
            'data': 'None', # response data
        }

        if (not args.has_key('command') or args['command'] not
            in panicDetectCommands['argumented'] + panicDetectCommands['simple']):
            response['type'] = 'error reply'

            response['status']['success'] = False
            response['status']['message'] = 'unknown command'

        elif (args['command'] in panicDetectCommands['argumented']
                and not args.has_key('data')):
            response['type'] = 'error reply'

            response['status']['success'] = False
            response['status']['message'] = 'no command data specified'


        # list_regular_expresions
        elif args['command'] == 'list':
            response['type'] = 'list_regular_expressions reply'

            #response['data'] = json.dumps(self.panicDetectRegularExpressions)
            response = json.dumps(self.panicDetectRegularExpressions)


        # add_regular_expression
        elif args['command'] == 'add':
            response['type'] = 'add_regular_expression reply'

            try:
                _args = args['data']
                regExpData = {}

                regExpData.update([('expression', _args['expression']), ])

                if regExpData.has_key('enabled'):
                    regExpData.update([('enabled', _args['enabled']), ])
                else:
                    regExpData.update([('enabled', False), ])

                regExpID = str(time.time()).replace('.', '|')

                if not self.panicDetectRegularExpressions.has_key(user):
                    self.panicDetectRegularExpressions.update([(user, {}), ])

                self.panicDetectRegularExpressions[user].update(
                                                    [(regExpID, regExpData), ])

                with self.int_lock:
                    config = open(self.panicDetectConfigPath, 'wb')
                    json.dump(self.panicDetectRegularExpressions, config)
                    config.close()

                #response['data'] = regExpID
                response = regExpID
                logDebug('Panic Detect: added regular expression `{e}` for user: {u}.'.format(u=user, e=regExpID))
            except Exception, e:
                #response['status']['success'] = False
                #response['status']['message'] = '{er}'.format(er=e)
                response = 'error: {er}'.format(er=e)


        # update_regular_expression
        elif args['command'] == 'update':
            response['type'] = 'update_regular_expression reply'

            try:
                _args = args['data']
                regExpID = _args.pop('id')
                regExpData = self.panicDetectRegularExpressions[user].pop(regExpID)

                regExpData.update([('expression', _args['expression']), ])

                if _args.has_key('enabled'):
                    regExpData.update([('enabled', _args['enabled']), ])
                else:
                    regExpData.update([('enabled', regExpData['enabled']), ])

                self.panicDetectRegularExpressions[user].update(
                                                    [(regExpID, regExpData), ])
                with self.int_lock:
                    config = open(self.panicDetectConfigPath, 'wb')
                    json.dump(self.panicDetectRegularExpressions, config)
                    config.close()

                #response['data'] = regExpID
                response = True
                logDebug('Panic Detect: updated regular expression `{e}` for user: {u}.'.format(u=user, e=regExpID))
            except Exception, e:
                #response['status']['success'] = False
                #response['status']['message'] = '{er}'.format(er=e)
                response = 'error: {er}'.format(er=e)

        # remove_regular_expression
        elif args['command'] == 'remove':
            response['type'] = 'remove_regular_expression reply'

            try:
                regExpID = args['data']
                regExpData = self.panicDetectRegularExpressions[user].pop(regExpID)
                del(regExpData)

                with self.int_lock:
                    config = open(self.panicDetectConfigPath, 'wb')
                    json.dump(self.panicDetectRegularExpressions, config)
                    config.close()

                #response['data'] = regExpID
                response = True
                logDebug('Panic Detect: removed regular expresion `{e}` for user: {u}.'.format(u=user, e=regExpID))
            except Exception, e:
                #response['status']['success'] = False
                #response['status']['message'] = '{er}'.format(er=e)
                response = 'error: {er}'.format(er=e)

        return response

# # #

# Eof()
