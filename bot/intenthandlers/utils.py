import logging
import collections
import functools
import time

logger = logging.getLogger(__name__)


def get_highest_confidence_entity(entities_dict, entity_name, confidence_threshold=0.75):
    if entity_name not in entities_dict:
        return None

    entities_of_interest = entities_dict[entity_name]
    highest_confidence_entity = None
    for entity in entities_of_interest:
        if 'confidence' in entity and entity['confidence'] > confidence_threshold:
            if highest_confidence_entity is None :
                highest_confidence_entity = entity
            elif entity['confidence'] > highest_confidence_entity['confidence']:
                highest_confidence_entity = entity
            else:
                pass

    if highest_confidence_entity is None:
        logger.info("Couldn't find a {} that met our confidence floor {}.".format(entity_name, confidence_threshold))
    else:
        logger.info("Found most likely {} with confidence {}".format(entity_name,
                                                                     highest_confidence_entity['confidence']))

    return highest_confidence_entity


# Copied from Python Decorator Library
# https://wiki.python.org/moin/PythonDecoratorLibrary
class memoized(object):
    """Decorator. Caches a function's return value each time it is called.
    If called later with the same arguments, the cached value is returned
    (not reevaluated).
    """

    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args):
        if not isinstance(args, collections.Hashable):
            # uncacheable. a list, for instance.
            # better to not cache than blow up.
            return self.func(*args)

        if args in self.cache:
            return self.cache[args]
        else:
            value = self.func(*args)
            self.cache[args] = value
            return value

    def __repr__(self):
        """Return the function's docstring."""
        return self.func.__doc__

    def __get__(self, obj, objtype):
        """Support instance methods."""
        return functools.partial(self.__call__, obj)


class CallOnce(object):
    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args, **kwargs):
        if 'return' in self.cache:
            return self.cache['return']
        else:
            value = self.func(*args, **kwargs)
            self.cache['return'] = value
            return value

    def __repr__(self):
        """Return the function's docstring."""
        return self.func.__doc__

    def __get__(self, obj, objtype):
        """Support instance methods."""
        return functools.partial(self.__call__, obj)



