from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util, template
from google.appengine.api import urlfetch, memcache, users, mail

from django.utils import simplejson
from django.template.defaultfilters import slugify
import logging, urllib
from models import Event, Feedback

from datetime import datetime, timedelta, time, date

class FeedbacksHandler(webapp.RequestHandler):
    def get(self, format):
        if format == 'ics':
            events = Event.all().filter('status IN', ['approved', 'canceled']).order('start_time')
            cal = Calendar()
            for event in events:
                cal.add_component(event.to_ical())
            self.response.headers['content-type'] = 'text/calendar'
            self.response.out.write(cal.as_string())

class FeedbackHandler(webapp.RequestHandler):
    def get(self, id):
        feedback = Feedback.get_by_id(int(id))
        user = users.get_current_user()
        if user:
          is_admin = username(user) in dojo('/groups/events')
          is_staff = username(user) in dojo('/groups/staff')
          logout_url = users.create_logout_url('/')
        else:
          login_url = users.create_login_url('/')
          self.response.out.write(template.render('templates/event.html', locals()))
    
    def post(self, id):
        feedback = Feedback.get_by_id(int(id))
        user = users.get_current_user()
        is_admin = username(user) in dojo('/groups/events')
        is_staff = username(user) in dojo('/groups/staff')
        # self.redirect('/feedback/%s-%s' % (feedback.key().id(), slugify(feedback.name)))

class NewFeedbackHandler(webapp.RequestHandler):
    @util.login_required
    def get(self, id):
        user = users.get_current_user()
        event = Event.get_by_id(int(id))
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        past_events = db.GqlQuery("SELECT * from Event WHERE end_time < :1", datetime.today())
        self.response.out.write(template.render('templates/new_feedback.html', locals()))
    
    def post(self,id):
        user = users.get_current_user()
        feedback = Feedback(
            submitter = user,
            event = Event.get_by_id(int(id)),
            rating = int(self.request.get('rating')),
            comment = self.request.get('comment'),
            submitted = datetime.today()
            )
        feedback.put()
        self.redirect('/events')

