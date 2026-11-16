from .views import alert_events, current_student


def nav(req):
  student = current_student(req)
  if student is None:
    return {}
  overdue, due_soon = alert_events(student)
  return {
    "nav_student": student,
    "alert_count": overdue.count() + due_soon.count(),
  }
