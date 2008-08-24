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
contact.py
This module provides a simple form for entering a message and the
handlers for receiving the message through a HTTP POST.
"""
__author__ = 'William T. Katz'

import logging
import string
import time

from google.appengine.api import users

from handlers import restful
import view
import config

RANDOM_TOKEN = '08yzek30krn4l' + config.BLOG['root_url']

class ContactHandler(restful.Controller):
    def get(self):
        user = users.get_current_user()
        # Don't use cache since we want to get current time for each post.
        view.ViewPage(cache_time=0). \
             render(self, {'email': user.email() if user else 'Required',
                           'nickname': user.nickname() if user else '',
                           'token': RANDOM_TOKEN, 'curtime': time.time()})

    def post(self):
        from google.appengine.api import mail

        if self.request.get('token') != RANDOM_TOKEN or \
           time.time() - string.atof(self.request.get('curtime')) < 2.0:
            logging.info("Aborted contact mailing because form submission "
                          "was less than 2 seconds.")
            self.error(403)

        user = users.get_current_user()
        sender = user.email() if user else config.BLOG['email']
        reply_to = self.request.get('email') or \
                   (user_email() if user else 'unknown@foo.com')
        mail.send_mail(
            sender = sender,
            reply_to = self.request.get('author') + '<' + reply_to + '>',
            to = config.BLOG['email'],
            subject = self.request.get('subject') or 'No Subject Given',
            body = self.request.get('message') or 'No Message Given'
        )

        view.ViewPage(cache_time=36000).render(self)