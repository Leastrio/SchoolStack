from django.db import models

class Student(models.Model):
  ical_url = models.URLField(unique=True)
  last_synced = models.DateTimeField(null=True, blank=True)

class Course(models.Model):
  student = models.ForeignKey(Student, on_delete=models.CASCADE)
  code = models.CharField(max_length=100)
  name = models.CharField(max_length=200, blank=True)

class CalendarEvent(models.Model):
  student = models.ForeignKey(Student, on_delete=models.CASCADE)
  course = models.ForeignKey(Course, on_delete=models.CASCADE)

  uid = models.CharField(max_length=255, unique=True)
  summary = models.CharField(max_length=255)
  description = models.TextField(blank=True)
  start_time = models.DateTimeField()
  canvas_url = models.URLField(blank=True)
