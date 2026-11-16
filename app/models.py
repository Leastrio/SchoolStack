import hashlib
from django.db import models
from django.utils import timezone
import zlib
from decimal import Decimal

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

PERSONAL_COURSE = "Personal"

class Course(models.Model):
  student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="courses")
  code = models.CharField(max_length=100)   # "CS 3300"
  name = models.CharField(max_length=200)   # "2026Fa CS 3300 001"

  class Meta:
    ordering = ["code"]
    constraints = [
      models.UniqueConstraint(fields=["student", "name"], name="unique_course_per_student"), # There can only be one of each course for each student
    ]

  def __str__(self):
    return self.code

  @property
  def color(self):
    if self.name == PERSONAL_COURSE:
      return "#64748b"  # slate
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
  notes = models.TextField(blank=True)
  is_custom = models.BooleanField(default=False)
  created_at = models.DateTimeField(default=timezone.now, editable=False)
  description_html = models.TextField(blank=True)

  class Meta:
    ordering = ["due_at"]
    constraints = [
      models.UniqueConstraint(fields=["student", "uid"], name="unique_event_per_student"),
    ]

  def __str__(self):
    return self.title

  @property
  def is_overdue(self):
    return not self.completed and self.due_at < timezone.now()

GRADE_POINTS = {
  "A": Decimal("4.0"), "A-": Decimal("3.7"),
  "B+": Decimal("3.3"), "B": Decimal("3.0"), "B-": Decimal("2.7"),
  "C+": Decimal("2.3"), "C": Decimal("2.0"), "C-": Decimal("1.7"),
  "D+": Decimal("1.3"), "D": Decimal("1.0"), "D-": Decimal("0.7"),
  "F": Decimal("0.0"),
}

class GradeEntry(models.Model):
  student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="grades")
  course_name = models.CharField(max_length=100)
  credits = models.DecimalField(max_digits=3, decimal_places=1)
  grade = models.CharField(max_length=2, choices=[(g, g) for g in GRADE_POINTS])

  class Meta:
    ordering = ["course_name"]

  def __str__(self):
    return f"{self.course_name}: {self.grade}"

  @property
  def points(self):
    return GRADE_POINTS[self.grade]


def calculate_gpa(entries):
  total_credits = sum((e.credits for e in entries), Decimal("0"))
  if total_credits == 0:
    return None
  total_points = sum((e.points * e.credits for e in entries), Decimal("0"))
  return round(total_points / total_credits, 2)