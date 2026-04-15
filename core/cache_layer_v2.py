import time

CACHE = {}


def set_cache(key, value, ttl=60):
    CACHE[key] = {
        "value": value,
        "expiry": time.time() + ttl
    }


def get_cache(key):
    item = CACHE.get(key)
    if not item:
        return None

    if time.time() > item["expiry"]:
        del CACHE[key]
        return None

    return item["value"]


def clear_cache():
    CACHE.clear()
