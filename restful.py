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


"""RESTful Controller

We want our RESTful controllers to simply throw up their hands if they get
an unhandled HTTP verb.  This is better for rich clients and server load
than throwing back lots of useless HTML.

These inherited methods should be overridden if there's a chance a human
browser is involved.

TODO: Return more information HTTP status codes that won't autotrip browser login forms.
For example, return status 405 (Method not allowed) with an Allow header containing the
list of valid methods.
"""
__author__ = 'William T. Katz'

from google.appengine.ext import webapp

# Some useful module methods

def successful_post_response(handler, permalink, post_type):
    handler.response.out.write('<a href="' + permalink + '">' + post_type + ' successfully stored</a>')

def get_hash_from_request(request, propname_list):
    """
    This maps request strings to values in a hash, optionally run through a function with previous request values as parameters to the func.
    1) string -> just read in the corresponding request value
    2) tuple (string, func) -> The string is the key and we run its request value through func
    3) tuple (string, func, previous strings...) -> Same as above but the parameters to func are current property values in our hash
    OK.. maybe I got a little carried away here experimenting and trying to be DRY.  We can just unroll it in a git branch :)
    """
    prop_hash = {}
    for item in propname_list:
        if type(item) == str:
            prop_hash[item] = request.get(item)
        elif type(item == tuple):
            key = item[0]
            prop_func = item[1]
            if len(item) <= 2:
                prop_hash[key] = prop_func(request.get(key))
            elif len(item) == 4:
                prop_hash[key] = prop_func(prop_hash[item[2]], prop_hash[item[3]])
    return prop_hash

class Controller(webapp.RequestHandler):

    def get(self, *params):
        self.redirect("/403.html")

    def post(self, *params):
        self.error(403)

    def put(self, *params):
        self.error(403)

    def delete(self, *params):
        self.error(403)

    def head(self, *params):
        self.error(403)

    def trace(self, *params):
        self.error(403)

    def options(self, *params):
        self.error(403)

