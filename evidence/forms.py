from django import forms
from .models import EvidenceFile
from cases.models import Case

class EvidenceFileForm(forms.ModelForm):
    class Meta:
        model = EvidenceFile
        fields = ['case', 'title', 'file']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['case'].queryset = Case.objects.filter(created_by=user)