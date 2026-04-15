CACHE = {}


def get_cache(key):
    return CACHE.get(key)


def set_cache(key, value):
    CACHE[key] = value


def clear_cache():
    CACHE.clear()
