# mantenimiento/views.py (Completo y Modificado)

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.contrib import messages
from django.db import transaction # <-- IMPORTANTE PARA TRANSACCIONES
from collections import OrderedDict
from flota.models import Unidad # Importación de Unidad
from django.db.models import Q, Avg
from datetime import timedelta
from .models import (
    TareaMantenimiento, CatalogoHerramienta, CatalogoMantenimientoCorrectivo,
    TareaPreventivaSubtask, HerramientaSolicitada, ruta_evidencia_subtask # <-- IMPORTAR ruta_evidencia_subtask
)
from .forms import (
    AsignarTareaForm, CatalogoHerramientaForm, CatalogoMantenimientoCorrectivoForm,
    SeleccionarHerramientasForm, TareaPreventivaFormSet
)

# --- NUEVAS IMPORTACIONES PARA PDF ---
import os
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO

# === IMPORTS ADICIONALES PARA S3 MANUAL ===
import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError
# ===================================================


# ==============================================================================
# === NUEVAS FUNCIONES AUXILIARES PARA GESTIONAR ARCHIVOS EN S3 MANUALMENTE ===
# ==============================================================================

def _subir_archivo_a_s3(archivo_obj, s3_ruta_relativa):
    """
    Sube un archivo a S3.
    - `s3_ruta_relativa` es la ruta SIN 'media/' (ej: 'mantenimiento/tarea_10/subtask_5.jpg').
    - Devuelve la misma ruta relativa si tiene éxito, para guardarla en la DB.
    """
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        
        # Boto3 necesita la ruta completa (Key) dentro del bucket
        # Asumimos que AWS_MEDIA_LOCATION está definido, ej: 'media'
        full_s3_path = f"{settings.AWS_MEDIA_LOCATION}/{s3_ruta_relativa}"

        # Asegurarse de que el archivo esté al inicio
        archivo_obj.seek(0)
        
        s3_client.upload_fileobj(
            archivo_obj,
            settings.AWS_STORAGE_BUCKET_NAME,
            full_s3_path
        )
        return s3_ruta_relativa
        
    except (BotoCoreError, NoCredentialsError, Exception) as e:
        print(f"Error al subir el archivo a S3: {e}")
        return None

def _eliminar_archivo_de_s3(ruta_completa_s3):
    """
    Elimina un archivo de S3.
    - `ruta_completa_s3` es la ruta que Django provee (ej: 'media/mantenimiento/tarea_10.jpg'),
      que es lo que Boto3 necesita como 'Key'.
    """
    if not ruta_completa_s3:
        return
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION_NAME
        )
        s3_client.delete_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=str(ruta_completa_s3)
        )
    except (BotoCoreError, NoCredentialsError, Exception) as e:
        print(f"Error al eliminar archivo antiguo de S3: {e}")


# --- Mixins de Permisos ---

def es_admin(user):
    """
    Comprueba si el usuario está en el grupo 'Administrador' o es superuser.
    """
    return user.is_authenticated and (user.groups.filter(name='Administrador').exists() or user.is_superuser)

def es_tecnico_o_supervisor(user):
    """
    Comprueba si el usuario está en el grupo 'Tecnico' O 'Supervisor'.
    """
    return user.is_authenticated and (user.groups.filter(name='Tecnico').exists() or user.groups.filter(name='Supervisor').exists())

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return es_admin(self.request.user)

class TecnicoRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return es_tecnico_o_supervisor(self.request.user)

# --- Vistas de Administrador ---

@method_decorator(login_required, name='dispatch')
class AdminDashboardView(AdminRequiredMixin, ListView):
    """
    Dashboard del Admin: Muestra todas las tareas y su estado.
    """
    model = TareaMantenimiento
    template_name = 'mantenimiento/admin_dashboard.html'
    context_object_name = 'tareas'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Panel de Tareas de Mantenimiento"
        return context
    
    def get_queryset(self):
        # Optimización: Precarga las relaciones ForeignKey
        return TareaMantenimiento.objects.all().select_related(
            'unidad', 'tecnico', 'admin', 'mantenimiento_correctivo'
        )

