# The MIT License
# 
# Copyright (c) 2008 William T. Katz
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import os
import re

import logging

from google.appengine.api import users
from google.appengine.ext.webapp import template

import config
import copy
import time
import urlparse
import string

bloog_version = "0.5"     # This constant should be in upgradable code files.

# Cache of recent rendered views, keyed by template file and parameters
VIEW_CACHE = {}

# Recording of non-cached views per url
NUM_FULL_RENDERS = {}

def invalidate_cache():
    global VIEW_CACHE, NUM_FULL_RENDERS
    VIEW_CACHE = {}
    NUM_FULL_RENDERS = {}
    

HANDLER_PATTERN = re.compile("<class '([^\.]*)\.(\w+)Handler'>")

def get_view_file(handler, params={}):
    """
    Looks for presence of template files with priority given to 
     HTTP method (verb) and role.
    Full filenames are <handler>.<role>.<verb>.<ext> where
     <handler> = lower-case handler name
     <role> = role of current user
     <verb> = HTTP verb, e.g. GET or POST
     <ext> = html, xml, etc.
    Only <handler> and <ext> are required.
    Properties 'module_name' and 'handler_name' can be passed in 
     params to override the current module/handler name.
    """
    desired_ext = 'html'
    if params.has_key('ext'):
        desired_ext = params['ext']

    verb = handler.request.method.lower()
    class_name = str(handler.__class__)
    nmatch = re.match(HANDLER_PATTERN, class_name)
    if nmatch:
        module_name = nmatch.group(1).lower()
        handler_name = nmatch.group(2).lower()
    else:
        module_name = None
        handler_name = None

    if params.has_key('module_name'):
        module_name = params['module_name']
    if params.has_key('handler_name'):
        handler_name = params['handler_name']

    if module_name and handler_name:
        filename_stem = 'views/' + module_name + '/' + handler_name
        possible_roles = []
        if users.is_current_user_admin():
            possible_roles.append('.admin.')
        if users.get_current_user():
            possible_roles.append('.user.')
        possible_roles.append('.')
        # Check possible template file names in order of decreasing priority
        for role in possible_roles:
            filename = filename_stem + role + verb + '.' + desired_ext
            if os.path.exists(filename):
                return filename
        for role in possible_roles:
            filename = filename_stem + role + desired_ext
            if os.path.exists(filename):
                return filename
    return 'views/404.html'

class ViewPage(object):
    def __init__(self, cache_time=None):
        """Each ViewPage has a variable cache timeout"""
        if cache_time == None:
            self.cache_time = config.blog['cache_time']
        else:
            self.cache_time = cache_time

    def full_render(self, handler, template_file, more_params):
        """Render a dynamic page from scatch."""
        global NUM_FULL_RENDERS, TAGS_NONBREAKING
        url = handler.request.uri
        scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
        if not NUM_FULL_RENDERS.has_key(path):
            NUM_FULL_RENDERS[path] = 0
        NUM_FULL_RENDERS[path] += 1     # This lets us see % of cached views
                                        # in /admin/timings (see timings.py)
        template_params = {
            "current_url": url,
            "bloog_version": bloog_version,
            "user": users.get_current_user(),
            "user_is_admin": users.is_current_user_admin(),
            "login_url": users.create_login_url(handler.request.uri),
            "logout_url": users.create_logout_url(handler.request.uri),
            "blog": config.blog or config.default_blog
        }
        template_params.update(config.page or config.default_page)
        template_params.update(more_params)
        return template.render(template_file, template_params,
                               debug=config.DEBUG)

    def render_or_get_cache(self, handler, template_file, template_params={}):
        """Checks if there's a non-stale cached version of this view, 
           and if so, return it."""
        if self.cache_time:
            # See if there's a cache within time.
            # The cache key suggests a problem with the url <-> function 
            #  mapping, because a significant advantage of RESTful design 
            #  is that a distinct url gets you a distinct, cacheable 
            #  resource.  If we have to include states like "user?" and 
            #  "admin?", then it suggests these flags should be in url.               
            # TODO - Think about the above with respect to caching.
            global VIEW_CACHE
            stateful_flags = str(users.get_current_user() != None) + \
                             str(users.is_current_user_admin())
            key = handler.request.url + stateful_flags
            if not VIEW_CACHE.has_key(key):
                logging.debug("Couldn't find a cache for %s", key)
                VIEW_CACHE[key] = {
                    'time': 0.0,
                    'output': ''
                }
            elif VIEW_CACHE[key]['time'] > time.time() - self.cache_time:
                logging.debug("Using cache for %s", template_file)
                return VIEW_CACHE[key]['output']

            output = self.full_render(handler, template_file, template_params)
            VIEW_CACHE[key]['output'] = output
            VIEW_CACHE[key]['time'] = time.time()
            return output
            
        return self.full_render(handler, template_file, template_params)
        
    def render(self, handler, params={}):
        """
        Can pass overriding parameters within dict.  These parameters can 
        include:
            'ext': 'xml' (or any other format type)
        """
        view_file = get_view_file(handler, params)
        if view_file:
            dirname = os.path.dirname(__file__)
            template_file = os.path.join(dirname, view_file)
            logging.debug("Using template at %s", template_file)
            output = self.render_or_get_cache(handler, template_file, params)
            handler.response.out.write(output)
        else:
            handler.response.out.write(
                "<h3>Couldn't get a view file -> " + view_file + "</h3>"
            )

    def render_query(self, handler, model_name, query, params={}):
        """
        Handles typical rendering of queries into datastore.
        """
        limit = string.atoi(handler.request.get("limit") or '5')
        offset = string.atoi(handler.request.get("offset") or '0')
        models = query.fetch(limit, offset)
        render_params = {model_name: models}
        render_params.update(params)

        self.render(handler, render_params)

