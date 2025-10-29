from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.utils import timezone
from django.db import transaction

# ===================================================================
# 1. MODELOS PRINCIPALES (SIN DEPENDENCIAS)
# ===================================================================

class Operador(models.Model):
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.nombre} {self.apellido}"
    
    def get_absolute_url(self):
        return reverse('operador-update', kwargs={'pk': self.pk})

class Unidad(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre o Alias de la Unidad", unique=True)
    TIPO_CHOICES = [('S', 'Seca'), ('R', 'Refrigerada'), ('A', 'Refrigerada/Seca')]    
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES, default='S')
    marca = models.CharField(max_length=50, blank=True, null=True)
    modelo = models.CharField(max_length=50, blank=True, null=True)
    placas = models.CharField(max_length=20, blank=True, null=True)
    vin = models.CharField(max_length=17, blank=True, null=True, verbose_name="VIN")
    poliza = models.CharField(max_length=100, blank=True, null=True)
    tag = models.CharField(max_length=50, blank=True, null=True, verbose_name="TAG IAVE")
    km_actual = models.PositiveIntegerField(default=0, verbose_name="Kilometraje Actual")

    # ========= ASEGÚRATE QUE ESTA LÍNEA ESTÉ AQUÍ =========
    ultima_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")
    # ======================================================

    def __str__(self):
        return self.nombre

    def get_absolute_url(self):
        return reverse('unidad-detail', kwargs={'pk': self.pk})
# ===================================================================
# 2. MODELOS DEPENDIENTES (QUE USAN 'UNIDAD' U 'OPERADOR')
# ===================================================================

class CargaDiesel(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE)
    operador = models.ForeignKey(Operador, on_delete=models.SET_NULL, null=True, blank=True)
    lts_diesel = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Litros Diésel")
    costo = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Costo Total", null=True, blank=True, editable=False)
    lts_thermo = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Litros Thermo")
    hrs_thermo = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Horas Thermo")
    km_actual = models.PositiveIntegerField(verbose_name="Kilometraje al Cargar")
    cinchos_anteriores = models.CharField(max_length=100, blank=True)
    cinchos_actuales = models.CharField(max_length=100, blank=True)
    persona_relleno = models.CharField(max_length=150)
    rendimiento = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Rendimiento (Km/L)")
    foto_motor = models.ImageField(upload_to='cargas_diesel/motor/', blank=True, null=True, verbose_name="Foto Motor")
    foto_thermo = models.ImageField(upload_to='cargas_diesel/thermo/', blank=True, null=True, verbose_name="Foto Thermo")
   
    def save(self, *args, **kwargs):
        """
        Versión simplificada. Ya no calcula el costo aquí.
        Simplemente guarda el registro de la carga.
        La recalculación se llama desde la VISTA.
        """
        # Se elimina toda la lógica de cálculo de costo que estaba aquí.
        super().save(*args, **kwargs)
        
        # ========= INICIO DE LA MODIFICACIÓN =========
        # ¡LAS LÍNEAS DE RECALCULACIÓN SE ELIMINARON DE AQUÍ!
        # ========= FIN DE LA MODIFICACIÓN =========

    def get_absolute_url(self):
        return reverse('cargadiesel-list')

class CargaAceite(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE)
    cantidad = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Cantidad (Lts)")
    motivo = models.CharField(max_length=200)
    comentario = models.TextField(blank=True)

    def get_absolute_url(self):
        return reverse('cargaaceite-list')

