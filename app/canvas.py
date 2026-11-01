import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone
from ical.calendar_stream import IcsCalendarStream
from ical.exceptions import CalendarParseError

from .models import CalendarEvent, Course

ALLOWED_HOSTS = {"canvas.uccs.edu"}
ALLOWED_HOST_SUFFIXES = (".instructure.com",)
FEED_PATH_RE = re.compile(r"^/feeds/calendars/user_[A-Za-z0-9]+\.ics$")

FETCH_TIMEOUT_SECONDS = 10
MAX_FEED_BYTES = 5 * 1024 * 1024
SYNC_INTERVAL = timedelta(minutes=15)

SUMMARY_RE = re.compile(r"^(?P<title>.*?)\s*\[(?P<course>[^\[\]]+)\]\s*$")
COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,5})(?:\s+[A-Z]{2,5})*\s+(\d{4})\b")
OTHER_COURSE = "Other"


class CanvasFeedError(Exception):
  """Something went wrong with the feed."""

@dataclass
class FeedEvent:
  uid: str
  title: str
  course_label: str
  description: str
  due_at: datetime
  all_day: bool
  canvas_url: str

# getting the ical feed

# Clean up the inputted raw url
def normalize_feed_url(raw):
  parts = urllib.parse.urlsplit(raw.strip())
  host = parts.hostname.lower()

  # Error out if invalid
  if parts.username or parts.password or (parts.port not in (None, 443)) or (parts.scheme != "https"):
    raise CanvasFeedError("That doesn't look like a Canvas calendar feed URL.")
  if host not in ALLOWED_HOSTS and not host.endswith(ALLOWED_HOST_SUFFIXES):
    raise CanvasFeedError("Only Canvas calendar feeds are supported.")
  if not FEED_PATH_RE.match(parts.path):
    raise CanvasFeedError("That doesn't look like a calendar feed. In Canvas, open Calendar and click \"Calendar Feed\" to copy it.")

  return f"https://{host}{parts.path}"

class _NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self, req, fp, code, msg, headers, newurl):
    return None

# send a get request to the parsed ical url and return the response text
def fetch_feed(url):
  opener = urllib.request.build_opener(_NoRedirect)
  request = urllib.request.Request(url, headers={"User-Agent": "SchoolStack/0.1"})
  try:
    with opener.open(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
      data = response.read(MAX_FEED_BYTES + 1)
  except urllib.error.HTTPError as e:
    if e.code in (401, 403, 404):
      raise CanvasFeedError("Canvas didn't recognize that calendar URL. Copy it again from Canvas → Calendar → Calendar Feed.") from e
    raise CanvasFeedError(f"Canvas returned an error ({e.code}). Try again in a minute.") from e
  except (urllib.error.URLError, TimeoutError, OSError) as e:
    raise CanvasFeedError("Couldn't reach Canvas. Try again in a minute.") from e

  if len(data) > MAX_FEED_BYTES:
    raise CanvasFeedError("That calendar feed is too large.")
  text = data.decode("utf-8", errors="replace")
  if "BEGIN:VCALENDAR" not in text:
    raise CanvasFeedError("Canvas didn't send back a calendar. Check the URL and try again.")
  return text

# parsing logic

# Split the summary text into the title and label
def split_summary(summary):
  match = SUMMARY_RE.match(summary)
  if match and match.group("title"):
    return match.group("title"), match.group("course").strip()
  return summary.strip(), OTHER_COURSE

# parse the short course code
def short_course_code(label):
  match = COURSE_CODE_RE.search(label)
  return f"{match.group(1)} {match.group(2)}" if match else label

# convert date to a datetime
def to_due_at(dtstart, local_tz):
  if isinstance(dtstart, datetime):
    if dtstart.tzinfo is None:
      dtstart = dtstart.replace(tzinfo=local_tz)
    return dtstart, False
    
  return datetime.combine(dtstart, time(23, 59), tzinfo=local_tz), True

# parse the ical data into events
def parse_feed(text, local_tz=None):
  local_tz = local_tz or timezone.get_default_timezone()
  try:
    calendar = IcsCalendarStream.calendar_from_ics(text)
  except CalendarParseError as e:
    raise CanvasFeedError("Canvas sent a calendar we couldn't read. Try again later.") from e

  events = []
  for event in calendar.events:
    if not event.uid or event.dtstart is None:
      continue
    due_at, all_day = to_due_at(event.dtstart, local_tz)
    title, course_label = split_summary(event.summary or "Untitled")
    events.append(FeedEvent(
      uid=event.uid.strip()[:255],
      title=title[:255],
      course_label=course_label[:200],
      description=(event.description or "").strip(),
      due_at=due_at,
      all_day=all_day,
      canvas_url=str(event.url or "").strip()[:500],
    ))
  return events

# saving feed to db

# save the event feed to the db
@transaction.atomic
def apply_feed(student, events):
  courses = {}
  seen_uids = []

  for event in events:
    course = courses.get(event.course_label)
    if course is None:
      course, _ = Course.objects.update_or_create(
        student=student,
        name=event.course_label,
        defaults={"code": short_course_code(event.course_label)},
      )
      courses[event.course_label] = course

    CalendarEvent.objects.update_or_create(
      student=student,
      uid=event.uid,
      defaults={
        "course": course,
        "title": event.title,
        "description": event.description,
        "due_at": event.due_at,
        "all_day": event.all_day,
        "canvas_url": event.canvas_url,
      },
    )
    seen_uids.append(event.uid)

  CalendarEvent.objects.filter(student=student).exclude(uid__in=seen_uids).delete()
  Course.objects.filter(student=student, events__isnull=True).delete()

  student.last_synced = timezone.now()
  student.save(update_fields=["last_synced"])

# fetch the ical data, parse the feed, and then apply to the db
def sync_student(student):
  events = parse_feed(fetch_feed(student.ical_url))
  apply_feed(student, events)

# check if student needs a sync
def needs_sync(student):
  return student.last_synced is None or timezone.now() - student.last_synced > SYNC_INTERVAL
