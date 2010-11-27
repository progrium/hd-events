from google.appengine.ext import webapp
register = webapp.template.create_template_register()

@register.filter
def check_filter(the_list, item):
    if item in the_list:
        cb = "checked='checked'"
    else:
        cb = ""
    return cb
    
@register.filter
def select_hour(event, item):
    return select_time(event,item,'hour')

@register.filter
def select_minute(event, item):
    return select_time(event,item,'minute')

@register.filter
def select_ampm(event, item):
    return select_time(event,item,'ampm')

# event = event timestamp
# item = UI element value (e.g., the specific hour or minute to compare)
# element = hour, minute, ampm
def select_time(event,item,element):
    st = ""
    if element == 'hour':
        eh = event.hour if event.hour < 12 else event.hour - 12
        if eh == item:
            st = "selected='selected'"
    if element == 'minute' and event.minute == item:
        st = "selected='selected'"
    if element == 'ampm':
        half = "am" if event.hour < 12 else "pm"
        if half == item:
            st = "selected='selected'"
    return st