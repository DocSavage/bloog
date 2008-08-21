# The MIT License
# 
# Copyright 2008 William T Katz
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
"""Extends Google's db.Model object generally and for specific app models.

Extensions include:
- Full-text searching with ability to hide properties from indexing
- Counter implemented with sharding to improve write performance
- Memcached aggregation of entities
- Serialization of designated properties to json and repr formats.
"""

import datetime
import random
import logging

from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api import datastore_types

from utils.external import simplejson

def to_dict(model_obj, attr_list, init_dict_func=None):
    """Converts Model properties into various formats.

    Supply a init_dict_func function that populates a
    dictionary with values.  In the case of db.Model, this
    would be something like _to_entity().  You may also
    designate more complex properties in attr_list, like
      "counter.count"
    Each object in the chain will be retrieved.  In the
    example above, the counter object will be retrieved
    from model_obj's properties.  And then counter.count
    will be retrieved.  The value returned will have a
    key set to the last name in the chain, e.g. 'count' 
    in the above example.
    """
    values = {}
    init_dict_func(values)
    for token in attr_list:
        elems = token.split('.')
        value = getattr(model_obj, elems[0])
        for elem in elems[1:]:
            value = getattr(value, elem)
        values[elems[-1]] = value
    return values

# Format for conversion of datetime to JSON
DATE_FORMAT = "%Y-%m-%d" 
TIME_FORMAT = "%H:%M:%S"

def replace_datastore_types(entity):
    """Replaces any datastore types in a dictionary with standard types.
    
    Passed-in entities are assumed to be dictionaries with values that
    can be at most a single list level.  These transformations are made:
      datetime.datetime      -> string
      db.Key                 -> key hash suitable for regenerating key
      users.User             -> dict with 'nickname' and 'email'
    TODO -- GeoPt when needed
    """
    def get_replacement(value):
        if isinstance(value, datetime.datetime):
            return value.strftime("%s %s" % (DATE_FORMAT, TIME_FORMAT))
        elif isinstance(value, datetime.date):
            return value.strftime(DATE_FORMAT)
        elif isinstance(value, datetime.time):
            return value.strftime(TIME_FORMAT)
        elif isinstance(value, datastore_types.Key):
            return str(value)
        elif isinstance(value, users.User):
            return { 'nickname': value.nickname(), 
                     'email': value.email() }
        else:
            return None

    for key, value in entity.iteritems():
        if isinstance(value, list):
            new_list = []
            for item in value:
                new_value = get_replacement(item)
                new_list.append(new_value or item)
            entity[key] = new_list
        else:
            new_value = get_replacement(value)
            if new_value:
                entity[key] = new_value

class SerializableModel(db.Model):
    """Extends Model to have json and possibly other serializations
    
    Use the class variable 'json_does_not_include' to declare properties
    that should *not* be included in json serialization.
    TODO -- Complete round-tripping
    """
    json_does_not_include = []

    def to_json(self, attr_list=[]):
        def to_entity(entity):
            """Convert datastore types in entity to 
               JSON-friendly structures."""
            self._to_entity(entity)
            for skipped_property in self.__class__.json_does_not_include:
                del entity[skipped_property]
            replace_datastore_types(entity)
        values = to_dict(self, attr_list, to_entity)
        return simplejson.dumps(values)

class MemcachedModel(SerializableModel):
    """MemcachedModel adds memcached all() retrieval through list().
    
    It adds memcache clearing into Model methods, both class
    and instance, that alter the datastore.  For valid memcaching,
    you should use Model methods instead of lower-level db calls.
    
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
        return repr(to_dict(self, self.__class__.list_includes, 
                    self._to_entity))

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
        list_repr = memcache.get(cls.memcache_key())
        if nocache or list_repr is None:
            q = db.Query(cls)
            objs = q.fetch(limit=1000)
            list_repr = '[' + ','.join([obj._to_repr() for obj in objs]) + ']'
            memcache.set(cls.memcache_key(), list_repr)
        return eval(list_repr)

class Counter(object):
    """A counter using sharded writes to prevent contentions.

    Should be used for counters that handle a lot of concurrent use.
    Follows pattern described in Google I/O talk:
        http://sites.google.com/site/io/building-scalable-web-applications-with-google-app-engine

    Memcache is used for caching counts, although you can force
    non-cached counts.

    Usage:
        hits = Counter('hits')
        hits.increment()
        hits.get_count()
        hits.get_count(nocache=True)  # Forces non-cached count.
        hits.decrement()
    """
    MAX_SHARDS = 50

    def __init__(self, name, num_shards=5, cache_time=30):
        self.name = name
        self.num_shards = min(num_shards, Counter.MAX_SHARDS)
        self.cache_time = cache_time

    def delete(self):
        q = db.Query(CounterShard).filter('name =', self.name)
        # Need to use MAX_SHARDS since current number of shards
        # may be smaller than previous value.
        shards = q.fetch(limit=Counter.MAX_SHARDS)
        for shard in shards:
            shard.delete()

    def memcache_key(self):
        return 'Counter' + self.name

    def get_count(self, nocache=False):
        total = memcache.get(self.memcache_key())
        if nocache or total is None:
            total = 0
            q = db.Query(CounterShard).filter('name =', self.name)  
            shards = q.fetch(limit=Counter.MAX_SHARDS)
            for shard in shards:
                total += shard.count
            memcache.add(self.memcache_key(), str(total), 
                         self.cache_time)
            return total
        else:
            logging.debug("Using cache on %s = %s", self.name, total)
            return int(total)
    count = property(get_count)

    def increment(self):
        CounterShard.increment(self.name, self.num_shards)
        return memcache.incr(self.memcache_key()) 

    def decrement(self):
        CounterShard.increment(self.name, self.num_shards, 
                               downward=True)
        return memcache.decr(self.memcache_key()) 

class CounterShard(db.Model):
    name = db.StringProperty(required=True)
    count = db.IntegerProperty(default=0)

    @classmethod
    def increment(cls, name, num_shards, downward=False):
        index = random.randint(1, num_shards)
        shard_key_name = 'Shard' + name + str(index)
        def get_or_create_shard():
            shard = CounterShard.get_by_key_name(shard_key_name)
            if shard is None:
                shard = CounterShard(key_name=shard_key_name, 
                                     name=name)
            if downward:
                shard.count -= 1
            else:
                shard.count += 1
            key = shard.put()
        try:
            db.run_in_transaction(get_or_create_shard)
            return True
        except db.TransactionFailedError():
            logging.error("CounterShard (%s, %d) - can't increment", 
                          name, num_shards)
            return False

