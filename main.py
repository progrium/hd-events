from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util, template
from google.appengine.api import urlfetch, memcache, users, mail

from django.utils import simplejson
from django.template.defaultfilters import slugify
from icalendar import Calendar, Event as CalendarEvent
import logging, urllib

from datetime import datetime, timedelta, time, date
from pytz import timezone
import pytz

ROOM_OPTIONS = ['cave', 'deck', 'savanna', 'frontarea', '140b']
GUESTS_PER_STAFF = 25
PENDING_LIFETIME = 30 # days
FROM_ADDRESS = "Dojo Events <no-reply@hackerdojo-events.appspotmail.com>"

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

def notify_owner_confirmation(event):
    mail.send_mail(sender=FROM_ADDRESS, to=event.member.email(),
        subject="Event application submitted",
        body="""This is a confirmation that your event:\n\n%s\n\n
        has been submitted for approval. If staff is needed for your event, they
        will be notified of your request. You will be notified as soon as it's 
        approved and on the calendar.""" % event.name)

def notify_staff_needed(event):
    pass

def notify_new_event(event):
    pass

def notify_owner_approved(event):
    pass

def notify_owner_expiring(event):
    pass

def notify_owner_expired(event):
    pass

def set_cookie(headers, name, value):
    headers.add_header('Set-Cookie', '%s=%s;' % (name, simplejson.dumps(value)))

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
    
    expired = db.DateTimeProperty()
    created = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)

    @classmethod
    def get_approved_list(cls):
        return cls.all() \
            .filter('start_time >', datetime.today()) \
            .filter('status IN', ['approved', 'canceled']) \
            .order('start_time')
    
    @classmethod
    def get_pending_list(cls):
        return cls.all() \
            .filter('start_time >', datetime.today()) \
            .filter('status IN', ['pending', 'understaffed', 'onhold', 'expired']) \
            .order('start_time')

    def is_staffed(self):
        return len(self.staff) >= int(self.estimated_size) / GUESTS_PER_STAFF

    def is_canceled(self):
        return self.status == 'canceled'

    def start_date(self):
        return self.start_time.date()
    
    def approve(self):
        if self.is_staffed():
            self.expired = None
            self.status = 'approved'
        else:
            self.status = 'understaffed'
        self.put()
        
    def cancel(self):
        self.status = 'canceled'
        self.put()
    
    def expire(self):
        self.expired = datetime.now()
        self.status = 'expired'
        self.put()
    
    def add_staff(self, user):
        self.staff.append(user)
        if self.is_staffed() and self.status == 'understaffed':
            self.status = 'approved'
        self.put()
    
    def to_ical(self):
        event = CalendarEvent()
        event.add('summary', self.name if self.status == 'approved' else self.name + ' (%s)' % self.status.upper())
        event.add('dtstart', self.start_time.replace(tzinfo=timezone('US/Pacific')))
        return event

class ExpireCron(webapp.RequestHandler):    
    def post(self):
        # Expire events marked to expire today
        today = datetime.combine(datetime.today(), time())
        events = Event.all() \
            .filter('status IN', ['pending', 'understaffed']) \
            .filter('expired >=', today) \
            .filter('expired <', today + timedelta(days=1))
        for event in events:
            event.expire()
            notify_owner_expired(event)

class ExpireReminderCron(webapp.RequestHandler):
    def post(self):
        # Find events expiring in 10 days to warn owner
        ten_days = datetime.combine(datetime.today(), time()) + timedelta(days=10)
        events = Event.all() \
            .filter('status IN', ['pending', 'understaffed']) \
            .filter('expired >=', ten_days) \
            .filter('expired <', ten_days + timedelta(days=1))
        for event in events:
            notify_owner_expiring(event)

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
            if state.lower() == 'expire' and is_admin:
                event.expire()
            
            if event.status == 'approved':
                notify_owner_approved(event)
        self.redirect('/event/%s-%s' % (event.key().id(), slugify(event.name)))

class ApprovedHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        today = datetime.today()
        events = Event.get_approved_list()
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
        events = Event.all().filter('start_time < ', today).order('-start_time')
        is_admin = username(user) in dojo('/groups/events')
        self.response.out.write(template.render('templates/past.html', locals()))

class PendingHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        events = Event.get_pending_list()
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
        try:
            start_time = datetime.strptime("%s %s:%s %s" % (
                self.request.get('date'),
                self.request.get('start_time_hour'),
                self.request.get('start_time_minute'),
                self.request.get('start_time_ampm')), "%d/%m/%Y %I:%M %p")
            end_time = datetime.strptime("%s %s:%s %s" % (
                self.request.get('date'),
                self.request.get('end_time_hour'),
                self.request.get('end_time_minute'),
                self.request.get('end_time_ampm')), "%d/%m/%Y %I:%M %p")
            if (end_time-start_time).days < 0:
                raise ValueError("End time must be after start time")
            else:
                event = Event(
                    name = self.request.get('name'),
                    start_time = start_time,
                    end_time = end_time,
                    type = self.request.get('type'),
                    estimated_size = self.request.get('estimated_size'),
                    contact_name = self.request.get('contact_name'),
                    contact_phone = self.request.get('contact_phone'),
                    details = self.request.get('details'),
                    url = self.request.get('url'),
                    fee = self.request.get('fee'),
                    notes = self.request.get('notes'),
                    rooms = self.request.get_all('rooms'),
                    expired = datetime.today() + timedelta(days=PENDING_LIFETIME), # Set expected expiration date
                    )
                event.put()
                notify_owner_confirmation(event)
                if not event.is_staffed():
                    notify_staff_needed(event)
                notify_new_event(event)
                self.redirect('/event/%s-%s' % (event.key().id(), slugify(event.name)))
        except Exception:
            set_cookie(self.response.headers, 'formvalues', dict(self.request.POST))
            self.redirect('/new')

def main():
    application = webapp.WSGIApplication([
        ('/', ApprovedHandler),
        ('/events\.(.+)', EventsHandler),
        ('/past', PastHandler),
        ('/pending', PendingHandler),
        ('/myevents', MyEventsHandler),
        ('/new', NewHandler),
        ('/event/(\d+).*', EventHandler),
        ('/expire', ExpireCron),
        ('/expiring', ExpireReminderCron), ],debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
