from google.appengine.ext import webapp, db
from google.appengine.ext.webapp import util, template
from google.appengine.api import urlfetch, memcache, users
from django.utils import simplejson
from datetime import datetime, timedelta
#import logging, urllib

ROOM_OPTIONS = ['cave', 'hall', 'savanna', 'sunroom', 'greenroom', 'frontarea', '140b']

class Event(db.Model):
    status = db.StringProperty(required=True, default='pending', choices=set(
        ['pending', 'preapproved', 'approved', 'canceled', 'onhold', 'expired']))
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

    def start_date(self):
        return self.start_time.date()

class EventHandler(webapp.RequestHandler):
    def get(self, id):
        event = Event.get_by_id(int(id))
        self.response.out.write(template.render('templates/event.html', locals()))

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

class PendingHandler(webapp.RequestHandler):
    def get(self):
        user = users.get_current_user()
        if user:
            logout_url = users.create_logout_url('/')
        else:
            login_url = users.create_login_url('/')
        events = Event.all().filter('status IN', ['pending', 'preapproved', 'onhold', 'expired']).order('start_time')
        today = datetime.today()
        tomorrow = today + timedelta(days=1)
        self.response.out.write(template.render('templates/pending.html', locals()))

class NewHandler(webapp.RequestHandler):
    #@util.login_required
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
        self.redirect('/')

def main():
    application = webapp.WSGIApplication([
        ('/', ApprovedHandler),
        ('/pending', PendingHandler),
        ('/new', NewHandler),
        ('/event/(\d+).*', EventHandler), ],debug=True)
    util.run_wsgi_app(application)

if __name__ == '__main__':
    main()
