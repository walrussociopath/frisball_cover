import logging
from contextlib import contextmanager
from time import perf_counter
from typing import Generator


@contextmanager
def perf_time(start_log_msg: str) -> Generator[None]:
    logging.info(start_log_msg)
    start_t = perf_counter()
    yield
    logging.info(f'Elapsed time: %ss', perf_counter() - start_t)
