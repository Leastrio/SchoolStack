import hashlib
from django.db import models
import zlib

def hash_feed_url(url):
  return hashlib.sha256(url.encode("utf-8")).hexdigest()

class Student(models.Model):
  ical_url = models.URLField(max_length=500)
  url_hash = models.CharField(max_length=64, unique=True)
  last_synced = models.DateTimeField(null=True, blank=True)
  created_at = models.DateTimeField(auto_now_add=True)

COURSE_COLORS = [
  "#3b82f6",  # blue
  "#10b981",  # green
  "#f59e0b",  # amber
  "#ef4444",  # red
  "#8b5cf6",  # purple
  "#ec4899",  # pink
  "#14b8a6",  # teal
  "#f97316",  # orange
]

class Course(models.Model):
  student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="courses")
  code = models.CharField(max_length=100)   # "CS 3300"
  name = models.CharField(max_length=200)   # "2026Fa CS 3300 001"

  class Meta:
    constraints = [
      models.UniqueConstraint(fields=["student", "name"], name="unique_course_per_student"), # There can only be one of each course for each student
    ]

  def __str__(self):
    return self.code

  @property
  def color(self): 
    return COURSE_COLORS[zlib.crc32(self.name.encode("utf-8")) % len(COURSE_COLORS)]


class CalendarEvent(models.Model):
  student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="events")
  course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="events")

  uid = models.CharField(max_length=255)
  title = models.CharField(max_length=255)
  description = models.TextField(blank=True)
  due_at = models.DateTimeField()
  all_day = models.BooleanField(default=False)
  canvas_url = models.URLField(max_length=500, blank=True)
  completed = models.BooleanField(default=False)

  class Meta:
    ordering = ["due_at"]
    constraints = [
      models.UniqueConstraint(fields=["student", "uid"], name="unique_event_per_student"),
    ]

  def __str__(self):
    return self.title
