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

from utils.external import textile

help_message = """
First argument must be an authentication cookie that can be cut & pasted after
logging in with a browser.  Cookies can be easily viewed by using the Web
Developer plugin with Firefox.

For example, for uploading data into the local datastore, you'd do something
like this:

drupal_uploader.py 'dev_appserver_login="root@example.com:True"'
(or you could skip the first argument and use the -r or --root options)

For uploading data into a Google AppEngine-hosted app, the cookie would begin
with ACSID:

drupal_uploader.py 'ACSID=AJXUWfE-aefkae...'

Options:
-D, --dbtype     = database type (default is 'mysql')
-t, --prefix     = table prefix, not supported by all blogtypes (default is '')
-b, --blogtype   = type of blog to import from (default is 'drupal')
-r, --root         sets authorization cookie for local dev admin
-d, --dbhostname = hostname of MySQL server (default is 'localhost')
-p, --dbport     = port of MySQL server (default is '3306')
-u, --dbuserpwd  = user:passwd for MySQL server (e.g., 'johndoe:mypasswd')
-n, --dbname     = name of Drupal database name (default is 'drupal')
-l, --url        = the url (web location) of the Bloog app
-a, --articles   = only upload this many articles (for testing)
-R, --static_redirect = generate redirects for static content by adding this
                        prefix. Not supported by all blogtypes.
"""
DB_ENCODING = 'latin-1'

# List the ASCII chars that are OK for our pages
NEWLINE_CHARS = [ord(x) for x in ['\n', '\t', '\r']]
OK_CHARS = range(32,126) + [ord(x) for x in ['\n', '\t', '\r']]
OK_TITLE = range(32,126)

db_types = {}
try:
    import MySQLdb
    def mysql_connect(dbuser, dbpasswd, dbhostname, dbport, dbname):
        if not dbport:
          dbport = 3306
        return MySQLdb.connect(user=dbuser,
                               passwd=dbpasswd,
                               host=dbhostname,
                               port=dbport,
                               db=dbname)
    db_types['mysql'] = mysql_connect
except ImportError:
    pass

try:
    import psycopg2
    def postgres_connect(dbuser, dbpasswd, dbhostname, dbport, dbname):
        if not dbport:
            dbport = 5432
        return psycopg2.connect(
            "user='%s' password='%s' host='%s' port='%s' dbname='%s'" %
            (dbuser, dbpasswd, dbhostname, dbport, dbname))
    db_types['postgres'] = postgres_connect
except ImportError:
    pass

def clean_multiline(raw_string):
    return ''.join([x for x in raw_string if ord(x) in OK_CHARS])

def force_singleline(raw_string):
    return ''.join([x for x in raw_string if ord(x) not in NEWLINE_CHARS])

def fix_string(str_from_db):
    # Add encoding change here if needed.
    # For Bloog, will just output latin-1 and let it convert to utf-8
    return str_from_db

def fix_thread_string(tstr):
    """
    Takes a string with numbers separated by period and possibly with /
    at end, and outputs a string with 3 digit numbers separated by periods.
    """
    remove_slash = lambda s: s[:-1] if s[-1] == '/' else s
    three_digits = lambda s: "%03d" % int(s)
    return '.'.join( map(three_digits, map(remove_slash, tstr.split('.'))))

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

    def do_request(self, url, verb, headers, body=''):
        scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
        print("Trying %s to %s (%s) using %s" % (verb, netloc, path, scheme))

        try:
            connection = HttpRESTClient.connect(scheme, netloc)
            try:
                connection.request(verb, path+'?'+query, body, headers)
                response = connection.getresponse()
                status = response.status
                reason = response.reason
                content = response.read()
                tuple_headers = response.getheaders()
                print('Received response code %d: %s\n%s' % 
                      (status, reason, content))
                if status != httplib.OK:
                    raise RequestError('Request error, code %d: %s\n%s' % 
                                       (status, reason, content))
                return status, reason, content, tuple_headers
            finally:
                connection.close()

        except (IOError, httplib.HTTPException, socket.error), e:
          print('Encountered exception accessing HTTP server: %s', e)
          raise HTTPConnectError(e)

    def get(self, url):
        headers = {}
        headers['Cookie'] = self.auth_cookie
        print "Cookie:", self.auth_cookie
        self.do_request(url, 'GET', headers)

    def post(self, url, body_dict):
        body = urllib.urlencode(body_dict)
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Content-Length': len(body),
            'Cookie': self.auth_cookie
        }
        status, reason, content, tuple_headers = \
            self.do_request(url, 'POST', headers, body)
        # Our app expects POSTs to return the new post's URL.
        if status != 200:
            raise RequestError('Unexpected response from web app: '
                               '%s, %s, %s' % (status, reason, content))
        return content

