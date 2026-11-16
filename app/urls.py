from django.urls import path
from . import views

urlpatterns = [
  path("", views.dashboard, name="dashboard"),
  path("connect/", views.connect, name="connect"),
  path("sync/", views.sync, name="sync"),
  path("logout/", views.logout, name="logout"),
  path("forget/", views.forget_me, name="forget_me"),
  path("event/<int:event_id>/", views.event_detail, name="event_detail"),
  path("event/<int:event_id>/toggle/", views.toggle_event_completion, name="toggle_event"),
  path("event/<int:event_id>/delete/", views.delete_task, name="delete_task"),
  path("tasks/new/", views.add_task, name="add_task"),
]
