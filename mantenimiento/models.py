from django.db import models
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.db.models import Q
from django.urls import reverse

# Importamos el modelo Unidad de tu app 'flota'
# Asegúrate de que el nombre 'flota' coincida con tu app existente.
from flota.models import Unidad

# --- Catálogos Administrables ---

class CatalogoHerramienta(models.Model):
    """
    Un catálogo de herramientas que el Admin puede dar de alta.
    """
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre de Herramienta")
    
    def __str__(self):
        return self.nombre

class CatalogoMantenimientoCorrectivo(models.Model):
    """
    Un catálogo de tareas correctivas comunes que el Admin puede dar de alta.
    """
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre de Tarea Correctiva")
    descripcion = models.TextField(blank=True, verbose_name="Descripción (Opcional)")

    def __str__(self):
        return self.nombre

# --- Modelos Principales de Tareas ---

class TareaMantenimiento(models.Model):
    """
    La tarea principal asignada por un Admin a un Técnico.
    """
    # --- Choices para los campos ---
    TIPO_CHOICES = [
        ('PREVENTIVO', 'Mantenimiento Preventivo'),
        ('CORRECTIVO', 'Mantenimiento Correctivo'),
    ]
    STATUS_CHOICES = [
        ('ASIGNADA', 'Asignada'),
        ('EN_PROCESO', 'En Proceso'),
        ('COMPLETADA', 'Completada'),
        ('CANCELADA', 'Cancelada'),
    ]
    
    PRIORIDAD_CHOICES = [
        ('BAJA', 'Baja'),
        ('MEDIA', 'Media'),
        ('ALTA', 'Alta'),
    ]

    # --- Filtro para el campo 'tecnico' ---
    # Busca usuarios que pertenezcan al grupo 'Tecnico' O 'Supervisor'
    limit_tecnicos = Q(groups__name='Tecnico') | Q(groups__name='Supervisor')

    # --- Campos de Asignación ---
    admin = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='tareas_asignadas',
        verbose_name="Administrador"
    )
    tecnico = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='tareas_recibidas',
        verbose_name="Técnico Asignado",
        limit_choices_to=limit_tecnicos
    )
    unidad = models.ForeignKey(
        Unidad, 
        on_delete=models.PROTECT, 
        related_name='mantenimientos',
        verbose_name="Unidad"
    )

    # --- Campos de Tarea ---
    tipo_mantenimiento = models.CharField(
        max_length=20, 
        choices=TIPO_CHOICES, 
        verbose_name="Tipo de Mantenimiento"
    )
    mantenimiento_correctivo = models.ForeignKey(
        CatalogoMantenimientoCorrectivo,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Tarea Correctiva Específica"
    )
    notas_admin = models.TextField(blank=True, verbose_name="Notas Adicionales (Admin)")

    prioridad = models.CharField(
        max_length=10, 
        choices=PRIORIDAD_CHOICES, 
        default='MEDIA',
        verbose_name="Prioridad"
    )

    # --- Campos de Estado y Tiempo ---
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='ASIGNADA',
        verbose_name="Estado"
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Asignación")
    fecha_inicio = models.DateTimeField(null=True, blank=True, verbose_name="Inicio de Tarea")
    fecha_fin = models.DateTimeField(null=True, blank=True, verbose_name="Fin de Tarea")
    tiempo_total_minutos = models.PositiveIntegerField(default=0, verbose_name="Duración Total (Minutos)")

    # --- Relación a Herramientas ---
    herramientas_solicitadas = models.ManyToManyField(
        CatalogoHerramienta,
        through='HerramientaSolicitada',
        related_name='tareas'
    )

    class Meta:
        ordering = ['-fecha_asignacion']
        verbose_name = "Tarea de Mantenimiento"
        verbose_name_plural = "Tareas de Mantenimiento"

    def __str__(self):
        return f"Tarea {self.id} ({self.get_tipo_mantenimiento_display()}) para {self.unidad.nombre}"

    def get_absolute_url(self):
        # URL para que el Admin vea el detalle
        return reverse('mantenimiento:admin_tarea_detalle', kwargs={'pk': self.pk})

    def get_tecnico_url(self):
        # URL para que el Técnico vea el detalle
        return reverse('mantenimiento:tecnico_tarea_detalle', kwargs={'pk': self.pk})

    def calcular_tiempo_total(self):
        """
        Calcula la diferencia entre fecha_fin y fecha_inicio en minutos.
        """
        if self.fecha_fin and self.fecha_inicio:
            diferencia = self.fecha_fin - self.fecha_inicio
            self.tiempo_total_minutos = int(diferencia.total_seconds() / 60)
        else:
            self.tiempo_total_minutos = 0


class TareaPreventivaSubtask(models.Model):
    """
    Almacena el estado de las sub-tareas fijas para un mantenimiento preventivo.
    """
    TAREAS_PREVENTIVAS_CHOICES = [
        ('cambio_aceite', 'Cambio de aceite'),
        ('cambio_filtros', 'Cambio de filtros'),
        ('revision_general', 'Revisión general'),
        ('niveles', 'Niveles'),
        ('diferenciales', 'Diferenciales'),
        ('buges', 'Buges'),
        ('direccion', 'Dirección'),
        ('fugas_aire', 'Fugas de aire'),
    ]

    tarea_principal = models.ForeignKey(
        TareaMantenimiento, 
        on_delete=models.CASCADE, 
        related_name='subtasks_preventivas'
    )
    nombre_subtask = models.CharField(
        max_length=100, 
        choices=TAREAS_PREVENTIVAS_CHOICES,
        verbose_name="Sub-tarea"
    )
    completada = models.BooleanField(default=False, verbose_name="Completada")

    class Meta:
        unique_together = ('tarea_principal', 'nombre_subtask') # Evita duplicados
        ordering = ['id']

    def __str__(self):
        return f"{self.get_nombre_subtask_display()} - {self.tarea_principal.id}"


class HerramientaSolicitada(models.Model):
    """
    Tabla intermedia que conecta Tareas con Herramientas.
    """
    tarea = models.ForeignKey(TareaMantenimiento, on_delete=models.CASCADE)
    herramienta = models.ForeignKey(CatalogoHerramienta, on_delete=models.PROTECT)
    # Puedes añadir cantidad si es necesario, por ahora lo omitimos por simplicidad.
    # cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('tarea', 'herramienta')

    def __str__(self):
        return f"{self.herramienta.nombre} para Tarea {self.tarea.id}"
