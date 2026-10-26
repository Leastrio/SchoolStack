from django.urls import path
from . import views

urlpatterns = [
  path("", views.dashboard, name="dashboard"),
  path("connect/", views.connect, name="connect"),
  path("sync/", views.sync, name="sync"),
  path("logout/", views.logout, name="logout"),
  path("forget/", views.forget_me, name="forget_me"),
]
