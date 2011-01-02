import cgi
from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util, template
from google.appengine.api import urlfetch, memcache, users, mail

from django.utils import simplejson
from django.template.defaultfilters import slugify
from icalendar import Calendar
import logging, urllib, os
from pprint import pprint
from datetime import datetime, timedelta

from models import Event, Feedback, HDLog, ROOM_OPTIONS, PENDING_LIFETIME
from utils import username, human_username, set_cookie, local_today, is_phone_valid, UserRights, dojo, is_event_dup
from notices import *

import PyRSS2Gen

webapp.template.register_template_library('templatefilters')

def event_path(event):
    return '/event/%s-%s' % (event.key().id(), slugify(event.name))

class DomainCacheCron(webapp.RequestHandler):
    def post(self):        
        noop = dojo('/groups/events',force=True)


class ReminderCron(webapp.RequestHandler):
    def post(self):        
        self.response.out.write("REMINDERS")
        today = local_today()
        # remind everyone 3 days in advance they need to show up
        events = Event.all() \
            .filter('status IN', ['approved']) \
            .filter('reminded =', False) \
            .filter('start_time <', today + timedelta(days=3))
        for event in events:   
            self.response.out.write(event.name)
            # only mail them if they created the event 2+ days ago
            if event.created < today - timedelta(days=2):
              schedule_reminder_email(event)
            event.reminded = True
            event.put()


class ExpireCron(webapp.RequestHandler):
    def post(self):
        # Expire events marked to expire today
        today = local_today()
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
        ten_days = local_today() + timedelta(days=10)
        events = Event.all() \
            .filter('status IN', ['pending', 'understaffed']) \
            .filter('expired >=', ten_days) \
            .filter('expired <', ten_days + timedelta(days=1))
        for event in events:
            notify_owner_expiring(event)


class EventsHandler(webapp.RequestHandler):
    def get(self, format):
        events = Event.all().filter('status IN', ['approved', 'canceled']).order('start_time')
        if format == 'ics':
            cal = Calendar()
            for event in events:
                cal.add_component(event.to_ical())
            self.response.headers['content-type'] = 'text/calendar'
            self.response.out.write(cal.as_string())
        elif format == 'json':
            self.response.headers['content-type'] = 'application/json'
            events = map(lambda x: x.to_dict(summarize=True), Event.get_approved_list())
            self.response.out.write(simplejson.dumps(events))
        elif format =='rss':
            url_base = 'http://' + self.request.headers.get('host', 'events.hackerdojo.com')
            rss = PyRSS2Gen.RSS2(
                title = "Hacker Dojo Events Feed",
                link = url_base,
                description = "Upcoming events at the Hacker Dojo in Mountain View, CA",
                lastBuildDate = datetime.now(),
                items = [PyRSS2Gen.RSSItem(
                            title = event.name,
                            link = url_base + event_path(event),
                            description = event.details,
                            guid = url_base + event_path(event),
                            pubDate = event.updated,
                         ) for event in events]
            )

            self.response.headers['content-type'] = 'application/xml'
            self.response.out.write(rss.to_xml())


class EditHandler(webapp.RequestHandler):
    def get(self, id):
        event = Event.get_by_id(int(id))
        user = users.get_current_user()
        show_all_nav = user
        access_rights = UserRights(user, event)
        if access_rights.can_edit:
            logout_url = users.create_logout_url('/')            
            rooms = ROOM_OPTIONS
            hours = [1,2,3,4,5,6,7,8,9,10,11,12]
            self.response.out.write(template.render('templates/edit.html', locals()))
        else:
            self.response.out.write("Access denied")

    def post(self, id):
        event = Event.get_by_id(int(id))
        user = users.get_current_user()
        access_rights = UserRights(user, event)
        if access_rights.can_edit:
            try:
                srg_date = self.request.get('date')
                if event.start_time == srg_date:
                    start_time = start_time
                else:
                    st_date = srg_date[0:len(srg_date)-9]
                    start_time = datetime.strptime('%s %s:%s %s' % (
                        st_date,
                        self.request.get('start_time_hour'),
                        self.request.get('start_time_minute'),
                        self.request.get('start_time_ampm')), '%Y-%m-%d %I:%M %p')
                    end_time = datetime.strptime('%s %s:%s %s' % (
                        st_date,
                        self.request.get('end_time_hour'),
                        self.request.get('end_time_minute'),
                        self.request.get('end_time_ampm')), '%Y-%m-%d %I:%M %p')
                if not self.request.get('estimated_size').isdigit():
                    raise ValueError('Estimated number of people must be a number')
                if not int(self.request.get('estimated_size')) > 0:
                    raise ValueError('Estimated number of people must be greater then zero')
                if (  self.request.get( 'contact_phone' ) and not is_phone_valid( self.request.get( 'contact_phone' ) ) ):
                    raise ValueError( 'Phone number does not appear to be valid' )
                else:
                    event.name = self.request.get('name')
                    event.start_time = start_time
                    event.end_time = end_time
                    event.estimated_size = cgi.escape(self.request.get('estimated_size'))
                    event.contact_name = cgi.escape(self.request.get('contact_name'))
                    event.contact_phone = cgi.escape(self.request.get('contact_phone'))
                    event.details = cgi.escape(self.request.get('details'))
                    event.url = cgi.escape(self.request.get('url'))
                    event.fee = cgi.escape(self.request.get('fee'))
                    event.notes = cgi.escape(self.request.get('notes'))
                    event.rooms = self.request.get_all('rooms')
                    event.put()
                    log = HDLog(event=event,description="Edited event")
                    log.put()
                    self.redirect(event_path(event))
            except ValueError, e:
                error = str(e)
                self.response.out.write(template.render('templates/error.html', locals()))
        else:
            self.response.out.write("Access denied")


