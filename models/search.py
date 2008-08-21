#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Full text indexing and search, implemented in pure python.

Note: This code is slightly altered from google.appengine.ext.search.
  The original code has timeout/quota problems when running in the
  cloud.  
  
Changes by Bill Katz on original:
  - Brought Query out from SearchableModel and renamed it FullTextQuery 
    due to issues with scoping (?) and online shell app.
  - Added unsearchable_properties class variable that lets you remove
    string-based properties from indexing.
  - Don't index over code inside pre with name 'code'.

Defines a SearchableModel subclass of db.Model that supports full text
indexing and search, based on the datastore's existing indexes.

Don't expect too much. First, there's no ranking, which is a killer drawback.
There's also no exact phrase match, substring match, boolean operators,
stemming, or other common full text search features. Finally, support for stop
words (common words that are not indexed) is currently limited to English.

To be indexed, entities must be created and saved as SearchableModel
instances, e.g.:

  class Article(search.SearchableModel):
    text = db.TextProperty()
    ...

  article = Article(text=...)
  article.save()

To search the full text index, use the SearchableModel.all() method to get an
instance of SearchableModel.Query, which subclasses db.Query. Use its search()
method to provide a search query, in addition to any other filters or sort
orders, e.g.:

  query = article.all().search('a search query').filter(...).order(...)
  for result in query:
    ...

The full text index is stored in a property named __searchable_text_index.


In general, if you just want to provide full text search, you *don't* need to
add any extra indexes to your index.yaml. However, if you want to use search()
in a query *in addition to* an ancestor, filter, or sort order, you'll need to
create an index in index.yaml with the __searchable_text_index property. For
example:

  - kind: Article
    properties:
    - name: __searchable_text_index
    - name: date
      direction: desc
    ...

