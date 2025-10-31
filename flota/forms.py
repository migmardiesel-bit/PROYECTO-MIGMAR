# flota/forms.py
# --- ARCHIVO CORREGIDO: SE ELIMINÓ LA VALIDACIÓN DE INVENTARIO ---
from django import forms
from .models import (
    Unidad, Operador, CargaDiesel, CargaAceite, CargaUrea, CompraSuministro, 
    ChecklistInspeccion, LlantasInspeccion, LlantaDetalle, AjusteInventario, AsignacionRevision,EntregaSuministros# <-- Añadir AjusteInventario
)
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.forms import BaseFormSet
from django.db.models import Sum, Q  # <--- MODIFICA ESTA LÍNEA (AÑADE LA Q)
from django.contrib.auth.models import User, Group # <-- Añadir Group
from .models import ChecklistCorreccion # <-- Asegúrate de importar tu nuevo modelo

class UnidadForm(forms.ModelForm):
    
    combustible_compartido = forms.ChoiceField(
        choices=[('False', 'No'), ('True', 'Sí')],
        label="Tanque de Combustible Compartido",
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )

    class Meta:
        model = Unidad
        fields = '__all__'
        
        widgets = {
            # --- Widgets para los nuevos campos ---
            'unidad_negocio': forms.Select(attrs={'class': 'form-select'}),
            'tipo_combustible': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_cilindros': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 6'}),
            
            # --- Widgets existentes con IDs para JS ---
            'tipo': forms.Select(attrs={'class': 'form-select', 'id': 'id_tipo_unidad'}),
            'tamano_caja_pies': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 53'}),
            'thermo_tipo_cierre': forms.Select(attrs={'class': 'form-select'}),
            'capacidad_total_tanque': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_tanque_diesel_motor': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_tanque_diesel_thermo': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Lógica para manejar el campo Booleano/ChoiceField
        if self.instance and self.instance.pk:
            self.fields['combustible_compartido'].initial = str(self.instance.combustible_compartido)
        else:
            self.fields['combustible_compartido'].initial = 'False'
            
        # --- INICIO DE LA CORRECCIÓN ---
        # Asigna una clase CSS solo a los campos descriptivos de thermo
        # para controlarlos en grupo con JS.
        # EXCLUIMOS 'total_tanque_diesel_thermo' de esta lista.
        thermo_fields_descriptivos = [
            'thermo_marca', 'thermo_serie', 'thermo_modelo', 
            'thermo_tipo_cierre' 
        ]
        
        for field_name in thermo_fields_descriptivos:
            if field_name in self.fields:
                # Usamos una clase CSS específica para este grupo
                self.fields[field_name].widget.attrs['class'] = self.fields[field_name].widget.attrs.get('class', '') + ' campo-thermo-descriptivo'
        # --- FIN DE LA CORRECCIÓN ---

    def clean(self):
        cleaned_data = super().clean()
        
        # Convertir el string 'True'/'False' de vuelta a un Booleano
        is_compartido = cleaned_data.get('combustible_compartido') == 'True'
        cleaned_data['combustible_compartido'] = is_compartido
        
        capacidad_total = cleaned_data.get('capacidad_total_tanque')
        tanque_motor = cleaned_data.get('total_tanque_diesel_motor')
        tanque_thermo = cleaned_data.get('total_tanque_diesel_thermo')
        tipo_unidad = cleaned_data.get('tipo')

        if is_compartido:
            # Si es compartido, 'capacidad_total' es requerido y los otros deben estar vacíos.
            if not capacidad_total or capacidad_total <= 0:
                self.add_error('capacidad_total_tanque', 'Este campo es requerido si el combustible es compartido.')
            cleaned_data['total_tanque_diesel_motor'] = None
            cleaned_data['total_tanque_diesel_thermo'] = None
        
        else: # Si NO es compartido
            cleaned_data['capacidad_total_tanque'] = None
            if not tanque_motor or tanque_motor <= 0:
                 self.add_error('total_tanque_diesel_motor', 'Este campo es requerido si el combustible NO es compartido.')
            
            # El tanque de thermo solo es requerido si la unidad es Refrigerada
            if tipo_unidad != 'S':
                if not tanque_thermo or tanque_thermo <= 0:
                    self.add_error('total_tanque_diesel_thermo', 'Este campo es requerido para unidades refrigeradas si el combustible NO es compartido.')
            else:
                cleaned_data['total_tanque_diesel_thermo'] = None
        
        return cleaned_data

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
        
        if 'foto_motor' in self.fields:
            self.fields['foto_motor'].widget.attrs.update({
                'class': 'form-control form-control-sm',
                'accept': 'image/*',
                'capture': 'environment'
            })
            self.fields['foto_motor'].required = False # Asegura que sea opcional
            # --- MODIFICACIÓN DE ETIQUETA ---
            self.fields['foto_motor'].label = "Foto Bomba Diésel Motor"

        if 'foto_thermo' in self.fields:
            self.fields['foto_thermo'].widget.attrs.update({
                'class': 'form-control form-control-sm',
                'accept': 'image/*',
                'capture': 'environment'
            })
            self.fields['foto_thermo'].required = False # Asegura que sea opcional
            # --- MODIFICACIÓN DE ETIQUETA ---
            self.fields['foto_thermo'].label = "Foto Bomba Diésel Thermo"

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

        # # --- INICIO: VALIDACIÓN DE INVENTARIO DESACTIVADA ---
        # if not self.instance.pk:
        #     lts_a_cargar = cleaned_data.get('lts_diesel', 0) or 0
        #     thermo_a_cargar = cleaned_data.get('lts_thermo', 0) or 0
        #     total_a_cargar = lts_a_cargar + thermo_a_cargar
        #
        #     if total_a_cargar > 0:
        #         total_comprado = CompraSuministro.objects.filter(tipo_suministro='DIESEL').aggregate(total=Sum('cantidad'))['total'] or 0
        #         consumo_motor = CargaDiesel.objects.aggregate(total=Sum('lts_diesel'))['total'] or 0
        #         consumo_thermo = CargaDiesel.objects.aggregate(total=Sum('lts_thermo'))['total'] or 0
        #         inventario_actual = total_comprado - (consumo_motor + consumo_thermo)
        #
        #         if total_a_cargar > inventario_actual:
        #             raise ValidationError(
        #                 f"No se puede cargar {total_a_cargar} L de diésel. "
        #                 f"Solo hay {inventario_actual:.2f} L disponibles en el inventario."
        #             )
        # # --- FIN: VALIDACIÓN DE INVENTARIO DESACTIVADA ---

        unidad = self.unidad_instance or cleaned_data.get('unidad')
        if not unidad: return cleaned_data
        ultima_carga = CargaDiesel.objects.filter(unidad=unidad).order_by('-fecha').first()
        if ultima_carga:
            km_actual_form = cleaned_data.get('km_actual')
            if km_actual_form is not None and km_actual_form <= ultima_carga.km_actual:
                self.add_error('km_actual', f"El kilometraje debe ser mayor al último registrado ({ultima_carga.km_actual} km).")
            
            hrs_thermo_form = cleaned_data.get('hrs_thermo')
            if hrs_thermo_form is not None and hrs_thermo_form <= (ultima_carga.hrs_thermo or 0):
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
        # # --- INICIO: VALIDACIÓN DE INVENTARIO DESACTIVADA ---
        # if not self.instance.pk:
        #     cantidad_a_cargar = cleaned_data.get('cantidad', 0) or 0
        #     if cantidad_a_cargar > 0:
        #         total_comprado = CompraSuministro.objects.filter(tipo_suministro='ACEITE').aggregate(total=Sum('cantidad'))['total'] or 0
        #         total_consumido = CargaAceite.objects.aggregate(total=Sum('cantidad'))['total'] or 0
        #         inventario_actual = total_comprado - total_consumido
        #         if cantidad_a_cargar > inventario_actual:
        #             raise ValidationError(
        #                 f"No se puede cargar {cantidad_a_cargar} L de aceite. "
        #                 f"Solo hay {inventario_actual:.2f} L disponibles en el inventario."
        #             )
        # # --- FIN: VALIDACIÓN DE INVENTARIO DESACTIVADA ---
        return cleaned_data

    class Meta:
        model = CargaAceite
        fields = '__all__'
        exclude = ['fecha']

class CargaUreaForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Esta línea es crucial. Permite enviar el formulario con el campo vacío.
        self.fields['litros_cargados'].required = False

        # --- INICIO DE BLOQUE A AÑADIR ---
        if 'foto_urea' in self.fields:
            self.fields['foto_urea'].widget.attrs.update({
                'class': 'form-control form-control-sm',
                'accept': 'image/*',
                'capture': 'environment'
            })
            self.fields['foto_urea'].required = False # Es opcional
            self.fields['foto_urea'].label = "Foto Bomba Urea"
        # --- FIN DE BLOQUE A AÑADIR ---

    class Meta:
        model = CargaUrea
        # --- CAMBIO AQUÍ ---
        fields = ['litros_cargados', 'foto_urea', 'comentarios'] # Añadir 'foto_urea'

# Capacidad máxima (en litros) de los tanques de almacenamiento.
MAX_CAPACIDAD_DIESEL = 20000
MAX_CAPACIDAD_UREA = 5000
MAX_CAPACIDAD_ACEITE = 2000

class CompraSuministroForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        tipo_suministro = cleaned_data.get('tipo_suministro')
        cantidad_compra = cleaned_data.get('cantidad', 0) or 0

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
        fields = '__all__'
        # ========= INICIO DEL CAMBIO =========
        widgets = {
            'fecha_compra': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
        # ========= FIN DEL CAMBIO ============

# Formulario completo del Checklist
class ChecklistInspeccionForm(forms.ModelForm):
    class Meta:
        model = ChecklistInspeccion
        exclude = ['fecha', 'tecnico']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # --- INICIO DE LÓGICA MODIFICADA ---

        # 1. Determinar la unidad que se está inspeccionando
        unidad = None
        if 'initial' in kwargs and 'unidad' in kwargs['initial']:
            # Caso 1: Al crear (la unidad viene en 'initial' desde la vista)
            unidad = kwargs['initial']['unidad']
        elif self.instance and self.instance.pk:
            # Caso 2: Al editar (la unidad ya existe en la 'instance')
            unidad = self.instance.unidad

        # 2. Configurar foto_odometro (sigue siendo obligatoria)
        if 'foto_odometro' in self.fields:
            self.fields['foto_odometro'].widget.attrs.update({
                'class': 'form-control',
                'accept': 'image/*',
                'capture': 'environment',
                'required': True 
            })
            self.fields['foto_odometro'].label = "Foto Clara del Odómetro"
        
        # 3. Configurar foto_thermo_hrs (LÓGICA CORREGIDA)
        if 'foto_thermo_hrs' in self.fields:
            self.fields['foto_thermo_hrs'].widget.attrs.update({
                'class': 'form-control',
                'accept': 'image/*',
                'capture': 'environment',
            })
            self.fields['foto_thermo_hrs'].label = "Foto Clara de Horas Thermo"
            
            # --- ESTA ES LA CORRECCIÓN CLAVE ---
            # Si la unidad es de tipo 'S' (Seca),
            # hacemos que este campo NO sea obligatorio.
            if unidad and unidad.tipo == 'S':
                self.fields['foto_thermo_hrs'].required = False
            else:
                # Para 'R' y 'A' (Refrigeradas), SÍ es obligatorio
                self.fields['foto_thermo_hrs'].required = True
        
        # 4. Configurar foto_sticker (opcional)
        if 'foto_sticker' in self.fields:
             self.fields['foto_sticker'].widget.attrs.update({
                'class': 'form-control',
                'accept': 'image/*',
                'capture': 'environment',
            })
             self.fields['foto_sticker'].label = "Foto Clara del sticker (si aplica)"
             self.fields['foto_sticker'].required = False # Nos aseguramos que sea opcional
        
        # --- FIN DE LÓGICA MODIFICADA ---
        
        # Lógica existente para deshabilitar la unidad y poner estilos
        if 'unidad' in self.initial:
             self.fields['unidad'].disabled = True
        else:
             self.fields['unidad'].widget.attrs.update({'class': 'form-select'})

        self.fields['operador'].widget.attrs.update({'class': 'form-select'})
        
        for field_name, field in self.fields.items():
            if isinstance(field, forms.ChoiceField) and field_name not in ['unidad', 'operador']:
                field.widget.attrs.update({'class': 'form-select form-select-sm'})
                
                # --- CORRECCIÓN ADICIONAL ---
                # Hacemos que todos los BIEN/MALO sean obligatorios
                field.required = True
                # --- FIN CORRECCIÓN ADICIONAL ---
                
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.update({
                    'class': 'form-control observation-field',
                    'rows': 2,
                    'placeholder': 'Describir el problema detalladamente...'
                })
                
            elif isinstance(field, forms.ImageField) and field_name not in ['foto_odometro', 'foto_thermo_hrs', 'foto_sticker']:
                field.widget.attrs.update({
                    'class': 'form-control evidence-field',
                    'accept': 'image/*',
                    'capture': 'environment'
                })

class LlantasInspeccionForm(forms.ModelForm):
    """Formulario para la cabecera de la inspección de llantas (Admin)."""
    class Meta:
        model = LlantasInspeccion
        fields = ['unidad', 'km']
        widgets = {
            'unidad': forms.Select(attrs={'class': 'form-select'}),
            'km': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class LlantasKmForm(forms.Form):
    """Formulario para capturar y validar el kilometraje de la unidad."""
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
        # Hacemos todos los campos opcionales para que el formulario siempre sea válido si está vacío.
        for field in self.fields.values():
            field.required = False
            
        self.fields['posicion'].widget = forms.HiddenInput()
        self.fields['medida'].initial = '11R22.5'
        self.fields['medida'].widget.attrs.update({'class': 'form-control text-uppercase'})
        placeholders = {'mm': 'MM', 'marca': 'Marca', 'modelo': 'Modelo', 'presion': 'PSI'}
        for name, placeholder in placeholders.items():
            field = self.fields[name]
            field.widget.attrs.update({'class': 'form-control', 'placeholder': placeholder})
            field.label = ''
            if name in ['marca', 'modelo']: field.widget.attrs['class'] += ' text-uppercase'
    
    # --- MÉTODO 'clean' ELIMINADO ---
    # Al quitar el método 'clean', eliminamos la regla que obligaba a llenar todos 
    # los campos de una fila si se llenaba uno. Ahora las filas pueden estar 
    # vacías o parcialmente llenas sin generar un error de validación.

    class Meta:
        model = LlantaDetalle
        fields = ['posicion', 'mm', 'marca', 'modelo', 'medida', 'presion']
    
class AjusteInventarioForm(forms.ModelForm):
    
    def clean_cantidad(self):
        """Valida que la cantidad ingresada sea siempre un número positivo."""
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is not None and cantidad <= 0:
            raise ValidationError("La cantidad debe ser un número positivo.")
        return cantidad

    class Meta:
        model = AjusteInventario
        fields = ['tipo_suministro', 'tipo_ajuste', 'cantidad', 'motivo']
        widgets = {
            'tipo_suministro': forms.Select(attrs={'class': 'form-select'}),
            'tipo_ajuste': forms.Select(attrs={'class': 'form-select'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 50.5'}),
            'motivo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        
class AsignacionRevisionForm(forms.ModelForm):
    
    # *** ELIMINAR EL MÉTODO __init__ COMPLETO ***
    # (Ya que solo se usaba para filtrar tecnicos_asignado)

    class Meta:
        model = AsignacionRevision
        # *** CAMBIO: REMOVER 'tecnico_asignado' DE fields ***
        fields = ['unidad', 'fecha_revision', 'comentario_cancelacion'] 
        widgets = {
            'unidad': forms.Select(attrs={'class': 'form-select'}),
            'fecha_revision': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            # ELIMINAR WIDGET DE tecnico_asignado
            'comentario_cancelacion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        
class ChecklistCorreccionForm(forms.ModelForm):
    """
    Formulario para que el administrador palomee y comente un ítem MALO.
    """
    # Usamos un campo oculto para el ID del registro de corrección
    id = forms.IntegerField(widget=forms.HiddenInput())
    
    # --- INICIO DE CAMPOS NUEVOS (No-Modelo) ---
    marcar_corregido = forms.BooleanField(
        required=False,
        label="Corregido",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    marcar_descartado = forms.BooleanField(
        required=False,
        label="Descartar",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input text-danger bg-danger'})
    )
    # --- FIN DE CAMPOS NUEVOS ---
    
    class Meta:
        model = ChecklistCorreccion
        # 'esta_corregido' se quita, 'status' no se maneja aquí directamente
        fields = ['id', 'comentario_admin'] 
        widgets = {
            'comentario_admin': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Comentario de la corrección/revisión'}),
        }

    # --- INICIO DE VALIDACIÓN AÑADIDA ---
    def clean(self):
        cleaned_data = super().clean()
        corregido = cleaned_data.get('marcar_corregido')
        descartado = cleaned_data.get('marcar_descartado')

        if corregido and descartado:
            # Lanza un error que se mostrará en el formulario
            raise ValidationError(
                "No puede marcar un ítem como 'Corregido' y 'Descartado' al mismo tiempo.",
                code='invalid_choice'
            )
        return cleaned_data
    
    
class EntregaSuministrosForm(forms.ModelForm):
    
    class Meta:
        model = EntregaSuministros
        # --- CAMPOS MODIFICADOS ---
        fields = [
            'operador', 
            'fecha_entrega', 
            'cant_cinchos', 
            'folio_inicial', 
            'folio_final', 
            'unidad', 
            'para_motor',  # <-- Nuevo
            'para_thermo', # <-- Nuevo
            'entregado'
        ]
        
        widgets = {
            'operador': forms.Select(attrs={'class': 'form-control select2-widget-operador'}),
            'unidad': forms.Select(attrs={'class': 'form-control select2-widget-unidad'}),
            
            'fecha_entrega': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'cant_cinchos': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 100'}),
            'folio_inicial': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 5001'}),
            'folio_final': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ej: 5100'}),
            
            # --- WIDGETS MODIFICADOS (AHORA SON CHECKBOXES) ---
            'para_motor': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'para_thermo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'entregado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Pone la fecha de hoy por defecto, pero permite cambiarla
        if not self.instance.pk:
            self.fields['fecha_entrega'].initial = timezone.now().date()
        
        # Campos opcionales
        self.fields['unidad'].required = False
        self.fields['para_motor'].required = False
        self.fields['para_thermo'].required = False