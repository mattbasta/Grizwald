"""Usage: console.py [options] <repo>

Options:
  -c --commit   The commit ID to set the repository to.
  --install     Flag to install the repo's requirements.txt
"""
import logging
import os
import shutil
import subprocess
import tempfile
import time

from docopt import docopt


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


def deploy(job_id, repo, commit=None, install=False, python_version=2.7):
    print "Deploying %s for job %s" % (repo, job_id)
    repo_dir = os.path.join(JOBS_DIR, job_id)

    def wait_for_deployment():
        while not os.path.exists(os.path.join(repo_dir, "__unlocked__.py")):
            time.sleep(1)

    # If the repo was already set up, great!
    if os.path.exists(repo_dir):
        wait_for_deployment()
        logging.info("Job already configured")
        return

    # Create the directory to run the job in.
    try:
        os.mkdir(repo_dir)
    except OSError:
        if not os.path.exists(repo_dir):
            logging.error("Permissions error when creating repo directory.")
            return
        wait_for_deployment()
        return

    # Clone the repo into the directory.
    logging.debug("Cloning git repo")
    _run_command("git clone %s %s" % (repo, job_id), JOBS_DIR)
    if commit is not None:
        logging.debug("Resetting to commit")
        _run_command("git reset --hard %s" % commit, repo_dir)

    # Install the prereqs.
    if install:
        envdir = os.path.join(JOBS_STAGE, job_id, "venv")
        os.mkdir(envdir)

        logging.debug("Creating virtualenv")
        _run_command("virtualenv %s -p /usr/bin/python%s" %
                         (envdir, python_version))

        logging.debug("Installing dependencies")
        _run_command("source %s/bin/activate && "
                     "pip install -r %s/requirements.txt" % (envdir, repo_dir))

    logging.info("Completed deployment")


def tear_down(job_id):
    print "Tearing down job %s" % job_id

    job_dir = os.path.join(JOBS_DIR, job_id)
    if not os.path.exists(job_dir):
        return

    try:
        shutil.rmtree(job_dir)
        logging.info("Teardown completed successfully")
    except Exception:
        if os.path.exists(job_dir):
            logging.error("Permissions error during teardown")
        else:
            logging.debug("Teardown already in process, aborting")


def run_in_venv(job_id, command):
    jobdir = os.path.join(JOBS_DIR, job_id)
    envdir = os.path.join(jobdir, "venv")
    return _run_command("source %s/bin/activate && %s" % (envdir, command),
                        dir=jobdir)


def do_work(job_id, work_unit):
    print "Running work unit %s" % work_unit
    return run_in_venv(job_id, "python griz.py %s" % work_unit)


def main(*arguments, **kwargs):
    job_id = create_job_id()
    deploy(job_id, kwargs["<repo>"],
           kwargs["--commit"] or None,
           kwargs["--install"] or False)


if __name__ == "__main__":
    main(**docopt(__doc__))