@method_decorator(login_required, name='dispatch')
class AsignarTareaView(AdminRequiredMixin, CreateView):
    """
    Formulario para que el Admin asigne una nueva tarea.
    """
    model = TareaMantenimiento
    form_class = AsignarTareaForm
    template_name = 'mantenimiento/generic_form.html'
    success_url = reverse_lazy('mantenimiento:admin_dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Asignar Nueva Tarea de Mantenimiento"
        return context

    def form_valid(self, form):
        # Asignar el admin actual
        form.instance.admin = self.request.user
        
        # Usamos una transacción para asegurar que la tarea y sub-tareas se creen juntas
        with transaction.atomic():
            # Guardamos la tarea principal
            tarea = form.save()
            
            # Si es Preventivo, creamos todas las sub-tareas fijas
            if tarea.tipo_mantenimiento == 'PREVENTIVO':
                subtasks_a_crear = []
                for choice_val, choice_name in TareaPreventivaSubtask.TAREAS_PREVENTIVAS_CHOICES:
                    subtasks_a_crear.append(
                        TareaPreventivaSubtask(tarea_principal=tarea, nombre_subtask=choice_val)
                    )
                # Creamos todas las sub-tareas en una sola consulta
                TareaPreventivaSubtask.objects.bulk_create(subtasks_a_crear)
                
        messages.success(self.request, f"Tarea {tarea.id} asignada a {tarea.tecnico.username}.")
        return redirect(self.success_url)

@method_decorator(login_required, name='dispatch')
class AdminTareaDetalleView(AdminRequiredMixin, DetailView):
    """
    Vista de detalle para que el Admin vea el progreso y herramientas.
    """
    model = TareaMantenimiento
    template_name = 'mantenimiento/admin_tarea_detalle.html'
    context_object_name = 'tarea'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tarea = self.get_object()
        context['titulo'] = f"Detalle Tarea {tarea.id} - {tarea.unidad.nombre}"
        
        # Obtenemos las herramientas solicitadas
        context['herramientas'] = tarea.herramientas_solicitadas.all()
        
        # Si es preventivo, obtenemos las sub-tareas
        if tarea.tipo_mantenimiento == 'PREVENTIVO':
            # Optimizamos para precargar las fotos
            context['subtasks'] = tarea.subtasks_preventivas.all()
            
        return context

# --- Vistas del Técnico ---

@method_decorator(login_required, name='dispatch')
@method_decorator(login_required, name='dispatch')
class TecnicoDashboardView(TecnicoRequiredMixin, ListView):
    """
    Dashboard del Técnico: Muestra tareas asignadas a él.
    """
    model = TareaMantenimiento
    template_name = 'mantenimiento/tecnico_dashboard.html'
    context_object_name = 'tareas'

    def get_queryset(self):
        qs = super().get_queryset() # Llama al get_queryset de la clase padre (ListView)
        
        # Obtenemos el queryset base (definido en la solución 1.A)
        qs = TareaMantenimiento.objects.filter(
            tecnico=self.request.user
        ).exclude(
            status__in=['COMPLETADA', 'CANCELADA']
        ).select_related('unidad', 'admin')

        # --- LÓGICA DE FILTRO DEL BACKEND ---
        filtro_estado = self.request.GET.get('filtroEstado', '')
        filtro_tipo = self.request.GET.get('filtroTipo', '')
        filtro_unidad = self.request.GET.get('filtroUnidad', '')

        if filtro_estado and filtro_estado != 'todos':
            qs = qs.filter(status=filtro_estado)
        
        if filtro_tipo and filtro_tipo != 'todos':
            qs = qs.filter(tipo_mantenimiento=filtro_tipo)
            
        if filtro_unidad and filtro_unidad != 'todos':
            qs = qs.filter(unidad_id=filtro_unidad)
            
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Obtenemos todas las tareas asignadas al técnico
        all_my_tasks = TareaMantenimiento.objects.filter(tecnico=self.request.user)
        
        # --- 1. CONTEOS PARA LAS TARJETAS DE MÉTRICAS ---
        context['tareas_pendientes_count'] = all_my_tasks.filter(status='ASIGNADA').count()
        context['tareas_en_proceso_count'] = all_my_tasks.filter(status='EN_PROCESO').count()
        
        # Tareas completadas en los últimos 7 días
        seven_days_ago = timezone.now() - timedelta(days=7)
        completadas_recientes_qs = all_my_tasks.filter(
            status='COMPLETADA',
            fecha_fin__gte=seven_days_ago
        )
        context['tareas_completadas_recientes_count'] = completadas_recientes_qs.count()

        # --- 2. CÁLCULO DE TIEMPO PROMEDIO ---
        avg_dict = completadas_recientes_qs.aggregate(Avg('tiempo_total_minutos'))
        context['tiempo_promedio_minutos'] = round(avg_dict['tiempo_total_minutos__avg'] or 0)

        # --- 3. LISTA DE UNIDADES PARA EL FILTRO ---
        # Pasamos todas las unidades del sistema para filtrar
        context['unidades'] = Unidad.objects.all().order_by('nombre')

        # --- 4. TAREAS COMPLETADAS (YA LO TENÍAS, PERO LO AJUSTAMOS) ---
        context['tareas_completadas'] = all_my_tasks.filter(
            status='COMPLETADA'
        ).order_by('-fecha_fin')[:5]
        
        context['titulo'] = "Mis Tareas Asignadas"
        return context


@method_decorator(login_required, name='dispatch')
class TecnicoTareaDetalleView(TecnicoRequiredMixin, DetailView):
    """
    Espacio de trabajo principal del Técnico para una tarea.
    Maneja la visualización de formularios según el estado de la tarea.
    """
    model = TareaMantenimiento
    template_name = 'mantenimiento/tecnico_tarea_detalle.html'
    context_object_name = 'tarea'

    def get_object(self, queryset=None):
        return get_object_or_404(
            TareaMantenimiento, 
            pk=self.kwargs['pk'], 
            tecnico=self.request.user
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs) 
        tarea = self.get_object()
        context['titulo'] = f"Trabajando en Tarea {tarea.id} ({tarea.unidad.nombre})"

        if tarea.status == 'ASIGNADA':
            context['form_herramientas'] = SeleccionarHerramientasForm(tarea=tarea)
        
        elif tarea.status == 'EN_PROCESO':
            if tarea.tipo_mantenimiento == 'PREVENTIVO':
                
                formset = TareaPreventivaFormSet(
                    instance=tarea,
                    prefix='subtasks'
                )
                
                # --- AQUÍ ESTÁ EL CAMBIO ---
                # Actualizamos los títulos (keys) según tu solicitud.
                # Corregí "suscepción" a "Suspensión" y "Revisor" a "Revisión".
                
                TASK_GROUPS = OrderedDict([
                    ('Cambios y Revisión', [
                        'camb_filtro', 'camb_anticong'
                    ]),
                    ('Revisión general de unidad', [
                        'gral_fusibles', 'gral_luces', 'gral_fugas_aire', 
                        'gral_llantas', 'gral_fugas_aceite'
                    ]),
                    ('Revisión Suspensión', [ # Título de grupo actualizado
                        'susp_amortiguadores', 'susp_bolsa_aire', 
                        'susp_bujes_muelle', 'susp_bujes_tirantes'
                    ]),
                    ('Revisión Dirección', [ # Título de grupo actualizado
                        'dir_vibracion', 'dir_pernos'
                    ])
                ])
                # --- FIN DEL CAMBIO ---
                
                grouped_forms = OrderedDict([(group, []) for group in TASK_GROUPS.keys()])
                otros_forms = [] 

                for form in formset:
                    task_id = form.instance.nombre_subtask
                    found = False
                    for group_name, task_ids in TASK_GROUPS.items():
                        if task_id in task_ids:
                            grouped_forms[group_name].append(form)
                            found = True
                            break
                    if not found:
                        otros_forms.append(form)

                context['grouped_formset'] = grouped_forms
                context['otros_forms'] = otros_forms
                context['formset_management'] = formset.management_form 
            
        return context

@login_required
@user_passes_test(es_tecnico_o_supervisor)
def seleccionar_herramientas(request, pk):
    """
    POST: Guarda las herramientas seleccionadas y muestra el botón de Iniciar.
    """
    tarea = get_object_or_404(TareaMantenimiento, pk=pk, tecnico=request.user)
    
    if tarea.status != 'ASIGNADA':
        messages.error(request, "Esta tarea ya no está en estado 'Asignada'.")
        return redirect('mantenimiento:tecnico_tarea_detalle', pk=tarea.pk)

    if request.method == 'POST':
        form = SeleccionarHerramientasForm(request.POST, tarea=tarea)
        if form.is_valid():
            # --- CORRECCIÓN AQUÍ ---
            # 1. Elimina las herramientas solicitadas ANTERIORES
            HerramientaSolicitada.objects.filter(tarea=tarea).delete()
            
            # 2. Añade las nuevas
            herramientas_seleccionadas = form.cleaned_data['herramientas']
            for herram in herramientas_seleccionadas:
                HerramientaSolicitada.objects.create(tarea=tarea, herramienta=herram)
            # --- FIN DE LA CORRECCIÓN ---
                
            messages.success(request, "Herramientas seleccionadas guardadas.")
        else:
            messages.error(request, "Hubo un error al seleccionar las herramientas.")
            
    return redirect('mantenimiento:tecnico_tarea_detalle', pk=tarea.pk)

@login_required
@user_passes_test(es_tecnico_o_supervisor)
def iniciar_tarea(request, pk):
    """
    POST: Inicia la tarea, capturando la fecha y hora de inicio.
    """
    tarea = get_object_or_404(TareaMantenimiento, pk=pk, tecnico=request.user)
    
    if tarea.status != 'ASIGNADA':
        messages.error(request, "Esta tarea no se puede iniciar (ya está en proceso o completada).")
        return redirect('mantenimiento:tecnico_tarea_detalle', pk=tarea.pk)
        
    if not tarea.herramientas_solicitadas.exists():
        messages.error(request, "Debe seleccionar las herramientas antes de iniciar la tarea.")
        return redirect('mantenimiento:tecnico_tarea_detalle', pk=tarea.pk)

    if request.method == 'POST':
        tarea.status = 'EN_PROCESO'
        tarea.fecha_inicio = timezone.now()
        tarea.save()
        messages.success(request, "Tarea iniciada. ¡Adelante!")
        
    return redirect('mantenimiento:tecnico_tarea_detalle', pk=tarea.pk)


# --- ******* VISTA MODIFICADA PARA S3 ******* ---

@login_required
@user_passes_test(es_tecnico_o_supervisor)
def guardar_progreso_preventivo(request, pk):
    """
    POST: Guarda el estado del checklist de mantenimiento preventivo.
    MODIFICADO: Para manejar manualmente la subida de archivos a S3.
    """
    tarea = get_object_or_404(TareaMantenimiento, pk=pk, tecnico=request.user)
    
    if tarea.status != 'EN_PROCESO' or tarea.tipo_mantenimiento != 'PREVENTIVO':
        messages.error(request, "No se puede guardar el progreso de esta tarea.")
        return redirect('mantenimiento:tecnico_tarea_detalle', pk=tarea.pk)

    if request.method == 'POST':
        # Instanciamos el formset con los datos POST y FILES
        formset = TareaPreventivaFormSet(request.POST, request.FILES, instance=tarea, prefix='subtasks')
        
        if formset.is_valid():
            try:
                # Obtenemos las instancias con los datos del formulario, pero sin guardarlas en la BD
                subtasks_a_guardar = formset.save(commit=False)
                
                # Obtenemos un mapa de las instancias originales para consultar sus archivos antiguos
                original_subtasks_map = {sub.id: sub for sub in formset.queryset}

                # Creamos un mapa para asociar el ID de una instancia con el archivo subido
                files_a_subir = {}
                
                # Mapeamos los archivos de request.FILES a sus instancias
                for file_key, new_file in request.FILES.items():
                    # El formato es 'prefix-index-fieldname' -> 'subtasks-0-foto_evidencia'
                    parts = file_key.split('-')
                    if len(parts) == 3 and parts[0] == 'subtasks' and parts[2] == 'foto_evidencia':
                        try:
                            form_index = int(parts[1])
                            # Usamos el índice para encontrar el formulario y su instancia
                            subtask_instance = formset.forms[form_index].instance
                            files_a_subir[subtask_instance.id] = new_file
                        except (IndexError, ValueError):
                            # Si el índice no es válido, lo ignoramos
                            pass
                
                # Iniciamos una transacción atómica
                with transaction.atomic():
                    # Iteramos sobre las instancias que el formset preparó
                    for subtask in subtasks_a_guardar:
                        original_subtask = original_subtasks_map.get(subtask.id)
                        form_correspondiente = formset.forms[subtasks_a_guardar.index(subtask)]

                        # Verificamos si se subió un archivo nuevo para esta instancia
                        if subtask.id in files_a_subir:
                            new_file = files_a_subir[subtask.id]
                            
                            # 1. Eliminar el archivo antiguo de S3
                            if original_subtask and original_subtask.foto_evidencia:
                                _eliminar_archivo_de_s3(original_subtask.foto_evidencia.name)
                            
                            # 2. Subir el archivo nuevo a S3
                            # Usamos la función 'upload_to' del modelo para generar la ruta
                            s3_path = ruta_evidencia_subtask(subtask, new_file.name)
                            ruta_guardada = _subir_archivo_a_s3(new_file, s3_path)
                            
                            if ruta_guardada:
                                subtask.foto_evidencia = ruta_guardada
                            else:
                                # Si falla la subida, abortamos la transacción
                                raise Exception(f"Error al subir el archivo {new_file.name}")

                        # Verificamos si el archivo fue "borrado" desde el formulario
                        elif 'foto_evidencia' in form_correspondiente.changed_data and not subtask.foto_evidencia:
                            if original_subtask and original_subtask.foto_evidencia:
                                _eliminar_archivo_de_s3(original_subtask.foto_evidencia.name)
                            # El valor de subtask.foto_evidencia ya es None
                        
                        # Guardamos la instancia en la BD (con la nueva ruta S3 o los cambios de texto/checkbox)
                        subtask.save()
                        
                messages.success(request, "Progreso del checklist guardado.")

            except Exception as e:
                messages.error(request, f"Error al guardar el progreso: {e}")
        
        else:
            # El formset no es válido, mostramos los errores
            all_errors = []
            for errors_dict in formset.errors:
                if errors_dict:
                    for field, err_list in errors_dict.items():
                        all_errors.append(f"{field}: {err_list[0]}")
            
            messages.error(request, f"Error al guardar: {', '.join(all_errors)}")
            
    return redirect('mantenimiento:tecnico_tarea_detalle', pk=tarea.pk)

# --- ******* FIN DE LA VISTA MODIFICADA ******* ---


@login_required
@user_passes_test(es_tecnico_o_supervisor)
def finalizar_tarea(request, pk):
    """
    POST: Finaliza la tarea, capturando la fecha/hora de fin y calculando el total.
    """
    tarea = get_object_or_404(TareaMantenimiento, pk=pk, tecnico=request.user)
    
    if tarea.status != 'EN_PROCESO':
        messages.error(request, "Esta tarea no se puede finalizar (no está en proceso).")
        return redirect('mantenimiento:tecnico_tarea_detalle', pk=tarea.pk)
    
    # Verificación para Mantenimiento Preventivo
    if tarea.tipo_mantenimiento == 'PREVENTIVO':
        # Comprobar si todas las sub-tareas están completadas
        if tarea.subtasks_preventivas.filter(completada=False).exists():
            messages.error(request, "No puede finalizar la tarea. Aún hay sub-tareas preventivas pendientes.")
            return redirect('mantenimiento:tecnico_tarea_detalle', pk=tarea.pk)

    if request.method == 'POST':
        tarea.status = 'COMPLETADA'
        tarea.fecha_fin = timezone.now()
        tarea.calcular_tiempo_total() # Usamos el método del modelo
        tarea.save()
        messages.success(request, f"¡Tarea {tarea.id} completada en {tarea.tiempo_total_minutos} minutos!")
        
    return redirect('mantenimiento:tecnico_dashboard')


# --- NUEVA FUNCIÓN Y VISTA PARA PDF ---

def link_callback(uri, rel):
    """
    Convierte URIs de HTML a rutas de sistema de archivos,
    necesario para que xhtml2pdf encuentre imágenes y CSS.
    """
    # Maneja rutas de media
    # ¡IMPORTANTE! Esta lógica asume que estás en PRODUCCIÓN
    # y que 'settings.MEDIA_URL' es una URL completa de S3.
    # Para desarrollo local, xhtml2pdf necesita rutas de disco.

    # Lógica para S3 (si usas 'django-storages' para MEDIA_URL)
    if uri.startswith(settings.MEDIA_URL):
        # xhtml2pdf puede leer URLs http/https directamente
        return uri
        
    # Lógica para desarrollo LOCAL (si MEDIA_URL es '/media/')
    elif uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, "", 1))
    
    # Maneja rutas de static (siempre locales)
    elif uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, "", 1))
    
    else:
        return uri # Devuelve la URI tal cual

    # Asegurarse de que el archivo exista localmente
    if not os.path.isfile(path):
        print(f"ERROR: Archivo no encontrado en link_callback (local): {path}")
        return None
    return path

