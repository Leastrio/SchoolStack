import calendar
import uuid
from datetime import date, datetime, time, timedelta

from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib.humanize.templatetags.humanize import naturaltime
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Count, Q

from . import canvas
from .canvas import CanvasFeedError
from .forms import NotesForm, TaskForm, GradeForm
from .models import PERSONAL_COURSE, CalendarEvent, Course, Student, calculate_gpa, hash_feed_url

HEAT_LEVELS = [
  "bg-white text-gray-400",
  "bg-sky-100",
  "bg-sky-200",
  "bg-sky-300",
  "bg-sky-400",
]
HEATMAP_DAYS = 14

def current_student(req):
  if not hasattr(req, "_student"):
    student_id = req.session.get("student_id")
    req._student = Student.objects.filter(pk=student_id).first() if student_id else None
  return req._student

def day_start(d):
  return timezone.make_aware(datetime.combine(d, time.min))

def week_progress(student, today):
  monday = today - timedelta(days=today.weekday())
  week = student.events.filter(due_at__gte=day_start(monday), due_at__lt=day_start(monday + timedelta(days=7)))
  total = week.count()
  done = week.filter(completed=True).count()
  return {"done": done, "total": total, "percent": round(done * 100 / total) if total else 0}

def local_date(dt):
  return timezone.localtime(dt).date()

def workload_heatmap(student, today):
  start = day_start(today)
  end = day_start(today + timedelta(days=HEATMAP_DAYS))
  counts = {}
  for due_at in student.events.filter(completed=False, due_at__gte=start, due_at__lt=end).values_list("due_at", flat=True):
    d = local_date(due_at)
    counts[d] = counts.get(d, 0) + 1

  days = []
  for i in range(HEATMAP_DAYS):
    d = today + timedelta(days=i)
    count = counts.get(d, 0)
    days.append({"date": d, "count": count, "classes": HEAT_LEVELS[min(count, len(HEAT_LEVELS) - 1)]})
  return days

@require_http_methods(["GET", "POST"])
def connect(req):
  if req.method == "GET":
    if current_student(req):
      return redirect("dashboard")
    return render(req, "app/connect.html")

  try:
    url = canvas.normalize_feed_url(req.POST.get("ical_url", ""))
    events = canvas.parse_feed(canvas.fetch_feed(url))
  except CanvasFeedError as e:
    return render(req, "app/connect.html", {"error": str(e)}, status=400)

  student, _ = Student.objects.get_or_create(url_hash=hash_feed_url(url), defaults={"ical_url": url})
  canvas.apply_feed(student, events)

  req.session.cycle_key()
  req.session["student_id"] = student.pk
  return redirect("dashboard")

def dashboard(req):
  student = current_student(req)
  if student is None:
    return redirect("connect")

  sync_error = req.session.pop("sync_error", None)
  if canvas.needs_sync(student):
    try:
      canvas.sync_student(student)
    except CanvasFeedError as e:
      sync_error = str(e)

  now = timezone.now()
  today = timezone.localdate()
  events = student.events.select_related("course")
  upcoming = events.filter(completed=False, due_at__gte=now)
  overdue = events.filter(completed=False, due_at__lt=now)

  return render(req, "app/dashboard.html", {
    "student": student,
    "sync_error": sync_error,
    "overdue": overdue,
    "overdue_count": overdue.count(),
    "upcoming": upcoming[:10],
    "due_next_7_days": upcoming.filter(due_at__lt=now + timedelta(days=7)).count(),
    "recently_done": events.filter(completed=True, due_at__gte=now - timedelta(days=7)),
    "progress": week_progress(student, today),
    "heatmap": workload_heatmap(student, today),
  })

@require_POST
def sync(req):
  student = current_student(req)
  if student is None:
    return redirect("connect")
  try:
    canvas.sync_student(student)
  except CanvasFeedError as e:
    req.session["sync_error"] = str(e)
  return redirect("dashboard")

