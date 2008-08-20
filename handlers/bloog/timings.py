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
timings.py

Created by William Katz on 2008-05-04.
Copyright (c) 2008 Publishare LLC.  Distributed under MIT License.
"""
__author__ = "William T. Katz"

# Global that stores timing runs, all keyed to incoming url path.
# Note that since this is a global, you'll only get stats from the
#  currently visited server and it could be reset.  The timing
#  utility is not meant to be comprehensive but only a hack that
#  doesn't interfere with memcached stats.
TIMINGS = {}

import time
import urlparse
import os

from handlers import restful
from utils import authorized
import view

def start_run():
    url = os.environ['PATH_INFO']
    scheme, netloc, path, query, fragment = urlparse.urlsplit(url)

    global TIMINGS
    if not path in TIMINGS:
        TIMINGS[path] = {
            "runs": 0,
            "duration": 0.0,
            "min_time": None,
            "max_time": None,
            "mutex_lock": False
        }
    timing = TIMINGS[path]
    if not timing["mutex_lock"]:
        timing["mutex_lock"] = True
        timing["start_time"] = time.time()
        return path
    return None

def stop_run(path):
    global TIMINGS
    if path and path in TIMINGS:
        timing = TIMINGS[path]
        elapsed_time = time.time() - timing["start_time"]
        timing["duration"] += elapsed_time
        timing["runs"] += 1
        if (not timing["min_time"]) or timing["min_time"] > elapsed_time:
            timing["min_time"] = elapsed_time
        if (not timing["max_time"]) or timing["max_time"] < elapsed_time:
            timing["max_time"] = elapsed_time
        timing["mutex_lock"] = False

class TimingHandler(restful.Controller):
    @authorized.role("admin")
    def get(self):
        global TIMINGS
        stats = []
        total_time = 0.0
        avg_speed = 0.0
        total_calls = 0
        total_full_renders = 0
        for key in TIMINGS:
            
            full_renders = 0
            if key in view.NUM_FULL_RENDERS:
                full_renders = view.NUM_FULL_RENDERS[key]
                total_full_renders += full_renders
            url_timing = TIMINGS[key]
            if url_timing["runs"] > 0:
                url_stats = url_timing.copy()
                url_stats.update({'url': key,
                                  'avg_speed': url_timing["duration"] / 
                                               url_timing["runs"],
                                  'full_renders': full_renders})
                stats.append(url_stats)
                total_time += url_timing["duration"]
                total_calls += url_timing["runs"]

        
        if total_calls > 0:
            avg_speed = total_time / total_calls
        view.ViewPage(cache_time=0).render(self, {"stats": stats, 
                                                  "avg_speed": avg_speed,
                                                  "total_time": total_time, 
                                                  "total_calls": total_calls,
                                                  "total_full_renders": 
                                                     total_full_renders})

    @authorized.role("admin")
    def delete(self):
        global TIMINGS
        TIMINGS = {}