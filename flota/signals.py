# flota/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CargaDiesel, CargaUrea, CargaAceite, CompraSuministro, AjusteInventario
from .alerts import check_inventory_and_alert, send_refuel_notification # <-- Importar la nueva función

@receiver(post_save, sender=CargaDiesel)
@receiver(post_save, sender=CargaUrea)
@receiver(post_save, sender=CargaAceite)
@receiver(post_save, sender=CompraSuministro)
@receiver(post_save, sender=AjusteInventario)
def on_inventory_change(sender, instance, created, **kwargs): # <-- Añadir 'created'
    """
    Se dispara cada vez que un modelo que afecta el inventario es guardado.
    """
    print(f"SIGNAL: Cambio en inventario por {sender.__name__}. Revisando alertas de bajo stock...")
    # 1. Siempre se ejecuta el chequeo de alertas de bajo inventario.
    check_inventory_and_alert()

    # 2. Adicionalmente, si se *creó* una nueva CargaDiesel, se envía la notificación de carga.
    if sender == CargaDiesel and created:
        print(f"SIGNAL: Nueva CargaDiesel creada para la unidad {instance.unidad.nombre}. Enviando notificación de carga...")
        send_refuel_notification(instance)
        
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ChecklistInspeccion, ChecklistCorreccion

@receiver(post_save, sender=ChecklistInspeccion)
def crear_o_actualizar_correcciones_checklist(sender, instance, created, **kwargs):
    """
    Esta señal se dispara DESPUÉS de que un ChecklistInspeccion se guarda (post_save).
    
    Aquí es donde vive la lógica que antes estaba en el método .save().
    Esto permite que la vista del usuario responda inmediatamente después de guardar
    el checklist, y esta lógica se ejecuta en segundo plano.
    
    Argumentos:
    - sender: El modelo que envió la señal (ChecklistInspeccion)
    - instance: La instancia específica del modelo que se guardó
    - created: Un booleano; True si el registro fue creado, False si fue una actualización.
    """

    # 1. Lista de campos a revisar
    FIELD_NAMES = [
        'cristales', 'espejos', 'logos', 'num_economico', 'puertas', 'cofre', 'parrilla', 
        'defensas', 'faros', 'plafoneria', 'stops', 'direccionales', 'tapiceria', 
        'instrumentos', 'carroceria', 'piso', 'costados', 'escape', 'pintura', 
        'franjas', 'loderas', 'extintor', 'senalamientos', 'estado_general', 
        'motor', 'caja', 'diferenciales', 'suspension_delantera', 'suspension_trasera', 
        'fugas_combustible', 'fugas_aceite', 'estado_llantas', 'presion_llantas', 
        'purga_tanques', 'estado_balatas', 'amortiguadores_delanteros', 
        'amortiguadores_traseros', 'rines_aluminio', 'mangueras_servicio', 
        'tarjeta_llave', 'revision_fusibles', 'revision_luces',
        'revision_fuga_aire'
    ]

    # 2. Iterar y aplicar la lógica (la misma que tenías antes)
    # Usamos 'instance' en lugar de 'self'
    for campo in FIELD_NAMES:
        estado_campo = getattr(instance, campo)

        if estado_campo == 'MALO':
            nueva_observacion = getattr(instance, f'{campo}_obs', None)
            nueva_foto = getattr(instance, f'{campo}_foto', None) 

            # Buscamos la falla pendiente
            existing_pending_fault = ChecklistCorreccion.objects.filter(
                inspeccion__unidad=instance.unidad,
                nombre_campo=campo,
                status='PENDIENTE'
            ).first()

            if existing_pending_fault:
                # SI EXISTE: Actualizamos el registro de corrección.
                existing_pending_fault.observacion_original = nueva_observacion
                if nueva_foto:
                    existing_pending_fault.foto_evidencia = nueva_foto
                existing_pending_fault.save() # Guarda los cambios

            else:
                # NO EXISTE: Creamos un nuevo registro de falla pendiente.
                ChecklistCorreccion.objects.create(
                    inspeccion=instance,
                    nombre_campo=campo,
                    observacion_original=nueva_observacion,
                    foto_evidencia=nueva_foto,
                    status='PENDIENTE',
                )
        
        elif estado_campo == 'BIEN':
            pass # No afecta fallas pendientes.