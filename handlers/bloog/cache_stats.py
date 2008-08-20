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

"""
cache_stats.py

Created by William Katz on 2008-05-04.
Copyright (c) 2008 Publishare LLC.  Distributed under MIT License.
"""
__author__ = "William T. Katz"

import time
import urlparse
import os

from google.appengine.api import memcache

from handlers import restful
from utils import authorized
import view

class CacheStatsHandler(restful.Controller):
    @authorized.role("admin")
    def get(self):
        cache_stats = memcache.get_stats()
        view.ViewPage(cache_time=0).render(self, {"stats": cache_stats})

    @authorized.role("admin")
    def delete(self):
        memcache.flush_all()