class EventHandler(webapp.RequestHandler):
    def get(self, id):
        event = Event.get_by_id(int(id))
        if self.request.path.endswith('json'):
            self.response.headers['content-type'] = 'application/json'
            self.response.out.write(simplejson.dumps(event.to_dict()))
        else:
            user = users.get_current_user()
            if user:
                access_rights = UserRights(user, event)
                logout_url = users.create_logout_url('/')
                
            else:
                login_url = users.create_login_url('/')
            event.details = db.Text(event.details.replace('\n','<br/>'))
            show_all_nav = user
            event.notes = db.Text(event.notes.replace('\n','<br/>'))
            self.response.out.write(template.render('templates/event.html', locals()))

    def post(self, id):
        event = Event.get_by_id(int(id))
        user = users.get_current_user()
        access_rights = UserRights(user, event)

        state = self.request.get('state')
        if state:
            desc = ''
            if state.lower() == 'approve' and access_rights.can_approve:
                event.approve()
                desc = 'Approved event'
            if state.lower() == 'staff' and access_rights.can_staff:
                event.add_staff(user)
                desc = 'Added self as staff'
            if state.lower() == 'unstaff' and access_rights.can_unstaff:
                event.remove_staff(user)
                desc = 'Removed self as staff'
            if state.lower() == 'cancel' and access_rights.can_cancel:
                event.cancel()
                desc = 'Cancelled event'
            if state.lower() == 'delete' and access_rights.is_admin:
                event.delete()
                desc = 'Deleted event'
            if state.lower() == 'undelete' and access_rights.is_admin:
                event.undelete()
                desc = 'Undeleted event'
            if state.lower() == 'expire' and access_rights.is_admin:
                event.expire()
                desc = 'Expired event'
            if event.status == 'approved':
                notify_owner_approved(event)
            if desc != '':
                log = HDLog(event=event,description=desc)
                log.put()
        self.redirect(event_path(event))


class ApprovedHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        today = local_today()
        show_all_nav = user
        events = Event.get_approved_list()
        tomorrow = today + timedelta(days=1)
        whichbase = 'base.html'
        if self.request.get('base'):
            whichbase = self.request.get('base') + '.html'
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
        show_all_nav = user
        today = local_today()
        tomorrow = today + timedelta(days=1)
        self.response.out.write(template.render('templates/myevents.html', locals()))


class PastHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        today = local_today()
        show_all_nav = user
        events = Event.all().filter('start_time < ', today).order('-start_time')
        self.response.out.write(template.render('templates/past.html', locals()))


class CronBugOwnersHandler(webapp.RequestHandler):
    def get(self):
        events = Event.get_pending_list()
        for e in events:
            bug_owner_pending(e)


class AllFutureHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        show_all_nav = user
        events = Event.get_all_future_list()
        today = local_today()
        tomorrow = today + timedelta(days=1)
        self.response.out.write(template.render('templates/all_future.html', locals()))


class PendingHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        events = Event.get_pending_list()
        show_all_nav = user
        today = local_today()
        tomorrow = today + timedelta(days=1)
        self.response.out.write(template.render('templates/pending.html', locals()))


