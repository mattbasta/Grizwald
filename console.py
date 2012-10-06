"""Usage: console.py [options] <repo>

Options:
  -c --commit   The commit ID to set the repository to.
  --install     Flag to install the repo's requirements.txt
"""
import os
import shutil
import subprocess
import tempfile
import time

from docopt import docopt


JOBS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs")


def _run_command(cmd, dir=None):
    print cmd
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
        print "Already set up!"
        return

    # Create the directory to run the job in.
    try:
        os.mkdir(repo_dir)
    except OSError:
        if not os.path.exists(repo_dir):
            print "Permissions errors while creating repo directory."
            return
        wait_for_deployment()
        return

    # Clone the repo into the directory.
    print "Cloning git repo..."
    _run_command("git clone %s %s" % (repo, job_id), JOBS_DIR)
    if commit is not None:
        print "Resetting to commit..."
        _run_command("git reset --hard %s" % commit, repo_dir)

    # Install the prereqs.
    if install:
        envdir = os.path.join("jobs", job_id, "venv")
        os.mkdir(envdir)
        print "Creating virtual environment..."
        _run_command("virtualenv %s -p /usr/bin/python%s" %
                         (envdir, python_version))
        print "Installing dependencies..."
        _run_command("source %s/bin/activate && "
                     "pip install -r %s/requirements.txt" % (envdir, repo_dir))

    _run_command("touch __unlocked__.py", dir=repo_dir)
    print "Deployment complete."


def tear_down(job_id):
    print "Tearing down job %s" % job_id

    job_dir = os.path.join(JOBS_DIR, job_id)
    if not os.path.exists(job_dir):
        return

    lockfile = os.path.join(job_dir, "__unlocked__.py")
    if not os.path.exists(lockfile):
        return

    try:
        os.unlink(lockfile)
    except OSError:
        print "Waiting for teardown"
    else:
        try:
            shutil.rmtree(job_dir)
        except Exception:
            if os.path.exists(job_dir):
                print "Permissions error while tearing down job."
            else:
                print "Already being torn down."


def do_work(job_id, work_unit):
    print "Running work unit %s" % work_unit
    jobdir = os.path.join(JOBS_DIR, job_id)
    envdir = os.path.join(jobdir, "venv")
    return _run_command("source %s/bin/activate && "
                        "python griz.py %s" % (envdir, work_unit),
                        dir=jobdir)


def main(*arguments, **kwargs):
    job_id = create_job_id()
    deploy(job_id, kwargs["<repo>"],
           kwargs["--commit"] or None,
           kwargs["--install"] or False)


if __name__ == "__main__":
    main(**docopt(__doc__))

