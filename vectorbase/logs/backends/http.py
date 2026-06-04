from base import LogBackend

import requests


class HTTPBackend(LogBackend):
    def __init__(self, endpoint, headers=None, timeout=2.0):
        self.endpoint = endpoint
        self.headers = headers or {}
        self.timeout = timeout

    def emit(self, event):
        try:
            requests.post(self.endpoint, json=event,
                          headers=self.headers, timeout=self.timeout)
        except requests.RequestException:
            pass  # never let logging break the app