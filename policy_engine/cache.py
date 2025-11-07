from collections import defaultdict

identity_cache = defaultdict(dict)

def remember_idp_attrs(key, attrs):
    if attrs:
        identity_cache[key].update(attrs)

def get_idp_attrs(key):
    return identity_cache.get(key, {})
