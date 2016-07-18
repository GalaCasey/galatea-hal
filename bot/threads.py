import threading
import logging
import flask
import zmq
from time import sleep

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
    def __init__(self, context, name='FlaskThread'):
        self.flask_sender = context.socket(zmq.PUSH)
        self.flask_sender.connect("inproc://flask")
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
                self.flask_sender.send_json(obj={'auth_code': auth_code, 'encrypted_state': encrypted_state})

            return ""  # Useful to keep flask from breaking, despite no need for a response to google

        # This line must be the last line, or functions will not be defined before the server starts, resulting in 404s
        app.run(port=5555, host="0.0.0.0")
