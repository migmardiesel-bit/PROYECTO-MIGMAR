# forms.py (Completo y Modificado)

from django import forms
from django.contrib.auth.models import User, Group
from django.db.models import Q
from .models import (
    TareaMantenimiento, CatalogoHerramienta, 
    CatalogoMantenimientoCorrectivo, TareaPreventivaSubtask
)

class CatalogoHerramientaForm(forms.ModelForm):
    class Meta:
        model = CatalogoHerramienta
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
        }

class CatalogoMantenimientoCorrectivoForm(forms.ModelForm):
    class Meta:
        model = CatalogoMantenimientoCorrectivo
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class AsignarTareaForm(forms.ModelForm):
    # Queryset para poblar el campo 'tecnico'
    tecnico = forms.ModelChoiceField(
        queryset=User.objects.filter(
            Q(groups__name='Tecnico') | Q(groups__name='Supervisor')
        ).distinct().order_by('username'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Técnico Asignado"
    )

    class Meta:
        model = TareaMantenimiento
        fields = [
            'tecnico', 'unidad', 'tipo_mantenimiento', 
            'prioridad', 
            'mantenimiento_correctivo', 'notas_admin'
        ]
        widgets = {
            'unidad': forms.Select(attrs={'class': 'form-select'}),
            'tipo_mantenimiento': forms.Select(attrs={'class': 'form-select'}),
            'prioridad': forms.Select(attrs={'class': 'form-select'}), 
            'mantenimiento_correctivo': forms.Select(attrs={'class': 'form-select'}),
            'notas_admin': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El campo de mant. correctivo no es requerido por defecto
        self.fields['mantenimiento_correctivo'].required = False
        
        # Opcional: Si quieres que las unidades se carguen con Select2
        # (requiere JS adicional en la plantilla)
        self.fields['unidad'].widget.attrs.update({'class': 'form-select select2-widget-unidad'})

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get('tipo_mantenimiento')
        correctivo = cleaned_data.get('mantenimiento_correctivo')

        if tipo == 'CORRECTIVO' and not correctivo:
            self.add_error('mantenimiento_correctivo', 
                           'Debe seleccionar una tarea específica para el mantenimiento correctivo.')
        
        return cleaned_data
class SeleccionarHerramientasForm(forms.Form):
    """
    Formulario para que el técnico seleccione las herramientas que necesita.
    """
    herramientas = forms.ModelMultipleChoiceField(
        queryset=CatalogoHerramienta.objects.all().order_by('nombre'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'id': 'select2-herramientas'}),
        required=True,
        label="Seleccionar Herramientas Requeridas"
    )
    
    def __init__(self, *args, **kwargs):
        # Recibimos la tarea para saber qué herramientas ya están seleccionadas
        self.tarea = kwargs.pop('tarea', None)
        super().__init__(*args, **kwargs)
        
        if self.tarea:
            # Marcamos las herramientas ya seleccionadas
            self.fields['herramientas'].initial = self.tarea.herramientas_solicitadas.all()


# --- ESTA CLASE FUE MODIFICADA ---

class TareaPreventivaSubtaskForm(forms.ModelForm):
    """
    Formulario para un solo item del checklist preventivo.
    """
    completada = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'form-check-input me-2'}))
    
    observaciones = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2, 'placeholder': 'Notas, mm, psi...'})
    )
    
    foto_evidencia = forms.ImageField(
        required=False, # <-- Queda siempre False
        widget=forms.ClearableFileInput(attrs={'class': 'form-control form-control-sm'})
    )

    class Meta:
        model = TareaPreventivaSubtask
        fields = ['completada', 'observaciones', 'foto_evidencia']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            # Usamos el "display name" de la subtask como la etiqueta del checkbox
            self.fields['completada'].label = self.instance.get_nombre_subtask_display()

            # --- LÓGICA DE VALIDACIÓN MODIFICADA (SE ELIMINÓ LA OBLIGATORIEDAD) ---
            
            # 1. Definimos los IDs de las tareas que SIEMPRE requieren foto
            TAREAS_SUSPENSION = [
                'susp_amortiguadores', 
                'susp_bolsa_aire', 
                'susp_bujes_muelle', 
                'susp_bujes_tirantes'
            ]
            
            # 2. Comprobamos si la instancia actual es una de ellas
            if self.instance.nombre_subtask in TAREAS_SUSPENSION:
                
                # 3. YA NO HACEMOS EL CAMPO DE FOTO OBLIGATORIO.
                # Se eliminó la línea: self.fields['foto_evidencia'].required = True
                
                # Opcional: añadimos un indicador visual a la etiqueta (ya no será "Requerido" si no es obligatorio)
                self.fields['foto_evidencia'].label = "Foto de Evidencia"
            
            # --- FIN DE LÓGICA DE VALIDACIÓN MODIFICADA ----


# Creamos un FormSet para el checklist preventivo
TareaPreventivaFormSet = forms.inlineformset_factory(
    TareaMantenimiento,
    TareaPreventivaSubtask,
    form=TareaPreventivaSubtaskForm,
    fields=('completada', 'observaciones', 'foto_evidencia'),
    extra=0, 
    can_delete=False
)