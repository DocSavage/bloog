#!/usr/bin/env python
# encoding: utf-8
#
# The MIT License
# 
# Copyright (c) 2008 William T. Katz
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to 
# deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER 
# DEALINGS IN THE SOFTWARE.


# --- Significant portions of the code was taken from Google App Engine SDK
# --- which is licensed under Apache 2.0
#
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import sys
import getopt

import datetime
import getpass
import logging
import mimetypes
import os
import re
import sha
import sys
import time
import httplib
import urllib
import urlparse
import socket
import string

help_message = '''
First argument must be an authentication cookie that can be cut & pasted after
logging in with a browser.  Cookies can be easily viewed by using the Web
Developer plugin with Firefox.

For example, for uploading data into the local datastore, you'd do something
like this:

clear_datastore.py 'dev_appserver_login="root@example.com:True"'
(or you could skip the first argument and use the -r or --root options)

For uploading data into a Google AppEngine-hosted app, the cookie would begin
with ACSID:

clear_datastore.py 'ACSID=AJXUWfE-aefkae...'

Options:
-r, --root         sets authorization cookie for local dev admin
-l, --url        = the url (web location) of the Bloog app
'''


class Error(Exception):
    """Base-class for exceptions in this module."""

class UsageError(Error):
    def __init__(self, msg):
        self.msg = msg

class HTTPConnectError(Error):
    """An error has occured while trying to connect to the Bloog app."""

class RequestError(Error):
    """An error occured while trying a HTTP request to the Bloog app."""

class UnsupportedSchemeError(Error):
    """Tried to access url with unsupported scheme (not http or https)."""

class HttpRESTClient(object):

    @staticmethod
    def connect(scheme, netloc):
        if scheme == 'http':
            return httplib.HTTPConnection(netloc)
        if scheme == 'https':
            return httplib.HTTPSConnection(netloc)
        raise UnsupportedSchemeError()

    def __init__(self, auth_cookie):
        self.auth_cookie = auth_cookie

    def delete(self, url):
        headers = {'Cookie': self.auth_cookie}
        scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
        success = False
        try:
            connection = HttpRESTClient.connect(scheme, netloc)
            try:
                connection.request('DELETE', path, '', headers)
                response = connection.getresponse()
                status = response.status
                reason = response.reason
                content = response.read()
                tuple_headers = response.getheaders()
                print('Received response code %d: %s\n%s' % \
                      (status, reason, content))
                success = (status == httplib.OK)
            finally:
                connection.close()
        except (IOError, httplib.HTTPException, socket.error), e:
          print('Encountered exception accessing HTTP server: %s', e)
          raise HTTPConnectError(e)

        return success


def main(argv):
    try:
        try:
            opts, args = getopt.gnu_getopt(argv, 'hrl:v', ["help", "url="])
        except getopt.error, msg:
            raise UsageError(msg)

        app_url = 'http://localhost:8080'
        local_admin = ''
        for option, value in opts:
            print "Looking at option:", str(option), str(value)
            if option == "-v":
                verbose = True
            if option in ("-h", "--help"):
                raise UsageError(help_message)
            if option in ("-r", "--root"):
                local_admin = 'dev_appserver_login="root@example.com:True"'
            if option in ("-l", "--url"):
                print "Got url:", value
                app_url = value
                if app_url[:4] != 'http':
                    app_url = 'http://' + app_url
                if app_url[-1] == '/':
                    app_url = app_url[:-1]

        if len(args) < 2 and not local_admin:
            raise UsageError("Please specify the authentication cookie "
                             "string as first argument.")
        else:
            auth_cookie = local_admin or args[1]

            #TODO - Use mechanize module to programmatically login
            #email = raw_input("E-mail: ")
            #passwd = getpass.getpass("Password: ")

            webserver = HttpRESTClient(auth_cookie)
            while webserver.delete(app_url + '/Article'):
                pass
            while webserver.delete(app_url + '/Comment'):
                pass
            while webserver.delete(app_url + '/Tag'):
                pass

    except UsageError, err:
        print >> sys.stderr, sys.argv[0].split("/")[-1] + ": " + str(err.msg)
        print >> sys.stderr, "\t for help use --help"
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
