from base import LogBackend


class NullBackend(LogBackend):
    def emit(self, event):
        return