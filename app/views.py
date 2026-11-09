from datetime import timedelta

from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from . import canvas
from .canvas import CanvasFeedError
from .models import Student, hash_feed_url, CalendarEvent
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render



def current_student(req):
  student_id = req.session.get("student_id")
  if student_id is None:
    return None
  return Student.objects.filter(pk=student_id).first()

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
  events = student.events.select_related("course")
  upcoming = events.filter(due_at__gte=now)

  return render(req, "app/dashboard.html", {
    "student": student,
    "sync_error": sync_error,
    "upcoming": upcoming[:10],
    "due_this_week": upcoming.filter(due_at__lt=now + timedelta(days=7)).count(),
    "past_due": events.filter(due_at__lt=now, due_at__gte=now - timedelta(days=7)).count(),
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