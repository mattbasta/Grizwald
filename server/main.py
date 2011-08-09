#!/usr/bin/env python

import tornado.ioloop
import tornado.web as web

import constants

patterns = []

import api.main as api
api.register(patterns)


class RootHandler(web.RequestHandler):
    """Give a general summary of the application."""

    def get(self):
        self.write(constants.loader.load("home.html").generate())


if __name__ == "__main__":
    print "Starting server..."
    patterns.extend([(r"/", RootHandler)])
    application = tornado.web.Application(patterns)

    application.listen(constants.PORT)
    print "Listening"
    tornado.ioloop.IOLoop.instance().start()

