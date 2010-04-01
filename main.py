from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util, template
from google.appengine.api import urlfetch, memcache, users
from django.utils import simplejson
from datetime import datetime, timedelta
from django.template.defaultfilters import slugify
import time
from datetime import datetime
import logging, urllib
from icalendar import Calendar, Event as CalendarEvent, UTC # timezone

# Hacker Dojo Domain API helper with caching
def dojo(path):
    base_url = 'http://hackerdojo-domain.appspot.com'
    cache_ttl = 3600
    resp = memcache.get(path)
    if not resp:
        resp = urlfetch.fetch(base_url + path)
        if 'Refreshing' in resp.content:
            time.sleep(2)
            return urlfetch.fetch(base_url + path)
        try:
            resp = simplejson.loads(resp.content)
        except Exception, e:
            resp = []
            cache_ttl = 10
        memcache.set(path, resp, cache_ttl)
    return resp

def username(user):
    return user.nickname().split('@')[0] if user else None

ROOM_OPTIONS = ['cave', 'hall', 'savanna', 'sunroom', 'greenroom', 'frontarea', '140b']
GUESTS_PER_STAFF = 25

class Event(db.Model):
    status = db.StringProperty(required=True, default='pending', choices=set(
        ['pending', 'understaffed', 'approved', 'canceled', 'onhold', 'expired']))
    member = db.UserProperty(auto_current_user_add=True)
    name = db.StringProperty(required=True)
    start_time = db.DateTimeProperty(required=True)
    end_time = db.DateTimeProperty()
    staff = db.ListProperty(users.User)
    rooms = db.StringListProperty() #choices=set(ROOM_OPTIONS)
    
    details = db.StringProperty()
    url = db.StringProperty()
    fee = db.StringProperty()
    notes = db.StringProperty()
    type = db.StringProperty(required=True)
    estimated_size = db.StringProperty(required=True)
    
    contact_name = db.StringProperty(required=True)
    contact_phone = db.StringProperty(required=True)
    
    created = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)

    def is_staffed(self):
        return len(self.staff) >= int(self.estimated_size) / GUESTS_PER_STAFF

    def is_canceled(self):
        return self.status == 'canceled'

    def start_date(self):
        return self.start_time.date()
    
    def approve(self):
        if self.is_staffed():
            self.status = 'approved'
        else:
            self.status = 'understaffed'
        self.put()
        
    def cancel(self):
        self.status = 'canceled'
        self.put()
    
    def add_staff(self, user):
        self.staff.append(user)
        if self.is_staffed() and self.status == 'understaffed':
            self.status = 'approved'
        self.put()
    
    def to_ical(self):
        event = CalendarEvent()
        event.add('summary', self.name if self.status == 'approved' else self.name + ' (%s)' % self.status.upper())
        event.add('dtstart', self.start_time)
        return event

class EventsHandler(webapp.RequestHandler):
    def get(self, format):
        if format == 'ics':
            events = Event.all().filter('status IN', ['approved', 'canceled']).order('start_time')
            cal = Calendar()
            for event in events:
                cal.add_component(event.to_ical())
            self.response.headers['content-type'] = 'text/calendar'
            self.response.out.write(cal.as_string())

class EventHandler(webapp.RequestHandler):
    def get(self, id):
        event = Event.get_by_id(int(id))
        user = users.get_current_user()
        if user:
            is_admin = username(user) in dojo('/groups/events')
            is_staff = username(user) in dojo('/groups/staff')
            can_approve = (event.status in ['pending'] and is_admin)
            can_staff = (event.status in ['pending', 'understaffed', 'approved'] and is_staff and not user in event.staff)
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        self.response.out.write(template.render('templates/event.html', locals()))
    
    def post(self, id):
        event = Event.get_by_id(int(id))
        user = users.get_current_user()
        is_admin = username(user) in dojo('/groups/events')
        is_staff = username(user) in dojo('/groups/staff')
        state = self.request.get('state')
        if state:
            if state.lower() == 'approve' and is_admin:
                event.approve()
            if state.lower() == 'staff' and is_staff:
                event.add_staff(user)
            if state.lower() == 'cancel' and is_admin:
                event.cancel()
        self.redirect('/event/%s-%s' % (event.key().id(), slugify(event.name)))

class ApprovedHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        events = Event.all().filter('status IN', ['approved', 'canceled']).order('start_time')
        today = datetime.today()
        tomorrow = today + timedelta(days=1)
        self.response.out.write(template.render('templates/approved.html', locals()))

class MyEventsHandler(webapp.RequestHandler):
    @util.login_required
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        events = Event.all().filter('member = ', user).order('start_time')
        today = datetime.today()
        tomorrow = today + timedelta(days=1)
        is_admin = username(user) in dojo('/groups/events')
        self.response.out.write(template.render('templates/myevents.html', locals()))

class PastHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        today = datetime.today()
        events = Event.all().filter('start_date < ', today).order('start_time DESC')
        is_admin = username(user) in dojo('/groups/events')
        self.response.out.write(template.render('templates/past.html', locals()))

class PendingHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        events = Event.all().filter('status IN', ['pending', 'understaffed', 'onhold', 'expired']).order('start_time')
        today = datetime.today()
        tomorrow = today + timedelta(days=1)
        is_admin = username(user) in dojo('/groups/events')
        self.response.out.write(template.render('templates/pending.html', locals()))

class NewHandler(webapp.RequestHandler):
    @util.login_required
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        rooms = ROOM_OPTIONS
        self.response.out.write(template.render('templates/new.html', locals()))
    
    def post(self):
        user = users.get_current_user()
        start_time = datetime.strptime("%s %s:%s %s" % (
            self.request.get('start_date'),
            self.request.get('start_time_hour'),
            self.request.get('start_time_minute'),
            self.request.get('start_time_ampm')), "%d/%m/%Y %I:%M %p")
        event = Event(
            name = self.request.get('name'),
            start_time = start_time,
            type = self.request.get('type'),
            estimated_size = self.request.get('estimated_size'),
            contact_name = self.request.get('contact_name'),
            contact_phone = self.request.get('contact_phone'),
            details = self.request.get('details'),
            url = self.request.get('url'),
            fee = self.request.get('fee'),
            notes = self.request.get('notes'),
            rooms = self.request.get_all('rooms'))
        event.put()
        self.redirect('/event/%s-%s' % (event.key().id(), slugify(event.name)))

def main():
    application = webapp.WSGIApplication([
        ('/', ApprovedHandler),
        ('/events\.(.+)', EventsHandler),
        ('/past\.(.+)', PastHandler),
        ('/pending', PendingHandler),
        ('/myevents', MyEventsHandler),
        ('/new', NewHandler),
        ('/event/(\d+).*', EventHandler), ],debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
