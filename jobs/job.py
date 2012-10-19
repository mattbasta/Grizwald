import fcntl
import json
import os

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

    def cancel(self):
        self.connection.delete("%s::work" % self.id_)
        self.connection.delete("%s::incomplete" % self.id_)

    def cleanup(self):
        self.connection.srem("jobs", self.id_)
        console.tear_down(self.id_)
        self._action("cleanup")

    def lock(self):
        return JobLock(self)

    def _action(self, type_, **kwargs):
        action_unit = {"type": type_, "worker": self.worker, "job": self.id_}
        action_unit.update(kwargs)
        self.connection.publish("activity", json.dumps(action_unit))

    def output(self, data):
        self.connection.set("%s::output" % self.id_, data)
        self.connection.expire("%s::output" % current_job, 1800)

    def run_job(self):
        raise NotImplementedError("`run_job` is unimplemented for stubbed jobs.")


class JobLock(object):
    """
    Lock the job's installation directory so it doesn't get cleaned up by
    another worker while we're using it.
    """

    def __init__(self, job):
        self.job = job
        self.lockfile = None

    def __enter__(self):
        self.lock_file = open(os.path.join(console.JOBS_DIR, self.job.id_,
                                           "__unlocked__.py"))
        fcntl.lockf(self.lock_file, fcntl.LOCK_SH)

    def __exit__(self, type, value, traceback):
        fcntl.lockf(self.lock_file, fcntl.LOCK_UN)
        self.lock_file.close()
