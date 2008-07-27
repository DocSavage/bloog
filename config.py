# Don't change default_blog or default_page to prevent conflicts when merging #  Bloog source code updates.
# Do change blog or page dictionaries at the bottom of this config module.

default_blog = {
    "html_type": "text/html",
    "charset": "iso-8859-1",
    "title": "Bloog",
    "author": "Bill Katz",
    # This must be the email address of a registered administrator for the 
    # application due to mail api restrictions.
    "email": "you@foo.com",
    "description": "A RESTful Blog/Homepage for Google AppEngine.",
    "root_url": "http://bloog.billkatz.com",
    "master_atom_url": "/feeds/atom.xml",
    # You can override this default for each page through a handler's call to 
    #  view.ViewPage(cache_time=...)
    "cache_time": 0,
    # If you want to use legacy ID mapping for your former blog platform,
    # define it here and insert the necessary mapping code in the
    # legacy_id_mapping() function in ArticleHandler (blog.py).
    # Currently only "Drupal" is supported.
    "legacy_blog_software": None
    #"legacy_blog_software": "Drupal"
}

default_page = {
    "title": default_blog["title"],
    "navlinks": [
        { "title": "Link", "description": "Short description", "url": "#"},
        { "title": "Link", "description": "Short description", "url": "#"},
        { "title": "Contact", "description": "Send me a note", 
          "url": "/contact"},
    ],
    # Currently tags are hardwired to prevent datastore access.  
    # Might shift to lookup + cache.
    "tags": [
        'AppEngine', 'Bloog', 'Google', 'GData API', 'Another Unused Tag'
    ],
    "featuredMyPages": {
        "title": "Bloog Development",
        "description": "Get involved",
        "entries": [
            { "title": "Announcement", 
              "url": "http://billkatz-test.appspot.com", 
              "description": "Author's Bloog" },
            { "title": "Source Code", 
              "url": "http://github.com/DocSavage/bloog", 
              "description": "GitHub repository" },
            { "title": "Tarball", 
              "url": "http://github.com/DocSavage/bloog/tarball/master", 
              "description": "Most recent snapshot" },
            { "title": "Group", 
              "url": "http://groups.google.com/group/bloog/topics", 
              "description": "Developer discussion" },
            { "title": "Architecture Diagram", 
              "url": "/static/images/architecture2.png", 
              "description": 
                "How Bloog interacts with clients through REST HTTP" }
        ]
    },
    "featuredOthersPages": {
        "title": "Google App Engine",
        "description": "Developer Resources",
        "entries": [
            { "title": "Google App Engine", 
              "url": "http://code.google.com/appengine/", 
              "description": "The mothership" },
            { "title": "AppEngine Group", 
              "url": "http://groups.google.com/group/google-appengine", 
              "description": "Google Group for App Engine developers" },
            { "title": "GAE SWF Project", 
              "url": "http://gaeswf.appspot.com/", 
              "description": "Flash and Flex on Google AppEngine" },
            { "title": "Dev Console", 
              "url": "http://localhost:8080/_ah/admin/datastore", 
              "description": 
                "Your datastore viewer and console if running locally" }
        ]
    },
}

# Customize the following two dictionaries to tailor this Bloog to your taste.
# The view will preferentially use 'blog' and 'page' dictionaries.

blog = default_blog
page = default_page

# Set to true if we want to have our webapp print stack traces, etc
DEBUG = True
