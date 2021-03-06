
# File: CeFs.py ; This file is part of Twister.

# version: 3.026

# Copyright (C) 2012-2014, Luxoft

# Authors:
#    Andrei Costachi <acostachi@luxoft.com>
#    Cristi Constantin <crconstantin@luxoft.com>
#    Daniel Cioata <dcioata@luxoft.com>
#    Mihai Tudoran <mtudoran@luxoft.com>

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
Local file system; used to help workign with files where user is owner
"""

import os, sys
import time
import copy
import random
import socket
import subprocess
from plumbum import local
import rpyc
import pwd
import grp
import signal

socket.setdefaulttimeout(3)

TWISTER_PATH = os.getenv('TWISTER_PATH')
if not TWISTER_PATH:
    print '$TWISTER_PATH environment variable is not set! Exiting!'
    exit(1)
if TWISTER_PATH not in sys.path:
    sys.path.append(TWISTER_PATH)

from common.helpers    import FsBorg, userHome
from common.tsclogging import logError, logInfo, logWarning, logDebug


class BaseFS(object):
    """
    Base file system class.
    """
    name = ''

    def _usr_service(self, *arg, **kargs):
        """
        This method is overwritten by the child classes
        """
        pass


    def __del__(self):
        """
        Kill all services for a user.
        """
        logInfo('Killing all services for the current CE.')
        for user in self._services:
            proc = self._services[user]['proc']
            read_conn = self._services[user]['conn_read']
            write_conn = self._services[user]['conn_write']
            try:
                read_conn.close()
            except Exception as err:
                logError('Cannot close connection: `{}`, exception `{}`!'.format(read_conn, err))
            try:
                write_conn.close()
            except Exception as err:
                logError('Cannot close connection: `{}`, exception `{}`!'.format(write_conn, err))
            try:
                proc.terminate()
            except Exception as err:
                logError('Cannot stop service: `{}`, exception `{}`!'.format(proc, err))
            try:
                time.sleep(0.1)
                os.killpg(proc.pid, signal.SIGTERM)
                time.sleep(0.1)
                proc.kill()
            except:
                pass


    def _kill(self, user):
        """
        Kill all services for a user.
        """
        p_ps = local['ps']
        grep = local['grep']

        try:
            pids = (p_ps['aux'] | grep['/server/UserService.py'] | grep['^' + user] | grep[self.name])()
        except Exception:
            return

        # Kill all leftover processes
        for line in pids.strip().splitlines():
            std_li = line.strip().decode('utf').split()
            p_pid = int(std_li[1])
            del std_li[2:5]
            if '/bin/sh' in std_li:
                continue
            if '/bin/grep' in std_li:
                continue
            logDebug('User {}: Killing ugly zombie `{}`.'.format(user, ' '.join(std_li)))
            try:
                os.kill(p_pid, 9)
            except:
                pass


    # ----- USER ---------------------------------------------------------------


    def is_folder(self, user, fpath):
        """
        Returns True of False. Client access via RPyc.
        """
        if not fpath:
            return '*ERROR* Empty `fpath` parameter on is folder, user `{}`!'.format(user)
        srvr = self._usr_service(user)
        if srvr:
            try:
                return srvr.root.is_folder(fpath)
            except Exception as exp_err:
                err = '*ERROR* Cannot detect file/ folder `{}`, user `{}`! {}'.format(fpath, user, exp_err)
                logWarning(err)
                return err
        else:
            return '*ERROR* Cannot access the UserService on is folder, user `{}`!'.format(user)


    def file_size(self, user, fpath):
        """
        Get file size for 1 file. Client access via RPyc.
        """
        if not fpath:
            return False
        srvr = self._usr_service(user)
        if srvr:
            try:
                return srvr.root.file_size(fpath)
            except Exception:
                return -1
        else:
            return -1


    def read_user_file(self, user, fpath, flag='r', fstart=0):
        """
        Read 1 file. Client access via RPyc.
        """
        if not fpath:
            return '*ERROR* Empty `fpath` parameter on read file, user `{}`!'.format(user)
        srvr = self._usr_service(user)
        if srvr:
            try:
                return srvr.root.read_file(fpath, flag, fstart)
            except Exception as exp_err:
                err = '*ERROR* Cannot read file `{}`, user `{}`! {}'.format(fpath, user, exp_err)
                logWarning(err)
                return err
        else:
            return '*ERROR* Cannot access the UserService on read file, user `{}`!'.format(user)


    def write_user_file(self, user, fpath, fdata, flag='w'):
        """
        Write 1 file. Client access via RPyc.
        """
        if not fpath:
            return '*ERROR* Empty `fpath` parameter on write file, user `{}`!'.format(user)
        srvr = self._usr_service(user, 'write')
        if len(fdata) > 20*1000*1000:
            err = '*ERROR* File data too long `{}`: {}; User {}.'.format(fpath, len(fdata), user)
            logWarning(err)
            return err
        if srvr:
            try:
                return srvr.root.write_file(fpath, fdata, flag)
            except Exception as exp_err:
                err = '*ERROR* Cannot write into file `{}`, user `{}`! {}'.format(fpath, user, exp_err)
                logWarning(err)
                return err
        else:
            return '*ERROR* Cannot access the UserService on write file, user `{}`!'.format(user)


    def copy_user_file(self, user, fpath, newpath):
        """
        Copy 1 user file.
        """
        if not fpath:
            return '*ERROR* Empty `fpath` parameter on copy file, user `{}`!'.format(user)
        srvr = self._usr_service(user, 'write')
        if srvr:
            return srvr.root.copy_file(fpath, newpath)
        else:
            return '*ERROR* Cannot access the UserService on copy file, user `{}`!'.format(user)


    def move_user_file(self, user, fpath, newpath):
        """
        Move/rename a user file.
        """
        if not fpath:
            return '*ERROR* Empty `fpath` parameter on move file, user `{}`!'.format(user)
        srvr = self._usr_service(user, 'write')
        if srvr:
            return srvr.root.move_file(fpath, newpath)
        else:
            return '*ERROR* Cannot access the UserService on move file, user `{}`!'.format(user)


    def delete_user_file(self, user, fpath):
        """
        Delete user file.
        """
        if not fpath:
            return '*ERROR* Empty `fpath` parameter on delete file, user `{}`!'.format(user)
        srvr = self._usr_service(user)
        if srvr:
            return srvr.root.delete_file(fpath)
        else:
            return '*ERROR* Cannot access the UserService on delete file, user `{}`!'.format(user)


    def create_user_folder(self, user, fdir):
        """
        Create a folder in user client directory.
        """
        if not fdir:
            return '*ERROR* Empty `fdir` parameter on create folder, user `{}`!'.format(user)
        srvr = self._usr_service(user)
        if srvr:
            return srvr.root.create_folder(fdir)
        else:
            return '*ERROR* Cannot access the UserService on create folder, user `{}`!'.format(user)


    def list_user_files(self, user, fdir, hidden=True, recursive=True, accept=[], reject=[]):
        """
        List the files in user directory.
        """
        if not fdir:
            return '*ERROR* Empty `fdir` parameter on list files, user `{}`!'.format(user)
        srvr = self._usr_service(user)
        if srvr:
            try:
                files = srvr.root.list_files(fdir, hidden, recursive, accept, reject)
                return copy.copy(files)
            except Exception as exp_err:
                err = '*ERROR* Cannot list files `{}`, user `{}`! {}'.format(fdir, user, exp_err)
                logWarning(err)
                return err
        else:
            return '*ERROR* Cannot access the UserService on list files, user `{}`!'.format(user)


    def delete_user_folder(self, user, fdir):
        """
        Delete a user folder.
        """
        if not fdir:
            return '*ERROR* Empty `fdir` parameter on delete folder, user `{}`!'.format(user)
        srvr = self._usr_service(user)
        if srvr:
            return srvr.root.delete_folder(fdir)
        else:
            return '*ERROR* Cannot access the UserService on delete folder, user `{}`!'.format(user)


    def targz_user_folder(self, user, fdir, root=''):
        """
        Tar.gz a folder, or file.
        """
        if not fdir:
            return '*ERROR* Empty `fdir` parameter on tar.gz folder, user `{}`!'.format(user)
        srvr = self._usr_service(user)
        if srvr:
            return srvr.root.targz_folder(fdir, root)
        else:
            return '*ERROR* Cannot access the UserService on tar.gz folder, user `{}`!'.format(user)


    def detect_libraries(self, user, files):
        """
        Autodetect libraries: parses all the tests and finds the import statements.
        Returns a list of the modules not available by default in python path.
        """
        srvr = self._usr_service(user)
        if srvr:
            libs = srvr.root.detect_libraries(files)
            return copy.copy(libs)
        else:
            return '*ERROR* Cannot access the UserService on tar.gz folder, user `{}`!'.format(user)


    # ----- SYSTEM -------------------------------------------------------------


    @staticmethod
    def sys_file_size(fpath):
        """
        Get file size for 1 file. ROOT access.
        """
        if not fpath:
            return False
        try:
            fsize = os.stat(fpath).st_size
            # logDebug('File `{}` is size `{}`.'.format(fpath, fsize))
            return fsize
        except Exception as exp_err:
            err = '*ERROR* Cannot find file `{}`! {}'.format(fpath, exp_err)
            logWarning(err)
            return err


    @staticmethod
    def read_system_file(fpath, flag='r', fstart=0):
        """
        Read 1 file. ROOT access.
        """
        if not fpath:
            return False
        if flag not in ['r', 'rb']:
            err = '*ERROR* Invalid flag `{}`! Cannot read!'.format(flag)
            logWarning(err)
            return err
        if not os.path.isfile(fpath):
            err = '*ERROR* No such file `{}`!'.format(fpath)
            logWarning(err)
            return err
        try:
            with open(fpath, flag) as file_p:
                # logDebug('Reading file `{}`, flag `{}`.'.format(fpath, flag))
                if fstart:
                    file_p.seek(fstart)
                fdata = file_p.read()
                if len(fdata) > 20*1000*1000:
                    err = '*ERROR* File data too long `{}`: {}!'.format(fpath, len(fdata))
                    logWarning(err)
                    return err
                return fdata
        except Exception as exp_err:
            err = '*ERROR* Cannot read file `{}`! {}'.format(fpath, exp_err)
            logWarning(err)
            return err


    @staticmethod
    def write_system_file(fpath, fdata, flag='a'):
        """
        Write data in a file. ROOT access.
        Overwrite or append, ascii or binary.
        """
        if not fpath:
            return False
        if flag not in ['w', 'wb', 'a', 'ab']:
            err = '*ERROR* Invalid flag `{}`! Cannot read!'.format(flag)
            logWarning(err)
            return err
        try:
            with open(fpath, flag) as file_p:
                file_p.write(fdata)
            # if flag == 'w':
            #     logDebug('Written `{}` chars in ascii file `{}`.'.format(len(fdata), fpath))
            # elif flag == 'wb':
            #     logDebug('Written `{}` chars in binary file `{}`.'.format(len(fdata), fpath))
            # elif flag == 'a':
            #     logDebug('Appended `{}` chars in ascii file `{}`.'.format(len(fdata), fpath))
            # else:
            #     logDebug('Appended `{}` chars in binary file `{}`.'.format(len(fdata), fpath))
            return True
        except Exception as exp_err:
            err = '*ERROR* Cannot write into file `{}`! {}'.\
            format(fpath, exp_err)
            logWarning(err)
            return err


    def delete_system_file(self, fname):
        """ Dummy method """
        pass


    def create_system_folder(self, fdir):
        """ Dummy method """
        pass


    def list_system_files(self, folder, hidden=True, recursive=True, accept=[], reject=[]):
        """
        List all files, recursively.
        """
        if folder == '/':
            base_path = '/'
            logWarning('*WARN* Listing folders from system ROOT.')
            recursive = False
        else:
            base_path = folder.rstrip('/')

        if not os.path.isdir(folder):
            err = '*ERROR* Invalid folder path `{}`!'.format(folder)
            logWarning(err)
            return err

        def dirList(path):
            """
            Create recursive list of folders and files from base path.
            The format of a node is: {"path": "/..." "data": "name", "folder":true|false, "children": []}
            """
            # The node is valid ?
            if not path:
                return False
            # Cleanup '/'
            if path != '/':
                path = path.rstrip('/')
            # This is folder ?
            if os.path.isfile(path):
                return False

            len_path = len(base_path) + 1
            dlist = [] # Folders list
            flist = [] # Files list

            try:
                names = sorted(os.listdir(path), key=str.lower)
            except Exception as exp_err:
                logWarning('*WARN* Cannot list folder `{}`: `{}`!'.\
                format(path, exp_err))
                return []

            # Cycle a folder
            for fname in names:
                long_path = path + '/' + fname

                # If Accept is active and file doesn't match, ignore file
                if accept and os.path.isfile(long_path):
                    valid = True
                    if isinstance(accept, list):
                        # If nothing from the Accept matches the file
                        if True not in [(long_path.startswith(f) or long_path.endswith(f)) for f in accept]:
                            valid = False
                    elif isinstance(accept, str):
                        if not (long_path.startswith(accept) or long_path.endswith(accept)):
                            valid = False
                    if not valid:
                        continue

                # If Reject is active and file matches, ignore the file
                if reject and os.path.isfile(long_path):
                    valid = True
                    if isinstance(reject, list):
                        # If nothing from the Reject matches the file
                        if True in [(long_path.startswith(f) or long_path.endswith(f)) for f in reject]:
                            valid = False
                    elif isinstance(reject, str):
                        if long_path.startswith(reject) or long_path.endswith(reject):
                            valid = False
                    if not valid:
                        continue

                # Ignore hidden files
                if hidden and fname[0] == '.':
                    continue
                # Meta info
                try:
                    fstat = os.stat(long_path)
                    try:
                        uname = pwd.getpwuid(fstat.st_uid).pw_name
                    except Exception:
                        uname = fstat.st_uid
                    try:
                        gname = grp.getgrgid(fstat.st_gid).gr_name
                    except Exception:
                        gname = fstat.st_gid
                    meta_info = '{}|{}|{}|{}'.\
                    format(uname, gname, fstat.st_size,\
                    time.strftime('%Y-%m-%d %H:%M:%S',\
                    time.localtime(fstat.st_mtime)))
                except Exception:
                    meta_info = ''

                # Semi long path
                short_path = long_path[len_path:]
                # Data to append
                data = {'path': short_path, 'data': fname, 'meta': meta_info}

                if os.path.isdir(long_path):
                    data['folder'] = True
                    # Recursive !
                    if recursive:
                        children = dirList(long_path)
                    else:
                        children = []
                    if children in [False, None]:
                        continue
                    data['children'] = children
                    dlist.append(data)
                else:
                    flist.append(data)

            # Folders first, files second
            return dlist + flist

        paths = {
            'path' : '/',
            'data' : base_path,
            'folder' : True,
            'children' : dirList(base_path) or []
        }

        clen = len(paths['children'])
        logDebug('Listing dir `{}`, it has `{}` direct children.'.format(base_path, clen))
        return paths


    def delete_system_folder(self, fdir):
        """ Dummy method """
        pass

#

class LocalFS(BaseFS, FsBorg):
    """
    All local file operations should be done via THIS class.
    This is a singleton.
    """

    def __init__(self):
        FsBorg.__init__(self)
        self.name = 'Local'
        if os.getuid():
            logError('{} FS: Central Engine must run as ROOT in order to start the User Service!'.format(self.name))
        logInfo('Created {} FS.'.format(self.name))


    def _usr_service(self, user, oper='read'):
        """
        Launch a user service.
        """
        if oper not in ['read', 'write']:
            logWarning('Invalid FS operation `{}`, for user `{}`! Will reset to "read".'.format(oper, user))
            oper = 'read'

        # Must block here, so more users cannot launch Logs at the same time and lose the PID
        with self._srv_lock:

            # Try to re-use the logger server, if available
            conn = self._services.get(user, {}).get('conn_' + oper, None)
            if conn:
                try:
                    conn.ping(data='Hello', timeout=30.0)
                    # logDebug('Reuse old {} User Service connection for `{}` OK.'.format(op, user))
                    return conn
                except Exception as exp_err:
                    logWarning('Cannot reuse {} User Service for `{}`: `{}`.'.format(oper, user, exp_err))
                    self._kill(user)
            else:
                logInfo('Launching a User Service for `{}`, the first time...'.format(user))

            port = None

            # If the server is not available, search for a free port in the safe range...
            while 1:
                port = random.randrange(63000, 65000)
                try:
                    socket.create_connection((None, port), 1)
                except Exception:
                    break

            p_cmd = 'su {} -c "{} -u {}/server/UserService.py {} {}"'.\
            format(user, sys.executable, TWISTER_PATH, port, self.name)
            proc = subprocess.Popen(p_cmd, cwd='{}/twister'.\
            format(userHome(user)), shell=True, close_fds=True,\
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            proc.poll()
            time.sleep(2.0)

            config = {
                'allow_pickle': True,
                'allow_getattr': True,
                'allow_setattr': True,
                'allow_delattr': True
            }

            retry = 10
            delay = 0.5
            success = False

            while retry > 0:
                if success:
                    break

                try:
                    stream_r = rpyc.SocketStream.connect('127.0.0.1', port, timeout=5.0)
                    conn_read = rpyc.connect_stream(stream_r, config=config)
                    conn_read.root.hello()
                    logDebug('Connected to User Service for `{}`, operation `read`.'.format(user))
                    success = True
                except Exception as exp_err:
                    logWarning('Cannot connect to User Service for `{}` - \
                    Exception: `{}`! Wait {}s...'.format(user, exp_err, delay))

                if success:
                    try:
                        stream_w = rpyc.SocketStream.connect('127.0.0.1', port, timeout=5.0)
                        conn_write = rpyc.connect_stream(stream_w, config=config)
                        conn_write.root.hello()
                        logDebug('Connected to User Service for `{}`, operation `write`.'.format(user))
                        break
                    except Exception as exp_err:
                        logWarning('Cannot connect to User Service for `{}` \
                        - Exception: `{}`! Wait {}s...'.\
                        format(user, exp_err, delay))
                        success = False

                time.sleep(delay)
                retry -= 1
                delay += 0.75

            if not success:
                logError('Error on starting User Service for `{}`!'.format(user))
                return None

            # Save the process inside the block.  99% of the time, this block is executed instantly!
            self._services[user] = {'proc': proc, 'conn_read': conn_read, 'conn_write': conn_write, 'port': port}

        logDebug('User Service for `{}` launched on `127.0.0.1:{}` - PID `{}`.'.format(user, port, proc.pid))

        return self._services[user].get('conn_' + oper, None)

#

if __name__ == '__main__':

    FS_1 = LocalFS()
    FS_2 = LocalFS()

    assert FS_1 == FS_2, 'Not equal!'
    assert FS_1 is FS_2, 'Not identical!'

    print FS_1
    print FS_2
    print 'Ok.'


# Eof()
