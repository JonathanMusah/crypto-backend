from django import forms
from .models import Settings


class AdminMomoDetailsWidget(forms.Widget):
    """Custom widget for admin_momo_details JSONField to make it easier to edit"""
    template_name = 'admin/analytics/admin_momo_details_widget.html'
    
    class Media:
        css = {
            'all': ('admin/css/admin_momo_details.css',)
        }
        js = ('admin/js/admin_momo_details.js',)
    
    def format_value(self, value):
        """Format the JSON value for display"""
        if isinstance(value, dict) and value:
            # Convert dict to list format for easier editing
            return list(value.items())
        return []
    
    def value_from_datadict(self, data, files, name):
        """Convert form data back to JSON dict format"""
        momo_details = {}
        i = 0
        while True:
            key = data.get(f'{name}_{i}_key', '').strip()
            provider = data.get(f'{name}_{i}_provider', '').strip()
            number = data.get(f'{name}_{i}_number', '').strip()
            momo_name = data.get(f'{name}_{i}_name', '').strip()
            
            if not key and not provider and not number:
                break  # No more entries
            
            if provider and number:
                # Use a unique key if not provided
                if not key:
                    key = f"momo_{i+1}"
                
                momo_details[key] = {
                    'provider': provider,
                    'number': number,
                }
                if momo_name:
                    momo_details[key]['name'] = momo_name
            i += 1
        
        return momo_details


class SettingsAdminForm(forms.ModelForm):
    """Custom form for Settings to use custom widget for admin_momo_details"""
    
    class Meta:
        model = Settings
        fields = '__all__'
        widgets = {
            'admin_momo_details': forms.Textarea(attrs={
                'rows': 10,
                'cols': 80,
                'style': 'font-family: monospace;',
                'placeholder': '{\n  "momo_1": {\n    "provider": "MTN",\n    "number": "0241234567",\n    "name": "Admin Name"\n  },\n  "momo_2": {\n    "provider": "Vodafone",\n    "number": "0209876543",\n    "name": "Admin Name"\n  }\n}'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add help text for admin_momo_details
        if 'admin_momo_details' in self.fields:
            self.fields['admin_momo_details'].help_text = (
                'Enter MoMo details in JSON format. Example:\n'
                '{\n'
                '  "momo_1": {\n'
                '    "provider": "MTN",\n'
                '    "number": "0241234567",\n'
                '    "name": "Admin Name"\n'
                '  },\n'
                '  "momo_2": {\n'
                '    "provider": "Vodafone",\n'
                '    "number": "0209876543",\n'
                '    "name": "Admin Name"\n'
                '  }\n'
                '}'
            )

