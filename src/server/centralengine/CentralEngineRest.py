
# File: CentralEngineRest.py ; This file is part of Twister.

# Copyright (C) 2012 , Luxoft

# Authors:
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
Central Engine REST functions
*****************************

All functions are exposed and can be accessed using the browser.
"""

import os, sys
import datetime
import cherrypy
from mako.template import Template

TWISTER_PATH = os.getenv('TWISTER_PATH')
if not TWISTER_PATH:
    print('$TWISTER_PATH environment variable is not set! Exiting!')
    exit(1)
sys.path.append(TWISTER_PATH)

from common.constants import *
from common.tsclogging import LOG_FILE


#
TMPL_DATA = """
<!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="utf-8">
	% if title is not UNDEFINED:
	<title>${title}</title>
	% else:
	<title>Central Engine REST</title>
	% endif
	<style>
	* {font-family: Courier New, Courier, Monospace, Verdana, Arial}
	</style>
</head>
<body><div style="margin:5px;">
% if title is not UNDEFINED:
<h2>${title}</h2>
% else:
<h2>Central Engine REST</h2>
% endif

${body}

</div></body>
</html>
"""
#


class CentralEngineRest:

    def __init__(self, parent, project):

        self.project = project
        self.parent  = parent


    def user_agent(self):
        """
        User agent returns Browser or XML RPC client.
        This function is not exposed.
        """
        if  cherrypy.request.headers['User-Agent'].startswith('xmlrpclib.py') or\
            cherrypy.request.headers['User-Agent'].startswith('Apache XML RPC'):
            # XML RPC client
            return 'x'
        else:
            # Browser
            return 'b'


    @cherrypy.expose
    def index(self):

        output = Template(text=TMPL_DATA)
        host = cherrypy.request.headers['Host']
        body = '<p>From here, you can access:<br><br>'\
               '<a href="http://{host}/rest/stats">Stats</a>  and  <a href="http://{host}/rest/logs">Logs</a>.</p>'.format(host=host)

        return output.render(body=body)


    @cherrypy.expose
    def stats(self, user='', epname='', suite=''):
        """
        This function should be used in the browser.
        It prints a few statistics about the Central Engine.
        """
        if self.user_agent() == 'x':
            return 0

        output = Template(text=TMPL_DATA)
        reversed = dict((v,k) for k,v in execStatus.iteritems())
        now = datetime.datetime.today()
        if now.second < 59:
            now_str = now.replace(second=now.second+1).strftime('%Y-%m-%d %H:%M:%S')
        else:
            now_str = now.replace(minute=now.minute+1, second=0).strftime('%Y-%m-%d %H:%M:%S')
        ce_host = cherrypy.config['server.socket_host']
        ce_port = cherrypy.config['server.socket_port']
        host = cherrypy.request.headers['Host']

        # -- This is before selecting a User
        if not user:
            body = '<b>Running on</b>: {ce_host}:{ce_port}<br><br>\n'\
                   '<h2>Registered users:</h2>\n'\
                   '{users}.'.format(ce_host=ce_host, ce_port=ce_port, users=';<br>'.join(
                   ['&nbsp;&nbsp;user <a href="http://{host}/rest/stats/{user}">{user}</a>'
                        .format(host=host, user=k)
                        for k in self.project.users.keys()]
                        ) or 'None')
            return output.render(title='Central Engine', body=body)
        else:
            if user not in self.project.users.keys():
                body = '<b>User name `{0}` doesn\'t exist!</b>'.format(user)
                return output.render(title='Error!', body=body)

        status = reversed[self.project.getUserInfo(user, 'status')]

        if epname:
            if not epname in self.project.getUserInfo(user, 'eps'):
                body = '<b>Execution Process `{0}` doesn\'t exist!</b>'.format(epname)
                return output.render(title='Error!', body=body)

            # -- After selecting a User. EP statistics
            if not suite:
                data = self.project.getEpInfo(user, epname)
                ret = '<h3>Execution Process `{epname}`</h3>\n'\
                      '<b>Status</b>: {status}<br><br>\n'\
                      '<b>Ping</b>: {ping}<br><br>\n'\
                      '<b>Suites</b>: [<br>{suites}<br>]\n'.format(
                    epname = epname,
                    status = reversed[data.get('status', STATUS_INVALID)],
                    ping = str( (now - datetime.datetime.strptime(data.get('last_seen_alive', now_str), '%Y-%m-%d %H:%M:%S')).seconds ) + 's',
                    suites = '<br>'.join(['&nbsp;&nbsp;<a href="http://{host}/rest/stats/{user}/{ep}/{id}">{name}</a>'.format(
                        host = host, user = user, ep = epname, id = k, name = v['name'])
                                          for k, v in data['suites'].items()])
                )

            # -- After selecting a User. Suite statistics
            else:
                data = self.project.getSuiteInfo(user, epname, suite)
                reversed = dict((v,k) for k,v in testStatus.iteritems())
                ret = '<h3>Suite `{name}` (id `{suite}`)</h3>'\
                      '<b>Files</b>: [<br>{files}<br>]'.format(
                    epname = epname,
                    suite = suite,
                    name = data['name'],
                    files = '<br>'.join(['&nbsp;&nbsp;{0}: {1}'.format(data['files'][k]['file'],
                                        reversed[data['files'][k].get('status', STATUS_INVALID)] )
                                        for k in data['files']])
                )

        # -- This is after selecting a User. General user statistics
        else:
            eps = self.project.getUserInfo(user, 'eps').keys()
            ret = '<h3>User `{user}`</h3>\n'\
                  '<b>Status</b>: {status} '\
                  '<small>(<a href="http://{host}/rest/setUserStatus/{user}/2">start</a> | '\
                  '<a href="http://{host}/rest/setUserStatus/{user}/0">stop</a> | '\
                  '<a href="http://{host}/rest/resetUser/{user}">reset!</a>)</small><br><br>\n'\
                  '<b>Config</b>: <small>{config}</small><br><br><br>\n'\
                  '<b>Processes</b>: [<br>{eps}<br>]\n'.format(
                host = host,
                user = user,
                status = status,
                config = self.project.getUserInfo(user, 'tests_path'),
                eps = '<br>'.join(
                    ['&nbsp;&nbsp;<a href="http://{host}/rest/stats/{user}/{ep}">{ep}</a>: {status}'.format(
                        user = user, ep=ep, host=host,
                        status=reversed[self.project.getEpInfo(user, ep).get('status', STATUS_INVALID)])
                     for ep in eps]
                )
            )

        return output.render(title='Central Engine Statistics', body=ret)


    @cherrypy.expose
    def status(self, user, epname='', suite=''):
        return self.stats(user, epname, suite)


    @cherrypy.expose
    def resetUser(self, user):
        self.project.reset(user)
        self.parent.resetLogs(user)
        raise cherrypy.HTTPRedirect('http://{host}/rest/stats/{user}'.format(
            host = cherrypy.request.headers['Host'], user = user
        ))


    @cherrypy.expose
    def setUserStatus(self, user, status):
        output = Template(text=TMPL_DATA)
        try: status = int(status)
        except: return output.render(title='Error!', body='<b>Status value `%s` is invalid!</b>' % str(status))
        self.parent.setExecStatusAll(user, status, 'Status changed from REST interface.')
        raise cherrypy.HTTPRedirect('http://{host}/rest/stats/{user}'.format(
            host = cherrypy.request.headers['Host'], user = user
        ))


    @cherrypy.expose
    def setEpStatus(self, user, epname, status):
        output = Template(text=TMPL_DATA)
        try: status = int(status)
        except: return output.render(title='Error!', body='<b>Status value `%s` is invalid!</b>' % str(status))
        self.parent.setExecStatus(user, epname, status, 'Status changed from REST interface.')
        raise cherrypy.HTTPRedirect('http://{host}/rest/stats/{user}/{epname}'.format(
            host = cherrypy.request.headers['Host'], user = user, epname = epname
        ))


    @cherrypy.expose
    def log(self):
        """
        This function should be used in the browser.
        It prints the Central Engine log.
        """
        if self.user_agent() == 'x':
            return 0

        output = Template(text=TMPL_DATA)
        log = open(LOG_FILE).read()
        body = log.replace('\n', '<br>\n').replace(' ', '&nbsp;')
        body = body.replace(';INFO&',   ';<b style="color:gray">INFO</b>&')
        body = body.replace(';DEBUG&',  ';<b style="color:gray">DEBUG</b>&')
        body = body.replace(';ERROR&',  ';<b style="color:orange">ERROR</b>&')
        body = body.replace(';WARNING&',  ';<b>WARNING</b>&')
        body = body.replace(';CRITICAL&', ';<b style="color:red">CRITICAL</b>&')
        return output.render(title='Central Engine Log', body=body)


    @cherrypy.expose
    def logs(self):
        return self.log()

#

# Eof()