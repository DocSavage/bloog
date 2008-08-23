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


import logging
import os
import re
import string
import time
import urlparse

from google.appengine.api import users
from google.appengine.api import memcache

from models.blog import Tag       # Might rethink if this is leaking into view
from utils import template
import config

NUM_FULL_RENDERS = {}       # Cached data for some timings.

def invalidate_cache():
    memcache.flush_all()

def to_filename(camelcase_handler_str):
    filename = camelcase_handler_str[0].lower()
    for ch in camelcase_handler_str[1:]:
        if ch in string.uppercase:
            filename += '_' + ch.lower()
        else:
            filename += ch
    return filename

HANDLER_PATTERN = re.compile(r"<class 'handlers\."
                             r"(?P<handler_path>.*)"
                             r"(?=Handler'>)")

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
     
    Returns:
      Tuple with first element = template file name and
      second element = template directory path tuple
    """
    if 'ext' in params:
        desired_ext = params['ext']
    else:
        desired_ext = 'html'

    verb = handler.request.method.lower()
    class_name = str(handler.__class__)
    nmatch = re.match(HANDLER_PATTERN, class_name)
    if nmatch:
        handler_path = nmatch.group('handler_path').split('.')
        if len(handler_path) == 3:
            app_name = to_filename(handler_path[0])
        else:
            app_name = ''
        module_name = to_filename(handler_path[-2])
        handler_name = to_filename(handler_path[-1])
    else:
        app_name = ''
        module_name = None
        handler_name = None

    if 'app_name' in params:
        app_name = params['app_name']
    if 'module_name' in params:
        module_name = params['module_name']
    if 'handler_name' in params:
        handler_name = params['handler_name']

    # Get template directory hierarchy -- Needed if we inherit from templates
    # in directories above us (due to sharing with other templates).
    
    root_folder = os.path.join(
        config.APP_ROOT_DIR, 
        'views', config.BLOG['theme'])
    template_dirs = ()
    if module_name:
        template_dirs += (os.path.join(root_folder, app_name, module_name),)
    if app_name:
        template_dirs += (os.path.join(root_folder, app_name),)
    template_dirs += (root_folder,)
        
    # Now check possible extensions for the given template file.
    if module_name and handler_name:
        filename_prefix = os.path.join(root_folder, app_name, module_name, handler_name)
        possible_roles = []
        if users.is_current_user_admin():
            possible_roles.append('.admin.')
        if users.get_current_user():
            possible_roles.append('.user.')
        possible_roles.append('.')
        # Check possible template file names in order of decreasing priority
        for role in possible_roles:
            filename = filename_prefix + role + verb + '.' + desired_ext
            if os.path.exists(filename):
                return {'file': filename, 'dirs': template_dirs}
        for role in possible_roles:
            filename = filename_prefix + role + desired_ext
            if os.path.exists(filename):
                return {'file': filename, 'dirs': template_dirs}
    return {'file': root_folder + '/notfound.html', 'dirs': template_dirs}

class ViewPage(object):
    def __init__(self, cache_time=None):
        """Each ViewPage has a variable cache timeout"""
        if cache_time == None:
            self.cache_time = config.BLOG['cache_time']
        else:
            self.cache_time = cache_time

    def full_render(self, handler, template_info, more_params):
        """Render a dynamic page from scatch."""
        logging.debug("Doing full render using template_file: %s", template_info['file'])
        url = handler.request.uri
        scheme, netloc, path, query, fragment = urlparse.urlsplit(url)

        global NUM_FULL_RENDERS
        if not path in NUM_FULL_RENDERS:
            NUM_FULL_RENDERS[path] = 0
        NUM_FULL_RENDERS[path] += 1     # This lets us see % of cached views
                                        # in /admin/timings (see timings.py)
        tags = Tag.list()

        # Define some parameters it'd be nice to have in views by default.
        template_params = {
            "current_url": url,
            "bloog_version": config.BLOG['bloog_version'],
            "user": users.get_current_user(),
            "user_is_admin": users.is_current_user_admin(),
            "login_url": users.create_login_url(handler.request.uri),
            "logout_url": users.create_logout_url(handler.request.uri),
            "blog": config.BLOG,
            "blog_tags": tags
        }
        template_params.update(config.PAGE)
        template_params.update(more_params)
        return template.render(template_info['file'], template_params,
                               debug=config.DEBUG, 
                               template_dirs=template_info['dirs'])

    def render_or_get_cache(self, handler, template_info, template_params={}):
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
                logging.debug("Using cache for %s", template_info['file'])
                return data
            else:
                logging.debug("Memcached miss using key: %s", key)

        output = self.full_render(handler, template_info, template_params)
        if self.cache_time:
            logging.debug("Adding %s to memcached (key %s) for %d sec",
                          template_info['file'], key, self.cache_time)
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
        template_info = get_view_file(handler, params)
        logging.debug("Using template at %s", template_info['file'])
        output = self.render_or_get_cache(handler, template_info, params)
        handler.response.out.write(output)

    def render_query(self, handler, model_name, query, params={},
                     num_limit=config.PAGE['articles_per_page'],
                     num_offset=0):
        """
        Handles typical rendering of queries into datastore
        with paging.
        """
        limit = string.atoi(handler.request.get("limit") or str(num_limit))
        offset = string.atoi(handler.request.get("offset") or str(num_offset))
        # Trick is to ask for one more than you need to see if 'next' needed.
        models = query.fetch(limit+1, offset)
        render_params = {model_name: models, 'limit': limit}
        if len(models) > limit:
            render_params.update({ 'next_offset': str(offset+limit) })
            models.pop()
        if offset > 0:
            render_params.update({ 'prev_offset': str(offset-limit) })
        render_params.update(params)

        self.render(handler, render_params)

