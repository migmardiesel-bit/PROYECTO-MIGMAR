# flota/forms.py
from django import forms
from .models import (
    Unidad, Operador, CargaDiesel, CargaAceite, CargaUrea, CompraSuministro, 
    ChecklistInspeccion, LlantasInspeccion, LlantaDetalle
)
from django.core.exceptions import ValidationError
from django.db.models import Sum

class UnidadForm(forms.ModelForm):
    class Meta:
        model = Unidad
        fields = '__all__'

class OperadorForm(forms.ModelForm):
    class Meta:
        model = Operador
        fields = '__all__'

class CargaDieselForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        self.unidad_instance = kwargs.pop('unidad', None)
        
        if 'instance' in kwargs and kwargs['instance']:
            self.unidad_instance = kwargs['instance'].unidad

        super().__init__(*args, **kwargs)

        if self.unidad_instance and self.unidad_instance.tipo == 'S':
            if 'lts_thermo' in self.fields:
                del self.fields['lts_thermo']
            if 'hrs_thermo' in self.fields:
                del self.fields['hrs_thermo']
        
        if user and user.groups.filter(name='Tecnico').exists():
            if 'unidad' in self.fields:
                self.fields['unidad'].disabled = True

        if 'cinchos_anteriores' in self.fields:
            self.fields['cinchos_anteriores'].required = False
            if self.unidad_instance:
                ya_existen_cinchos = CargaDiesel.objects.filter(
                    unidad=self.unidad_instance
                ).exclude(cinchos_actuales__exact='').exists()
                if ya_existen_cinchos:
                    self.fields['cinchos_anteriores'].widget.attrs['readonly'] = True
                    self.fields['cinchos_anteriores'].widget.attrs['class'] = 'form-control-plaintext'


    def clean(self):
        cleaned_data = super().clean()

        if not self.instance.pk:
            lts_a_cargar = cleaned_data.get('lts_diesel', 0) or 0
            thermo_a_cargar = cleaned_data.get('lts_thermo', 0) or 0
            total_a_cargar = lts_a_cargar + thermo_a_cargar

            if total_a_cargar > 0:
                total_comprado = CompraSuministro.objects.filter(tipo_suministro='DIESEL').aggregate(total=Sum('litros_restantes'))['total'] or 0
                if total_a_cargar > total_comprado:
                    raise ValidationError(
                        f"No se puede cargar {total_a_cargar} L de diésel. "
                        f"Solo hay {total_comprado:.2f} L disponibles en el inventario."
                    )
        
        unidad = self.unidad_instance or cleaned_data.get('unidad')
        if not unidad: return cleaned_data
        ultima_carga = CargaDiesel.objects.filter(unidad=unidad).order_by('-fecha').first()
        if ultima_carga:
            km_actual_form = cleaned_data.get('km_actual')
            if km_actual_form is not None and km_actual_form <= ultima_carga.km_actual:
                self.add_error('km_actual', f"El kilometraje debe ser mayor al último registrado ({ultima_carga.km_actual} km).")
            
            hrs_thermo_form = cleaned_data.get('hrs_thermo')
            if hrs_thermo_form is not None and ultima_carga.hrs_thermo is not None and hrs_thermo_form <= ultima_carga.hrs_thermo:
                self.add_error('hrs_thermo', f"Las horas del thermo deben ser mayores a las últimas registradas ({ultima_carga.hrs_thermo} hrs).")
        return cleaned_data

    def clean_cinchos_actuales(self):
        cinchos_actuales = self.cleaned_data.get('cinchos_actuales')
        if cinchos_actuales:
            if CargaDiesel.objects.filter(cinchos_actuales=cinchos_actuales).exists():
                raise ValidationError("Este número de cincho ya ha sido registrado. No se puede repetir.")
        return cinchos_actuales

    class Meta:
        model = CargaDiesel
        fields = '__all__'
        exclude = ['fecha', 'rendimiento', 'costo'] 
        widgets = {
            'unidad': forms.Select(attrs={'class': 'form-control'}),
            'operador': forms.Select(attrs={'class': 'form-control'}),
        }
        
class CargaAceiteForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        if not self.instance.pk:
            cantidad_a_cargar = cleaned_data.get('cantidad', 0) or 0
            if cantidad_a_cargar > 0:
                total_comprado = CompraSuministro.objects.filter(tipo_suministro='ACEITE').aggregate(total=Sum('litros_restantes'))['total'] or 0
                if cantidad_a_cargar > total_comprado:
                    raise ValidationError(
                        f"No se puede cargar {cantidad_a_cargar} L de aceite. "
                        f"Solo hay {total_comprado:.2f} L disponibles en el inventario."
                    )
        return cleaned_data

    class Meta:
        model = CargaAceite
        fields = '__all__'
        exclude = ['fecha']

class CargaUreaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'unidad' in self.fields:
            self.fields['unidad'].disabled = True

    def clean_litros_cargados(self):
        # --- LÓGICA MEJORADA ---
        # Obtenemos la cantidad que se quiere cargar desde el formulario
        cantidad_a_cargar = self.cleaned_data.get('litros_cargados', 0) or 0

        if cantidad_a_cargar > 0:
            # Calculamos el inventario actual usando el mismo método FIFO del modelo.
            # Esto asegura que la validación sea consistente.
            compras_disponibles = CompraSuministro.objects.filter(
                tipo_suministro='UREA', litros_restantes__gt=0
            ).aggregate(total=Sum('litros_restantes'))['total'] or 0
            
            inventario_actual = compras_disponibles

            # Si se intenta cargar más de lo que hay, lanzamos un error claro.
            if cantidad_a_cargar > inventario_actual:
                raise ValidationError(
                    f"No se puede cargar {cantidad_a_cargar} L de urea. "
                    f"Solo hay {inventario_actual:.2f} L disponibles en el inventario."
                )
        
        return cantidad_a_cargar
        # --- FIN DE LA LÓGICA ---

    class Meta:
        model = CargaUrea
        fields = '__all__'
        exclude = ['fecha', 'rendimiento', 'costo']

# Define la capacidad máxima (en litros) de los tanques de almacenamiento.
MAX_CAPACIDAD_DIESEL = 20000
MAX_CAPACIDAD_UREA = 5000
MAX_CAPACIDAD_ACEITE = 2000

class CompraSuministroForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        tipo_suministro = cleaned_data.get('tipo_suministro')
        cantidad_compra = cleaned_data.get('cantidad', 0) or 0
        
        precio_litro = cleaned_data.get('precio_por_litro')
        if tipo_suministro in ['DIESEL', 'UREA'] and not precio_litro:
            self.add_error('precio_por_litro', 'Este campo es obligatorio para Diésel y Urea.')

        if tipo_suministro == 'OTRO' or cantidad_compra <= 0:
            return cleaned_data

        qs_compras = CompraSuministro.objects.filter(tipo_suministro=tipo_suministro)
        if self.instance.pk:
            qs_compras = qs_compras.exclude(pk=self.instance.pk)

        inventario_actual = 0
        capacidad_maxima = 0

        if tipo_suministro == 'DIESEL':
            total_comprado = qs_compras.aggregate(total=Sum('cantidad'))['total'] or 0
            consumo_motor = CargaDiesel.objects.aggregate(total=Sum('lts_diesel'))['total'] or 0
            consumo_thermo = CargaDiesel.objects.aggregate(total=Sum('lts_thermo'))['total'] or 0
            inventario_actual = total_comprado - (consumo_motor + consumo_thermo)
            capacidad_maxima = MAX_CAPACIDAD_DIESEL
        
        elif tipo_suministro == 'UREA':
            total_comprado = qs_compras.aggregate(total=Sum('cantidad'))['total'] or 0
            total_consumido = CargaUrea.objects.aggregate(total=Sum('litros_cargados'))['total'] or 0
            inventario_actual = total_comprado - total_consumido
            capacidad_maxima = MAX_CAPACIDAD_UREA

        elif tipo_suministro == 'ACEITE':
            total_comprado = qs_compras.aggregate(total=Sum('cantidad'))['total'] or 0
            total_consumido = CargaAceite.objects.aggregate(total=Sum('cantidad'))['total'] or 0
            inventario_actual = total_comprado - total_consumido
            capacidad_maxima = MAX_CAPACIDAD_ACEITE

        espacio_disponible = capacidad_maxima - inventario_actual
        if cantidad_compra > espacio_disponible:
            raise ValidationError(
                f"La compra excede la capacidad del tanque. "
                f"Inventario actual (sin esta compra): {inventario_actual:.2f} L. "
                f"Espacio disponible: {espacio_disponible:.2f} L. "
                f"Está intentando comprar {cantidad_compra} L."
            )
        return cleaned_data

    class Meta:
        model = CompraSuministro
        fields = [
            'fecha_compra', 'tipo_suministro', 'cantidad', 'precio_por_litro', 
            'proveedor', 'notificacion_pago', 'factura', 'comprobante_pago'
        ]
        widgets = { 'fecha_compra': forms.DateInput(attrs={'type': 'date'}),}

