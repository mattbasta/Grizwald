import random
import signal
import socket
import subprocess

import console
from job import Job


class TimeoutException(Exception):
    pass


DEFAULT_DURATION = 3600
MY_IP = socket.gethostbyname(socket.gethostname())

class DaemonJob(Job):
    """A job handler that executes a long-running task."""

    def get_task(self):
        unit = self.connection.lpop("%s::work" % self.id_)
        if not unit:
            self.connection.srem("jobs", self.id_)
            self.connection.delete("%s::work" % self.id_)
            return None, None

        type_, command = unit.split(" ", 1)
        self._action("started")
        return type_, command

    def run_job(self):

        self.duration = int(self.description.get("duration", DEFAULT_DURATION))

        # Keep grabbing work until there is no more work.
        process_type, command = self.get_task()
        if not process_type:
            self.log.info("No task available to start")
            return

        self._action("startproc")

        def handler(signum, frame):
            self.log.info("Shutting down process.")
            raise TimeoutException()
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(self.duration)

        self.log.info("Starting process (%s %s)" % (process_type, command))
        try:
            if process_type == "wsgi":
                self.log.info("Installing gunicorn")
                console.run_in_venv(self.id_, "pip install gunicorn")
                self.wsgi(command)
            else:
                self.proc(command)

            self.log.info("Process terminated")
        except TimeoutException:
            self.log.info("Process completed")
            return

        signal.alarm(0)

    def output(self, data):
        self.connection.append("%s::output" % self.id_, "%s\n" % data)
        self.connection.expire("%s::output" % self.id_, self.duration)

        self._action("output")

    def wsgi(self, command):
        port = random.randrange(9000, 9999)
        host = "%s:%d" % ("0.0.0.0", port)
        self.output("wsgi %s @@ %s" % (command, host))
        console.run_in_venv(self.id_,
                            "gunicorn -w 4 -b %s %s" % (host, command))

    def proc(self, command):
        self.output("proc %s @@ %s" % (command, MY_IP))
        console.run_in_venv(self.id_, command)
