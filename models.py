from google.appengine.ext import db
from google.appengine.api import urlfetch, memcache, users, mail
from datetime import datetime, timedelta
from icalendar import Calendar, Event as CalendarEvent
from utils import human_username, local_today, to_sentence_list
import logging
import pytz

ROOM_OPTIONS = (
    ('Cave', 15),
    ('Deck', 30),
    ('Savanna', 120),
    ('140b', 129),
    ('Cubby 1', 2),
    ('Cubby 2', 2),
    ('Cubby 3', 2),
    ('Upstairs Office', 2),
    ('Front Area', 20))
# GUESTS_PER_STAFF = 25
PENDING_LIFETIME = 30 # days

class Event(db.Model):
    status  = db.StringProperty(required=True, default='pending', choices=set(
                ['pending', 'understaffed', 'approved', 'canceled', 'onhold', 'expired', 'deleted']))
    member  = db.UserProperty(auto_current_user_add=True)
    name        = db.StringProperty(required=True)
    start_time  = db.DateTimeProperty(required=True)
    end_time    = db.DateTimeProperty()
    staff       = db.ListProperty(users.User)
    rooms       = db.StringListProperty() #choices=set(ROOM_OPTIONS)

    details     = db.TextProperty()
    url         = db.StringProperty()
    fee         = db.StringProperty()
    notes       = db.TextProperty()
    type        = db.StringProperty(required=True)
    estimated_size = db.StringProperty(required=True)
    reminded    = db.BooleanProperty(default=False)

    contact_name    = db.StringProperty()
    contact_phone   = db.StringProperty()

    expired = db.DateTimeProperty()
    created = db.DateTimeProperty(auto_now_add=True)
    updated = db.DateTimeProperty(auto_now=True)

    @classmethod
    def get_all_future_list(cls):
        return cls.all() \
            .filter('start_time >', local_today()) \
            .filter('status IN', ['approved', 'canceled', 'pending', 'onhold']) \
            .order('start_time')

    @classmethod
    def get_approved_list(cls):
        return cls.all() \
            .filter('start_time >', local_today()) \
            .filter('status IN', ['approved', 'canceled']) \
            .order('start_time')

    @classmethod
    def get_pending_list(cls):
        return cls.all() \
            .filter('start_time >', local_today()) \
            .filter('status IN', ['pending', 'understaffed', 'onhold', 'expired']) \
            .order('start_time')

    def owner(self):
        return human_username(self.member)
        
    def stafflist(self):
        return to_sentence_list(map(human_username, self.staff))

    def roomlist(self):
        return to_sentence_list(self.rooms)

    def roomlist_as_phrase(self):
        if len(self.rooms) > 0:
            return "in " + self.roomlist()
        else:
            return ""
        
    def is_staffed(self):
        return len(self.staff) >= self.staff_needed()

    def staff_needed(self):
      return 0
#      if self.estimated_size.isdigit():
#        return int(self.estimated_size) / GUESTS_PER_STAFF
#      else:
#        # invalid data; just return something reasonable
#        return 2

    def is_approved(self):
        """Has the events team approved the event?  Note: This does not
        necessarily imply that the event is in state 'approved'."""
        return self.status in ('understaffed', 'approved', 'cancelled')

    def is_canceled(self):
        return self.status == 'canceled'

    def is_onhold(self):
        return self.status == 'onhold'

    def is_deleted(self):
        return self.status == 'deleted'

    def is_past(self):
        return self.end_time < local_today()

    def start_date(self):
        return self.start_time.date()

    def approve(self):
        user = users.get_current_user()
        if self.is_staffed():
            self.expired = None
            self.status = 'approved'
            logging.info('%s approved %s' % (user.nickname, self.name))
        else:
            self.status = 'understaffed'
            logging.info('%s approved %s but it is still understaffed' % (user.nickname, self.name))
        self.put()

    def cancel(self):
        user = users.get_current_user()
        self.status = 'canceled'
        self.put()
        logging.info('%s canceled %s' % (user.nickname, self.name))

    def on_hold(self):
        user = users.get_current_user()
        self.status = 'onhold'
        self.put()
        logging.info('%s put %s on hold' % (user.nickname, self.name))

    def delete(self):
        user = users.get_current_user()
        self.status = 'deleted'
        self.put()
        logging.info('%s deleted %s' % (user.nickname, self.name))

    def undelete(self):
        user = users.get_current_user()
        self.status = 'pending'
        self.put()
        logging.info('%s undeleted %s' % (user.nickname, self.name))

    def delete(self):
        user = users.get_current_user()
        self.status = 'deleted'
        self.put()
        logging.info('%s deleted %s' % (user.nickname, self.name))

    def undelete(self):
        user = users.get_current_user()
        self.status = 'pending'
        self.put()
        logging.info('%s undeleted %s' % (user.nickname, self.name))

    def expire(self):
        user = users.get_current_user()
        self.expired = datetime.now()
        self.status = 'expired'
        self.put()
        logging.info('%s expired %s' % (user.nickname, self.name))

    def add_staff(self, user):
        self.staff.append(user)
        if self.is_staffed() and self.status == 'understaffed':
            self.status = 'approved'
        self.put()
        logging.info('%s staffed %s' % (user.nickname, self.name))

    def remove_staff(self, user):
        self.staff.remove(user)
        if not self.is_staffed() and self.status == 'approved':
            self.status = 'understaffed'
        self.put()
        logging.info('%s staffed %s' % (user.nickname, self.name))

    def to_ical(self):
        event = CalendarEvent()
        event.add('summary', self.name if self.status == 'approved' else self.name + ' (%s)' % self.status.upper())
        if self.url:
          event.add('url', self.url)
        if self.start_time:
          event.add('dtstart', self.start_time.replace(tzinfo=pytz.timezone('US/Pacific')))
        if self.end_time:
          event.add('dtend', self.end_time.replace(tzinfo=pytz.timezone('US/Pacific')))
        return event

    def to_dict(self, summarize=False):
        d = dict()
        if summarize:
            props = ['member', 'start_time', 'name', 'type', 'estimated_size', 'end_time', 'rooms', 'status']
        else:
            props = Event.properties().keys()
        for prop in props:
            if prop == 'member':
                d[prop] = getattr(self, prop).email()
            elif prop == 'staff':
                d[prop] = map(lambda x: x.email(), getattr(self, prop))
            elif prop in ['start_time', 'end_time', 'created', 'expired', 'updated']:
                if getattr(self, prop):
                    d[prop] = getattr(self, prop).replace(tzinfo=pytz.timezone('US/Pacific')).strftime('%Y-%m-%dT%H:%M:%S')
            else:
                d[prop] = getattr(self, prop)
        d['id'] = self.key().id()
        return d

class Feedback(db.Model):
    user    = db.UserProperty(auto_current_user_add=True)
    event   = db.ReferenceProperty(Event)
    rating  = db.IntegerProperty()
    comment = db.StringProperty(multiline=True)
    created = db.DateTimeProperty(auto_now_add=True)

class HDLog(db.Model):
    event       = db.ReferenceProperty(Event)
    created     = db.DateTimeProperty(auto_now_add=True)
    user        = db.UserProperty(auto_current_user_add=True)
    description = db.StringProperty(multiline=True)

    @classmethod
    def get_logs_list(cls):
        return cls.all() \
            .order('-created')
