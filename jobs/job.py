import json
import logging
import os
import shutil
import time

import console
import settings
from console import _run_command, JOBS_DIR, run_in_venv


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
        repo = self.description.get("repo")
        commit = self.description.get("commit", None)

        self.log.info("Deploying (%s)" % repo)
        repo_dir = os.path.join(JOBS_DIR, self.id_)

        def wait_for_deployment():
            while not os.path.exists(os.path.join(repo_dir, "__unlocked__.py")):
                time.sleep(1)

        # If the repo was already set up, great!
        if os.path.exists(repo_dir):
            wait_for_deployment()
            self.log.info("Job already configured")
            return

        # Create the directory to run the job in.
        try:
            os.mkdir(repo_dir)
        except OSError:
            if not os.path.exists(repo_dir):
                self.log.error("Permissions error when creating repo directory.")
                return
            wait_for_deployment()
            return

        # Clone the repo into the directory.
        self.log.debug("Cloning git repo")
        _run_command("git clone %s %s" % (repo, self.id_), JOBS_DIR)
        if commit is not None:
            self.log.debug("Resetting to commit: %s" % commit)
            _run_command("git reset --hard %s" % commit, repo_dir)

        # Install the prereqs.
        if self.description.get("install", True):
            envdir = os.path.join(repo_dir, "venv")
            os.mkdir(envdir)

            self.log.debug("Creating virtualenv")
            _run_command("virtualenv %s -p /usr/bin/python%s" %
                             (envdir, self.description.get("python", "2.7")))

            self.log.debug("Installing dependencies")
            run_in_venv(self.id_, "pip install -r requirements.txt")

        self.log.info("Completed deployment")
        _run_command("touch __unlocked__.py", dir=repo_dir)

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
            self._tear_down(self.id_)
            # Delete the lock key.
            self.connection.delete(self.lock_id)

        self._action("cleanup")

    def _tear_down(self):
        self.log.info("Tearing down environment")

        job_dir = os.path.join(JOBS_DIR, self.id_)
        if not os.path.exists(job_dir):
            return

        try:
            shutil.rmtree(job_dir)
            self.log.info("Teardown completed successfully")
        except Exception:
            if os.path.exists(job_dir):
                self.log.error("Permissions error during teardown")
            else:
                self.log.debug("Teardown already in process, aborting")

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
