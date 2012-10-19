import json
import os

import brukva
import redis
from tornado.escape import url_escape
import tornado.ioloop
import tornado.template
import tornado.web
from tornado.websocket import WebSocketHandler

from console import create_job_id
import settings


SOCKETS = set()

REDIS = redis.StrictRedis(host=settings.HOST, port=6379)

BRUKVA_PS = brukva.Client(host=settings.HOST)
BRUKVA_PS.connect()
BRUKVA_PS.subscribe("activity")
BRUKVA_PS.subscribe("work")

def get_job_size(job_id):
    return REDIS.llen("%s::work" % job_id)

def on_activity(message):
    if isinstance(message, brukva.ResponseError):
        return

    channel = message.channel
    output = {"channel": channel}
    if channel == "work":
        output["job"] = message.body
        output["size"] = get_job_size(message.body)
    elif channel == "activity":
        ser = json.loads(message.body)
        output.update(ser)
        output["size"] = get_job_size(ser["job"])

    for socket in SOCKETS:
        socket.write_message(json.dumps(output))

BRUKVA_PS.listen(on_activity)


class WSHandler(WebSocketHandler):
    def open(self):
        SOCKETS.add(self)
        jobs = REDIS.smembers("jobs")
        for job in jobs:
            self.write_message(json.dumps({
                "channel": "jobs",
                "job": job,
                "size": get_job_size(job)
            }))

    def on_close(self):
        SOCKETS.discard(self)


loader = tornado.template.Loader(
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "templates"))

class WorkHandler(tornado.web.RequestHandler):
    """
    A class to handle requests to add work to the queue.
    """

    def get(self):
        self.write(loader.load("workform.html").generate())

    def post(self):
        try:
            repo = self.get_argument("repo")
            commit = self.get_argument("commit")
            resources = self.get_argument("resources")
            reducer = self.get_argument("reducer")
            python = self.get_argument("pythonversion")
            job_type = self.get_argument("job_type")
            procfile = self.get_argument("procfile")

            if python not in ("2.7", "2.6"):
                raise ValueError("Invalid Python version selected.")

            if any(x is None for x in (repo, commit, resources, )):
                raise ValueError("Values may not be None.")

            if resources not in os.listdir(settings.RESOURCES):
                raise ValueError(
                    "Resource does not exist in `%s`" % settings.RESOURCES)

            # Create the new job.
            job_id = create_job_id()

            if job_type == "taskjob":
                # Push all the input items to the work queue.
                c = 0
                for job in os.listdir(
                        os.path.join(settings.RESOURCES, resources)):
                    c += 1
                    if c > 500:
                        break
                    REDIS.lpush("%s::work" % job_id,
                                os.path.join(settings.RESOURCES, resources,
                                             job))
            elif job_type == "daemonjob":
                for line in procfile.split("\n"):
                    REDIS.lpush("%s::work" % job_id, line)

            description = {
                "type": job_type,
                "repo": repo,
                "commit": commit,
                "install": True,
                "python": python,
            }
            if job_type == "taskjob":
                description["reducer"] = reducer

            REDIS.set(job_id, json.dumps(description))
            REDIS.set("%s::incomplete" % job_id, c)

            # Put the job in the list of jobs.
            REDIS.sadd("jobs", job_id)
            REDIS.publish("work", job_id)

        except ValueError as e:
            self.redirect("/?error=%s" % url_escape(e.message))
        else:
            self.redirect("/")


tsettings = {"static_path":
                 os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "static"),
             "auto_reload": True}
application = tornado.web.Application([
    (r"/socket", WSHandler),
    (r"/", WorkHandler),
], **tsettings)

application.listen(8080)
tornado.ioloop.IOLoop.instance().start()