class CargaUrea(models.Model):
    fecha = models.DateTimeField(auto_now_add=True)
    unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE)
    litros_cargados = models.DecimalField(max_digits=8, decimal_places=2)
    costo = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Costo Total", null=True, blank=True, editable=False)
    
    # --- ESTA LÍNEA ES LA IMPORTANTE ---
    foto_urea = models.ImageField(upload_to='cargas_urea/', blank=True, null=True, verbose_name="Foto Bomba Urea")
    # ------------------------------------
    
    comentarios = models.TextField(blank=True)
    rendimiento = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Rendimiento (Km/L)")
    def save(self, *args, **kwargs):
        """
        Versión simplificada. Ya no calcula el costo aquí.
        Simplemente guarda el registro y la recalculación se dispara desde la VISTA.
        """
        super().save(*args, **kwargs)
        
        # ========= INICIO DE LA MODIFICACIÓN =========
        # ¡LAS LÍNEAS DE RECALCULACIÓN SE ELIMINARON DE AQUÍ!
        # ========= FIN DE LA MODIFICACIÓN =========


    
class CompraSuministro(models.Model):
    TIPO_SUMINISTRO_CHOICES = [
        ('DIESEL', 'Diésel'),
        ('UREA', 'Urea'),
        ('ACEITE', 'Aceite'),
        ('OTRO', 'Otro'),
    ]
    # ========= INICIO DEL CAMBIO =========
    fecha_compra = models.DateTimeField()
    # ========= FIN DEL CAMBIO ============
    tipo_suministro = models.CharField(max_length=10, choices=TIPO_SUMINISTRO_CHOICES)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, help_text="Litros o unidades compradas")
    proveedor = models.CharField(max_length=200)
    
    # --- CAMPOS MODIFICADOS / AÑADIDOS ---
    precio_por_litro = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio por Litro/Unidad", null=True, blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio Total", editable=False)
    litros_restantes = models.DecimalField(max_digits=10, decimal_places=2, editable=False, help_text="Litros disponibles de esta compra")
    # --- FIN DE CAMPOS ---

    notificacion_pago = models.FileField(upload_to='comprobantes/notificaciones/', blank=True, null=True)
    factura = models.FileField(upload_to='comprobantes/facturas/', blank=True, null=True)
    comprobante_pago = models.FileField(upload_to='comprobantes/pagos/', blank=True, null=True)
    
    def save(self, *args, **kwargs):
        """
        Método modificado. Calcula el precio total de esta compra y,
        si es de diésel o urea, dispara la recalculación global de costos.
        """
        if self.precio_por_litro and self.cantidad:
            self.precio = self.cantidad * self.precio_por_litro
        
        if not self.pk:
            self.litros_restantes = self.cantidad

        super().save(*args, **kwargs)

        # ========= INICIO DE LA MODIFICACIÓN =========
        # Solo dispara la recalculación si NO estamos 
        # dentro de una transacción atómica.
        if not transaction.get_connection().in_atomic_block:
            if self.tipo_suministro == 'DIESEL':
                from .utils import recalcular_costos_cargas_diesel
                recalcular_costos_cargas_diesel()
            elif self.tipo_suministro == 'UREA':
                from .utils import recalcular_costos_cargas_urea
                recalcular_costos_cargas_urea()
        # ========= FIN DE LA MODIFICACIÓN =========

    def get_absolute_url(self):
        return reverse('comprasuministro-list')


# ... (Todos tus otros imports y modelos van aquí arriba) ...
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
# ... (etc) ...

