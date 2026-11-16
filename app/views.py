from datetime import datetime, time, timedelta

from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from . import canvas
from .canvas import CanvasFeedError
from .models import Student, hash_feed_url, CalendarEvent
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render


HEAT_LEVELS = [
  "bg-slate-100 text-slate-400",
  "bg-indigo-100 text-indigo-900",
  "bg-indigo-300 text-indigo-950",
  "bg-indigo-500 text-white",
  "bg-indigo-700 text-white",
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
    # Done items due in the last week or later, so they don't clutter the main list
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