class ChecklistInspeccionForm(forms.ModelForm):
    class Meta:
        model = ChecklistInspeccion
        exclude = ['fecha', 'tecnico']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if 'unidad' in self.initial:
             self.fields['unidad'].disabled = True
        else:
             self.fields['unidad'].widget.attrs.update({'class': 'form-select'})

        self.fields['operador'].widget.attrs.update({'class': 'form-select'})
        
        for field_name, field in self.fields.items():
            if isinstance(field, forms.ChoiceField) and field_name not in ['unidad', 'operador']:
                field.widget.attrs.update({'class': 'form-select form-select-sm'})
                field.required = True
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({
                    'class': 'form-control observation-field',
                    'rows': 2,
                    'placeholder': 'Describir el problema detalladamente...'
                })
            elif isinstance(field, forms.ImageField):
                field.widget.attrs.update({
                    'class': 'form-control evidence-field',
                })

class LlantasInspeccionForm(forms.ModelForm):
    class Meta:
        model = LlantasInspeccion
        fields = ['unidad', 'km']
        widgets = {
            'unidad': forms.Select(attrs={'class': 'form-select'}),
            'km': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class LlantasKmForm(forms.Form):
    km = forms.IntegerField(
        label="Kilometraje de la Unidad",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.unidad = kwargs.pop('unidad', None)
        super().__init__(*args, **kwargs)

    def clean_km(self):
        km_ingresado = self.cleaned_data.get('km')
        if self.unidad and km_ingresado is not None:
            if km_ingresado <= self.unidad.km_actual:
                raise ValidationError(
                    f"El kilometraje debe ser mayor al último registrado ({self.unidad.km_actual} km)."
                )
        return km_ingresado

class LlantaDetalleForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['posicion'].required = False
        self.fields['posicion'].widget = forms.HiddenInput()

        self.fields['medida'].initial = '11R22.5'
        self.fields['medida'].widget.attrs.update({'class': 'form-control text-uppercase'})
        
        placeholders = {
            'mm': 'MM',
            'marca': 'Marca',
            'modelo': 'Modelo',
            'presion': 'PSI'
        }
        
        for field_name, placeholder_text in placeholders.items():
            field = self.fields[field_name]
            field.widget.attrs.update({
                'class': 'form-control',
                'placeholder': placeholder_text
            })
            field.required = False
            field.label = ''
            if field_name in ['marca', 'modelo']:
                 field.widget.attrs['class'] += ' text-uppercase'

    class Meta:
        model = LlantaDetalle
        fields = ['posicion', 'mm', 'marca', 'modelo', 'medida', 'presion']