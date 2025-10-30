from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from flota.models import Unidad # Importación de Unidad
from django.db.models import Q, Avg
from datetime import timedelta # <-- La línea que necesitas
from .models import (
    TareaMantenimiento, CatalogoHerramienta, CatalogoMantenimientoCorrectivo,
    TareaPreventivaSubtask, HerramientaSolicitada
)
from .forms import (
    AsignarTareaForm, CatalogoHerramientaForm, CatalogoMantenimientoCorrectivoForm,
    SeleccionarHerramientasForm, TareaPreventivaFormSet
)

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
        # Sobreescribimos para asegurar que el técnico solo vea sus propias tareas
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
            # 1. Tarea asignada: Mostrar formulario de herramientas
            context['form_herramientas'] = SeleccionarHerramientasForm(tarea=tarea)
        
        elif tarea.status == 'EN_PROCESO':
            # 2. Tarea en proceso: Mostrar checklist (si es preventivo)
            if tarea.tipo_mantenimiento == 'PREVENTIVO':
                # Creamos el FormSet para las sub-tareas
                context['formset_preventivo'] = TareaPreventivaFormSet(
                    instance=tarea,
                    prefix='subtasks'
                )
            
            # Si es correctivo, no necesita formulario, solo el botón de finalizar.
            
        return context

# --- Vistas de Funciones (Acciones POST del Técnico) ---

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

@login_required
@user_passes_test(es_tecnico_o_supervisor)
def guardar_progreso_preventivo(request, pk):
    """
    POST: Guarda el estado del checklist de mantenimiento preventivo.
    """
    tarea = get_object_or_404(TareaMantenimiento, pk=pk, tecnico=request.user)
    
    if tarea.status != 'EN_PROCESO' or tarea.tipo_mantenimiento != 'PREVENTIVO':
        messages.error(request, "No se puede guardar el progreso de esta tarea.")
        return redirect('mantenimiento:tecnico_tarea_detalle', pk=tarea.pk)

    if request.method == 'POST':
        formset = TareaPreventivaFormSet(request.POST, instance=tarea, prefix='subtasks')
        if formset.is_valid():
            formset.save()
            messages.success(request, "Progreso del checklist guardado.")
        else:
            messages.error(request, "Error al guardar el progreso.")
            
    return redirect('mantenimiento:tecnico_tarea_detalle', pk=tarea.pk)

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