def render_to_pdf(template_src, context_dict={}):
    """
    Renderiza un template HTML a un objeto PDF.
    """
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    
    # Convertir HTML a PDF
    # Usamos link_callback para resolver rutas de imágenes/CSS
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result, link_callback=link_callback)
    
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    print(f"Error al generar PDF: {pdf.err}")
    return None

@login_required
@user_passes_test(es_tecnico_o_supervisor) # O 'es_admin' si también quieres
def generar_pdf_mantenimiento(request, pk):
    """
    Genera un reporte PDF para una tarea de mantenimiento completada.
    """
    try:
        tarea = TareaMantenimiento.objects.select_related(
            'unidad', 'tecnico', 'admin', 'mantenimiento_correctivo'
        ).prefetch_related(
            'herramientas_solicitadas', 'subtasks_preventivas'
        ).get(pk=pk)
    except TareaMantenimiento.DoesNotExist:
        messages.error(request, "La tarea solicitada no existe.")
        return redirect('mantenimiento:tecnico_dashboard')

    # Solo tareas completadas o en proceso pueden generar un reporte
    if tarea.status not in ['COMPLETADA', 'EN_PROCESO']:
         messages.error(request, "Solo se pueden generar reportes de tareas en proceso o completadas.")
         return redirect('mantenimiento:tecnico_tarea_detalle', pk=pk)

    context = {
        'tarea': tarea,
        'subtasks': tarea.subtasks_preventivas.all(),
        'herramientas': tarea.herramientas_solicitadas.all(),
        'settings': settings # Pasamos settings para acceder a MEDIA_URL etc.
    }
    
    pdf = render_to_pdf('mantenimiento/pdf_template.html', context)
    
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        # Define el nombre del archivo PDF
        filename = f"Mantenimiento_Tarea_{tarea.id}_{tarea.unidad.nombre}.pdf"
        # Muestra en el navegador con 'inline'
        content = f"inline; filename='{filename}'"
        response['Content-Disposition'] = content
        return response

    messages.error(request, "No se pudo generar el reporte PDF.")
    return redirect('mantenimiento:tecnico_tarea_detalle', pk=pk)