class ChecklistInspeccion(models.Model):
    ESTADO_CHOICES = [('BIEN', 'Bien'), ('MALO', 'Malo')]
    
    fecha = models.DateTimeField(auto_now_add=True)
    unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE)
    operador = models.ForeignKey(Operador, on_delete=models.CASCADE)
    tecnico = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # --- INICIO DE LA CORRECCIÓN ---
    # Estos son los campos correctos para el Checklist
    foto_odometro = models.ImageField(
        upload_to='checklist_odometros/', 
        blank=True, null=True, 
        verbose_name="Foto Odómetro (KM)"
    )
    foto_thermo_hrs = models.ImageField(
        upload_to='checklist_thermo_hrs/', 
        blank=True, null=True, 
        verbose_name="Foto Horas Thermo"
    )
    
    foto_sticker = models.ImageField(
        upload_to='checklist_stickers/', 
        blank=True, null=True, 
        verbose_name="Foto Sticker"
    )
    # --- FIN DE LA CORRECCIÓN ---

    # Estructura Exterior
    cristales = models.CharField(max_length=4, choices=ESTADO_CHOICES); cristales_obs = models.TextField(blank=True); cristales_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Cristales")
    espejos = models.CharField(max_length=4, choices=ESTADO_CHOICES); espejos_obs = models.TextField(blank=True); espejos_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Espejos")
    logos = models.CharField(max_length=4, choices=ESTADO_CHOICES); logos_obs = models.TextField(blank=True); logos_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Logos")
    num_economico = models.CharField(max_length=4, choices=ESTADO_CHOICES, verbose_name="Núm. Económico"); num_economico_obs = models.TextField(blank=True); num_economico_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Núm. Económico")
    puertas = models.CharField(max_length=4, choices=ESTADO_CHOICES); puertas_obs = models.TextField(blank=True); puertas_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Puertas")
    cofre = models.CharField(max_length=4, choices=ESTADO_CHOICES); cofre_obs = models.TextField(blank=True); cofre_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Cofre")
    parrilla = models.CharField(max_length=4, choices=ESTADO_CHOICES); parrilla_obs = models.TextField(blank=True); parrilla_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Parrilla")
    defensas = models.CharField(max_length=4, choices=ESTADO_CHOICES); defensas_obs = models.TextField(blank=True); defensas_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Defensas")
    faros = models.CharField(max_length=4, choices=ESTADO_CHOICES); faros_obs = models.TextField(blank=True); faros_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Faros")
    plafoneria = models.CharField(max_length=4, choices=ESTADO_CHOICES); plafoneria_obs = models.TextField(blank=True); plafoneria_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Plafonería")
    stops = models.CharField(max_length=4, choices=ESTADO_CHOICES); stops_obs = models.TextField(blank=True); stops_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Stops")
    direccionales = models.CharField(max_length=4, choices=ESTADO_CHOICES); direccionales_obs = models.TextField(blank=True); direccionales_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Direccionales")
    tapiceria = models.CharField(max_length=4, choices=ESTADO_CHOICES); tapiceria_obs = models.TextField(blank=True); tapiceria_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Tapicería")
    instrumentos = models.CharField(max_length=4, choices=ESTADO_CHOICES); instrumentos_obs = models.TextField(blank=True); instrumentos_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Instrumentos")
    carroceria = models.CharField(max_length=4, choices=ESTADO_CHOICES); carroceria_obs = models.TextField(blank=True); carroceria_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Carrocería")
    piso = models.CharField(max_length=4, choices=ESTADO_CHOICES); piso_obs = models.TextField(blank=True); piso_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Piso")
    costados = models.CharField(max_length=4, choices=ESTADO_CHOICES); costados_obs = models.TextField(blank=True); costados_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Costados")
    escape = models.CharField(max_length=4, choices=ESTADO_CHOICES); escape_obs = models.TextField(blank=True); escape_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Escape")
    pintura = models.CharField(max_length=4, choices=ESTADO_CHOICES); pintura_obs = models.TextField(blank=True); pintura_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Pintura")
    franjas = models.CharField(max_length=4, choices=ESTADO_CHOICES); franjas_obs = models.TextField(blank=True); franjas_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Franjas")
    loderas = models.CharField(max_length=4, choices=ESTADO_CHOICES); loderas_obs = models.TextField(blank=True); loderas_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Loderas")
    extintor = models.CharField(max_length=4, choices=ESTADO_CHOICES); extintor_obs = models.TextField(blank=True); extintor_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Extintor")
    senalamientos = models.CharField(max_length=4, choices=ESTADO_CHOICES, verbose_name="Señalamientos"); senalamientos_obs = models.TextField(blank=True); senalamientos_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Señalamientos")
    estado_general = models.CharField(max_length=4, choices=ESTADO_CHOICES); estado_general_obs = models.TextField(blank=True); estado_general_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Estado General")
    
    # Mecánica y Motor
    motor = models.CharField(max_length=4, choices=ESTADO_CHOICES); motor_obs = models.TextField(blank=True); motor_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Motor")
    caja = models.CharField(max_length=4, choices=ESTADO_CHOICES); caja_obs = models.TextField(blank=True); caja_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Caja")
    diferenciales = models.CharField(max_length=4, choices=ESTADO_CHOICES); diferenciales_obs = models.TextField(blank=True); diferenciales_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Diferenciales")
    suspension_delantera = models.CharField(max_length=4, choices=ESTADO_CHOICES, verbose_name="Suspensión Del."); suspension_delantera_obs = models.TextField(blank=True); suspension_delantera_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Suspensión Del.")
    suspension_trasera = models.CharField(max_length=4, choices=ESTADO_CHOICES, verbose_name="Suspensión Tras."); suspension_trasera_obs = models.TextField(blank=True); suspension_trasera_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Suspensión Tras.")
    fugas_combustible = models.CharField(max_length=4, choices=ESTADO_CHOICES); fugas_combustible_obs = models.TextField(blank=True); fugas_combustible_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Fugas Combustible")
    fugas_aceite = models.CharField(max_length=4, choices=ESTADO_CHOICES); fugas_aceite_obs = models.TextField(blank=True); fugas_aceite_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Fugas Aceite")
    estado_llantas = models.CharField(max_length=4, choices=ESTADO_CHOICES); estado_llantas_obs = models.TextField(blank=True); estado_llantas_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Estado Llantas")
    presion_llantas = models.CharField(max_length=4, choices=ESTADO_CHOICES, verbose_name="Presión Llantas"); presion_llantas_obs = models.TextField(blank=True); presion_llantas_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Presión Llantas")
    purga_tanques = models.CharField(max_length=4, choices=ESTADO_CHOICES, verbose_name="Purga Tanques Aire/Comb"); purga_tanques_obs = models.TextField(blank=True); purga_tanques_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Purga Tanques")
    estado_balatas = models.CharField(max_length=4, choices=ESTADO_CHOICES); estado_balatas_obs = models.TextField(blank=True); estado_balatas_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Estado Balatas")
    amortiguadores_delanteros = models.CharField(max_length=4, choices=ESTADO_CHOICES, verbose_name="Amortiguadores Del."); amortiguadores_delanteros_obs = models.TextField(blank=True); amortiguadores_delanteros_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Amortiguadores Del.")
    amortiguadores_traseros = models.CharField(max_length=4, choices=ESTADO_CHOICES, verbose_name="Amortiguadores Tras."); amortiguadores_traseros_obs = models.TextField(blank=True); amortiguadores_traseros_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Amortiguadores Tras.")
    rines_aluminio = models.CharField(max_length=4, choices=ESTADO_CHOICES); rines_aluminio_obs = models.TextField(blank=True); rines_aluminio_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Rines Aluminio")
    mangueras_servicio = models.CharField(max_length=4, choices=ESTADO_CHOICES); mangueras_servicio_obs = models.TextField(blank=True); mangueras_servicio_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Mangueras Servicio")
    tarjeta_llave = models.CharField(max_length=4, choices=ESTADO_CHOICES, verbose_name="Tarjeta Lave"); tarjeta_llave_obs = models.TextField(blank=True); tarjeta_llave_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Tarjeta Llave")
    revision_fusibles = models.CharField(max_length=4, choices=ESTADO_CHOICES, verbose_name="Revisión Fusibles/Relay"); revision_fusibles_obs = models.TextField(blank=True); revision_fusibles_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Revisión Fusibles")
    revision_luces = models.CharField(max_length=4, choices=ESTADO_CHOICES, verbose_name="Revisión Gral. Luces"); revision_luces_obs = models.TextField(blank=True); revision_luces_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Revisión Luces")
    revision_fuga_aire = models.CharField(max_length=4, choices=ESTADO_CHOICES, verbose_name="Revisión Fuga de Aire"); revision_fuga_aire_obs = models.TextField(blank=True); revision_fuga_aire_foto = models.ImageField(upload_to='checklist_evidencia/', blank=True, null=True, verbose_name="Foto Revisión Fuga de Aire")

    def __str__(self):
        return f"Checklist para {self.unidad} el {self.fecha.strftime('%Y-%m-%d')}"

    # --- ESTE ES EL MÉTODO .SAVE() CORRECTO, RÁPIDO Y FINAL ---
    def save(self, *args, **kwargs):
        """
        Lógica de guardado simplificada.
        La creación/actualización de 'ChecklistCorreccion' ha sido movida
        a una señal post_save (en signals.py) para mejorar el rendimiento
        ...
        """
        super().save(*args, **kwargs)
