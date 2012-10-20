"""Usage: console.py [options] <repo>

Options:
  -c --commit   The commit ID to set the repository to.
  --install     Flag to install the repo's requirements.txt
"""
import loghelper as logging
import os
import subprocess
import time


JOBS_STAGE = "stage"
JOBS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        JOBS_STAGE)


def _run_command(cmd, dir=None):
    logging.debug(">>> " + cmd)
    pipe = subprocess.Popen(cmd, shell=True, cwd=dir, stdout=subprocess.PIPE,
                            executable="/bin/bash")
    data, stderr_data = pipe.communicate()
    return data


def create_job_id():
    return time.strftime("%M.%H.%d.%m.%Y")


def run_in_venv(job_id, command):
    jobdir = os.path.join(JOBS_DIR, job_id)
    envdir = os.path.join(jobdir, "venv")
    return _run_command("source %s/bin/activate && %s" % (envdir, command),
                        dir=jobdir)


def do_work(job_id, work_unit):
    logging.info("Running work unit (%s)" % work_unit)
    return run_in_venv(job_id, "python griz.py %s" % work_unit)
