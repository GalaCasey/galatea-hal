import logging
from intenthandlers.utils import get_highest_confidence_entity, CallOnce
from cached_property import cached_property
from intenthandlers.google_helpers import google_query

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

    location_totals = get_galateans(event)

    if normalized_loc == "all":
        msg_writer.send_message_with_attachments(event['channel'],
                                                 location_totals.get('text'),
                                                 location_totals.get('attachments'))
    else:
        full_fields = location_totals.get('attachments')[0].get('fields')
        partial_fields = [full_fields[0], full_fields[1]]
        index = 0
        for f in full_fields:
            index += 1  # not pythonic, but not sure how else to get the next item
            if f.get('value') == normalized_loc:
                partial_fields.append(f)
                partial_fields.append(full_fields[index])
        msg_writer.send_message_with_attachments(event['channel'],
                                                 location_totals.get('text'),
                                                 [{"fields": partial_fields}])


@CallOnce
def get_galateans(event):
    return google_query("count_galateans", {'text': "show count of Galateans"}, event)
