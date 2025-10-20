# flota/alerts.py

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from .models import CompraSuministro, CargaDiesel, CargaUrea, CargaAceite, AjusteInventario, AlertaInventario
from twilio.rest import Client

# --- La función para obtener inventario no cambia ---
def get_inventory_levels():
    """
    Calcula los niveles de inventario actuales para cada suministro.
    """
    levels = {}
    # Diésel
    compras_d = CompraSuministro.objects.filter(tipo_suministro='DIESEL').aggregate(total=Sum('cantidad'))['total'] or 0
    consumo_d_motor = CargaDiesel.objects.aggregate(total=Sum('lts_diesel'))['total'] or 0
    consumo_d_thermo = CargaDiesel.objects.aggregate(total=Sum('lts_thermo'))['total'] or 0
    ajustes_d = AjusteInventario.objects.filter(tipo_suministro='DIESEL').aggregate(total=Sum('cantidad'))['total'] or 0
    levels['DIESEL'] = compras_d - (consumo_d_motor + consumo_d_thermo) + ajustes_d
    # Urea
    compras_u = CompraSuministro.objects.filter(tipo_suministro='UREA').aggregate(total=Sum('cantidad'))['total'] or 0
    consumo_u = CargaUrea.objects.aggregate(total=Sum('litros_cargados'))['total'] or 0
    ajustes_u = AjusteInventario.objects.filter(tipo_suministro='UREA').aggregate(total=Sum('cantidad'))['total'] or 0
    levels['UREA'] = compras_u - consumo_u + ajustes_u
    # Aceite
    compras_a = CompraSuministro.objects.filter(tipo_suministro='ACEITE').aggregate(total=Sum('cantidad'))['total'] or 0
    consumo_a = CargaAceite.objects.aggregate(total=Sum('cantidad'))['total'] or 0
    ajustes_a = AjusteInventario.objects.filter(tipo_suministro='ACEITE').aggregate(total=Sum('cantidad'))['total'] or 0
    levels['ACEITE'] = compras_a - consumo_a + ajustes_a
    return levels

# --- Lógica de Alertas Unificadas (sin cambios) ---
def check_inventory_and_alert():
    current_levels = get_inventory_levels()
    alert_configs = settings.INVENTORY_ALERT_SETTINGS
    low_inventory_items = []
    should_notify = False
    is_reminder = True
    for suministro, config in alert_configs.items():
        current_level = current_levels.get(suministro, 0)
        threshold = config.get('threshold', 0)
        alerta_db, _ = AlertaInventario.objects.get_or_create(tipo_suministro=suministro)
        if current_level <= threshold:
            low_inventory_items.append({
                'nombre': suministro.title(), 'nivel': current_level,
                'umbral': threshold, 'alerta_db': alerta_db
            })
            if not alerta_db.activa:
                should_notify = True
                is_reminder = False
        elif alerta_db.activa:
            print(f"INFO: Desactivando alerta para {suministro}.")
            send_resolution_notification(suministro, current_level, threshold)
            alerta_db.activa = False
            alerta_db.nivel_reportado = current_level
            alerta_db.save()
    if not low_inventory_items: return
    if not should_notify:
        first_item = low_inventory_items[0]
        if first_item['alerta_db'].ultimo_aviso and (timezone.now() - first_item['alerta_db'].ultimo_aviso > timedelta(hours=2)):
            should_notify = True
            is_reminder = True
    if should_notify:
        print(f"INFO: Enviando notificación unificada para {len(low_inventory_items)} suministros.")
        send_unified_notification(low_inventory_items, is_reminder)
        now = timezone.now()
        for item in low_inventory_items:
            item['alerta_db'].activa = True
            item['alerta_db'].ultimo_aviso = now
            item['alerta_db'].nivel_reportado = item['nivel']
            item['alerta_db'].save()

