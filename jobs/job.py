import json
import logging

import console
import settings


class Job(object):
    """A distributed job instance."""

    def __init__(self, id_, description, connection, worker):
        self.id_ = id_
        self.description = description
        self.connection = connection
        self.worker = worker

        self.lock_id = "%s::%s::lockfile" % (self.id_, settings.WORKER_NAME)
        self.incomplete = True

        self.logger = logging.getLogger("grizwald.job")
        self.log = logging.LoggerAdapter(self.logger, {"worker": self.worker,
                                                       "job": self.id_})

    def deploy(self):
        console.deploy(job_id=self.id_, repo=self.description["repo"],
                       commit=self.description["commit"],
                       install=self.description["install"],
                       python_version=self.description["python"])

        self._action("deploy")

    def cancel(self):
        self.log.debug("Cancelling")
        self.connection.delete("%s::work" % self.id_)
        self.connection.delete("%s::incomplete" % self.id_)

        self._action("cancel")

    def cleanup(self):
        self.log.debug("Cleaning up")
        self.connection.srem("jobs", self.id_)

        self.log.debug("Polling deployment lock (%s)" % self.lock_id)
        lock = int(self.connection.get(self.lock_id) or 0)
        if not lock:
            self.log.debug("Cleanup lock acquired")
            # Delete the environment.
            console.tear_down(self.id_)
            # Delete the lock key.
            self.connection.delete(self.lock_id)

        self._action("cleanup")

    def lock(self):
        return JobLock(self)

    def output(self, data):
        self.log.debug("Setting output")
        self.connection.set("%s::output" % self.id_, data)
        self.connection.expire("%s::output" % self.id_, 1800)

        self._action("output")

    def _action(self, type_, **kwargs):
        action_unit = {"type": type_, "worker": self.worker, "job": self.id_}
        action_unit.update(kwargs)
        self.connection.publish("activity", json.dumps(action_unit))

    def run_job(self):
        raise NotImplementedError("`run_job` is unimplemented for stubbed jobs.")


class JobLock(object):
    """
    Lock the job's installation directory so it doesn't get cleaned up by
    another worker while we're using it.
    """

    def __init__(self, job):
        self.job = job

    def __enter__(self):
        lv = self.job.connection.incr(self.job.lock_id)
        self.job.log.debug("Deployment locked (lvl %d; %s)" % (lv, self.job.lock_id))

    def __exit__(self, type, value, traceback):
        lv = self.job.connection.decr(self.job.lock_id)
        self.job.log.debug("Deployment unlocked (lvl %d; %s)" % (lv, self.job.lock_id))
