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

from google.appengine.api import memcache
from google.appengine.ext import db

import config
import models
from models import search

# Handle generation of thread strings
def get_thread_string(article, cur_thread_string):
    min_str = cur_thread_string + '000'
    max_str = cur_thread_string + '999'
    q = db.GqlQuery("SELECT * FROM Comment " +
                    "WHERE article = :1 " +
                    "AND thread >= :2 AND thread <= :3",
                    article, min_str, max_str)
    num_comments = q.count(999)
    if num_comments > 998:
        return None         # Only allow 999 comments on each tree level
    return cur_thread_string + "%03d" % (num_comments + 1)

class Article(search.SearchableModel):
    unsearchable_properties = ['permalink', 'legacy_id', 'article_type', 
                               'excerpt', 'html', 'format']
    json_does_not_include = ['assoc_dict']

    permalink = db.StringProperty(required=True)
    # Useful for aliasing of old urls
    legacy_id = db.StringProperty()
    title = db.StringProperty(required=True)
    article_type = db.StringProperty(required=True, 
                                     choices=set(["article", "blog entry"]))
    # Body can be in any format supported by Bloog (e.g. textile)
    body = db.TextProperty(required=True)
    # If available, we use 'excerpt' to summarize instead of 
    # extracting the first 68 words of 'body'.
    excerpt = db.TextProperty()
    # The html property is generated from body
    html = db.TextProperty()
    published = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now_add=True)
    format = db.StringProperty(required=True, 
                               choices=set(["html", "textile", 
                                            "markdown", "text"]))
    # Picked dict for sidelinks, associated Amazon items, etc.
    assoc_dict = db.BlobProperty()
    # To prevent full query when just showing article headlines
    num_comments = db.IntegerProperty(default=0)
    # Use keys instead of db.Category for consolidation of tag names
    tags = db.StringListProperty(default=[])
    tag_keys = db.ListProperty(db.Key, default=[])
    two_columns = db.BooleanProperty()
    allow_comments = db.BooleanProperty()
    # A list of languages for code embedded in article.
    # This lets us choose the proper javascript for pretty viewing.
    embedded_code = db.StringListProperty()

    def get_comments(self):
        """Return comments lexicographically sorted on thread string"""
        q = db.GqlQuery("SELECT * FROM Comment " +
                        "WHERE article = :1 " +
                        "ORDER BY thread ASC", self.key())
        return [comment for comment in q]
    comments = property(get_comments)       # No set for now

    def set_associated_data(self, data):
        """
        Serialize data that we'd like to store with this article.
        Examples include relevant (per article) links and associated 
        Amazon items.
        """
        import pickle
        self.assoc_dict = pickle.dumps(data)

    def get_associated_data(self):
        import pickle
        return pickle.loads(self.assoc_dict)

    def full_permalink(self):
        return config.BLOG['root_url'] + '/' + self.permalink
    
    def rfc3339_published(self):
        return self.published.strftime('%Y-%m-%dT%H:%M:%SZ')

    def rfc3339_updated(self):
        return self.updated.strftime('%Y-%m-%dT%H:%M:%SZ')

    def is_big(self):
        guess_chars = len(self.html) + self.num_comments * 80
        if guess_chars > 2000 or \
           self.embedded_code or \
           '<img' in self.html or \
           '<code>' in self.html or \
           '<pre>' in self.html:
            return True
        else:
            return False

    def next_comment_thread_string(self):
        'Returns thread string for next comment for this article'
        return get_thread_string(self, '')

class Comment(models.SerializableModel):
    """Stores comments and their position in comment threads.

    Thread string describes the tree using 3 digit numbers.
    This allows lexicographical sorting to order comments
    and easy indentation computation based on the string depth.
    Example for comments that are nested except first response:
    001
      001.001
      001.002
        001.002.001
          001.002.001.001
    NOTE: This means we assume less than 999 comments in
      response to a parent comment, and we won't have
      nesting that causes our thread string > 500 bytes.
      TODO -- Put in error checks
    """
    name = db.StringProperty()
    email = db.EmailProperty()
    homepage = db.StringProperty()
    title = db.StringProperty()
    body = db.TextProperty(required=True)
    published = db.DateTimeProperty(auto_now_add=True)
    article = db.ReferenceProperty(Article)
    thread = db.StringProperty(required=True)

    def get_indentation(self):
        # Indentation is based on degree of nesting in "thread"
        nesting_str_array = self.thread.split('.')
        return min([len(nesting_str_array), 10])

    def next_child_thread_string(self):
        'Returns thread string for next child of this comment'
        return get_thread_string(self.article, self.thread + '.')


class Tag(models.MemcachedModel):
    # Inserts these values into aggregate list returned by Tag.list()
    list_includes = ['counter.count', 'name']

    def delete(self):
        self.delete_counter()
        super(Tag, self).delete()

    def get_counter(self):
        counter = models.Counter('Tag' + self.name)
        return counter

    def set_counter(self, value):
        # Not implemented at this time
        pass

    def delete_counter(self):
        models.Counter('Tag' + self.name).delete()

    counter = property(get_counter, set_counter, delete_counter)

    def get_name(self):
        return self.key().name()
    name = property(get_name)
    