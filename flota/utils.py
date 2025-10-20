# flota/utils.py

from django.db import transaction
from .models import CompraSuministro, CargaDiesel, CargaUrea
from decimal import Decimal

def recalcular_costos_cargas_diesel():
    """
    Función central que recalcula el costo de TODAS las cargas de diésel
    y actualiza los litros restantes en TODAS las compras.
    Es la única fuente de verdad para el inventario FIFO.
    """
    with transaction.atomic():
        compras = CompraSuministro.objects.filter(tipo_suministro='DIESEL').order_by('fecha_compra')
        cargas = CargaDiesel.objects.all().order_by('fecha')

        for compra in compras:
            compra.litros_restantes = compra.cantidad
        
        compras_iterator = iter(compras)
        current_compra = next(compras_iterator, None)

        cargas_a_actualizar = []
        compras_a_actualizar = {}

        for carga in cargas:
            carga.costo = Decimal('0.0')
            litros_pendientes_de_la_carga = carga.lts_diesel + (carga.lts_thermo or 0)

            while litros_pendientes_de_la_carga > 0 and current_compra:
                litros_a_tomar = min(litros_pendientes_de_la_carga, current_compra.litros_restantes)
                
                if current_compra.precio_por_litro:
                    carga.costo += litros_a_tomar * current_compra.precio_por_litro

                current_compra.litros_restantes -= litros_a_tomar
                litros_pendientes_de_la_carga -= litros_a_tomar
                
                compras_a_actualizar[current_compra.pk] = current_compra

                if current_compra.litros_restantes <= 0:
                    current_compra = next(compras_iterator, None)
            
            cargas_a_actualizar.append(carga)

        if cargas_a_actualizar:
            CargaDiesel.objects.bulk_update(cargas_a_actualizar, ['costo'])
        
        if compras_a_actualizar:
            CompraSuministro.objects.bulk_update(
                list(compras_a_actualizar.values()),
                ['litros_restantes']
            )

# --- INICIO DE LA NUEVA FUNCIÓN PARA UREA ---
def recalcular_costos_cargas_urea():
    """
    Función central que recalcula el costo de TODAS las cargas de urea
    y actualiza los litros restantes en TODAS las compras de urea.
    Funciona de manera idéntica a la del diésel, pero para el suministro de urea.
    """
    with transaction.atomic():
        # 1. Obtener todos los registros de UREA, ordenados por fecha.
        compras = CompraSuministro.objects.filter(tipo_suministro='UREA').order_by('fecha_compra')
        cargas = CargaUrea.objects.all().order_by('fecha')

        # 2. Reiniciar el estado del inventario de urea.
        for compra in compras:
            compra.litros_restantes = compra.cantidad
        
        compras_iterator = iter(compras)
        current_compra = next(compras_iterator, None)

        cargas_a_actualizar = []
        compras_a_actualizar = {}

        # 3. Iterar sobre cada carga de urea y calcular su costo.
        for carga in cargas:
            carga.costo = Decimal('0.0')
            litros_pendientes_de_la_carga = carga.litros_cargados

            while litros_pendientes_de_la_carga > 0 and current_compra:
                litros_a_tomar = min(litros_pendientes_de_la_carga, current_compra.litros_restantes)
                
                if current_compra.precio_por_litro:
                    carga.costo += litros_a_tomar * current_compra.precio_por_litro

                current_compra.litros_restantes -= litros_a_tomar
                litros_pendientes_de_la_carga -= litros_a_tomar
                
                compras_a_actualizar[current_compra.pk] = current_compra

                if current_compra.litros_restantes <= 0:
                    current_compra = next(compras_iterator, None)
            
            cargas_a_actualizar.append(carga)

        # 4. Guardar todos los cambios en la base de datos de forma masiva.
        if cargas_a_actualizar:
            CargaUrea.objects.bulk_update(cargas_a_actualizar, ['costo'])
        
        if compras_a_actualizar:
            CompraSuministro.objects.bulk_update(
                list(compras_a_actualizar.values()),
                ['litros_restantes']
            )
# --- FIN DE LA NUEVA FUNCIÓN PARA UREA ---