class BlogConverter(object):
    def __init__(self, auth_cookie, conn, app_url, table_prefix='',
                 static_redirect=None):
        self.webserver = HttpRESTClient(auth_cookie)
        self.app_url = app_url
        self.table_prefix = table_prefix
        self.conn = conn
        self.cursor = self.conn.cursor()
        self.static_redirect = static_redirect
    
    def close(self):
        self.cursor.close()
        self.conn.close()
    
    def go(self, num_articles = None):
        # Get all articles
        self.redirect = {}    # Keys are legacy IDs and maps to permalink

        article_count = 0
        for article in self.get_articles():
            article = self.get_article_tags(article)

            # Store the article by posting to either root (if "page") 
            # or blog month (if "blog" entry)
            print('Posting article with title "%s" to %s' % 
                  (article['title'], article['post_url']))
            entry_permalink = self.webserver.post(
                                self.app_url + article['post_url'],
                                article)
            if article['legacy_id']:
                self.redirect[article['legacy_id']] = entry_permalink
            print('Bloog successfully stored at %s' % (entry_permalink))

            comment_posting_url = self.app_url + entry_permalink
            for comment in self.get_article_comments(article):
                print ("Posting comment '%s' to %s"
                       % (comment['title'], comment_posting_url))
                self.webserver.post(comment_posting_url, comment)

            article_count += 1
            if num_articles and article_count >= num_articles:
                break

        # create_python_routing from url_alias table
        f = open('legacy_aliases.py', 'w')
        print >>f, "redirects = {"
        for src, dest in self.get_redirects():
            print >>f, "    '%s': '%s'," % \
                       (src.lower(), dest)
        print >>f, "}"
        f.close()
    
    def get_articles(self):
        """Returns an iterable of blog articles to be imported."""
        raise NotImplementedError()
    
    def get_article_tags(self, article):
        """Annotates an article with tags."""
        return article

    def get_article_comments(self, article):
        """Returns an iterable of comments associated with an article."""
        return []

    def get_redirects(self):
        """Returns an iterable of (src, dest) redirect tuples."""
        return []


class SerendipityConverter(BlogConverter):
    def get_articles(self):
        self.cursor.execute("SELECT id, title, timestamp, last_modified, body"
                            " FROM %sentries WHERE NOT isdraft"
                            % (self.table_prefix,))
        rows = self.cursor.fetchall()
        for row in rows:
            article = {}
            article['legacy_id'] = row[0]
            article['title'] = force_singleline(row[1])
            article['format'] = None
            article['body'] = re.sub('\n', '<br />', row[4])
            article['html'] = article['body']
            article['format'] = 'html'
            published = datetime.datetime.fromtimestamp(row[2])
            last_modified = datetime.datetime.fromtimestamp(row[3])
            article['published'] = str(published)
            article['updated'] = str(last_modified)
            article['post_url'] = '/%s/%s/' % (published.year, published.month)
            yield article
    
    def get_article_tags(self, article):
        article_tags = set()
        self.cursor.execute("SELECT categoryid FROM %sentrycat"
                            " WHERE entryid = %s"
                            % (self.table_prefix, article['legacy_id']))
        rows = self.cursor.fetchall()
        for row in rows:
            tag = self.tags.get(row[0], None)
            while tag:
              article_tags.add(tag['name'])
              tag = self.tags.get(tag['parent'], None)
        article['tags'] = ','.join(article_tags)
        return article

    def get_article_comments(self, article):
        self.cursor.execute("SELECT entry_id, id, parent_id, title, body, "
                            "timestamp, author, email, url FROM %scomments "
                            "WHERE entry_id = %s ORDER BY entry_id,parent_id,id"
                            % (self.table_prefix, article['legacy_id']))
        rows = self.cursor.fetchall()
        comments = {0: { 'children': []}}
        thread_id_ctr = 0
        for row in rows:
            comments[row[1]] = {
                'data': row,
                'children': [],
                'thread_id': thread_id_ctr
            }
            comments[row[2]]['children'].append(row[1])
            thread_id_ctr += 1

        stack = []
        for i in comments[0]['children']:
            stack.append(((comments[i]['thread_id'],), comments[i]))
        while stack:
            thread, entry = stack.pop()
            data = entry['data']
            yield {
                'title': data[3],
                'body': re.sub('\n', '<br />', data[4]),
                'published': str(datetime.datetime.fromtimestamp(data[5])),
                'thread': '.'.join('%03d' % x for x in thread),
                'name': data[6],
                'email': data[7],
                'homepage': data[8],
            }
            for i in comments[data[1]]['children']:
                stack.append((thread + (comments[i]['thread_id'],), 
                             comments[i]))
    
    def get_redirects(self):
        if self.static_redirect:
            self.cursor.execute("SELECT name, extension, thumbnail_name "
                                "FROM %simages" % (self.table_prefix,))
            rows = self.cursor.fetchall()
            for row in rows:
                path = "uploads/%s.%s" % row[0:2]
                yield (path, self.static_redirect + path)
                if row[2]:
                  thumbpath = "uploads/%s.%s.%s" % (row[0], row[2], row[1])
                  yield (thumbpath, self.static_redirect + thumbpath)

    def go(self, num_articles=None):
        self.cursor.execute("SELECT categoryid, parentid, category_name"
                            " FROM %scategory"
                            % (self.table_prefix,))
        rows = self.cursor.fetchall()
        self.tags = {}
        for row in rows:
            self.tags[row[0]] = {
                'parent': row[1],
                'name': row[2],
            }

        super(SerendipityConverter, self).go(num_articles)


