from django import forms
from .models import EvidenceFile
from cases.models import Case

class EvidenceFileForm(forms.ModelForm):
    class Meta:
        model = EvidenceFile
        fields = ['case', 'title', 'file']
        labels = {
            'title' : 'Evidence Title'
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['case'].empty_label='Select Case'

        if user:
            self.fields['case'].queryset = Case.objects.filter(created_by=user)