# --- Vistas CRUD para Catálogos (Solo Admin) ---

class CatalogoHerramientaListView(AdminRequiredMixin, ListView):
    model = CatalogoHerramienta
    template_name = 'mantenimiento/generic_list.html'
    context_object_name = 'items'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Catálogo de Herramientas"
        context['url_crear'] = 'mantenimiento:herramienta_crear'
        context['headers'] = ['ID', 'Nombre']
        context['url_update_name'] = 'mantenimiento:herramienta_editar'
        context['url_delete_name'] = 'mantenimiento:herramienta_eliminar'
        return context

class CatalogoHerramientaCreateView(AdminRequiredMixin, CreateView):
    model = CatalogoHerramienta
    form_class = CatalogoHerramientaForm
    template_name = 'mantenimiento/generic_form.html'
    success_url = reverse_lazy('mantenimiento:herramienta_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Nueva Herramienta"
        return context

class CatalogoHerramientaUpdateView(AdminRequiredMixin, UpdateView):
    model = CatalogoHerramienta
    form_class = CatalogoHerramientaForm
    template_name = 'mantenimiento/generic_form.html'
    success_url = reverse_lazy('mantenimiento:herramienta_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Editar Herramienta"
        return context

class CatalogoHerramientaDeleteView(AdminRequiredMixin, DeleteView):
    model = CatalogoHerramienta
    template_name = 'mantenimiento/generic_confirm_delete.html'
    success_url = reverse_lazy('mantenimiento:herramienta_list')
    
    def form_valid(self, form):
        messages.success(self.request, f"Herramienta '{self.object.nombre}' eliminada.")
        return super().form_valid(form)

# ---
class CatalogoCorrectivoListView(AdminRequiredMixin, ListView):
    model = CatalogoMantenimientoCorrectivo
    template_name = 'mantenimiento/generic_list.html'
    context_object_name = 'items'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Catálogo de Mantenimiento Correctivo"
        context['url_crear'] = 'mantenimiento:correctivo_crear'
        context['headers'] = ['ID', 'Nombre', 'Descripción']
        context['url_update_name'] = 'mantenimiento:correctivo_editar'
        context['url_delete_name'] = 'mantenimiento:correctivo_eliminar'
        return context

class CatalogoCorrectivoCreateView(AdminRequiredMixin, CreateView):
    model = CatalogoMantenimientoCorrectivo
    form_class = CatalogoMantenimientoCorrectivoForm
    template_name = 'mantenimiento/generic_form.html'
    success_url = reverse_lazy('mantenimiento:correctivo_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Nueva Tarea Correctiva"
        return context

class CatalogoCorrectivoUpdateView(AdminRequiredMixin, UpdateView):
    model = CatalogoMantenimientoCorrectivo
    form_class = CatalogoMantenimientoCorrectivoForm
    template_name = 'mantenimiento/generic_form.html'
    success_url = reverse_lazy('mantenimiento:correctivo_list')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Editar Tarea Correctiva"
        return context

class CatalogoCorrectivoDeleteView(AdminRequiredMixin, DeleteView):
    model = CatalogoMantenimientoCorrectivo
    template_name = 'mantenimiento/generic_confirm_delete.html'
    success_url = reverse_lazy('mantenimiento:correctivo_list')

    def form_valid(self, form):
        messages.success(self.request, f"Tarea '{self.object.nombre}' eliminada.")
        return super().form_valid(form)
    
@method_decorator(login_required, name='dispatch')
class TareaMantenimientoDeleteView(AdminRequiredMixin, DeleteView):
    """
    Vista para que el Admin elimine una tarea (con confirmación).
    """
    model = TareaMantenimiento
    template_name = 'mantenimiento/generic_confirm_delete.html' # Reutilizamos la plantilla
    success_url = reverse_lazy('mantenimiento:admin_dashboard')
    context_object_name = 'object' # Nombre del objeto en la plantilla

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = f"Confirmar Eliminación de Tarea {self.object.id}"
        # Añadimos un mensaje de advertencia personalizado
        context['confirm_message'] = f"¿Estás seguro de que deseas eliminar permanentemente la tarea {self.object.id} ({self.object.get_tipo_mantenimiento_display}) para la unidad {self.object.unidad.nombre}? Esta acción no se puede deshacer."
        return context

    def form_valid(self, form):
        # Mensaje de éxito antes de eliminar
        messages.success(self.request, f"La Tarea {self.object.id} ha sido eliminada exitosamente.")
        return super().form_valid(form)