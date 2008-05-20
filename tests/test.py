APP_ID = u'test_app'
AUTH_DOMAIN = 'gmail.com'
LOGGED_IN_USER = 't...@example.com'  # set to '' for no logged in user

class MyTest(unittest.TestCase):

 def setUp(self):
   # Ensure we're in UTC.
   os.environ['TZ'] = 'UTC'
   time.tzset()

   # Start with a fresh api proxy.
   apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()

   # Use a fresh stub datastore.
   stub = datastore_file_stub.DatastoreFileStub(APP_ID, '/dev/null', '/dev/null')
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
