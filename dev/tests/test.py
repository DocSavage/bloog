import unittest
import urllib
from utils import template
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_file_stub
from google.appengine.api import user_service_stub
from google.appengine.api import urlfetch_stub
from google.appengine.api import mail_stub
from google.appengine.api.memcache import memcache_stub
from google.appengine.ext import webapp
import os
import time

APP_ID = u'test_app'
AUTH_DOMAIN = 'gmail.com'
LOGGED_IN_USER = 't...@example.com'  # set to '' for no logged in user
HOST = 'localhost:8080'

os.environ['SERVER_SOFTWARE'] = 'TestServer/1.0'
os.environ['APPLICATION_ID'] = 'test_app'
os.environ['TZ'] = 'UTC'
os.environ['USER_IS_ADMIN'] = '1'
time.tzset()

from handlers.bloog import blog
import models.blog

class BloogTest(unittest.TestCase):

    def setUp(self):
        # Start with a fresh api proxy.
        apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()

        # Use a fresh stub datastore.
        stub = datastore_file_stub.DatastoreFileStub(APP_ID, '/dev/null',
                                                     '/dev/null')
        apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', stub)

        # Use a fresh stub UserService.
        apiproxy_stub_map.apiproxy.RegisterStub(
         'user', user_service_stub.UserServiceStub())
        os.environ['AUTH_DOMAIN'] = AUTH_DOMAIN
        os.environ['USER_EMAIL'] = LOGGED_IN_USER

        # Use a fresh urlfetch stub.
        apiproxy_stub_map.apiproxy.RegisterStub(
         'urlfetch', urlfetch_stub.URLFetchServiceStub())

        # Use a fresh mail stub.
        apiproxy_stub_map.apiproxy.RegisterStub(
         'mail', mail_stub.MailServiceStub())

        # Use a fresh memcache stub
        apiproxy_stub_map.apiproxy.RegisterStub(
         'memcache', memcache_stub.MemcacheServiceStub())

        # Create a fake remplate renderer
        self.render_calls = []
        def template_render(filename, params, debug, template_dirs):
            self.render_calls.append(params)
        template.render = template_render
    
    def createHandler(self, cls, uri, env=None, auth=False):
        handler = cls()
        environ = {
            'wsgi.url_scheme': 'http',
            'HTTP_HOST': HOST,
            'SCRIPT_NAME': uri,
        }
        if auth:
            environ['HTTP_COOKIE'] = 'dev_appserver_login="root@example.com:True"'
        if env:
            environ.update(env)
        request = webapp.Request(environ)
        response = webapp.Response()
        handler.initialize(request, response)
        return handler, request, response

    def testRoot(self):
        root, request, response = self.createHandler(blog.RootHandler, '/')
        root.get()
        self.failUnlessEqual(len(self.render_calls), 1)
        self.failUnlessEqual(self.render_calls[0]['articles'], [])

    def testArticleSubmission(self):
        root, request, response = self.createHandler(blog.RootHandler, '/', {
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'REQUEST_METHOD': 'POST',
        })
        postdata = {
            'title': 'Test post',
            'body': 'Post body',
            'format': 'html',
            'published': '',
            'updated': '',
            'tags': 'foo,bar',
        }
        request.body = urllib.urlencode(postdata)
        root.post()
        self.failUnlessEqual(response.out.getvalue(), '/Test-post')
        
        article = models.blog.Article.all().get()
        self.failUnlessEqual(article.permalink, 'Test-post')
        self.failUnlessEqual(article.title, postdata['title'])
        self.failUnlessEqual(article.body, postdata['body'])
        self.failUnlessEqual(article.tags, postdata['tags'].split(','))
        self.failUnlessEqual(article.article_type, 'article')
        
        articles, request, response = self.createHandler(blog.ArticlesHandler,
                                                         '/articles')
        articles.get()
        self.failUnlessEqual(len(self.render_calls), 1)
        self.failUnlessEqual(self.render_calls[0]['articles'][0].key(),
                             article.key())
        
        handler, request, response = self.createHandler(blog.ArticleHandler,
                                                        '/Test-post')
        handler.get('Test-post')
        self.failUnlessEqual(len(self.render_calls), 2)
        self.failUnlessEqual(self.render_calls[1]['article'].key(),
                             article.key())

    def testPostSubmission(self):
        url = '2008/1'
        root, request, response = self.createHandler(blog.MonthHandler, url, {
            'CONTENT_TYPE': 'application/x-www-form-urlencoded',
            'REQUEST_METHOD': 'POST',
        })
        postdata = {
            'title': 'Test blog post',
            'body': 'Another post body',
            'format': 'html',
            'published': '2008-01-01 12:00:00',
            'updated': '',
            'tags': 'foo,baz,bleh',
        }
        request.body = urllib.urlencode(postdata)
        root.post('2008', '01')
        self.failUnlessEqual(response.out.getvalue(), '/2008/1/Test-blog-post')

        article = models.blog.Article.all().get()
        self.failUnlessEqual(article.permalink, '2008/1/Test-blog-post')
        self.failUnlessEqual(article.title, postdata['title'])
        self.failUnlessEqual(article.body, postdata['body'])
        self.failUnlessEqual(article.tags, postdata['tags'].split(','))
        self.failUnlessEqual(article.article_type, 'blog entry')

        root, request, response = self.createHandler(blog.RootHandler, '/')
        root.get()
        self.failUnlessEqual(len(self.render_calls), 1)
        self.failUnlessEqual(self.render_calls[0]['articles'][0].key(),
                             article.key())

        handler, request, response = self.createHandler(blog.BlogEntryHandler,
                                                        '/2008/1/Test-blog-post')
        handler.get('2008', '1', 'Test-blog-post')
        self.failUnlessEqual(len(self.render_calls), 2)
        self.failUnlessEqual(self.render_calls[1]['article'].key(),
                             article.key())


if __name__ == '__main__':
    unittest.main()
