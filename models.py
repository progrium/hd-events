from google.appengine.ext import db
from google.appengine.api import urlfetch, memcache, users, mail
from datetime import datetime, timedelta, time, date
from icalendar import Calendar, Event as CalendarEvent
from pytz import timezone
from utils import human_username

ROOM_OPTIONS = ['cave', 'deck', 'savanna', 'frontarea', '140b']
GUESTS_PER_STAFF = 25
PENDING_LIFETIME = 30 # days

def to_sentence(aList):
    sentence = ', '.join([e for e in aList if aList.index(e) != len(aList) -1])
    if len(aList) > 1: sentence = '%s and %s' % (sentence, aList[-1])
    return sentence
    
def to_name_list(aList):
    sentence = ', '.join([human_username(e) for e in aList if aList.index(e) != len(aList) -1])
    if len(aList) > 1: sentence = '%s and %s' % (sentence, human_username(aList[-1]))
    return sentence

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

    def stafflist(self):
        return to_name_list(self.staff)

    def roomlist(self):
        return to_sentence(self.rooms)

    def is_staffed(self):
        return len(self.staff) >= self.staff_needed()

    def staff_needed(self):
        return int(self.estimated_size) / GUESTS_PER_STAFF

    def is_canceled(self):
        return self.status == 'canceled'

    def is_past(self):
        return self.end_time < datetime.today()

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

class Feedback(db.Model):
    user = db.UserProperty(auto_current_user_add=True)
    event = db.ReferenceProperty(Event)
    rating = db.IntegerProperty()
    comment = db.StringProperty(multiline=True)
    created = db.DateTimeProperty(auto_now_add=True)

