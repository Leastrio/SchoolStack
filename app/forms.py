from django import forms

INPUT = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"

class NotesForm(forms.Form):
  notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"class": INPUT, "rows": 5,
                          "placeholder": "Enter notes here"}))
