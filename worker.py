import fcntl
import imp
import json
import multiprocessing
import os
import urllib2

import redis

from console import deploy, do_work, JOBS_DIR, tear_down
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
           install=job_description["install"],
           python_version=job_description["python"])

    # Lock the deployment so it doesn't get torn down while we're working.
    lock_file = open(os.path.join(JOBS_DIR, current_job, "__unlocked__.py"))
    fcntl.lockf(lock_file, fcntl.LOCK_SH)

    def build_reducer_module(url):
        print "Downloading reducer..."
        reducer = urllib2.urlopen(job_description["reducer"]).read()
        redmod = imp.new_module("reducer")
        print "Instantiating reducer..."
        exec reducer in redmod.__dict__

        if "reduce" not in redmod.__dict__:
            raise Exception("No function `reduce` found in reducer.")

        redmod.current_job = current_job
        redmod.connection = connection
        if "start" in redmod.__dict__:

            redmod.start()

        return redmod

    def reducer(mod):
        reduction = None
        data = (yield None)
        while data is not None:
            reduction = mod.reduce(data, reduction)
            data = (yield reduction)
        yield reduction

    try:
        red_mod = build_reducer_module(job_description["reducer"])
    except Exception as exc:

        # TODO: Wrap things better so this stuff isn't duped.
        print "Reducer setup failed."
        # If there's a problem setting up the reducer, kill the job
        # immediately.
        connection.delete("%s::work" % current_job)
        connection.delete("%s::incomplete" % current_job)
        connection.srem("jobs", current_job)
        connection.set("%s::output" % current_job,
                       "Error: Could not set up reducer. (%s)" % exc)
        connection.expire("%s::output" % current_job, 1800)

        # Release the lock for teardown.
        fcntl.lockf(lock_file, fcntl.LOCK_UN)
        lock_file.close()

        # Clean up when we're done.
        tear_down(current_job)
        continue

    red_inst = reducer(red_mod)
    red_inst.next()

    # Keep grabbing work until there is no more work.
    work = get_work_unit(current_job)
    remaining = int(connection.decr("%s::incomplete" % current_job) or 0)
    while work and remaining:
        # Perform the action on the current job item.
        output = do_work(current_job, work)
        # Pass the output of the action to the reducer.
        red_inst.send(output)

        if remaining > 1:
            # Decrease the number of incomplete tasks by 1.
            remaining = int(connection.decr("%s::incomplete" %
                                                current_job) or 0)
            if not remaining:
                break

        # Get another job item from the queue.
        work = get_work_unit(current_job)

    # Push the reduced result to the results set.
    result = red_inst.send(None)
    connection.sadd("%s::results" % current_job, result)

    # If we're the last ones running, do the reduction of the final data.
    if remaining:
        # Clean up the incomplete counter.
        connection.delete("%s::incomplete" % current_job)

        # Get the reduced results and push them into the reducer.
        results = connection.smembers("%s::results" % current_job)
        red_inst = reducer(red_mod)
        red_inst.next()
        for result in results:
            red_inst.send(result)

        # Set the final job output and have it expire in a half hour.
        connection.set("%s::output" % current_job, red_inst.send(None))
        connection.expire("%s::output" % current_job, 1800)

        # Delete the un-sub-reduced results.
        connection.delete("%s::results" % current_job)

    # There's no more work so remove it from the list of active jobs.
    connection.srem("jobs", current_job)

    # Release the lock for teardown.
    fcntl.lockf(lock_file, fcntl.LOCK_UN)
    lock_file.close()

    # Clean up when we're done.
    tear_down(current_job)
