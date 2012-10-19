import logging

import console
import reducer
from job import Job


class TaskJob(Job):
    """A job handler that executes as series of tasks on a project instance."""

    def get_task(self):
        unit = self.connection.lpop("%s::work" % self.id_)
        if not unit:
            self.connection.delete("%s::work" % self.id_)
            return

        self._action("working")
        return unit

    def get_reducer(self):

        def red_gen(mod):
            reduction = None
            data = (yield None)
            while data is not None:
                reduction = mod.reduce(data, reduction)
                data = (yield reduction)
            yield reduction

        rm = reducer.build_reducer_module(self.description["reducer"],
                                          job=self.id_,
                                          connection=connection)
        if not rm:
            raise Exception("Could not build reducer module.")
        gen = red_gen(rm)
        gen.next()
        return gen

    def deploy(self):
        self.connection.incr("%s::workers" % self.id_)
        super(TaskJob, self).deploy()

    def cancel(self):
        super(TaskJob, self).cancel()
        self.connection.delete("%s::results" % self.id_)

    def run_job(self):
        # Get the reducer set up and ready.
        try:
            red = self.get_reducer()
        except Exception as exc:
            self.cancel()
            self.output("Error: Could not set up reducer. (%s)" % exc.message)
            return

        # Keep grabbing work until there is no more work.
        work = self.get_task()
        remaining_key = "%s::incomplete" % self.id_
        remaining = int(self.connection.decr(remaining_key) or 0)
        self.incomplete = bool(remaining)

        while work and remaining:
            # Perform the action on the current job item.
            output = console.do_work(self.id_, work)

            try:
                # Pass the output of the action to the reducer.
                red.send(output)
            except Exception:
                self.cancel()
                logging.error("Reducer raised exception.")
                self.output("Error: Reduction exception. (%s)" % exc.message)
                raise

            if remaining > 1:
                # Decrease the number of incomplete tasks by 1.
                remaining = int(self.connection.decr(remaining_key) or 0)
                self.incomplete = bool(remaining)
                if not remaining:
                    break

            # Get another job item from the queue.
            work = self.get_task()

        # Perform the final reduction.
        try:
            result = red.send(None)
        except Exception:
            self.cancel()
            logging.error("Reducer raised exception on final pass.")
            self.output("Error: Reduction exception. (%s)" % exc.message)
            raise
        else:
            self.connection.sadd("%s::results" % self.id_, result)

        logging.info("Worker completed job.")

        workers_left = self.connection.decr("%s::workers" % self.id_)
        if not workers_left:
            # This means that we're in charge of combining the reduced results.
            results = self.connection.smembers("%s::results" % self.id_)

            # Get the final reducer set up and ready.
            try:
                red = self.get_reducer()
            except Exception as exc:
                self.cancel()
                self.output("Error: Could not set up final reducer. (%s)" %
                            exc.message)
                return

            for result in results:
                red.send(result)

            try:
                result = red.send(None)
            except Exception:
                self.cancel()
                logging.error("Reducer raised exception on final reduction.")
                self.output("Error: Reduction exception. (%s)" % exc.message)
                raise
            else:
                self.output(result)

            logging.info("Job reduction completed.")