class DrupalConverter(BlogConverter):
    """
    Makes remote connection to MySQL database for Drupal 4.* blog.
    Uses data in the following tables to initialize a Bloog app:
    - comments
    - node
    - term_data
    - term_hierarchy
    - term_node
    - url_alias
    Uploading data to the Bloog app is done solely through RESTful calls.
    """

    drupal_format_description = [
        None,
        "filtered html",
        None,           # php code which we'll reject
        "html",         # full html
        "textile"
    ]

    def get_html(self, raw_body, markup_type):
        """ Convert various Drupal formats to html """
        
        utf8_body = fix_string(raw_body)

        def repl(tmatch):
            if tmatch:   # Assume latin-1.  Will be converted by Bloog.
                return textile.textile(tmatch.group(1), 
                                       encoding='latin-1', output='latin-1')

        # Because Drupal textile formatting allows use of [textile][/textile] 
        # delimeters, remove them.
        if markup_type == 'textile':
            pattern = re.compile('\[textile\](.*)\[/textile\]', 
                                 re.MULTILINE | re.IGNORECASE | re.DOTALL)
            body = re.sub(pattern, repl, utf8_body)
        elif markup_type == 'filtered html':
            body = re.sub('\n', '<br />', utf8_body)
        else:
            body = raw_body
        return body
    
    def get_articles(self):
        self.cursor.execute("SELECT * FROM node")
        rows = self.cursor.fetchall()
        for row in rows:
            article = {}
            ntype = row[1]
            if ntype in ['page', 'blog']:
                article['legacy_id'] = row[0]
                article['title'] = force_singleline(row[2])
                article['format'] = None
                if row[14] >= 0 and row[14] <= 4:
                    cur_format = self.drupal_format_description[row[14]]
                    article['body'] = self.get_html(raw_body=row[11], 
                                                    markup_type=cur_format)
                    article['html'] = article['body']

                    # Because Drupal lets you intermix textile with other 
                    # markup, just convert it all to HTML
                    article['format'] = 'html'
                    published = datetime.datetime.fromtimestamp(row[5])
                    article['published'] = str(published)
                    article['updated'] = \
                        str(datetime.datetime.fromtimestamp(row[6]))
                    # Determine where to POST this article if it's a 
                    # article or a blog entry
                    if ntype == 'blog':
                        article['post_url'] = '/' + str(published.year) + \
                                              '/' + str(published.month) + "/"
                    else:
                        article['post_url'] = '/'
                    yield article
                else:
                    print "Rejected article with title (", \
                          article['title'], ") because bad format."
    
    def get_article_tags(self, article):
        # Add tags to each article by looking at term_node table
        sql = "SELECT d.tid FROM term_data d, term_node n " \
              "WHERE d.tid = n.tid AND n.nid = " + \
              str(article['legacy_id'])
        self.cursor.execute(sql)
        rows = self.cursor.fetchall()
        tag_names = set()
        for row in rows:
            tid = row[0]
            # Walk up the term tree and add all tags along path to root
            while tid:
                tag_names.update([self.tags[tid]['name']])
                tid = self.tags[tid]['parent']
        article['tags'] = ','.join(tag_names)
        return article
    
    def get_article_comments(self, article):
        # Store comments associated with the article
        sql = "SELECT subject, comment, timestamp, thread, name, mail, " \
              "homepage FROM comments WHERE nid = " + \
              str(article['legacy_id'])
        self.cursor.execute(sql)
        rows = self.cursor.fetchall()
        for row in rows:
            # Store comment associated with article by POST to 
            # article entry url
            comment = {
                'title': force_singleline(row[0]),
                'body': fix_string(row[1]),
                'published': str(datetime.datetime.fromtimestamp(row[2])),
                'thread': fix_thread_string(force_singleline(row[3])),
                'name': force_singleline(row[4]),
                'email': force_singleline(row[5]),
                'homepage': force_singleline(row[6])
            }
            yield comment
    
    def get_redirects(self):
        self.cursor.execute("SELECT * FROM url_alias")
        rows = self.cursor.fetchall()
        for row in rows:
            nmatch = re.match('node/(\d+)', row[1])
            if nmatch:
                legacy_id = string.atoi(nmatch.group(1))
                if legacy_id in self.redirect:
                    yield (row[2], self.redirect[legacy_id])

    def go(self, num_articles=None):
        # Get all the term (tag) data and the hierarchy pattern
        self.cursor.execute("SELECT tid, name FROM term_data")
        rows = self.cursor.fetchall()
        self.tags = {}
        for row in rows:
            tid = row[0]
            self.tags[tid] = {'name': row[1]}
        self.cursor.execute("SELECT tid, parent FROM term_hierarchy")
        rows = self.cursor.fetchall()
        for row in rows:
            self.tags[row[0]]['parent'] = row[1]

        super(DrupalConverter, self).go(num_articles)


