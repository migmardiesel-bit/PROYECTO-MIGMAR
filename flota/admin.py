# flota/admin.py

from django.contrib import admin
from .models import (
    Operador,
    Unidad,
    CargaDiesel,
    CargaAceite,
    CargaUrea,
    CompraSuministro,
    ChecklistInspeccion,
)

# Se recomienda usar ModelAdmin para mejorar la visualización
class UnidadAdmin(admin.ModelAdmin):
    list_display = ('marca', 'modelo', 'placas', 'tipo', 'km_actual')
    list_filter = ('tipo', 'marca')
    search_fields = ('placas', 'vin', 'modelo')

class CargaDieselAdmin(admin.ModelAdmin):
    list_display = ('unidad', 'fecha', 'operador', 'lts_diesel', 'km_actual')
    list_filter = ('unidad',)
    date_hierarchy = 'fecha'

class CompraSuministroAdmin(admin.ModelAdmin):
    list_display = ('fecha_compra', 'tipo_suministro', 'proveedor', 'cantidad', 'precio')
    list_filter = ('tipo_suministro', 'proveedor')
    date_hierarchy = 'fecha_compra'

# Registrando todos los modelos
admin.site.register(Operador)
admin.site.register(Unidad, UnidadAdmin)
admin.site.register(CargaDiesel, CargaDieselAdmin)
admin.site.register(CargaAceite)
admin.site.register(CargaUrea)
admin.site.register(CompraSuministro, CompraSuministroAdmin)
admin.site.register(ChecklistInspeccion)