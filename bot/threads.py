import threading
import logging
import flask
from queue import Queue, Empty
from time import sleep
import concurrent.futures
from concurrent.futures import TimeoutError

logger = logging.getLogger(__name__)

app = flask.Flask(__name__)


class StoppableThread(threading.Thread):
    """
    A Stoppable thread is a thread which takes a function and a delay, and repeats the function every
    delay seconds until it is told to join, at which point it stops.
    """
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


class FlaskThread(threading.Thread):
    """
    FlaskThread is a used to host the flask app as a REST endpoint. There should only be one
    such thread.
    """
    def __init__(self, state_updating_q, name='FlaskThread'):
        self.state_updating_q = state_updating_q
        threading.Thread.__init__(self, name=name)

    def run(self):
        @app.route("/")
        def _handle_flask_redirect():

            if 'code' not in flask.request.args:
                # This shouldn't happen
                raise KeyError
            else:
                auth_code = flask.request.args.get('code')
                encrypted_state = flask.request.args.get('state')
                self.state_updating_q.put({'type': 'flask_response',
                                           'auth_code': auth_code,
                                           'encrypted_state': encrypted_state})

            return "<H1>Authentication Successful</H1>"
            # Useful to keep flask from breaking, despite no need for a response to google

        # This line must be the last line, or functions will not be defined before the server starts, resulting in 404s
        app.run(port=5555, host="0.0.0.0")


class ValidationThread(threading.Thread):
    """
    A validation thread is used by a worker pool thread to validate that all async requests are completed without
    timing out, as a timeout would indicate that the thread crashed.
    """
    def __init__(self, validation_q, q, name='ValidationThread'):
        self.q = q
        self.validation_q = validation_q
        threading.Thread.__init__(self, name=name)

    def run(self):
        while True:
            try:  # This try except is used in order to use the timeout on a queue get as a heartbeat timer
                event = self.validation_q.get(timeout=5)
                logger.info("Checking an Event")
                try:
                    future = event['future']
                    future.result(5)  # arbitrary 5 second check. How long should this be?
                    logger.info("Checking an Event Worked")
                except TimeoutError:
                    self.q.put(event['calling_event'])
                    logger.info("Checking an Event Failed with a Timeout Error,"
                                " Now putting the event back into the queue")
                except Exception as e:
                    logger.error("Checking an Event Failed with some other error {}".format(e))
                finally:
                    logger.info("Done Checking an Event")
            except Empty:
                pass
            logger.info("Validation Thread Heartbeat")

    def join(self, timeout=None):
        threading.Thread.join(self, timeout=timeout)


class WorkerPoolThread(threading.Thread):
    """
    A worker pool thread contains a threadpool, where the thread submits requests it pulls off the event q. Then,
    the submissions are verified using the validation thread
    """
    def __init__(self, event_q, state_q, name='WorkerPoolThread'):
        self.event_q = event_q
        self.state_q = state_q
        self._stopevent = threading.Event()
        self.validation_q = Queue()
        self.validation_thread = ValidationThread(self.validation_q, self.event_q)
        self.validation_thread.start()
        threading.Thread.__init__(self, name=name)

    def callback(self, future):
        state = future.result()
        self.state_q.put({'type': 'state_update', 'state': state})

    def run(self):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            while True:
                if not self._stopevent.is_set():
                    try:  # This try except is used in order to use the timeout on a queue get as a heartbeat timer
                        event_json = self.event_q.get(timeout=5)
                        logger.info("Got an Event")
                        future = executor.submit(event_json['intent'],
                                                 event_json['msg_writer'],
                                                 event_json['event'],
                                                 event_json['wit_entities'],
                                                 event_json['credentials'])
                        future.add_done_callback(self.callback)
                        self.validation_q.put({'future': future, 'calling_event': event_json})
                    except Empty:
                        pass
                    logger.info("WorkerPool Thread Heartbeat")

    def join(self, timeout=None):
        self.validation_q.join()
        self.validation_thread.join()
        self._stopevent.set()
        threading.Thread.join(self, timeout=timeout)


