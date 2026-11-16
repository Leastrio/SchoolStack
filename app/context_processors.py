from .views import current_student

def nav(req):
  student = current_student(req)
  if student is None:
    return {}
  return {"nav_student": student}
