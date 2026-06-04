class LogBackend:
    def emit(self, event: dict) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass