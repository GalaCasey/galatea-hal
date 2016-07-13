import threading
import logging
from time import sleep

logger = logging.getLogger(__name__)


class StoppableThread(threading.Thread):
    def __init__(self, function, *args, delay=0, name='StoppableThread', **kwargs):
        self._stopevent = threading.Event()
        self._function = function
        self._fun_args = args
        self._fun_kwargs = kwargs
        self._delay = delay
        threading.Thread.__init__(self, name=name)

    def run(self):
        while True:
            self._function(*self._fun_args, **self._fun_kwargs)
            for i in range(self._delay):
                if not self._stopevent.is_set():
                    sleep(1)
                else:
                    break
            if self._stopevent.is_set():
                break

    def join(self, timeout=None):
        self._stopevent.set()
        threading.Thread.join(self, timeout)