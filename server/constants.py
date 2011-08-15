import os

import tornado.template as template


loader = template.Loader(os.path.join(os.path.dirname(__file__), "templates"))

DEBUG = True
PORT = 8080

COUCH_URL = "http://localhost:5984"

