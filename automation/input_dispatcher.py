"""Serialize all normal system input through one dedicated worker thread."""

import queue
import threading
from functools import wraps
from typing import Any, Callable, Optional, Tuple


class _InputTask:
    def __init__(self, function: Callable[..., Any], args: Tuple[Any, ...], kwargs: dict):
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.done = threading.Event()
        self.result: Any = None
        self.error: Optional[BaseException] = None


class InputDispatcher:
    """A synchronous facade over a single thread that owns normal OS input."""

    def __init__(self):
        self._tasks = queue.Queue()
        self._closed = False
        self._lock = threading.Lock()
        self._held_lock = threading.Lock()
        self._held_keys = set()
        self._held_buttons = set()
        self._ready = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="DeskPilot-InputDispatcher"
        )
        self._thread.start()
        if not self._ready.wait(5.0):
            raise RuntimeError("The system input dispatcher did not start.")

    def _run(self):
        self._ready.set()
        while True:
            task = self._tasks.get()
            try:
                if task is None:
                    return
                try:
                    task.result = task.function(*task.args, **task.kwargs)
                except BaseException as exc:
                    task.error = exc
                finally:
                    task.done.set()
            finally:
                self._tasks.task_done()

    def dispatch(self, function: Callable[..., Any], *args, **kwargs) -> Any:
        if threading.current_thread() is self._thread:
            return function(*args, **kwargs)

        task = _InputTask(function, args, kwargs)
        with self._lock:
            if self._closed:
                raise RuntimeError("The system input dispatcher is shut down.")
            self._tasks.put(task)

        task.done.wait()
        if task.error is not None:
            raise task.error
        return task.result

    def shutdown(self, timeout: float = 2.0) -> bool:
        with self._lock:
            if self._closed:
                thread = self._thread
            else:
                self._closed = True
                self._tasks.put(None)
                thread = self._thread
        if threading.current_thread() is not thread:
            thread.join(timeout=max(0.0, timeout))
        return not thread.is_alive()

    def track_key_down(self, key: str):
        with self._held_lock:
            self._held_keys.add(key.lower().strip())

    def track_key_up(self, key: str):
        with self._held_lock:
            self._held_keys.discard(key.lower().strip())

    def track_mouse_down(self, button: str):
        with self._held_lock:
            self._held_buttons.add(button.lower().strip())

    def track_mouse_up(self, button: str):
        with self._held_lock:
            self._held_buttons.discard(button.lower().strip())

    def held_inputs(self):
        with self._held_lock:
            return set(self._held_keys), set(self._held_buttons)


input_dispatcher = InputDispatcher()


def serialized_input(function: Callable[..., Any]) -> Callable[..., Any]:
    """Run a controller operation as one indivisible input-dispatcher task."""
    @wraps(function)
    def wrapper(*args, **kwargs):
        return input_dispatcher.dispatch(function, *args, **kwargs)
    return wrapper


def serialized_function(function: Callable[..., Any]) -> Callable[..., Any]:
    """Serialize a standalone operation that performs multiple system inputs."""
    @wraps(function)
    def wrapper(*args, **kwargs):
        return input_dispatcher.dispatch(function, *args, **kwargs)
    return wrapper
