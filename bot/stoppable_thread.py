import threading
import logging
import flask
import os
import zmq
#from intenthandlers.google_helpers import SCOPES
from oauth2client import client
from time import sleep

logger = logging.getLogger(__name__)

app = flask.Flask(__name__)

context = zmq.Context()

flask_sender = context.socket(zmq.PUSH)
flask_sender.connect("tcp://localhost:6666")


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


class FlaskThread(threading.Thread):
    def __init__(self, name='FlaskThread'):
        threading.Thread.__init__(self, name=name)

    def run(self):
        app.run(port=5555, host="0.0.0.0")


@app.route("/")
def _handle_flask_redirect():

    if 'code' not in flask.request.args:
        # This shouldn't happen
        pass
    else:
        auth_code = flask.request.args.get('code')
        encrypted_state = flask.request.args.get('state')
        flask_sender.send_json(obj={'auth_code': auth_code, 'encrypted_state': encrypted_state})

    return ""  # Useful to keep flask from breaking, despite no need for a response
