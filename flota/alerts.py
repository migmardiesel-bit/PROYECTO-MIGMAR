# flota/alerts.py

from django.conf import settings
# --- IMPORT MODIFICADO ---
from django.core.mail import send_mail, EmailMultiAlternatives
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from .models import CompraSuministro, CargaDiesel, CargaUrea, CargaAceite, AjusteInventario, AlertaInventario
from twilio.rest import Client

# --- NUEVOS IMPORTS ---
from email.mime.image import MIMEImage
from django.core.files.storage import default_storage # Para leer archivos de S3/local
import os


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
# INICIO DE LA FUNCIÓN REEMPLAZADA (CON IMÁGENES)
# ======================================================================
def send_refuel_notification(carga_diesel_instance):
    """
    Envía una notificación informativa por CORREO (con imágenes) y WhatsApp
    con el desglose de la carga de diésel y el estado del inventario.
    """
    
    # --- 1. Obtener datos básicos ---
    unidad = carga_diesel_instance.unidad
    current_levels = get_inventory_levels()
    hora_local = timezone.localtime(carga_diesel_instance.fecha)
    fecha_formateada = hora_local.strftime('%d/%m/%Y %H:%M')

    lts_motor = carga_diesel_instance.lts_diesel
    lts_thermo = carga_diesel_instance.lts_thermo or 0
    total_cargado = lts_motor + lts_thermo

    # --- 2. Preparar el contexto para los mensajes ---
    context = {
        'unidad_nombre': unidad.nombre,
        'fecha_formateada': fecha_formateada,
        'lts_motor': lts_motor,
        'lts_thermo': lts_thermo,
        'total_cargado': total_cargado,
        'diesel_actual': current_levels.get('DIESEL', 0),
        'urea_actual': current_levels.get('UREA', 0),
        'aceite_actual': current_levels.get('ACEITE', 0),
    }

    # --- 3. Construir lista de imágenes y cuerpo HTML ---
    
    # (Usaremos un string simple, pero podrías usar un template de Django)
    html_body = f"""
    <h3>Notificación de Carga de Combustible</h3>
    <p>Se ha registrado una nueva carga para la unidad: <strong>{context['unidad_nombre']}</strong></p>
    <p><strong>Fecha y Hora:</strong> {context['fecha_formateada']}</p>
    
    <h4>Detalle de la Carga:</h4>
    <ul>
        <li>Diésel (Motor): {context['lts_motor']:.2f} L</li>
    """
    if context['lts_thermo'] > 0:
        html_body += f"<li>Diésel (Thermo): {context['lts_thermo']:.2f} L</li>"
        html_body += f"<li><strong>TOTAL CARGADO: {context['total_cargado']:.2f} L</strong></li>"
    
    html_body += "</ul><h4>Evidencia Fotográfica:</h4>"

    # Lista de tuplas (Content-ID, campo_de_imagen)
    imagenes_a_adjuntar = []
    
    # Intentar obtener fotos del checklist
    try:
        # El modelo ProcesoCarga tiene un OneToOne A la CargaDiesel,
        # así que podemos acceder a él con .procesocarga
        checklist = carga_diesel_instance.procesocarga.checklist
        if checklist.foto_odometro:
            imagenes_a_adjuntar.append(('foto_odometro', checklist.foto_odometro))
            html_body += '<p><strong>Foto Odómetro:</strong><br/><img src="cid:foto_odometro" style="max-width: 300px; height: auto;"></p>'
        
        if checklist.foto_thermo_hrs:
            imagenes_a_adjuntar.append(('foto_thermo_hrs', checklist.foto_thermo_hrs))
            html_body += '<p><strong>Foto Horas Thermo:</strong><br/><img src="cid:foto_thermo_hrs" style="max-width: 300px; height: auto;"></p>'

    except Exception as e:
        print(f"NOTA: No se pudo obtener el checklist para la carga {carga_diesel_instance.pk}. Error: {e}")
        html_body += "<p><em>(No se encontró un checklist asociado para las fotos del odómetro)</em></p>"

    # Añadir fotos de la carga de diésel
    if carga_diesel_instance.foto_motor:
        imagenes_a_adjuntar.append(('foto_motor', carga_diesel_instance.foto_motor))
        html_body += '<p><strong>Foto Bomba Motor:</strong><br/><img src="cid:foto_motor" style="max-width: 300px; height: auto;"></p>'

    if carga_diesel_instance.foto_thermo:
        imagenes_a_adjuntar.append(('foto_thermo', carga_diesel_instance.foto_thermo))
        html_body += '<p><strong>Foto Bomba Thermo:</strong><br/><img src="cid:foto_thermo" style="max-width: 300px; height: auto;"></p>'
    
    # Añadir pie de página con inventario
    html_body += f"""
    <hr>
    <h4>Estado Actual del Inventario General:</h4>
    <ul>
        <li>Diésel: {context['diesel_actual']:.2f} L</li>
        <li>Urea: {context['urea_actual']:.2f} L</li>
        <li>Aceite: {context['aceite_actual']:.2f} L</li>
    </ul>
    """
    
    # --- 4. Enviar Correo Electrónico ---
    email_subject = f"Notificación de Carga de Diésel - Unidad {unidad.nombre}"
    email_recipients = settings.INVENTORY_ALERT_SETTINGS.get('DIESEL', {}).get('recipients', [])

    if email_recipients:
        try:
            # Texto alternativo para clientes que no leen HTML
            text_body = (
                f"Se ha registrado una nueva carga de combustible.\n\n"
                f"  - Unidad: {context['unidad_nombre']}\n"
                f"  - Fecha y Hora: {context['fecha_formateada']}\n\n"
                f"DETALLE DE LA CARGA:\n"
                f"  - Diésel (Motor): {context['lts_motor']:.2f} L\n"
                + (f"  - Diésel (Thermo): {context['lts_thermo']:.2f} L\n" if context['lts_thermo'] > 0 else "") +
                f"\nESTADO ACTUAL DEL INVENTARIO GENERAL:\n"
                f"  - Diésel: {context['diesel_actual']:.2f} Litros\n"
                f"  - Urea:   {context['urea_actual']:.2f} Litros\n"
                f"  - Aceite: {context['aceite_actual']:.2f} Litros\n"
            )

            # Crear el mensaje
            msg = EmailMultiAlternatives(
                subject=email_subject,
                body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=email_recipients
            )
            
            # Adjuntar la versión HTML
            msg.attach_alternative(html_body, "text/html")
            
            # Adjuntar las imágenes
            for cid, image_field in imagenes_a_adjuntar:
                if image_field and hasattr(image_field, 'name') and image_field.name:
                    try:
                        # Abrir el archivo desde el storage (S3 o local)
                        with default_storage.open(image_field.name, 'rb') as f:
                            image_data = f.read()
                        
                        img = MIMEImage(image_data)
                        img.add_header('Content-ID', f'<{cid}>') #cid
                        img.add_header('Content-Disposition', 'inline', filename=os.path.basename(image_field.name))
                        msg.attach(img)
                    except Exception as e:
                        print(f"ERROR: No se pudo adjuntar la imagen {image_field.name} al correo. Error: {e}")

            # Enviar el correo
            msg.send()
            print(f"ÉXITO: Correo de notificación de carga (CON IMÁGENES) para {unidad.nombre} enviado.")
        
        except Exception as e:
            # Si falla el envío con imágenes, intenta enviar el de texto simple como fallback
            print(f"ERROR: No se pudo enviar el correo HTML con imágenes. Error: {e}. Intentando fallback de texto...")
            try:
                # Re-usa el text_body y subject definidos antes
                send_mail(email_subject, text_body, settings.DEFAULT_FROM_EMAIL, email_recipients, fail_silently=False)
                print(f"ÉXITO (Fallback): Correo de notificación de carga (solo texto) para {unidad.nombre} enviado.")
            except Exception as e_inner:
                print(f"ERROR (Fallback): Falló también el envío de texto. Error: {e_inner}")

    # --- 5. Enviar WhatsApp (Sin cambios) ---
    try:
        whatsapp_body = (
            f"⛽ *Notificación de Carga*\n\n"
            f"▪️ *Unidad:* {context['unidad_nombre']}\n"
            f"▪️ *Fecha:* {context['fecha_formateada']}\n"
            f"*Detalle de Carga:*\n"
            f"  - Motor: {context['lts_motor']:.2f} L\n"
            + (f"  - Thermo: {context['lts_thermo']:.2f} L\n" if context['lts_thermo'] > 0 else "") +
            f"\n📊 *Inventario Actual:*\n"
            f"  - Diésel: {context['diesel_actual']:.2f} L\n"
            f"  - Urea: {context['urea_actual']:.2f} L\n"
            f"  - Aceite: {context['aceite_actual']:.2f} L"
        )
        
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