# --- INICIO DE CÓDIGO AÑADIDO ---
# ===================================================================
# 3. MODELOS PARA INSPECCIÓN DE LLANTAS
# ===================================================================

class LlantasInspeccion(models.Model):
    """Guarda la cabecera de una inspección completa de llantas."""
    fecha = models.DateTimeField(auto_now_add=True)
    unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE, related_name='inspecciones_llantas')
    tecnico = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    km = models.PositiveIntegerField(verbose_name="Kilometraje en Inspección")

    def __str__(self):
        return f"Inspección de Llantas para {self.unidad} el {self.fecha.strftime('%Y-%m-%d')}"

class LlantaDetalle(models.Model):
    """Almacena el detalle de cada llanta individual en una inspección."""
    inspeccion = models.ForeignKey(LlantasInspeccion, on_delete=models.CASCADE, related_name='detalles_llanta')
    posicion = models.CharField(max_length=50, verbose_name="Posición")
    mm = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="MM")
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    medida = models.CharField(max_length=50, verbose_name="Medida de Llanta")
    presion = models.PositiveIntegerField(verbose_name="Presión (PSI)")

    def __str__(self):
        return f"{self.posicion} - {self.marca} ({self.mm}mm)"


class ProcesoCarga(models.Model):
    """
    Orquesta el flujo de trabajo completo, desde el checklist hasta la carga de diésel.
    Permite dividir el proceso entre el Técnico y el Encargado.
    """
    STATUS_CHOICES = [
        ('PENDIENTE', 'Pendiente de Carga'),
        ('COMPLETADO', 'Completado'),
    ]
    
    # --- RELACIONES CON CADA ETAPA ---
    unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE, related_name='procesos_carga')
    checklist = models.OneToOneField(ChecklistInspeccion, on_delete=models.CASCADE)
    inspeccion_llantas = models.OneToOneField(LlantasInspeccion, on_delete=models.CASCADE)
    carga_diesel = models.OneToOneField(CargaDiesel, on_delete=models.SET_NULL, null=True, blank=True)
    carga_urea = models.OneToOneField(CargaUrea, on_delete=models.SET_NULL, null=True, blank=True)

    # --- DATOS DE AUDITORÍA Y ESTADO ---
    tecnico_inicia = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='procesos_iniciados')
    encargado_finaliza = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='procesos_finalizados')
    
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDIENTE')

    def __str__(self):
        return f"Proceso para {self.unidad.nombre} - {self.status}"

    class Meta:
        ordering = ['-fecha_inicio']
        
