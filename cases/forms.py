from django import forms
from .models import Case
from django.contrib.auth.forms import PasswordChangeForm

class CaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ['title', 'description', 'status','case_type']

class CustomPasswordChangeForm(PasswordChangeForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({
                "class": "w-full bg-gray-900 border border-gray-700 rounded-lg p-3 text-white focus:border-cyan-500 focus:outline-none"
            })