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

import os
import re

import logging

from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.api import memcache

import config
import copy
import time
import urlparse
import string

bloog_version = "0.8"       # Constant should be in upgradable code files.

NUM_FULL_RENDERS = {}       # Cached data for some timings.

def invalidate_cache():
    memcache.flush_all()

HANDLER_PATTERN = re.compile(r"<class '(?P<module_name>[^\.]*)"
                             r"\."
                             r"(?P<handler_name>\w+)Handler'>")

def to_filename(camelcase_handler_str):
    filename = camelcase_handler_str[0].lower()
    for ch in camelcase_handler_str[1:]:
        if ch in string.uppercase:
            filename += '_' + ch.lower()
        else:
            filename += ch
    return filename

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
    if 'ext' in params:
        desired_ext = params['ext']
    else:
        desired_ext = 'html'

    verb = handler.request.method.lower()
    class_name = str(handler.__class__)
    nmatch = re.match(HANDLER_PATTERN, class_name)
    if nmatch:
        module_name = to_filename(nmatch.group('module_name'))
        handler_name = to_filename(nmatch.group('handler_name'))
    else:
        module_name = None
        handler_name = None

    if 'module_name' in params:
        module_name = params['module_name']
    if 'handler_name' in params:
        handler_name = params['handler_name']

    if module_name and handler_name:
        filename_stem = 'views/' + module_name + '/' + handler_name
        logging.debug("Looking for template with stem %s", filename_stem)
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
    return 'views/blog/notfound.html'

class ViewPage(object):
    def __init__(self, cache_time=None):
        """Each ViewPage has a variable cache timeout"""
        if cache_time == None:
            self.cache_time = config.blog['cache_time']
        else:
            self.cache_time = cache_time

    def full_render(self, handler, template_file, more_params):
        """Render a dynamic page from scatch."""
        logging.debug("Doing full render using template_file: %s", template_file)
        url = handler.request.uri
        scheme, netloc, path, query, fragment = urlparse.urlsplit(url)

        global NUM_FULL_RENDERS
        if not path in NUM_FULL_RENDERS:
            NUM_FULL_RENDERS[path] = 0
        NUM_FULL_RENDERS[path] += 1     # This lets us see % of cached views
                                        # in /admin/timings (see timings.py)
        # Define some parameters it'd be nice to have in views by default.
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
            stateful_flags = str(users.get_current_user() != None) + \
                             str(users.is_current_user_admin())
            key = handler.request.url + stateful_flags
            data = memcache.get(key)
            if data is not None:
                logging.debug("Using cache for %s", template_file)
                return data
            else:
                logging.debug("Memcached miss using key: %s", key)

        output = self.full_render(handler, template_file, template_params)
        if self.cache_time:
            logging.debug("Adding %s to memcached (key %s) for %d sec",
                          template_file, key, self.cache_time)
            memcache.add(key, output, self.cache_time)
        else:
            logging.debug("Ignoring caching since cache_time set to %d",
                          self.cache_time)
        return output

    def render(self, handler, params={}):
        """
        Can pass overriding parameters within dict.  These parameters can 
        include:
            'ext': 'xml' (or any other format type)
        """
        view_file = get_view_file(handler, params)

        dirname = os.path.dirname(__file__)
        template_file = os.path.join(dirname, view_file)
        logging.debug("Using template at %s", template_file)
        output = self.render_or_get_cache(handler, template_file, params)
        handler.response.out.write(output)

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