blog_types = {
  'serendipity': SerendipityConverter,
  'drupal': DrupalConverter,
}


def main(argv):
    try:
        try:
            opts, args = getopt.gnu_getopt(argv, 'hrd:p:u:n:l:a:vD:t:b:R:',
                                           ["help", "root", "dbhostname=",
                                            "dbport=", "dbuserpwd=", "dbname=",
                                            "url=", "articles=", "dbtype=",
                                            "prefix=", "blogtype=",
                                            "static_redirect="])
        except getopt.error, msg:
            raise UsageError(msg)

        blogtype = 'drupal'
        dbtype = 'mysql'
        table_prefix = ''
        dbhostname = 'localhost'
        dbport = None
        dbname = None
        dbuser = ''
        dbpasswd = ''
        app_url = 'http://localhost:8080'
        num_articles = None
        static_redirect = None
        
        # option processing
        local_admin = None
        for option, value in opts:
            print "Looking at option:", str(option), str(value)
            if option == "-v":
                verbose = True
            if option in ("-h", "--help"):
                raise UsageError(help_message)
            if option in ("-r", "--root"):
                local_admin = 'dev_appserver_login="root@example.com:True"'
            if option in ("-D", "--dbtype"):
                if value not in db_types:
                    print "-D, --dbtype must be one of %r" % db_types.keys()
                    return 1
                dbtype = value
            if option in ("-t", "--prefix"):
                table_prefix = value
            if option in ("-b", "--blogtype"):
                if value not in blog_types:
                    print "-b, --blogtype must be one of %r" % blog_types.keys()
                    return 1
                blogtype = value
            if option in ("-d", "--dbhostname"):
                dbhostname = value
            if option in ("-p", "--dbport"):
                dbport = value
            if option in ("-u", "--dbuserpwd"):
                userpwd = value.split(":")
                try:
                    dbuser = userpwd[0]
                    dbpasswd = userpwd[1]
                except:
                    print "-u, --dbuserpwd should be followed by " \
                          "'username:passwd' with colon separating " \
                          "required information"
            if option in ("-n", "--dbname"):
                dbname = value
            if option in ("-a", "--articles"):
                num_articles = string.atoi(value)
            if option in ("-l", "--url"):
                print "Got url:", value
                app_url = value
                if app_url[:4] != 'http':
                    app_url = 'http://' + app_url
                if app_url[-1] == '/':
                    app_url = app_url[:-1]
            if option in ("-R", "--static_redirect"):
                static_redirect = value
        
        if not dbname:
            dbname = blogtype

        if len(args) < 2 and not local_admin:
            raise UsageError("Please specify the authentication cookie string"
                             " as first argument.")
        else:
            auth_cookie = local_admin or args[1]

            #TODO - Use mechanize module to programmatically login
            #email = raw_input("E-mail: ")
            #passwd = getpass.getpass("Password: ")

            print dbuser, dbpasswd, dbhostname, dbport, dbname
            conn = db_types[dbtype](dbuser, dbpasswd, dbhostname, dbport,
                                    dbname)
            converter = blog_types[blogtype](auth_cookie=auth_cookie,
                                             conn=conn,
                                             app_url=app_url,
                                             table_prefix=table_prefix,
                                             static_redirect=static_redirect)
            converter.go(num_articles)
            converter.close()
    
    except UsageError, err:
        print >> sys.stderr, sys.argv[0].split("/")[-1] + ": " + str(err.msg)
        print >> sys.stderr, "\t for help use --help"
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
