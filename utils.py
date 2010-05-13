from google.appengine.api import urlfetch, memcache
from django.utils import simplejson

# Hacker Dojo Domain API helper with caching
def dojo(path):
    base_url = 'http://hackerdojo-domain.appspot.com'
    cache_ttl = 3600
    resp = memcache.get(path)
    if not resp:
        resp = urlfetch.fetch(base_url + path, deadline=10)
        try:
            resp = simplejson.loads(resp.content)
        except Exception, e:
            resp = []
            cache_ttl = 10
        memcache.set(path, resp, cache_ttl)
    return resp

def username(user):
    return user.nickname().split('@')[0] if user else None

def human_username(user):
    if user:
        nick = user.nickname().split('@')[0]
        return nick.replace('.', ' ').title()
    else:
        return None

def set_cookie(headers, name, value):
    headers.add_header('Set-Cookie', '%s=%s;' % (name, simplejson.dumps(value)))