class NewHandler(webapp.RequestHandler):
    @util.login_required
    def get(self):
        user = users.get_current_user()
        human = human_username(user)
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        rooms = ROOM_OPTIONS
        self.response.out.write(template.render('templates/new.html', locals()))


    def post(self):
        user = users.get_current_user()
        try:
            start_time = datetime.strptime('%s %s:%s %s' % (
                self.request.get('date'),
                self.request.get('start_time_hour'),
                self.request.get('start_time_minute'),
                self.request.get('start_time_ampm')), '%m/%d/%Y %I:%M %p')
            end_time = datetime.strptime('%s %s:%s %s' % (
                self.request.get('date'),
                self.request.get('end_time_hour'),
                self.request.get('end_time_minute'),
                self.request.get('end_time_ampm')), '%m/%d/%Y %I:%M %p')
            if not self.request.get('estimated_size').isdigit():
              raise ValueError('Estimated number of people must be a number')
            if not int(self.request.get('estimated_size')) > 0:
              raise ValueError('Estimated number of people must be greater then zero')
            if (end_time-start_time).days < 0:
                raise ValueError('End time must be after start time')
            if (  self.request.get( 'contact_phone' ) and not is_phone_valid( self.request.get( 'contact_phone' ) ) ):
                raise ValueError( 'Phone number does not appear to be valid' )
            else:
                event = Event(
                    name = cgi.escape(self.request.get('name')),
                    start_time = start_time,
                    end_time = end_time,
                    type = cgi.escape(self.request.get('type')),
                    estimated_size = cgi.escape(self.request.get('estimated_size')),
                    contact_name = cgi.escape(self.request.get('contact_name')),
                    contact_phone = cgi.escape(self.request.get('contact_phone')),
                    details = cgi.escape(self.request.get('details')),
                    url = cgi.escape(self.request.get('url')),
                    fee = cgi.escape(self.request.get('fee')),
                    notes = cgi.escape(self.request.get('notes')),
                    rooms = self.request.get_all('rooms'),
                    expired = local_today() + timedelta(days=PENDING_LIFETIME), # Set expected expiration date
                    )
                event.put()
                log = HDLog(event=event,description="Created new event")
                log.put()
                notify_owner_confirmation(event)
                notify_new_event(event)
                set_cookie(self.response.headers, 'formvalues', None)
                self.redirect('/event/%s-%s' % (event.key().id(), slugify(event.name)))
        except Exception, e:
            message = str(e)
            if 'match format' in message:
                message = 'Date is required.'
            if message.startswith('Property'):
                message = message[9:].replace('_', ' ').capitalize()
            # This is NOT a reliable way to handle erorrs
            #set_cookie(self.response.headers, 'formerror', message)
            #set_cookie(self.response.headers, 'formvalues', dict(self.request.POST))
            #self.redirect('/new')
            error = message
            self.response.out.write(template.render('templates/error.html', locals()))
            
class CheckConflict(webapp.RequestHandler):            
    def post(self, id):
        start_time = datetime.strptime('%s %s:%s %s' % (
            self.request.get('date'),
            self.request.get('start_time_hour'),
            self.request.get('start_time_minute'),
            self.request.get('start_time_ampm')), '%m/%d/%Y %I:%M %p')
        end_time = datetime.strptime('%s %s:%s %s' % (
            self.request.get('date'),
            self.request.get('end_time_hour'),
            self.request.get('end_time_minute'),
            self.request.get('end_time_ampm')), '%m/%d/%Y %I:%M %p')
        rooms = self.request.get_all('rooms')
        message = is_event_dup(start_date, end_date, rooms)
        self.response.out.write(message)

class LogsHandler(webapp.RequestHandler):
    @util.login_required
    def get(self):
        user = users.get_current_user()
        logs = HDLog.get_logs_list()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        show_all_nav = user
        self.response.out.write(template.render('templates/logs.html', locals()))

class FeedbackHandler(webapp.RequestHandler):
    @util.login_required
    def get(self, id):
        user = users.get_current_user()
        event = Event.get_by_id(int(id))
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        self.response.out.write(template.render('templates/feedback.html', locals()))

    def post(self, id):
        user = users.get_current_user()
        event = Event.get_by_id(int(id))
        try:
            if self.request.get('rating'):
                feedback = Feedback(
                    event = event,
                    rating = int(self.request.get('rating')),
                    comment = cgi.escape(self.request.get('comment')))
                feedback.put()
                log = HDLog(event=event,description="Posted feedback")
                log.put()
                self.redirect('/event/%s-%s' % (event.key().id(), slugify(event.name)))
            else:
                raise ValueError('Please select a rating')
        except Exception:
            set_cookie(self.response.headers, 'formvalues', dict(self.request.POST))
            self.redirect('/feedback/new/' + id)

def main():
    application = webapp.WSGIApplication([
        ('/', ApprovedHandler),
        ('/events\.(.+)', EventsHandler),
        ('/all_future', AllFutureHandler),
        ('/past', PastHandler),
        ('/pending', PendingHandler),
        ('/cronbugowners', CronBugOwnersHandler),
        ('/myevents', MyEventsHandler),
        ('/new', NewHandler),
        ('/edit/(\d+).*', EditHandler),
        ('/event/(\d+).*', EventHandler),
        ('/event/(\d+)\.json', EventHandler),
        ('/expire', ExpireCron),
        ('/expiring', ExpireReminderCron),
        ('/domaincache', DomainCacheCron),        
        ('/reminder', ReminderCron),
        ('/check_conflict', CheckConflict),
        ('/logs', LogsHandler),
        ('/feedback/new/(\d+).*', FeedbackHandler) ],debug=True)
    util.run_wsgi_app(application)


if __name__ == '__main__':
    main()