Note that using SearchableModel will noticeable increase the latency of save()
operations, since it writes an index row for each indexable word. This also
means that the latency of save() will increase roughly with the size of the
properties in a given entity. Caveat hacker!
"""

import logging
import re
import string
import sys

from google.appengine.api import datastore
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.ext import db
from google.appengine.datastore import datastore_pb

class SearchableEntity(datastore.Entity):
  """A subclass of datastore.Entity that supports full text indexing.

  Automatically indexes all string and Text properties, using the datastore's
  built-in per-property indices. To search, use the SearchableQuery class and
  its Search() method.
  """
  # Note that AppEngine servers will cache all imported modules including
  # the interior of a class definition.  So the following _FULL_TEXT_*
  # properties will be executed once and cached.

  _FULL_TEXT_INDEX_PROPERTY = '__searchable_text_index'

  _FULL_TEXT_MIN_LENGTH = 3

  _FULL_TEXT_STOP_WORDS = frozenset([
   'a', 'about', 'according', 'accordingly', 'affected', 'affecting', 'after',
   'again', 'against', 'all', 'almost', 'already', 'also', 'although',
   'always', 'am', 'among', 'an', 'and', 'any', 'anyone', 'apparently', 'are',
   'arise', 'as', 'aside', 'at', 'away', 'be', 'became', 'because', 'become',
   'becomes', 'been', 'before', 'being', 'between', 'both', 'briefly', 'but',
   'by', 'came', 'can', 'cannot', 'certain', 'certainly', 'could', 'did', 'do',
   'does', 'done', 'during', 'each', 'either', 'else', 'etc', 'ever', 'every',
   'following', 'for', 'found', 'from', 'further', 'gave', 'gets', 'give',
   'given', 'giving', 'gone', 'got', 'had', 'hardly', 'has', 'have', 'having',
   'here', 'how', 'however', 'i', 'if', 'in', 'into', 'is', 'it', 'itself',
   'just', 'keep', 'kept', 'knowledge', 'largely', 'like', 'made', 'mainly',
   'make', 'many', 'might', 'more', 'most', 'mostly', 'much', 'must', 'nearly',
   'necessarily', 'neither', 'next', 'no', 'none', 'nor', 'normally', 'not',
   'noted', 'now', 'obtain', 'obtained', 'of', 'often', 'on', 'only', 'or',
   'other', 'our', 'out', 'owing', 'particularly', 'past', 'perhaps', 'please',
   'poorly', 'possible', 'possibly', 'potentially', 'predominantly', 'present',
   'previously', 'primarily', 'probably', 'prompt', 'promptly', 'put',
   'quickly', 'quite', 'rather', 'readily', 'really', 'recently', 'regarding',
   'regardless', 'relatively', 'respectively', 'resulted', 'resulting',
   'results', 'said', 'same', 'seem', 'seen', 'several', 'shall', 'should',
   'show', 'showed', 'shown', 'shows', 'significantly', 'similar', 'similarly',
   'since', 'slightly', 'so', 'some', 'sometime', 'somewhat', 'soon',
   'specifically', 'state', 'states', 'strongly', 'substantially',
   'successfully', 'such', 'sufficiently', 'than', 'that', 'the', 'their',
   'theirs', 'them', 'then', 'there', 'therefore', 'these', 'they', 'this',
   'those', 'though', 'through', 'throughout', 'to', 'too', 'toward', 'under',
   'unless', 'until', 'up', 'upon', 'use', 'used', 'usefully', 'usefulness',
   'using', 'usually', 'various', 'very', 'was', 'we', 'were', 'what', 'when',
   'where', 'whether', 'which', 'while', 'who', 'whose', 'why', 'widely',
   'will', 'with', 'within', 'without', 'would', 'yet', 'you'])

  _PUNCTUATION_REGEX = re.compile('[' + re.escape(string.punctuation) + ']')

  def __init__(self, kind_or_entity, *args, **kwargs):
    """Constructor. May be called as a copy constructor.

    If kind_or_entity is a datastore.Entity, copies it into this Entity.
    datastore.Get() and Query() returns instances of datastore.Entity, so this
    is useful for converting them back to SearchableEntity so that they'll be
    indexed when they're stored back in the datastore.

    Otherwise, passes through the positional and keyword args to the
    datastore.Entity constructor.

    Args:
      kind_or_entity: string or datastore.Entity
    """
    if isinstance(kind_or_entity, datastore.Entity):
      self._Entity__key = kind_or_entity._Entity__key
      self.update(kind_or_entity)
    else:
      super(SearchableEntity, self).__init__(kind_or_entity, *args, **kwargs)

  def _ToPb(self):
    """Rebuilds the full text index, then delegates to the superclass.

    Returns:
      entity_pb.Entity
    """
    if SearchableEntity._FULL_TEXT_INDEX_PROPERTY in self:
      del self[SearchableEntity._FULL_TEXT_INDEX_PROPERTY]

    index = set()
    searchable = lambda (name, value): name not in self.unsearchable_properties
    for (name, values) in filter(searchable, self.items()):
      if not isinstance(values, list):
        values = [values]
      if (isinstance(values[0], basestring) and
          not isinstance(values[0], datastore_types.Blob)):
        for value in values:
          index.update(SearchableEntity._FullTextIndex(value))

    index_list = list(index)
    if index_list:
      self[SearchableEntity._FULL_TEXT_INDEX_PROPERTY] = index_list

    return super(SearchableEntity, self)._ToPb()

  @classmethod
  def _FullTextIndex(cls, text):
    """Returns a set of keywords appropriate for full text indexing.

    See SearchableQuery.Search() for details.

    Args:
      text: string

    Returns:
      set of strings
    """

    if text:
      datastore_types.ValidateString(text, 'text', max_len=sys.maxint)
      # TODO -- Remove embedded code blogs marked by 'pre' tags
      # and name="code"
      text = cls._PUNCTUATION_REGEX.sub(' ', text)
      words = text.lower().split()

      words = set(words)

      words -= cls._FULL_TEXT_STOP_WORDS
      for word in list(words):
        if len(word) < cls._FULL_TEXT_MIN_LENGTH:
          words.remove(word)

    else:
      words = set()

    return words


class SearchableQuery(datastore.Query):
  """A subclass of datastore.Query that supports full text search.

  Only searches over entities that were created and stored using the
  SearchableEntity or SearchableModel classes.
  """

  def Search(self, search_query):
    """Add a search query. This may be combined with filters.

    Note that keywords in the search query will be silently dropped if they
    are stop words or too short, ie if they wouldn't be indexed.

    Args:
     search_query: string

    Returns:
      # this query
      SearchableQuery
    """
    datastore_types.ValidateString(search_query, 'search query')
    self._search_query = search_query
    return self

  def _ToPb(self, limit=None, offset=None):
    """Adds filters for the search query, then delegates to the superclass.

    Raises BadFilterError if a filter on the index property already exists.

    Args:
      # an upper bound on the number of results returned by the query.
      limit: int
      # number of results that match the query to skip.  limit is applied
      # after the offset is fulfilled.
      offset: int

    Returns:
      datastore_pb.Query
    """
    if SearchableEntity._FULL_TEXT_INDEX_PROPERTY in self:
      raise datastore_errors.BadFilterError(
        '%s is a reserved name.' % SearchableEntity._FULL_TEXT_INDEX_PROPERTY)

    pb = super(SearchableQuery, self)._ToPb(limit=limit, offset=offset)

    if hasattr(self, '_search_query'):
      keywords = SearchableEntity._FullTextIndex(self._search_query)
      for keyword in keywords:
        filter = pb.add_filter()
        filter.set_op(datastore_pb.Query_Filter.EQUAL)
        prop = filter.add_property()
        prop.set_name(SearchableEntity._FULL_TEXT_INDEX_PROPERTY)
        prop.mutable_value().set_stringvalue(keyword)

    return pb

class FullTextQuery(db.Query):
  """A subclass of db.Query that supports full text search."""
  _search_query = None

  def search(self, search_query):
    """Adds a full text search to this query.

    Args:
      search_query, a string containing the full text search query.

    Returns:
      self
    """
    self._search_query = search_query
    return self

  def _get_query(self):
    """Wraps db.Query._get_query() and injects SearchableQuery."""
    query = db.Query._get_query(self, _query_class=SearchableQuery)
    if self._search_query:
      query.Search(self._search_query)
    return query

import models

class SearchableModel(models.SerializableModel):
  """A subclass of db.Model that supports full text search and indexing.

  Automatically indexes all string-based properties. To search, use the all()
  method to get a FullTextQuery, then use its search() method.
  
  Looks for a class variable, unsearchable_properties, and if set, removes
  indexing on those properties.  Note that only properties with string
  base types are indexed in any case.
  """
  unsearchable_properties = []

  def _populate_internal_entity(self):
    """Wraps db.Model._populate_internal_entity() and injects
    SearchableEntity."""
    entity = db.Model._populate_internal_entity(self,
                                            _entity_class=SearchableEntity)
    entity.unsearchable_properties = self.__class__.unsearchable_properties
    return entity

  @classmethod
  def from_entity(cls, entity):
    """Wraps db.Model.from_entity() and injects SearchableEntity."""
    if not isinstance(entity, SearchableEntity):
      entity = SearchableEntity(entity)
    return super(SearchableModel, cls).from_entity(entity)

  @classmethod
  def all(cls):
    """Returns a FullTextQuery for this kind."""
    return FullTextQuery(cls)
