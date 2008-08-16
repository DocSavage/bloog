# The MIT License
# 
# Copyright (c) 2008 William T. Katz
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

import random
import logging
import time

from google.appengine.api import memcache
from google.appengine.ext import db

class Counter(db.Model):
    """A counter that uses sharded writes to improve transaction throughput.

    Counters *should* be initialized with a key_name.  This key_name is
    used as the name for the counter.  If you will only have one Counter,
    you can omit the key_name and a Counter with key_name 'global' will
    be created, but any attempt to initialize another key_name-less
    Counter will result in an error.

    Should be used for counters that handle a lot of concurrent use.
    Follows pattern described in Google I/O talk:

http://sites.google.com/site/io/building-scalable-web-applications-with-google-app-engine
    
    Memcache is used for caching counts, although you can force
    non-cached counts.
    
    Usage:
        hits = Counter(key_name='hits')
        hits.put()                    # Need to put() before using Counter
        hits.increment()
        hits.get_count()
        hits.get_count(nocache=True)  # Forces non-cached count.
        hits.decrement()
    """
    MAX_SHARDS = 50
    cache_time = db.IntegerProperty(default=30)
    num_shards = db.IntegerProperty(default=5)

    def __init__(self, parent=None, key_name='global', _app=None, **kwargs):
        super(Counter, self).__init__(parent, key_name, _app, **kwargs)
        memcache.set(self.memcache_key(key_name=key_name), "0")

    def delete(self):
        q = db.Query(CounterShard).filter('name =', self.key().name())  
        shards = q.fetch(limit=Counter.MAX_SHARDS)
        for shard in shards:
            shard.delete()
        super(Counter, self).delete()

    def memcache_key(self, key_name=None):
        if not key_name:
            key_name = self.key().name()
        return 'Counter' + key_name

    def get_count(self, nocache=False):
        total = memcache.get(self.memcache_key())
        if nocache or total is None:
            total = 0
            logging.debug("Getting count for %s", self.key().name())
            time1 = time.time()
            q = db.Query(CounterShard).filter('name =', self.key().name())  
            shards = q.fetch(limit=1000)
            for shard in shards:
                total += shard.count
                time2 = time.time()
                logging.debug("    Time to access shard %s (cumm count %d): %f", 
                              shard.key().name(), total, time2 - time1)
                time1 = time2
            memcache.add(self.memcache_key(), str(total), self.cache_time)
            return total
        else:
            logging.debug("Using cache on %s = %s", self.key().name(), total)
            return int(total)
    count = property(get_count)

    def increment(self, downward=False):
        incremented = False
        while not incremented and self.num_shards <= Counter.MAX_SHARDS:
            key = self.key()
            incremented = CounterShard.increment(key, self.num_shards, 
                                                 downward)
            if not incremented:
                self.num_shards += 5
                self.put()      # OK if multiple processes do overriding puts.
        if not incremented:
            logging.error('Counter (%s, %d) - Unable to increment', 
                          self.key().name(), self.num_shards)
        if downward:
            return memcache.decr(self.memcache_key()) 
        else:
            return memcache.incr(self.memcache_key()) 

    def decrement(self):
        return self.increment(downward=True)

class CounterShard(db.Model):
    name = db.StringProperty(required=True)
    count = db.IntegerProperty(default=0)

    @classmethod
    def increment(cls, counter_key, num_shards, downward=False):
        index = random.randint(1, num_shards)
        counter_name = counter_key.name()
        shard_key_name = 'Shard' + counter_name + str(index)
        logging.debug("increment %s for key = %s", counter_name, shard_key_name)
        def txn():
            shard = CounterShard.get_by_key_name(shard_key_name)
            if shard is None:
                shard = CounterShard(key_name=shard_key_name, 
                                     name=counter_name)
                logging.debug("Creating CounterShard: key_name=%s", 
                              shard_key_name)
            else:
                logging.debug("CounterShard obtained!  Name = %s", 
                              shard.key().name())
            if downward:
                shard.count -= 1
            else:
                shard.count += 1
            key = shard.put()
            logging.debug("CounterShard put with key_name = %s", key.name())
        try:
            time1 = time.time()
            db.run_in_transaction(txn)
            time2 = time.time()
            logging.debug("Shard %s took %f s", shard_key_name, time2 - time1)
            return True
        except db.TransactionFailedError():
            return False
