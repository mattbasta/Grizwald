import logging


WORKER = None

logging.basicConfig(level=logging.DEBUG,
                    datefmt='%m-%d %H:%M',
                    format="%(asctime)-12s %(levelname)-8s %(worker)-20s "
                           "%(job)-16s %(message)s")

class ContextFilter(logging.Filter):

    def filter(self, record):
        if not getattr(record, "worker", None):
            record.worker = WORKER or "<unknown>"
        if not getattr(record, "job", None):
            record.job = "<none>"
        return True

logger = logging.getLogger("log_helper")
logger.addFilter(ContextFilter())

debug = logger.debug
info = logger.info
warning = logger.warning
error = logger.error
critical = logger.critical
exception = logger.exception