#For completion of assignments
@require_POST
def toggle_event_completion(req, event_id):
  student = current_student(req)
  if student is None:
    return JsonResponse({"error": "Not connected"}, status = 401)
  event = get_object_or_404(CalendarEvent, pk=event_id, student=student)
  event.completed = not event.completed
  event.save(update_fields=["completed"])
  return JsonResponse({"completed": event.completed})

@require_POST
def logout(req):
  req.session.flush()
  return redirect("connect")

@require_POST
def forget_me(req):
  student = current_student(req)
  if student is not None:
    student.delete()
  req.session.flush()
  return redirect("connect")

@require_http_methods(["GET", "POST"])
def event_detail(req, event_id):
  """One assignment: Canvas details plus the student's own notes."""
  student = current_student(req)
  if student is None:
    return redirect("connect")
  event = get_object_or_404(CalendarEvent.objects.select_related("course"), pk=event_id, student=student)

  if req.method == "POST":
    form = NotesForm(req.POST)
    if form.is_valid():
      event.notes = form.cleaned_data["notes"].strip()
      event.save(update_fields=["notes"])
      return redirect(f"{req.path}?saved=1")
  else:
    form = NotesForm(initial={"notes": event.notes})

  return render(req, "app/event_detail.html", {
    "event": event,
    "form": form,
    "saved": req.GET.get("saved") == "1",
  })


def redirect_back(req, default):
  nxt = req.POST.get("next") or req.GET.get("next")
  if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={req.get_host()}, require_https=req.is_secure()):
    return redirect(nxt)
  return redirect(default)

@require_http_methods(["GET", "POST"])
def add_task(req):
  student = current_student(req)
  if student is None:
    return redirect("connect")

  if req.method == "POST":
    form = TaskForm(req.POST, student=student)
    if form.is_valid():
      data = form.cleaned_data
      course = data["course"]
      if course is None:
        course, _ = Course.objects.get_or_create(student=student, name=PERSONAL_COURSE, defaults={"code": PERSONAL_COURSE})
      due_time = data["due_time"]
      CalendarEvent.objects.create(
        student=student,
        course=course,
        uid=f"custom-{uuid.uuid4().hex}",
        title=data["title"].strip(),
        notes=data["notes"].strip(),
        due_at=timezone.make_aware(datetime.combine(data["due_date"], due_time or time(23, 59))),
        all_day=due_time is None,
        is_custom=True,
      )
      return redirect_back(req, "dashboard")
  else:
    form = TaskForm(student=student, initial={"course": req.GET.get("course"), "due_date": timezone.localdate()})

  nxt = req.POST.get("next") or req.GET.get("next") or ""
  if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={req.get_host()}, require_https=req.is_secure()):
    nxt = ""
  return render(req, "app/task_form.html", {"form": form, "next": nxt})

@require_POST
def delete_task(req, event_id):
  student = current_student(req)
  if student is None:
    return redirect("connect")
  event = get_object_or_404(CalendarEvent, pk=event_id, student=student, is_custom=True)
  event.delete()
  return redirect("dashboard")


def calendar_view(req):
  student = current_student(req)
  if student is None:
    return redirect("connect")

  today = timezone.localdate()
  try:
    year, month = (int(part) for part in req.GET.get("month", "").split("-"))
    first = date(year, month, 1)
  except ValueError:
    first = today.replace(day=1)

  # Full weeks (Sunday first) covering the month, including spill-over days from next/previous months
  weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(first.year, first.month)
  start, end = day_start(weeks[0][0]), day_start(weeks[-1][-1] + timedelta(days=1))

  by_day = {}
  for event in student.events.filter(due_at__gte=start, due_at__lt=end).select_related("course"):
    by_day.setdefault(local_date(event.due_at), []).append(event)

  prev_month = (first - timedelta(days=1)).replace(day=1)
  next_month = (first + timedelta(days=32)).replace(day=1)

  return render(req, "app/calendar.html", {
    "month": first,
    "weeks": [
      [{"date": d, "in_month": d.month == first.month, "is_today": d == today, "events": by_day.get(d, [])} for d in week]
      for week in weeks
    ],
    "weekday_names": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    "prev_month": prev_month.strftime("%Y-%m"),
    "next_month": next_month.strftime("%Y-%m"),
    "this_month": today.strftime("%Y-%m"),
  })


