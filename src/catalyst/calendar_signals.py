"""DEPRECATED — functionality removed per system audit 2026-05-29.

Module retained as a stub so existing imports do not break.
Any attribute access returns a no-op lambda. Safe to physically
delete once CI confirms zero runtime errors.
"""


def __getattr__(name):
    return lambda *args, **kwargs: None

