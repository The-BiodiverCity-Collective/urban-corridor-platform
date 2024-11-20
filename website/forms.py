from django import forms
from .models import Garden

class GardenForm(forms.ModelForm):
    class Meta:
        model = Garden
        fields = ["name", "description", "phase_assessment", "phase_alienremoval", "phase_landscaping", "phase_pioneers", "phase_birdsinsects", "phase_specialists", "phase_placemaking"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update({"class": "input"})
        self.fields["description"].widget.attrs.update({"class": "textarea"})
