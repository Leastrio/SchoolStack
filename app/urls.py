from django.urls import path

from . import views

urlpatterns = [
  path("", views.dashboard, name="dashboard"),
  path("connect/", views.connect, name="connect"),
  path("sync/", views.sync, name="sync"),
  path("logout/", views.logout, name="logout"),
  path("forget/", views.forget_me, name="forget_me"),
  path("event/<int:event_id>/", views.event_detail, name="event_detail"),
  path(
    "event/<int:event_id>/toggle/",
    views.toggle_event_completion,
    name="toggle_event",
  ),
  path("event/<int:event_id>/delete/", views.delete_task, name="delete_task"),
  path("tasks/new/", views.add_task, name="add_task"),
  path("calendar/", views.calendar_view, name="calendar"),
  path("courses/", views.course_list, name="courses"),
  path("courses/<int:course_id>/", views.course_detail, name="course_detail"),
  path("notifications/", views.notifications, name="notifications"),
  path("notifications/check/", views.notifications_check, name="notifications_check"),
  path("gpa/", views.gpa, name="gpa"),
  path("gpa/<int:grade_id>/delete/", views.delete_grade, name="delete_grade"),
]
