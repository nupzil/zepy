from threading import Lock

from app.infra.rich_progress import create_progress


class ProgressManager:
    def __init__(self):
        self._lock = Lock()
        self._total = 0
        self._failures = 0
        self._bar = create_progress()
        self._task_id = self._bar.add_task(description="Downloading...", total=None, failures=0)

    def add_total(self, total: int):
        self._total += total
        self._bar.update(self._task_id, total=self._total)

    def update(self, advance: int = 1, failures: bool = False):
        if failures:
            self._failures += 1
        self._bar.update(self._task_id, advance=advance, failures=self._failures)

    def start(self):
        self._bar.start()

    def close(self):
        self._bar.stop()
