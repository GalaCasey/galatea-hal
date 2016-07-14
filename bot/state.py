import logging
from uuid import uuid4

logger = logging.getLogger(__name__)


class State(object):
    def __init__(self, obj=None):
        if obj:
            self.id = obj.get('id')
            self.complete = obj.get('complete')
        else:
            self.id = uuid4()
            self.complete = False

    def __cmp__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def get_id(self):
        return self.id

    def is_complete(self):
        return self.complete

    def complete(self):
        self.complete = True

    def objectify(self):
        return {
            'id': self.id,
            'complete': self.complete
        }


class WaitState(State):
    def __init__(self, intent_value=None, event=None, wit_entities=None, credentials=None, obj=None):
        State.__init__(self, obj)
        if obj:
            self.intent_value = obj.get('intent_value')
            self.event = obj.get('event')
            self.wit_entities = obj.get('wit_entities')
            self.credentials = obj.get('credentials')
        else:
            self.intent_value = intent_value
            self.event = event
            self.wit_entities = wit_entities
            self.credentials = credentials

    def get_intent_value(self):
        return self.intent_value

    def get_event(self):
        return self.event

    def get_wit_entites(self):
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
    def __init__(self):
        State.__init__(self)
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
    def __init__(self, return_target, new_employee, start_date):
        ConversationState.__init__(self)
        self.waiting_for = ['accounts-setup', 'desk-setup', 'phones-setup', 'email-setup', 'slack-setup']
        self.context = {
            'return': return_target,
            'new_employee_name': new_employee,
            'start_date': start_date
        }


class NaggingConversation(ConversationState):
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