class AjusteInventario(models.Model):
    """
    Registra ajustes manuales al inventario para balancear las existencias
    teóricas con las reales, sin modificar registros históricos de compras o cargas.
    """
    TIPO_SUMINISTRO_CHOICES = [
        ('DIESEL', 'Diésel'),
        ('UREA', 'Urea'),
        ('ACEITE', 'Aceite'),
    ]
    TIPO_AJUSTE_CHOICES = [
        ('ENTRADA', 'Entrada (Sobrante)'),
        ('SALIDA', 'Salida (Faltante)'),
    ]

    fecha = models.DateTimeField(auto_now_add=True)
    tipo_suministro = models.CharField(max_length=10, choices=TIPO_SUMINISTRO_CHOICES, verbose_name="Suministro a Ajustar")
    tipo_ajuste = models.CharField(max_length=10, choices=TIPO_AJUSTE_CHOICES, verbose_name="Tipo de Ajuste")
    
    # El usuario siempre ingresará una cantidad positiva. El modelo la hará negativa si es una 'SALIDA'.
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, help_text="Litros a ajustar (siempre en positivo)")
    
    motivo = models.TextField(help_text="Ej: Conteo físico, derrame, merma, etc.")
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ajustes_inventario')

    def __str__(self):
        return f"Ajuste de {self.tipo_suministro} de {self.cantidad}L el {self.fecha.strftime('%Y-%m-%d')}"

    def save(self, *args, **kwargs):
        # Asegura que la cantidad se guarde como negativa si es una salida (faltante)
        if self.tipo_ajuste == 'SALIDA' and self.cantidad > 0:
            self.cantidad *= -1
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-fecha']
        
