from django.conf import settings
from .conf import get_backend

_backend = None

def _get():
    global _backend
    if _backend is None:
        _backend = get_backend()
    return _backend

def record_event(level, message, **fields):
    if not getattr(settings, "ENABLE_LOGGING", False):
        return
    event = {"level": level, "message": message, **fields}
    _get().emit(event)