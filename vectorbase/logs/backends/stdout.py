from base import LogBackend

import json, sys


class StdoutBackend(LogBackend):
    def emit(self, event):
        sys.stdout.write(json.dumps(event) + "\n")
        sys.stdout.flush()