import imp
import loghelper
import urllib2


def build_reducer_module(url, job, connection):
    # If the reducer is in the repo, just fetch it.
    if url.startswith("/"):
        print "Fetching reducer..."
        with open(os.path.join(JOBS_DIR, job, url)) as redfile:
            reducer = redfile.read()
    else:
        logging.debug("Downloading reducer")
        reducer = urllib2.urlopen(url).read()

    logging.debug("Instantiating reducer...")
    redmod = imp.new_module("reducer")
    exec reducer in redmod.__dict__

    if "reduce" not in redmod.__dict__:
        logging.error("`reduce` function not found in reducer")
        raise Exception("No function `reduce` found in reducer.")

    redmod.current_job = job
    redmod.connection = connection
    if callable(redmod.__dict__.get("start")):
        logging.debug("Running reducer `start()` method")
        try:
            redmod.start()
        except Exception as exc:
            exc.message += "; Reducer setup failed."

    return redmod