class AsignacionRevision(models.Model):
    """
    Modela la asignación de una unidad para revisión en una fecha específica.
    """
    STATUS_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_PROCESO', 'En Proceso'),  # <--- AÑADIR ESTA LÍNEA
        ('TERMINADO', 'Terminado'),
        ('CANCELADO', 'Cancelado'),
        ('NO_VINO', 'No Vino'),
    ]

    unidad = models.ForeignKey(Unidad, on_delete=models.CASCADE, verbose_name="Unidad Asignada")
    fecha_revision = models.DateField(verbose_name="Fecha de Revisión")
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDIENTE', verbose_name="Estado")
    comentario_cancelacion = models.TextField(blank=True, null=True, verbose_name="Motivo de Cancelación")
    
    class Meta:
        verbose_name = "Asignación de Revisión"
        verbose_name_plural = "Asignaciones de Revisión"
        ordering = ['fecha_revision', 'unidad__nombre']
        unique_together = ('unidad', 'fecha_revision')

    def __str__(self):
        return f"Revisión de {self.unidad.nombre} para el {self.fecha_revision.strftime('%d/%m/%Y')}"

    @property
    def proceso_del_dia(self):
        """
        Busca y devuelve el ProcesoCarga asociado a esta asignación por unidad y fecha.
        """
        return ProcesoCarga.objects.filter(
            unidad=self.unidad,
            fecha_inicio__date=self.fecha_revision
        ).first()
        
    def save(self, *args, **kwargs):
        # La lógica que estaba aquí (status_changed_to_pending) era incorrecta y
        # trataba de actualizar el ProcesoCarga con campos que no existen.
        # La eliminamos para que el guardado sea simple.
        # La lógica de actualización se moverá a la vista EncargadoProcesoUreaView.
        super().save(*args, **kwargs)
        
        
class AlertaInventario(models.Model):
    """
    Gestiona el estado de las alertas de inventario para evitar notificaciones repetitivas
    y permitir recordatorios periódicos.
    """
    TIPO_SUMINISTRO_CHOICES = [
        ('DIESEL', 'Diésel'),
        ('UREA', 'Urea'),
        ('ACEITE', 'Aceite'),
    ]
    tipo_suministro = models.CharField(
        max_length=10, 
        choices=TIPO_SUMINISTRO_CHOICES, 
        unique=True, 
        verbose_name="Tipo de Suministro"
    )
    activa = models.BooleanField(
        default=False, 
        help_text="Indica si la alerta por bajo inventario está actualmente activa."
    )
    ultimo_aviso = models.DateTimeField(
        null=True, blank=True, 
        help_text="Fecha y hora del último aviso enviado."
    )
    nivel_reportado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="El nivel de inventario que disparó la alerta."
    )

    def __str__(self):
        estado = "Activa" if self.activa else "Inactiva"
        return f"Alerta para {self.get_tipo_suministro_display()} - {estado}"

    class Meta:
        verbose_name = "Alerta de Inventario"
        verbose_name_plural = "Alertas de Inventario"

