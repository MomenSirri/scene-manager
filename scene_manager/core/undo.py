"""One undo step that does not hide errors.

In 3ds Max 2026, pymxs.undo(True, label) swallows any exception raised inside the `with` block (the
caller carries on as if it worked, and a function returning inside it returns None). undo_step keeps
the undo record and re-raises the error after the block closes.
"""
from contextlib import contextmanager

import pymxs


@contextmanager
def undo_step(label, on=True):
    errors = []
    with pymxs.undo(on, label):
        try:
            yield
        except BaseException as e:  # re-raised below, outside pymxs.undo
            errors.append(e)
    if errors:
        raise errors[0]
