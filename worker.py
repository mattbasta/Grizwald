import json
import logging
import multiprocessing
import os

import redis

from jobs import DaemonJob, TaskJob
import settings


logging.basicConfig(level=logging.DEBUG)

CORES = multiprocessing.cpu_count()
NAME = settings.WORKER_NAME

for i in range(CORES - 1):
    if os.fork() == 0:
        NAME += ".%d" % os.getpid()
        break

print "%s was started." % NAME

connection = redis.StrictRedis(host=settings.HOST, port=6379)
pubsub = connection.pubsub()
pubsub.subscribe("work")


def get_job():
    """Return a job id to begin working on."""
    jobs = connection.smembers("jobs")
    if not jobs:
        return

    return list(jobs)[0]


job_types = {"taskjob": TaskJob, "daemonjob": DaemonJob}

# The main work loop.
while 1:
    current_job = get_job()
    # If there's no work in the queue, wait for work.
    if not current_job:
        pubsub = connection.pubsub()
        pubsub.subscribe("work")
        current_job = pubsub.listen().next()

    # Double check that we're working on an active job and that it hasn't
    # already been completed.
    if not connection.sismember("jobs", current_job):
        continue

    # Load the job description.
    job_description = connection.get(current_job)
    job_description = json.loads(job_description)

    job_type = job_description.get("type", "unknown")
    job_inst = job_types.get(job_type)
    if not job_inst:
        raise Exception("Unknown Job Type: worker out of date.")

    # Instantiate the job.
    job_inst = job_inst(current_job, job_description, connection, NAME)

    # Prevent the job from being cleaned up while we're using it.
    with job_inst.lock():
        job_inst.deploy()
        try:
            job_inst.run_job()
        except Exception as exc:
            logging.error("Job finished prematurely due to error. (%s)" %
                              exc.message)

    job_inst.cleanup()
