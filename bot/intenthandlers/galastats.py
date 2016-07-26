import logging
import httplib2
from uuid import uuid4
from state import WaitState
from apiclient import discovery
from intenthandlers.utils import get_highest_confidence_entity, CallOnce

logger = logging.getLogger(__name__)


# added ghce=get_highest_confidence_entity to allow for testing with alternate GHCE
def count_galateans(msg_writer, event, wit_entities, credentials, ghce=get_highest_confidence_entity):

    # We need to find a geocoding service for this so we don't need to hardcode
    location_normalization = {
        "london": "LN",
        "england": "LN",
        "britain": "LN",
        "great britain": "LN",
        "uk": "LN",
        "boston": "MA",
        "somerville": "MA",
        "davis": "MA",
        "davis square": "MA",
        "davis sq": "MA",
        "massachusetts": "MA",
        "mass": "MA",
        "tampa": "FL",
        "florida": "FL"
    }

    # Find the location with the highest confidence that met our default threshold
    loc_entity = ghce(wit_entities, 'location')
    if loc_entity is not None:
        loc = loc_entity['value'].lower()
    else:
        loc = 'all'

    # We need to normalize the location since wit doesn't do that for us
    # Need to use a geocode service for this instead of our hack
    normalized_loc = location_normalization.get(loc, "all")  # should we return all if we get a valid location,
                                                             # but where we have no office?
    state_id = uuid4()
    current_creds = credentials.get_credential(event, state_id, user=event['user'])
    if current_creds is None:
        state = WaitState(build_uuid=state_id, intent_value='galatean-count', event=event,
                          wit_entities=wit_entities, credentials=credentials)
        return state
    location_totals = get_galateans(current_creds)
    text = "*Office | Count*"
    if normalized_loc == "all":
        for office in location_totals:
            text += "\n" + office + "             " + location_totals[office]
    else:
        if normalized_loc == "LN":
            text += "\nLN             " + location_totals['LN']
        elif normalized_loc == "MA":
            text += "\nMA             " + location_totals['MA']
        elif normalized_loc == "FL":
            text += "\nFL             " + location_totals['FL']
    msg_writer.send_message(event['channel'], "Count of Galateans\n" + text)


@CallOnce
def get_galateans(current_creds):
    # This should make an API call.
    http = current_creds.authorize(httplib2.Http())
    discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                    'version=v4')
    service = discovery.build('sheets', 'v4', http=http, discoveryServiceUrl=discoveryUrl)
    spreadsheetId = "14Sl7L5r5R1OLX9FmY4yZABsSD4b8GuX0uC8btlSl1cM"
    rangeName = 'Count by office!Gala_Count'
    result = service.spreadsheets().values().get(spreadsheetId=spreadsheetId, range=rangeName).execute()
    values = result.get('values', [])
    offices = {
        "LN": values[1][1],
        "FL": values[0][1],
        "MA": values[2][1]
    }
    return offices
