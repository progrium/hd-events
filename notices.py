from google.appengine.api import mail
from django.template.defaultfilters import slugify
from google.appengine.ext import deferred
import random
import os

FROM_ADDRESS = 'Dojo Events <no-reply@hackerdojo-events.appspotmail.com>'
NEW_EVENT_ADDRESS = 'events@hackerdojo.com'
STAFF_ADDRESS = 'staff@hackerdojo.com'

def bug_owner_pending(e):
  body = """
Event: %s
Owner: %s
Date: %s
URL: http://%s/event/%s-%s
""" % (
    e.name, 
    str(e.member),
    e.start_time.strftime('%A, %B %d'),
    os.environ.get('HTTP_HOST'),
    e.key().id(),
    slugify(e.name),)
  
  if not e.is_approved():
    body += """
Alert! The events team has not approved your event yet.
Please e-mail them at events@hackerdojo.com to see whats up.
"""

  body += """

Cheers,
Hacker Dojo Events Team
events@hackerdojo.com
"""
 
  deferred.defer(mail.send_mail, sender=FROM_ADDRESS, to=e.member.email(),
   subject="[Pending Event] Your event is still pending: " + e.name,
   body=body, _queue="emailthrottle")

def schedule_reminder_email(e):
  body = """

*REMINDER*

Event: %s
Owner: %s
Date: %s
URL: http://%s/event/%s-%s
""" % (
    e.name, 
    str(e.owner()),
    e.start_time.strftime('%A, %B %d'),
    os.environ.get('HTTP_HOST'),
    e.key().id(),
    slugify(e.name),)
  body += """

Hello!  Friendly reminder that your event is scheduled to happen at Hacker Dojo.

 * The person named above must be physically present
 * If the event has been cancelled, resecheduled or moved, you must login and cancel the event on our system

Cheers,
Hacker Dojo Events Team
events@hackerdojo.com

"""
 
  deferred.defer(mail.send_mail, sender=FROM_ADDRESS, to=e.member.email(),
   subject="[Event Reminder] " + e.name,
   body=body, _queue="emailthrottle")
             
def notify_owner_confirmation(event):
    mail.send_mail(sender=FROM_ADDRESS, to=event.member.email(),
        subject="[New Event] Submitted but **not yet approved**",
        body="""This is a confirmation that your event:

%s
on %s

has been submitted to be approved. You will be notified as soon as it's
approved and on the calendar. Here is a link to the event page:

http://events.hackerdojo.com/event/%s-%s

Again, your event is NOT YET APPROVED and not on the calendar.

Cheers,
Hacker Dojo Events Team
events@hackerdojo.com

""" % (
    event.name, 
    event.start_time.strftime('%A, %B %d'),
    event.key().id(),
    slugify(event.name),))


def notify_new_event(event):
    mail.send_mail(sender=FROM_ADDRESS, to=NEW_EVENT_ADDRESS,
        subject='[New Event] %s on %s' % (event.name, event.start_time.strftime('%a %b %d')),
        body="""Member: %s
When: %s to %s
Type: %s
Size: %s
Contact: %s (%s)
Notes: %s

http://events.hackerdojo.com/event/%s-%s
""" % (
    event.member.email(), 
    event.start_time.strftime('%I:%M%p'), 
    event.end_time.strftime('%I:%M%p'),
    event.type,
    event.estimated_size,
    event.contact_name,
    event.contact_phone,
    event.notes,
    event.key().id(),
    slugify(event.name),))


def notify_owner_approved(event):
    mail.send_mail(sender=FROM_ADDRESS, to=event.member.email(),
        subject="[Event Approved] %s" % event.name,
        body="""Your event is approved and on the calendar!

Friendly Reminder: You must be present at the event and make sure Dojo policies are followed.

Note: If you cancel or reschedule the event, please log in to our system and cancel the event!

http://events.hackerdojo.com/event/%s-%s

Cheers,
Hacker Dojo Events Team
events@hackerdojo.com

""" % (event.key().id(), slugify(event.name)))


def notify_owner_expiring(event):
    pass

def notify_owner_expired(event):
    pass
