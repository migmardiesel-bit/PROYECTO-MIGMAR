import os
import django

# 1. --- ESTA ES LA PARTE NUEVA ---
# Le dice al script dónde encontrar la configuración de tu proyecto
# Tu proyecto se llama 'gestion_transporte'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_transporte.settings')
django.setup()
# ---------------------------------


# 2. --- ESTE ES EL SCRIPT ORIGINAL ---
from flota.models import ChecklistInspeccion, ChecklistCorreccion
from django.db import transaction

# Esta es la lista de campos a revisar, sacada de tu models.py
FIELD_NAMES = [
    'cristales', 'espejos', 'logos', 'num_economico', 'puertas', 'cofre', 'parrilla', 
    'defensas', 'faros', 'plafoneria', 'stops', 'direccionales', 'tapiceria', 
    'instrumentos', 'carroceria', 'piso', 'costados', 'escape', 'pintura', 
    'franjas', 'loderas', 'extintor', 'senalamientos', 'estado_general', 
    'motor', 'caja', 'diferenciales', 'suspension_delantera', 'suspension_trasera', 
    'fugas_combustible', 'fugas_aceite', 'estado_llantas', 'presion_llantas', 
    'purga_tanques', 'estado_balatas', 'amortiguadores_delanteros', 
    'amortiguadores_traseros', 'rines_aluminio', 'mangueras_servicio', 
    'tarjeta_llave', 'revision_fusibles', 'revision_luces', 'revision_cable_7vias', 
    'revision_fuga_aire'
]

items_creados = 0
items_ya_pendientes = 0
items_ya_resueltos = 0

print("Iniciando migración de datos de fallas antiguas...")

# Usamos transaction.atomic para que sea una sola operación
with transaction.atomic():
    # Iteramos sobre todas las inspecciones, de la más antigua a la más nueva
    for inspeccion in ChecklistInspeccion.objects.order_by('fecha'):
        for campo in FIELD_NAMES:
            # Verificamos si el campo está como 'MALO'
            if getattr(inspeccion, campo) == 'MALO':
                
                # 1. Revisamos si ya existe una falla PENDIENTE para esta *unidad* y *campo*
                # (Esta es la lógica de de-duplicación de tu models.py)
                falla_pendiente_existe = ChecklistCorreccion.objects.filter(
                    inspeccion__unidad=inspeccion.unidad,
                    nombre_campo=campo,
                    status='PENDIENTE' #
                ).exists()
                
                if falla_pendiente_existe:
                    # Ya existe una falla pendiente. No hacemos nada.
                    items_ya_pendientes += 1
                else:
                    # No hay falla pendiente.
                    # 2. Creamos el registro de corrección si no existe para ESTA inspección.
                    obj, created = ChecklistCorreccion.objects.get_or_create(
                        inspeccion=inspeccion,
                        nombre_campo=campo,
                        defaults={
                            'observacion_original': getattr(inspeccion, f'{campo}_obs', ""),
                            'status': 'PENDIENTE' # Lo creamos como PENDIENTE
                        }
                    )
                    
                    if created:
                        # ¡Éxito! Creamos el nuevo registro de corrección.
                        items_creados += 1
                    else:
                        # Ya existía un registro (ej. 'CORREGIDO' o 'DESCARTADO')
                        # asociado a ESTA inspección. No lo tocamos.
                        items_ya_resueltos += 1

print("\n¡Migración completada!")
print(f"Se crearon {items_creados} nuevos registros 'PENDIENTE'.")
print(f"Se omitieron {items_ya_pendientes} porque ya existía una falla 'PENDIENTE' para esa unidad/item.")
print(f"Se omitieron {items_ya_resueltos} porque ya existía un registro (resuelto) asociado a esa inspección específica.")