from django import forms
from .models import Course

INPUT = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"

class NotesForm(forms.Form):
  notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": INPUT, "rows": 5,
                          "placeholder": "Enter notes here"}))

class TaskForm(forms.Form):
  title = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": INPUT, "placeholder": "Study for midterm"}))
  due_date = forms.DateField(widget=forms.DateInput(attrs={"class": INPUT, "type": "date"}))
  due_time = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"class": INPUT, "type": "time"}),
                             help_text="Leave blank for end of day.")
  course = forms.ModelChoiceField(queryset=Course.objects.none(), required=False, empty_label="Personal (no class)",
                                  widget=forms.Select(attrs={"class": INPUT}))
  notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": INPUT, "rows": 3}))

  def __init__(self, *args, student, **kwargs):
    super().__init__(*args, **kwargs)
    # Only let students pick their own courses
    self.fields["course"].queryset = student.courses.all()
