from django.apps import AppConfig


class FlotaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'flota'

    def ready(self):
        # Esta línea importa y registra los signals cuando la aplicación está lista.
        import flota.signals