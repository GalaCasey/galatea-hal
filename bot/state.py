import logging
from uuid import uuid4

logger = logging.getLogger(__name__)


class State(object):
    """
    A generic object used as a base class for other stateful objects
    """
    def __init__(self, obj=None):
        if obj:
            self.id = obj.get('id')
            self.finished = obj.get('finished')
        else:
            self.id = uuid4()
            self.finished = False

    def __cmp__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def get_id(self):
        return self.id

    def is_complete(self):
        return self.complete

    def complete(self):
        self.finished = True

    def objectify(self):
        return {
            'id': self.id,
            'finished': self.finished
        }


class WaitState(State):
    """
    A WaitState holds the state of a Hal command, and is used to ensure that once a user is authenticated with
    OAuth, their original command continues executing
    """
    def __init__(self, build_uuid=None, intent_value=None, event=None, wit_entities=None, credentials=None, obj=None):
        State.__init__(self, obj)
        if obj:
            self.id = obj.get('id')
            self.intent_value = obj.get('intent_value')
            self.event = obj.get('event')
            self.wit_entities = obj.get('wit_entities')
            self.credentials = obj.get('credentials')
            self.finished = obj.get('finished')
        else:
            self.id = build_uuid
            self.intent_value = intent_value
            self.event = event
            self.wit_entities = wit_entities
            self.credentials = credentials

    def get_intent_value(self):
        return self.intent_value

    def get_event(self):
        return self.event

    def get_wit_entities(self):
        return self.wit_entities

    def get_credentials(self):
        return self.credentials

    def objectify(self):
        obj = State.objectify(self)
        obj.update({
            'intent_value': self.intent_value,
            'event': self.event,
            'wit_entites': self.wit_entities,
            'credentials': self.credentials
        })
        return obj


class ConversationState(State):
    """
    A generic conversation state, used as a base for specific conversations
    """
    def __init__(self, obj=None):
        State.__init__(self, obj)
        if obj:
            self.id = obj.get('id')
            self.finished = obj.get('finished')
            self.waiting_for = obj.get('waiting_for')
            self.context = obj.get('context')
        else:
            self.waiting_for = None
            self.context = None

    def get_waiting_for(self):
        return self.waiting_for

    def get_context(self):
        return self.context

    def remove_from_waiting(self, intent_type):
        if intent_type in self.waiting_for:
            self.waiting_for.remove(intent_type)
        else:
            logger.error("Attempted removing non-existent intent from waiting for list")
            raise KeyError

    def objectify(self):
        obj = State.objectify(self)
        obj.update({
            'waiting_for': self.waiting_for,
            'context': self.context
        })
        return obj


class OnboardingConversation(ConversationState):
    """
    A Conversation used to keep track of where in the onboarding process this onboarding is.
    """
    def __init__(self, return_target, new_employee, start_date):
        ConversationState.__init__(self)
        self.waiting_for = ['accounts-setup', 'desk-setup', 'phones-setup', 'email-setup', 'slack-setup']
        self.context = {
            'return': return_target,
            'new_employee_name': new_employee,
            'start_date': start_date
        }


class NaggingConversation(ConversationState):
    """
    A Conversation used to keep track of who is currently being nagged, to ensure that when they complete their task,
    they are no longer nagged.
    """
    def __init__(self, return_target, dm, user_name_to_nag, nag_subject, thread):
        ConversationState.__init__(self)
        self.waiting_for = ['nag-response']
        self.context = {
                'return': return_target,
                'dm_channel': dm,
                'user_name_to_nag': user_name_to_nag,
                'nag_subject': nag_subject,
                'reminder_thread': thread
        }
