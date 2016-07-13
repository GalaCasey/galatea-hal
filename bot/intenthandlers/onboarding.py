import logging
from uuid import uuid4

from intenthandlers.utils import get_highest_confidence_entity

logger = logging.getLogger(__name__)

onboarding_authed_user_ids = []


def onboarding_start(msg_writer, event, wit_entities):
    if event['user'] not in onboarding_authed_user_ids:
        msg_writer.send_message(event['channel'], "You are not allowed to start onboarding")
        return

    new_employee = get_highest_confidence_entity(wit_entities, 'name')
    start_date = get_highest_confidence_entity(wit_entities, 'date')

    # abstract from here on
    msg_writer.send_message('IT', "Please begin setting up accounts for {}, who starts on {}".format(new_employee, start_date))
    msg_writer.send_message('Kim', "Please begin setting up the desk for {}, who starts on {}".format(new_employee, start_date))
    msg_writer.send_message('Phones', "Please begin setting up phones for {}, who starts on {}".format(new_employee, start_date))
    msg_writer.send_message('Email', "Please begin setting up email for {}, who starts on {}".format(new_employee, start_date))
    msg_writer.send_message('Sheri', "Please sign {} up for slack, who starts on {}".format(new_employee, start_date))

    conversation = {
        'id': uuid4(),
        'waiting_for': ['accounts-setup', 'desk-setup', 'phones-setup', 'email-setup', 'slack-setup'],
        'context': {
            'return': {'user': event['user'], 'channel': event['channel']},
            'new_employee_name': new_employee,
            'start_date': start_date
        }
    }

    return conversation


def accounts_setup(msg_writer, event, wit_entities):
    info = get_highest_confidence_entity(wit_entities, 'account')
    conversation = event.get('conversation')
    context = conversation.get('context')
    msg_writer.send_message(context.get('return').get('channel'),
                            "Account for {} setup, with {} info".format(context.get('new_employee_name'), info))
    conversation.get('waiting_for').remove('accounts_setup')
    if conversation.get('waiting_for') is None:
        email_new_hire(msg_writer, conversation)
        return None
    return conversation


def desk_setup(msg_writer, event, wit_entities):
    conversation = event.get('conversation')
    context = conversation.get('context')
    msg_writer.send_message(context.get('return').get('channel'),
                            "Desk for {} setup".format(context.get('new_employee_name')))
    conversation.get('waiting_for').remove('desk_setup')
    if conversation.get('waiting_for') is None:
        email_new_hire(msg_writer, conversation)
        return None
    return conversation


def phones_setup(msg_writer, event, wit_entities):
    info = get_highest_confidence_entity(wit_entities, 'phone_number')
    conversation = event.get('conversation')
    context = conversation.get('context')
    msg_writer.send_message(context.get('return').get('channel'),
                            "Phones for {} setup, with {} number".format(context.get('new_employee_name'), info))
    conversation.get('waiting_for').remove('phones_setup')
    if conversation.get('waiting_for') is None:
        email_new_hire(msg_writer, conversation)
        return None
    return conversation


def email_setup(msg_writer, event, wit_entities):
    conversation = event.get('conversation')
    email = get_highest_confidence_entity(wit_entities, 'email')
    context = conversation.get('context')
    msg_writer.send_message(context.get('return').get('channel'),
                            "Email for {} setup".format(context.get('new_employee_name')))
    conversation.get('waiting_for').remove('email_setup')
    conversation.get('context').add({'email': email})
    if conversation.get('waiting_for') is None:
        email_new_hire(msg_writer, conversation)
        return None
    return conversation


def slack_setup(msg_writer, event, wit_entities):
    conversation = event.get('conversation')
    context = conversation.get('context')
    msg_writer.send_message(context.get('return').get('channel'),
                            "Email for {} setup".format(context.get('new_employee_name')))
    conversation.get('waiting_for').remove('slack_setup')
    if conversation.get('waiting_for') is None:
        email_new_hire(msg_writer, conversation)
        return None
    return conversation


def email_new_hire(msg_writer, conversation):
    context = conversation.get('context')
    address = context.get('email')
    name = context.get('new_employee_name')
    # do some stuff to send the mail to the new employee
    msg_writer.send_message(context.get('return').get('channel'),
                            "Email sent to {}".format(context.get('new_employee_name')))
