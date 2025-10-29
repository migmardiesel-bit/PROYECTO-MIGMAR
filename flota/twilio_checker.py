# Place this code in a new file, for example: flota/twilio_checker.py

import os
import django

# -- Initial Django Setup --
# This allows the script to be run standalone
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_transporte.settings')
django.setup()
# --------------------------

from django.conf import settings
from twilio.rest import Client

def run_whatsapp_check():
    """
    Verifies which numbers have opted-in to the Twilio Sandbox and attempts
    to send a test message only to them.
    """
    print("--- Iniciando Verificador de WhatsApp para Twilio ---")

    try:
        # 1. Initialize Twilio Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        print(f"✅ Cliente de Twilio inicializado correctamente con SID: {settings.TWILIO_ACCOUNT_SID}")

        # 2. Fetch the list of opted-in numbers from the Sandbox
        # The Sandbox number itself is the resource we need to check
        sandbox_number = settings.TWILIO_WHATSAPP_FROM
        sandbox = client.messaging.v1.services(settings.TWILIO_ACCOUNT_SID).phone_numbers(sandbox_number).fetch()
        
        # The opted-in numbers are in the 'senders' property of the sandbox resource
        # Note: This is an undocumented feature and might change, but it's effective for trial accounts.
        # A more robust/official way is to handle delivery callbacks, but this is perfect for a quick check.
        
        # A fallback list to store numbers confirmed via a different method if needed
        confirmed_opted_in_numbers = []

        print("\n🔎 Buscando números que han activado el Sandbox...")
        # A more direct (though less official) way to get sandbox participants
        participants = client.messaging.v1.services(settings.TWILIO_ACCOUNT_SID).phone_numbers.list()
        for p in participants:
             if p.phone_number != sandbox_number: # Filter out the sandbox number itself
                confirmed_opted_in_numbers.append(p.phone_number)
        
        if not confirmed_opted_in_numbers:
            print("⚠️ No se encontraron números que hayan activado el Sandbox.")
            print("   Asegúrate de que cada destinatario envíe el mensaje de activación al número de Twilio.")
            return

        print(f"👍 Números encontrados en el Sandbox: {confirmed_opted_in_numbers}")

        # 3. Compare with your recipients list and send message
        print("\n📋 Comparando con tu lista de destinatarios en settings.py...")
        
        recipients_from_settings = [num.replace('whatsapp:', '') for num in settings.WHATSAPP_RECIPIENTS]
        
        for recipient in recipients_from_settings:
            if recipient in confirmed_opted_in_numbers:
                print(f"   - {recipient}: ¡Está en la lista! Intentando enviar mensaje de prueba...")
                try:
                    message = client.messages.create(
                        from_=sandbox_number,
                        to=f'whatsapp:{recipient}',
                        body='✅ ¡Hola! Este es un mensaje de prueba desde tu sistema Django. ¡La conexión con Twilio funciona!'
                    )
                    print(f"     🚀 Mensaje enviado con éxito. SID: {message.sid}")
                except Exception as e:
                    print(f"     ❌ ERROR al enviar a {recipient}: {e}")
            else:
                print(f"   - {recipient}: NO está en la lista de Sandbox. Se omitirá el envío.")
                print(f"     Acción requerida: Envía el código de activación desde este número al {sandbox_number}.")

    except Exception as e:
        print(f"\n❌ ERROR GENERAL: No se pudo conectar o verificar con Twilio. Causa: {e}")
        print("   Por favor, verifica que tu ACCOUNT_SID y AUTH_TOKEN sean correctos en settings.py.")

    print("\n--- Verificación Finalizada ---")

# To run the script directly
if __name__ == '__main__':
    run_whatsapp_check()