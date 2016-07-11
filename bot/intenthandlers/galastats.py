import logging
import json
import requests
import os
from utils import get_highest_confidence_entity

logger = logging.getLogger(__name__)


# added ghce=get_highest_confidence_entity to allow for testing with alternate GHCE
def count_galateans(msg_writer, event, wit_entities, user_name, channel_name, ghce=get_highest_confidence_entity):

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
    normalized_loc = location_normalization.get(loc, "all")

    data = {
        "token": os.getenv("GOOGLE_SLACK_TOKEN", ""),
        "office": normalized_loc,
        "function": "count_galateans"
    }

    target_url = os.getenv("SCRIPTS_URL", "")

    resp = requests.get(target_url, data)
    logger.info(resp.text)
    if resp.status_code == 200:  # could use more error handling in this block
        txt = ""
        if normalized_loc == "all":
            txt = "*Office* : *Count*\n"
            for o in json.loads(resp.text).get('office_counts'):
                txt = txt + ">" + o['office'] + " : " + str(o['count']) + "\n"
        else:
            office = json.loads(resp.text).get('office_counts')[0]
            txt = office['office']+" : "+str(office['count'])
    else:
        txt = "Error in retrieving office counts"

    msg_writer.send_message(event['channel'], txt)
