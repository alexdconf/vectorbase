from django.conf import settings
from django.utils.module_loading import import_string


def get_backend():
    if not getattr(settings, "ENABLE_LOGGING", False):
        from .backends.null import NullBackend
        return NullBackend()
    cls = import_string(settings.LOG_BACKEND)
    return cls(**getattr(settings, "LOG_BACKEND_OPTIONS", {}))