def course_list(req):
  student = current_student(req)
  if student is None:
    return redirect("connect")

  now = timezone.now()
  courses = student.courses.annotate(
    total=Count("events"),
    done=Count("events", filter=Q(events__completed=True)),
    overdue=Count("events", filter=Q(events__completed=False, events__due_at__lt=now)),
    remaining=Count("events", filter=Q(events__completed=False, events__due_at__gte=now)),
  )
  return render(req, "app/courses.html", {"courses": courses})

def course_detail(req, course_id):
  student = current_student(req)
  if student is None:
    return redirect("connect")
  course = get_object_or_404(Course, pk=course_id, student=student)

  now = timezone.now()
  events = course.events.select_related("course")
  total = events.count()
  done = events.filter(completed=True).count()
  return render(req, "app/course_detail.html", {
    "course": course,
    "upcoming": events.filter(due_at__gte=now),
    # Most recent first for past work
    "past": events.filter(due_at__lt=now).order_by("-due_at"),
    "total": total,
    "done": done,
    "percent": round(done * 100 / total) if total else 0,
  })


def alert_events(student):
  now = timezone.now()
  open_events = student.events.filter(completed=False).select_related("course")
  overdue = open_events.filter(due_at__lt=now)
  due_soon = open_events.filter(due_at__gte=now, due_at__lt=now + timedelta(hours=24))
  return overdue, due_soon

def notifications(req):
  student = current_student(req)
  if student is None:
    return redirect("connect")

  now = timezone.now()
  overdue, due_soon = alert_events(student)
  # Assignments Canvas added in the last 3 days. Skip the first hour after signing up,
  # otherwise every assignment counts as "new" on day one.
  new_since = max(now - timedelta(days=3), student.created_at + timedelta(hours=1))
  new_from_canvas = student.events.filter(is_custom=False, created_at__gte=new_since).select_related("course").order_by("-created_at")

  return render(req, "app/notifications.html", {
    "overdue": overdue,
    "due_soon": due_soon,
    "new_from_canvas": new_from_canvas,
  })


def notifications_check(req):
  student = current_student(req)
  if student is None:
    return JsonResponse({"error": "Not connected"}, status=401)
  overdue, due_soon = alert_events(student)
  items = []
  # Due-soon first: it's the one you can still do something about
  for event in list(due_soon) + list(overdue):
    items.append({
      "id": event.pk,
      "title": event.title,
      "course": event.course.code,
      "overdue": event.is_overdue,
      "when": naturaltime(event.due_at),  # "in 3 hours" / "2 days ago"
      "url": reverse("event_detail", args=[event.pk]),
    })
  return JsonResponse({"items": items})


@require_http_methods(["GET", "POST"])
def gpa(req):
  student = current_student(req)
  if student is None:
    return redirect("connect")

  if req.method == "POST":
    form = GradeForm(req.POST)
    if form.is_valid():
      entry = form.save(commit=False)
      entry.student = student
      entry.save()
      return redirect_back(req, "gpa")
  else:
    form = GradeForm()

  grades = list(student.grades.all())
  return render(req, "app/gpa.html", {
    "form": form,
    "grades": grades,
    "gpa": calculate_gpa(grades),
    "total_credits": sum(g.credits for g in grades),
  })

@require_POST
def delete_grade(req, grade_id):
  student = current_student(req)
  if student is None:
    return redirect("connect")
  deleted, _ = student.grades.filter(pk=grade_id).delete()
  if not deleted:
    raise Http404
  return redirect_back(req, "gpa")