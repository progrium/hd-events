from google.appengine.api import mail
from django.template.defaultfilters import slugify

FROM_ADDRESS = "Dojo Events <no-reply@hackerdojo-events.appspotmail.com>"
NEW_EVENT_ADDRESS = "events@hackerdojo.com"
STAFF_ADDRESS = "staff@hackerdojo.com"

def notify_owner_confirmation(event):
    mail.send_mail(sender=FROM_ADDRESS, to=event.member.email(),
        subject="[New Event] Submitted but **not yet approved**",
        body="""This is a confirmation that your event:

%s
on %s

has been submitted to be approved. If staff is needed for your event, they
will be notified of your request. You will be notified as soon as it's
approved and on the calendar. Here is a link to the event page:

http://events.hackerdojo.com/event/%s-%s

Again, your event is NOT YET APPROVED and not on the calendar.""" % (
    event.name, 
    event.start_time.strftime('%A, %B %d'),
    event.key().id(),
    slugify(event.name),))

def notify_staff_needed(event):
    mail.send_mail(sender=FROM_ADDRESS, to=STAFF_ADDRESS,
        subject="[Event Staffing] %s on %s" % (event.name, event.start_time.strftime('%a %b %d')),
        body="""Hello staff!

Fellow member %s is sponsoring a ~%s person event:

%s
at %s to %s on %s

At %s people expected, %s staff members need to opt in to support this event.

Without your help, this event won't happen. If you can staff this event, click
the Staff button once logged in on this page:

http://events.hackerdojo.com/event/%s-%s
""" % (
    event.member.email(),
    event.estimated_size,
    event.name,
    event.start_time.strftime('%I:%M%p'),
    event.end_time.strftime('%I:%M%p'),
    event.start_time.strftime('%A, %B %d'),
    event.estimated_size,
    event.staff_needed(),
    event.key().id(),
    slugify(event.name),))

def notify_new_event(event):
    mail.send_mail(sender=FROM_ADDRESS, to=NEW_EVENT_ADDRESS,
        subject="[New Event] %s on %s" % (event.name, event.start_time.strftime('%a %b %d')),
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

Please notify the event organizer if that is not you. You still need to be
present at the event! And remember your duties as a Hacker Dojo event sponsor.

http://events.hackerdojo.com/event/%s-%s
""" % (event.key().id(), slugify(event.name)))

def notify_owner_expiring(event):
    pass

def notify_owner_expired(event):
    pass