def send_unified_notification(low_items, is_reminder=False):
    subject_prefix = "[RECORDATORIO] " if is_reminder else "[ALERTA] "
    email_subject = f"{subject_prefix}Niveles Bajos de Inventario Detectados"
    details_list = [f"  - {item['nombre']}: {item['nivel']:.2f} L (Umbral: {item['umbral']:.2f} L)" for item in low_items]
    details_str = "\n".join(details_list)
    email_body = (f"Se han detectado los siguientes niveles bajos de inventario:\n\n{details_str}\n\nPor favor, programe las compras necesarias.")
    whatsapp_details_list = []
    for item in low_items:
        icon = "⛽" if item['nombre'] == 'Diésel' else ("💧" if item['nombre'] == 'Urea' else "🛢️")
        whatsapp_details_list.append(f"{icon} *{item['nombre']}:* {item['nivel']:.2f} L")
    whatsapp_body = (f"🚨 *{subject_prefix.strip()}* 🚨\nNiveles bajos de inventario:\n\n{'\n'.join(whatsapp_details_list)}\n\nFavor de reabastecer.")
    email_recipients = settings.INVENTORY_ALERT_SETTINGS.get('DIESEL', {}).get('recipients', [])
    if email_recipients:
        try:
            send_mail(email_subject, email_body, settings.DEFAULT_FROM_EMAIL, email_recipients, fail_silently=False)
            print("ÉXITO: Correo de alerta unificado enviado.")
        except Exception as e:
            print(f"ERROR: No se pudo enviar el correo de alerta unificado. Error: {e}")
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        for recipient in settings.WHATSAPP_RECIPIENTS:
            message = client.messages.create(from_=settings.TWILIO_WHATSAPP_FROM, to=recipient, body=whatsapp_body)
            print(f"ÉXITO: Mensaje de WhatsApp unificado enviado a {recipient}.")
    except Exception as e:
        print(f"ERROR: No se pudo enviar el mensaje de WhatsApp unificado. Error: {e}")

def send_resolution_notification(suministro, current_level, threshold):
    subject = f"[RESUELTO] Nivel de {suministro.title()} Normalizado"
    message = (f"El nivel de inventario para {suministro.title()} ha sido reabastecido.\n\nNivel Actual: {current_level:.2f} Litros\n\nLa alerta ha sido desactivada.")
    recipients = settings.INVENTORY_ALERT_SETTINGS.get(suministro, {}).get('recipients', [])
    if recipients:
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)
            print(f"ÉXITO: Correo de resolución para {suministro} enviado.")
        except Exception as e:
            print(f"ERROR: No se pudo enviar el correo de resolución. Error: {e}")

# --- Reporte Manual (sin cambios) ---
def send_on_demand_status_report(user):
    current_levels = get_inventory_levels()
    report_body = (
        f"Reporte de Estado de Inventario solicitado por: {user.get_full_name() or user.username}\n"
        f"Fecha y Hora: {timezone.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
        "-------------------------------------\n"
        f"  - Diésel: {current_levels.get('DIESEL', 0):.2f} Litros\n"
        f"  - Urea:   {current_levels.get('UREA', 0):.2f} Litros\n"
        f"  - Aceite: {current_levels.get('ACEITE', 0):.2f} Litros\n"
        "-------------------------------------"
    )
    email_subject = "Reporte Manual de Estado de Inventario de Flota"
    email_recipients = settings.INVENTORY_ALERT_SETTINGS.get('DIESEL', {}).get('recipients', [])
    if email_recipients:
        try:
            send_mail(email_subject, report_body, settings.DEFAULT_FROM_EMAIL, email_recipients, fail_silently=False)
            print("ÉXITO: Reporte de estado manual enviado por correo.")
        except Exception as e: print(f"ERROR: No se pudo enviar el correo del reporte. Error: {e}")
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        whatsapp_body = (f"📋 *Reporte de Inventario Manual*\n\n⛽ *Diésel:* {current_levels.get('DIESEL', 0):.2f} L\n💧 *Urea:* {current_levels.get('UREA', 0):.2f} L\n🛢️ *Aceite:* {current_levels.get('ACEITE', 0):.2f} L\n\n_Solicitado por: {user.get_full_name() or user.username}_")
        for recipient in settings.WHATSAPP_RECIPIENTS:
            message = client.messages.create(from_=settings.TWILIO_WHATSAPP_FROM, to=recipient, body=whatsapp_body)
            print(f"ÉXITO: Reporte manual enviado por WhatsApp a {recipient}.")
    except Exception as e: print(f"ERROR: No se pudo enviar el WhatsApp del reporte. Error: {e}")
    return True

