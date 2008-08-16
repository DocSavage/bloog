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

import config
from counter import Counter

import logging
import time

from google.appengine.api import memcache
from google.appengine.ext import db

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

# Searchable model and entities were derived from code in SDK at
# under google.appengine.ext import search.  Modifications were
# necessary to decrease computation that tripped quotas.
import search

class Article(search.SearchableModel):
    # The following string-based properties shouldn't be indexed
    unsearchable_properties = [
        'permalink', 'legacy_id', 'article_type', 'excerpt', 'html', 'format'
    ]
    permalink = db.StringProperty(required=True)
    # Useful for aliasing of old urls
    legacy_id = db.StringProperty()
    title = db.StringProperty(required=True)
    article_type = db.StringProperty(
                        required=True, 
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
    format = db.StringProperty(
                        required=True, 
                        choices=set(["html", "textile", 
                                     "markdown", "text"]))
    # Picked dict for sidelinks, associated Amazon items, etc.
    assoc_dict = db.BlobProperty()
    # To prevent full query when just showing article headlines
    num_comments = db.IntegerProperty(default=0)
    # Use keys instead of db.Category for consolidation of tag names
    tags = db.ListProperty(db.Key)
    two_columns = db.BooleanProperty()
    allow_comments = db.BooleanProperty()

    def get_comments(self):
        """Return comments lexicographically sorted on thread string"""
        q = db.GqlQuery("SELECT * FROM Comment " +
                        "WHERE article = :1 " +
                        "ORDER BY thread ASC", self.key())
        return [comment for comment in q]
    comments = property(get_comments)       # No set for now

    # Serialize data that we'd like to store with this article.
    # Examples include relevant (per article) links and associated 
    #  Amazon items.
    def set_associated_data(self, data):
        import pickle
        self.assoc_dict = pickle.dumps(data)

    def get_associated_data(self):
        import pickle
        return pickle.loads(self.assoc_dict)

    def full_permalink(self):
        return config.blog['root_url'] + '/' + self.permalink
    
    def rfc3339_published(self):
        return self.published.strftime('%Y-%m-%dT%H:%M:%SZ')

    def rfc3339_updated(self):
        return self.updated.strftime('%Y-%m-%dT%H:%M:%SZ')

    def is_big(self):
        guess_chars = len(self.html) + self.num_comments * 80
        if guess_chars > 2000 or \
           '<img' in self.html or \
           '<code>' in self.html or \
           '<pre>' in self.html:
            return True
        else:
            return False

    def next_comment_thread_string(self):
        'Returns thread string for next comment for this article'
        return get_thread_string(self, '')

class Comment(db.Model):
    name = db.StringProperty()
    email = db.EmailProperty()
    homepage = db.StringProperty()
    title = db.StringProperty()
    body = db.TextProperty(required=True)
    published = db.DateTimeProperty(auto_now_add=True)
    article = db.ReferenceProperty(Article)

    thread = db.StringProperty(required=True)
    # Thread string describes the tree using 3 digit numbers.
    # This allows lexicographical sorting to order comments
    # and easy indentation computation based on the string depth.
    # Example for comments that are nested except first response:
    # 001
    #   001.001
    #   001.002
    #     001.002.001
    #       001.002.001.001
    # NOTE: This means we assume less than 999 comments in
    #   response to a parent comment, and we won't have
    #   nesting that causes our thread string > 500 bytes.
    #   TODO -- Put in error checks

    def get_indentation(self):
        # Indentation is based on degree of nesting in "thread"
        nesting_str_array = self.thread.split('.')
        return min([len(nesting_str_array), 10])

    def next_child_thread_string(self):
        'Returns thread string for next child of this comment'
        return get_thread_string(self.article, self.thread + '.')

class MemcachedModel(db.Model):
    """MemcachedModel adds memcached all() retrieval through list().
    
    It adds memcache clearing into Model methods, both class
    and instance, that alter the datastore.  The model also
    provides a namespace for children in memcache.
    
    Currently, this class does not care about failed attempts
    to alter the datastore, so uncompleted deletes and puts
    will still clear the cache.
    """
    list_includes = []

    def delete(self):
        super(MemcachedModel, self).delete()
        memcache.delete(self.__class__.memcache_key())

    def put(self):
        key = super(MemcachedModel, self).put()
        memcache.delete(self.__class__.memcache_key())
        return key

    def _to_repr(self):
        # Handle properties
        entity = {}
        time1 = time.time()
        self._to_entity(entity)
        time2 = time.time()
        logging.debug("  Time for _to_entity: %f", time2 - time1)
        # Add properties/methods in class variable 'add_to_list'
        for token in self.__class__.list_includes:
            elems = token.split('.')
            time1 = time.time()
            value = getattr(self, elems[0])
            time2 = time.time()
            logging.debug("  Time to get %s: %f", elems[0], time2 - time1)
            for elem in elems[1:]:
                value = getattr(value, elem)
                time3 = time.time()
                logging.debug("  Time to get %s: %f", elem, time3 - time2)
                time2 = time3
            entity[elems[-1]] = value
        time3 = time.time()
        entity_string = repr(entity)
        logging.debug("  Time to repr entity: %f", time.time() - time3)
        return entity_string

    @classmethod
    def get_or_insert(cls, key_name, **kwds):
        obj = super(MemcachedModel, cls).get_or_insert(key_name, **kwds)
        memcache.delete(cls.memcache_key())
        return obj

    @classmethod
    def memcache_key(cls):
        return 'PS_' + cls.__name__ + '_ALL'

    # TODO -- Verify security issues involved with eval of repr.
    #  Since in Bloog, only admin is creating tags, not an issue,
    #  but consider possible security issues with injection
    #  of user data.
    # TODO -- Break this up so we won't trip quota on huge lists.
    @classmethod
    def list(cls, nocache=False):
        """Returns a list of up to 1000 dicts of model values.
           Unless nocache is set to True, memcache will be checked first.
        Returns:
          List of dicts with each dict holding an entities property names
          and values.
        """
        time1 = time.time()
        list_repr = memcache.get(cls.memcache_key())
        time2 = time.time()
        logging.debug("Time for list_repr memcache get: %f", time2 - time1)
        if nocache or list_repr is None:
            logging.debug("%s.list being regenerated", cls.__name__)
            time3 = time.time()
            q = db.Query(cls)
            objs = q.fetch(limit=1000)
            time4 = time.time()
            list_repr = '[' + ','.join([obj._to_repr() for obj in objs]) + ']'
            time5 = time.time()
            memcache.set(cls.memcache_key(), list_repr)
            time6 = time.time()
            logging.debug("Time to fetch: %f", time4 - time3)
            logging.debug("Time for repr: %f", time5 - time4)
            logging.debug("Time for memcache set: %f", time6 - time5)
        time1 = time.time()
        values = eval(list_repr)
        time2 = time.time()
        logging.debug("Time for eval: %f", time2 - time1)
        return values


class Tag(MemcachedModel):
    list_includes = ['counter.count', 'name']

    def delete(self):
        counter = Counter.get_by_key_name('Tag' + self.key().name())
        counter.delete()
        super(Tag, self).delete()

    def get_counter(self):
        # If we were worried about lots of concurrent gets, this
        # should be get_or_insert().  OK for a admin-only blog.
        counter = Counter.get_by_key_name('Tag' + self.key().name())
        if counter is None:
            counter = Counter(key_name='Tag'+self.key().name())
            counter.put()
        return counter

    def set_counter(self, value):
        # TODO -- Not implemented yet
        pass

    def delete_counter(self):
        counter = Counter.get_by_key_name('Tag' + self.key().name())
        if counter:
            counter.delete()

    counter = property(get_counter, set_counter, delete_counter)

    def get_name(self):
        return self.key().name()

    name = property(get_name)
    