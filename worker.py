import json
import multiprocessing
import os

import redis

from console import deploy, do_work, tear_down
import settings


CORES = multiprocessing.cpu_count()
NAME = settings.WORKER_NAME

for i in range(CORES - 1):
    if os.fork() == 0:
        NAME += ".%d" % os.getpid()
        break

print "%s was started." % NAME

connection = redis.StrictRedis(host=settings.HOST, port=6379)
connection.sadd("workers", NAME)
pubsub = connection.pubsub()
pubsub.subscribe("work")

def get_job():
    """Return a job id to begin working on."""
    jobs = connection.smembers("jobs")
    if not jobs:
        return

    return list(jobs)[0]

def get_work_unit(job_id):
    """Return a work unit for the supplied job id."""

    unit = connection.lpop("%s::work" % job_id)
    if not unit:
        connection.delete("%s::work" % job_id)
        connection.srem("jobs", job_id)
        return

    activity_unit = {"type": "working",
                     "worker": NAME,
                     "job": job_id}
    connection.publish("activity", json.dumps(activity_unit))
    return unit

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

    # Deploy the job.
    deploy(job_id=current_job, repo=job_description["repo"],
           commit=job_description["commit"],
           install=job_description["install"])

    # Keep grabbing work until there is no more work.
    work = get_work_unit(current_job)
    while work:
        do_work(current_job, work)
        work = get_work_unit(current_job)

    # There's no more work so remove it from the list of active jobs.
    connection.srem("jobs", current_job)

    # Clean up when we're done.
    tear_down(current_job)

