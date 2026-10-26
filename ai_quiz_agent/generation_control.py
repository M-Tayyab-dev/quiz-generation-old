"""Bound generation time and prevent repeated requests from piling up."""
import contextvars
import functools
import os
import threading
import time

_deadline = contextvars.ContextVar('quiz_deadline', default=None)
_lock = threading.Lock()


def remaining_seconds():
    deadline = _deadline.get()
    remaining = deadline - time.monotonic() if deadline is not None else 120.0
    if remaining <= 0:
        raise TimeoutError('AI generation reached the two-minute limit. Use a GPU backend for larger quizzes.')
    return remaining


def bounded_generation(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        if not _lock.acquire(blocking=False):
            raise ValueError('A quiz is already generating. Wait for it to finish before trying again.')
        token = _deadline.set(time.monotonic() + min(120, max(10, float(os.getenv('QUIZ_GENERATION_SECONDS', '120')))))
        try:
            return function(*args, **kwargs)
        finally:
            _deadline.reset(token)
            _lock.release()
    return wrapped