# ======================================================================
# INICIO DE LA FUNCIÓN MODIFICADA
# ======================================================================
def send_refuel_notification(carga_diesel_instance):
    """
    Envía una notificación informativa con el desglose de la carga de diésel
    y el estado actual del inventario general.
    """
    unidad = carga_diesel_instance.unidad
    current_levels = get_inventory_levels()
    total_liters = carga_diesel_instance.lts_diesel

    # --- 1. Construir el desglose de la carga dinámicamente ---
    
    # Para el correo electrónico (más detallado)
    email_charge_details = [f"  - Diésel (Motor): {carga_diesel_instance.lts_diesel:.2f} L"]
    if carga_diesel_instance.lts_thermo and carga_diesel_instance.lts_thermo > 0:
        email_charge_details.append(f"  - Diésel (Thermo): {carga_diesel_instance.lts_thermo:.2f} L")
        total_liters += carga_diesel_instance.lts_thermo
        email_charge_details.append(f"  - TOTAL CARGADO: {total_liters:.2f} L")
    
    # Para WhatsApp (más conciso)
    whatsapp_charge_details = [f"  - Motor: {carga_diesel_instance.lts_diesel:.2f} L"]
    if carga_diesel_instance.lts_thermo and carga_diesel_instance.lts_thermo > 0:
        whatsapp_charge_details.append(f"  - Thermo: {carga_diesel_instance.lts_thermo:.2f} L")

    # --- 2. Construir cuerpos completos de los mensajes ---
    email_subject = f"Notificación de Carga de Diésel - Unidad {unidad.nombre}"
    email_body = (
        f"Se ha registrado una nueva carga de combustible.\n\n"
        f"  - Unidad: {unidad.nombre}\n"
        f"  - Fecha y Hora: {carga_diesel_instance.fecha.strftime('%d/%m/%Y %H:%M')}\n\n"
        f"DETALLE DE LA CARGA:\n"
        f"{'\n'.join(email_charge_details)}\n\n"
        "-------------------------------------\n"
        "ESTADO ACTUAL DEL INVENTARIO GENERAL:\n"
        "-------------------------------------\n"
        f"  - Diésel: {current_levels.get('DIESEL', 0):.2f} Litros\n"
        f"  - Urea:   {current_levels.get('UREA', 0):.2f} Litros\n"
        f"  - Aceite: {current_levels.get('ACEITE', 0):.2f} Litros\n"
    )

    whatsapp_body = (
        f"⛽ *Notificación de Carga*\n\n"
        f"▪️ *Unidad:* {unidad.nombre}\n"
        f"*Detalle de Carga:*\n"
        f"{'\n'.join(whatsapp_charge_details)}\n\n"
        f"📊 *Inventario Actual:*\n"
        f"  - Diésel: {current_levels.get('DIESEL', 0):.2f} L\n"
        f"  - Urea: {current_levels.get('UREA', 0):.2f} L\n"
        f"  - Aceite: {current_levels.get('ACEITE', 0):.2f} L"
    )

    # --- 3. Enviar Correo Electrónico ---
    email_recipients = settings.INVENTORY_ALERT_SETTINGS.get('DIESEL', {}).get('recipients', [])
    if email_recipients:
        try:
            send_mail(email_subject, email_body, settings.DEFAULT_FROM_EMAIL, email_recipients, fail_silently=False)
            print(f"ÉXITO: Correo de notificación de carga para {unidad.nombre} enviado.")
        except Exception as e:
            print(f"ERROR: No se pudo enviar el correo de notificación de carga. Error: {e}")

    # --- 4. Enviar WhatsApp ---
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        for recipient in settings.WHATSAPP_RECIPIENTS:
            message = client.messages.create(
                from_=settings.TWILIO_WHATSAPP_FROM,
                to=recipient,
                body=whatsapp_body
            )
            print(f"ÉXITO: WhatsApp de notificación de carga para {unidad.nombre} enviado a {recipient}.")
    except Exception as e:
        print(f"ERROR: No se pudo enviar el WhatsApp de notificación de carga. Error: {e}")