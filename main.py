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


"""A simple blog for Google App Engine"""

__author__ = 'William T. Katz'

import wsgiref.handlers

from google.appengine.ext import webapp

import blog
import contact
import cache_stats
import logging
import config
import timings

# TODO: Add global that caches url aliases read in from YAML file

# TODO: Global that stores cached regexs for routing
# Each imported handler can check if its routes are already present, 
#  and if not, it adds them.
# This might already be done by webapp.WSGIApplication, 
#  in which case we should look for hook to add routes within modules.
ROUTES = []

# TODO: Add caching for error pages. 
# Make sure the error pages doesn't reuse things that shouldn't
# be reused across requests, like user logins.  Caching error pages 
# is probably a big win because of spam robots.

def main():
    path = timings.start_run()
    logging.debug("Received request with path %s", path)
    application = webapp.WSGIApplication(
                    [('/*$', blog.RootHandler),
                     ('/403.html', blog.UnauthorizedHandler),
                     ('/404.html', blog.NotFoundHandler),
                     ('/([12]\d\d\d)/*$', blog.YearHandler),
                     ('/([12]\d\d\d)/(\d|[01]\d)/*$', blog.MonthHandler),
                     ('/([12]\d\d\d)/(\d|[01]\d)/([-\w]+)/*$',          
                        blog.BlogEntryHandler),
                     ('/admin/cache_stats/*$', cache_stats.CacheStatsHandler),
                     ('/admin/timings/*$', timings.TimingHandler),
                     ('/search', blog.SearchHandler),
                     ('/contact/*$', contact.ContactHandler),
                     ('/tag/(.*)', blog.TagHandler),
                     (config.blog['master_atom_url'] + '/*$', 
                        blog.AtomHandler),
                     ('/(.*)', blog.ArticleHandler)], 
                    debug=True)
    wsgiref.handlers.CGIHandler().run(application)
    timings.stop_run(path)

if __name__ == "__main__":
    main()