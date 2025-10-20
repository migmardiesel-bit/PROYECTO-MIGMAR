# flota/management/commands/check_inventory.py

from django.core.management.base import BaseCommand
from flota.alerts import check_inventory_and_alert

class Command(BaseCommand):
    help = 'Ejecuta la verificación de niveles de inventario y envía las alertas correspondientes.'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando la verificación programada de inventario...')
        check_inventory_and_alert()
        self.stdout.write(self.style.SUCCESS('Verificación de inventario completada exitosamente.'))