class ChecklistCorreccion(models.Model):
    """
    Almacena los ítems específicos de una inspección que fueron marcados como 'MALO'
    y deben ser revisados y corregidos por el administrador.
    """
    inspeccion = models.ForeignKey(
        ChecklistInspeccion, 
        on_delete=models.CASCADE, 
        related_name='correcciones'
    )
    # Almacena el nombre del campo del ChecklistInspeccion (ej: 'cristales', 'motor')
    nombre_campo = models.CharField(
        max_length=50, 
        verbose_name="Ítem del Checklist"
    ) 
    
    observacion_original = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Observación original del técnico"
    )
    
    foto_evidencia = models.ImageField(
        upload_to='checklist_correcciones/', # Usará una nueva carpeta
        blank=True, 
        null=True, 
        verbose_name="Foto de Evidencia"
    )
    
    # --- CAMPO 'esta_corregido' REEMPLAZADO ---
    STATUS_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('CORREGIDO', 'Corregido (Reparado)'),
        ('DESCARTADO', 'Descartado (Admin)'),
    ]
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='PENDIENTE', 
        verbose_name="Estado"
    )
    # --- FIN DEL REEMPLAZO ---

    comentario_admin = models.TextField(
        blank=True, 
        null=True,
        verbose_name="Comentario del Administrador"
    )
    fecha_correccion = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Fecha de Corrección/Descarte"
    )
    corregido_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, blank=True,
        verbose_name="Administrador que corrigió",
        related_name='correcciones_checklist'
    )

    def __str__(self):
        # --- CAMBIO: Actualizado para usar el nuevo campo status ---
        return f"Corrección: {self.nombre_campo} - {self.inspeccion.unidad.nombre} ({self.get_status_display()})"
    
    class Meta:
        # Clave única para evitar dos registros de corrección abiertos para el mismo ítem.
        unique_together = ('inspeccion', 'nombre_campo')
        verbose_name = "Corrección de Checklist"
        verbose_name_plural = "Correcciones de Checklist"
        
class EntregaSuministros(models.Model):
    """
    Modelo para registrar la entrega de cinchos, tarjetas u otros 
    suministros a un operador.
    """
    operador = models.ForeignKey(Operador, on_delete=models.SET_NULL, null=True, verbose_name="Nombre de quien recibe")
    entregado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Entregado por", related_name="entregas_realizadas")
    fecha_entrega = models.DateField(default=timezone.now, verbose_name="Fecha de Entrega")
    
    # Cinchos
    cant_cinchos = models.PositiveIntegerField(verbose_name="Cantidad Cinchos", null=True, blank=True)
    folio_inicial = models.PositiveIntegerField(verbose_name="Folio Inicial (Cinchos)", null=True, blank=True)
    folio_final = models.PositiveIntegerField(verbose_name="Folio Final (Cinchos)", null=True, blank=True)
    
    # Tarjeta / Unidad
    unidad = models.ForeignKey(Unidad, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Número de Unidad")
    
    # --- CAMPOS MODIFICADOS ---
    para_motor = models.BooleanField(default=False, verbose_name="Para Motor")
    para_thermo = models.BooleanField(default=False, verbose_name="Para Thermo")
    # --- FIN DE MODIFICACIÓN ---
    
    entregado = models.BooleanField(default=False, verbose_name="Entregado")
    
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entrega de Suministro"
        verbose_name_plural = "Entregas de Suministros"
        ordering = ['-fecha_entrega']

    def __str__(self):
        return f"Entrega a {self.operador} el {self.fecha_entrega}"

    def get_absolute_url(self):
        return reverse('entrega-suministros-update', kwargs={'pk': self.pk})