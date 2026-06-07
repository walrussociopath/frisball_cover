import logging
import threading
from functools import wraps
from contextlib import contextmanager
from time import perf_counter


def in_thread(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return thread
    return wrapper


@contextmanager
def elapse_time(start_log_msg: str):
    logging.info(start_log_msg)
    start_t = perf_counter()
    yield
    logging.info(f'Elapsed time: %ss', perf_counter() - start_t)

