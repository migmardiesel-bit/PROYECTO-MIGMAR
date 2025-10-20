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