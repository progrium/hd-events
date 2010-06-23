from google.appengine.api import urlfetch, memcache
from django.utils import simplejson
from datetime import datetime
import pytz

LOCAL_TZ = 'America/Los_Angeles'

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
    
def to_sentence_list(lst):
    lst = map(str, lst)
    count = len(lst)
    if count == 0:
        return ''
    elif count == 1: 
        return lst[0]
    else:
        if count > 2:
            pre_and = ', '.join(lst[:-1])
        else:
            pre_and = lst[0]
        return ' and '.join([pre_and, lst[-1]])
    
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

def local_today():
    '''Return a datetime object representing the start of today, local time.'''
    utc_now = pytz.utc.localize(datetime.utcnow())
    local_now = utc_now.astimezone(pytz.timezone(LOCAL_TZ))
    return datetime(*local_now.timetuple()[:3])
