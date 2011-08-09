import os

import tornado.template as template


loader = template.Loader(os.path.join(os.path.dirname(__file__), "templates"))

PORT = 8080

