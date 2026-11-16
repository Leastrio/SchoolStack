from decimal import Decimal
from django import forms
from .models import Course, GradeEntry

INPUT = "w-full rounded-lg border bg-white px-3 py-2 focus:outline-none focus:ring-2 focus:ring-black/20"

class NotesForm(forms.Form):
  notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": INPUT, "rows": 5,
                          "placeholder": "Enter notes here"}))

class TaskForm(forms.Form):
  title = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": INPUT, "placeholder": "Study for midterm"}))
  due_date = forms.DateField(widget=forms.DateInput(attrs={"class": INPUT, "type": "date"}))
  due_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"class": INPUT, "type": "time"}),
                             help_text="Leave blank for end of day.")
  course = forms.ModelChoiceField(queryset=Course.objects.none(), required=False, empty_label="Personal",
                                  widget=forms.Select(attrs={"class": INPUT}))
  notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": INPUT, "rows": 3}))

  def __init__(self, *args, student, **kwargs):
    super().__init__(*args, **kwargs)
    # Only let students pick their own courses
    self.fields["course"].queryset = student.courses.all()

class GradeForm(forms.ModelForm):
  class Meta:
    model = GradeEntry
    fields = ["course_name", "credits", "grade"]
    widgets = {
      "course_name": forms.TextInput(attrs={"class": INPUT, "placeholder": "Course name", "list": "course-options"}),
      "credits": forms.NumberInput(attrs={"class": INPUT, "placeholder": "Credits", "step": "0.5", "min": "0.5", "max": "10"}),
      "grade": forms.Select(attrs={"class": INPUT}),
    }

  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.fields["grade"].choices = [("", "Grade")] + list(self.fields["grade"].choices)[1:]

  def clean_credits(self):
    credits = self.cleaned_data["credits"]
    if credits <= 0 or credits > Decimal("10"):
      raise forms.ValidationError("Credits must be between 0.5 and 10.")
    return credits