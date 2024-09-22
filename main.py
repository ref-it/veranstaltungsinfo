import caldav, jinja2, json, pathlib, smtplib
from datetime import datetime, timedelta, time
from babel.dates import format_date
from operator import itemgetter
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from htmlmin.minify import html_minify

# Read configuration files
with open('config/config.json', 'r') as file:
    config = json.load(file)

with open('config/calendars.json', 'r') as file:
    calendars = json.load(file)

# Get date of next monday
today = datetime.combine(datetime.today(), time(0,0))
days_ahead = config['start_day'] - today.weekday()

if days_ahead <= 0:
    days_ahead += 7

next_monday = today + timedelta(days=days_ahead)

# Set empty lists for events
all_events = []
all_events_sorted = []

# Iterate over all calendars and find events
for calendar_url in calendars:
    client = caldav.DAVClient(calendar_url)
    calendar_data = client.principal().calendar()
    events = calendar_data.date_search(next_monday, next_monday + timedelta(days=10)) # timedelta komisch, aber klappt scheinbar nur so

    for event in events:
        event.load()
        e = event.instance.vevent

        if (e.status.value == "CONFIRMED"):
            event_data = {
                "title": e.summary.value,
                "date": e.dtstart.value,
                "date_de": format_date(e.dtstart.value, "EEEE, dd.MM.yyyy", locale='de'),
                "date_en": format_date(e.dtstart.value, "EEEE, yyyy-MM-dd", locale='en'),
                "time": e.dtstart.value.strftime("%H:%M"),
                "location": e.location.value,
            }

            if 'description' in e.contents.keys():
                event_data['description'] = e.description.value

            all_events.append(event_data)
        
# Sort events by date
all_events_sorted = sorted(all_events, key=itemgetter('date'))

# Group events by day
events_of_day = []
all_events_by_day = []
last_date = next_monday

for event in all_events_sorted:
    current_date = event['date'].strftime("%Y-%m-%d")

    if (current_date == last_date):
        events_of_day.append(event)
    else:
        if (len(events_of_day) != 0):
            all_events_by_day.append(events_of_day)
        events_of_day = []
        events_of_day.append(event)

    last_date = current_date

# Compose the email headers and contents
message = MIMEMultipart('alternative')
message['Subject'] = config['subject_de'] + " | " + config['subject_en']
message['From'] = formataddr(('Veranstaltungsinfo | Studierendenrat Ilmenau', config['sender']['address']))
message['To'] = config['recipient']
message['message-id'] = make_msgid(domain=config['sender']['address'].split("@",1)[1])
message['Content-Transfer-Encoding'] = "base64"
message['MIME-Version'] = "1.0"
message['Date'] = formatdate(localtime=True)

template_txt = jinja2.Template(pathlib.Path("templates/template.txt").read_text())
template_html = jinja2.Template(pathlib.Path("templates/template.html").read_text())

message.attach(MIMEText(template_txt.render(events=all_events_by_day, subject_de=config['subject_de'], subject_en=config['subject_en']), 'plain'))

html_rendered = template_html.render(events=all_events_by_day, subject_de=config['subject_de'], subject_en=config['subject_en'])
html_minified = html_minify(html_rendered)
message.attach(MIMEText(html_minified, 'html'))

# Send the email
smtp = smtplib.SMTP(config['sender']['server'], config['sender']['port'])
smtp.starttls()
smtp.login(config['sender']['address'], config['sender']['password'])
smtp.sendmail(config['sender']['address'], config['recipient'], message.as_string())
smtp.quit()