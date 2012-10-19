import random
import signal
import socket
import subprocess

import console
from job import Job


class TimeoutException(Exception):
    pass


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

        duration = int(self.description.get("duration", 3600))

        # Keep grabbing work until there is no more work.
        process_type, command = self.get_task()
        if not process_type:
            return

        self._action("startproc")

        def handler(signum, frame):
            logging.info("Shutting down process.")
            raise TimeoutException()
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(duration)

        try:
            if process_type == "wsgi":
                console.run_in_venv("pip install gunicorn")
                self.wsgi(command)
            else:
                self.proc(command)
        except TimeoutException:
            return

        signal.alarm(0)

    def wsgi(self, command):
        port = random.randrange(9000, 9999)
        console.run_in_venv(self.id_,
                            "gunicorn -w 4 -b %s %s" %
                                ("%s:%d" % (MY_ID, port), command))

    def proc(self, command):
        console.run_in_venv(self.id_, command)
