import json

import console


class Job(object):
    """A distributed job instance."""

    def __init__(self, id_, description, connection, worker):
        self.id_ = id_
        self.description = description
        self.connection = connection
        self.worker = worker

        self.incomplete = True

    def deploy(self):
        console.deploy(job_id=self.id_, repo=self.description["repo"],
                       commit=self.description["commit"],
                       install=self.description["install"],
                       python_version=self.description["python"])

        self._action("deploy")

    def cancel(self):
        self.connection.delete("%s::work" % self.id_)
        self.connection.delete("%s::incomplete" % self.id_)

        self._action("cancel")

    def cleanup(self):
        self.connection.srem("jobs", self.id_)

        lock_id = "%s::%s::lockfile" % (self.id_, self.worker)
        lock = int(self.connection.get(lock_id) or 0)
        if not lock:
            # Delete the environment.
            console.tear_down(self.id_)
            # Delete the lock key.
            self.connection.delete(lock_id)

        self._action("cleanup")

    def lock(self):
        return JobLock(self)

    def output(self, data):
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
        self.lock = "%s::%s::lockfile" % (self.job.id_, self.job.worker)

    def __enter__(self):
        self.job.connection.incr(self.lock)

    def __exit__(self, type, value, traceback):
        self.job.connection.decr(self.lock)
