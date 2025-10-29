# flota/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from .views import *

urlpatterns = [
    # =============================================================
    # AUTENTICACIÓN Y PÁGINAS PRINCIPALES
    # =============================================================
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # --- RUTAS DE INICIO POR ROL ---
    path('', home_dispatcher_view, name='home'),
    path('dashboard/', AdminDashboardView.as_view(), name='dashboard'),
    path('dashboard/graficas/', DashboardGraficasView.as_view(), name='dashboard_graficas'),

    # --- RUTA PARA EL PANEL DE ADMIN ---
    path('revisiones/asignar/', AsignacionRevisionView.as_view(), name='asignar-revision'),
    path('revisiones/monitor/', MonitorRevisionesView.as_view(), name='monitor-revisiones'),
    path('reportes/panel-de-control/', AdminPanelDeControlView.as_view(), name='admin-panel-de-control'),

    # --- RUTA CORREGIDA PARA QUE EL ADMIN CONTINÚE EL PROCESO ---
    path('procesos/continuar/<int:checklist_pk>/', admin_continuar_proceso_llantas, name='admin-continuar-proceso'),

    # =============================================================
    # RUTAS PARA INICIAR PROCESO (TÉCNICO Y ENCARGADO)
    # =============================================================
    path('proceso/seleccionar-unidad/', SeleccionarUnidadView.as_view(), name='tecnico-seleccionar-unidad'),
    path('proceso/checklist/<int:unidad_pk>/', ProcesoChecklistView.as_view(), name='proceso-checklist'),
    path('proceso/llantas/<int:unidad_pk>/', ProcesoLlantasView.as_view(), name='proceso-llantas'),

    # =============================================================
    # RUTAS PARA FINALIZAR PROCESO (SOLO ENCARGADO)
    # =============================================================
    path('encargado/pendientes/', EncargadoPendientesListView.as_view(), name='encargado-pendientes-list'),
    path('encargado/proceso/diesel/<int:proceso_pk>/', EncargadoProcesoDieselView.as_view(), name='encargado-proceso-diesel'),
    path('encargado/proceso/urea/<int:proceso_pk>/', EncargadoProcesoUreaView.as_view(), name='encargado-proceso-urea'),

    # =============================================================
    # RUTAS DE ADMINISTRADOR (CRUDs)
    # =============================================================
    
    # --- Gestión de Unidades ---
    path('unidades/', UnidadListView.as_view(), name='unidad-list'),
    path('unidades/nueva/', UnidadCreateView.as_view(), name='unidad-create'),
    path('unidades/<int:pk>/', UnidadDetailView.as_view(), name='unidad-detail'),
    path('unidades/<int:pk>/editar/', UnidadUpdateView.as_view(), name='unidad-update'),
    path('unidades/<int:pk>/eliminar/', UnidadDeleteView.as_view(), name='unidad-delete'),
    path('unidades/<int:pk>/rendimiento/', UnidadDetailRendimientoView.as_view(), name='unidad-rendimiento-detail'),
    
    # --- NUEVA RUTA PARA EL REPORTE PDF ---
    path('unidades/<int:pk>/reporte-pdf/', download_unidad_reporte_pdf, name='unidad-reporte-pdf'),

    # --- Gestión de Operadores ---
    path('operadores/', OperadorListView.as_view(), name='operador-list'),
    path('operadores/nuevo/', OperadorCreateView.as_view(), name='operador-create'),
    path('operadores/<int:pk>/', OperadorDetailView.as_view(), name='operador-detail'),
    path('operadores/<int:pk>/editar/', OperadorUpdateView.as_view(), name='operador-update'),
    path('operadores/<int:pk>/eliminar/', OperadorDeleteView.as_view(), name='operador-delete'),
    
    # --- Gestión de Cargas de Diésel ---
    path('cargas/diesel/', CargaDieselListView.as_view(), name='cargadiesel-list'),
    path('cargas/diesel/nueva/', CargaDieselCreateView.as_view(), name='cargadiesel-create'),
    path('cargas/diesel/<int:pk>/editar/', CargaDieselUpdateView.as_view(), name='cargadiesel-update'),
    path('cargas/diesel/<int:pk>/eliminar/', CargaDieselDeleteView.as_view(), name='cargadiesel-delete'),
    
    # --- Gestión de Cargas de Aceite ---
    path('cargas/aceite/', CargaAceiteListView.as_view(), name='cargaaceite-list'),
    path('cargas/aceite/nueva/', CargaAceiteCreateView.as_view(), name='cargaaceite-create'),
    path('cargas/aceite/<int:pk>/editar/', CargaAceiteUpdateView.as_view(), name='cargaaceite-update'),
    path('cargas/aceite/<int:pk>/eliminar/', CargaAceiteDeleteView.as_view(), name='cargaaceite-delete'),
    
    # --- Gestión de Cargas de Urea ---
    path('cargas/urea/', CargaUreaListView.as_view(), name='cargaurea-list'),
    path('cargas/urea/nueva/', CargaUreaCreateView.as_view(), name='cargaurea-create'),
    path('cargas/urea/<int:pk>/editar/', CargaUreaUpdateView.as_view(), name='cargaurea-update'),
    path('cargas/urea/<int:pk>/eliminar/', CargaUreaDeleteView.as_view(), name='cargaurea-delete'),
    
    # --- Gestión de Compras de Suministros ---
    path('compras/', CompraSuministroListView.as_view(), name='comprasuministro-list'),
    path('compras/nueva/', CompraSuministroCreateView.as_view(), name='comprasuministro-create'),
    path('compras/<int:pk>/editar/', CompraSuministroUpdateView.as_view(), name='comprasuministro-update'),
    path('compras/<int:pk>/eliminar/', CompraSuministroDeleteView.as_view(), name='comprasuministro-delete'),

    # --- Gestión de Inspecciones (Checklists) ---
    path('inspecciones/checklists/', ChecklistListView.as_view(), name='checklist-list'),
    path('inspecciones/checklists/nuevo/', ChecklistCreateView.as_view(), name='checklist-create'),
    path('inspecciones/checklists/<int:pk>/', ChecklistDetailView.as_view(), name='checklist-detail'),
    path('inspecciones/checklists/<int:pk>/editar/', ChecklistUpdateView.as_view(), name='checklist-update'),
    path('inspecciones/checklists/<int:pk>/eliminar/', ChecklistDeleteView.as_view(), name='checklist-delete'),
    path('inspecciones/checklists/<int:pk>/exportar-excel/', download_checklist_excel, name='checklist-export-excel'),

    # --- Gestión de Inspecciones (Llantas) ---
    path('inspecciones/llantas/', LlantasInspeccionListView.as_view(), name='llantas-list'),
    path('inspecciones/llantas/nuevo/', LlantasInspeccionCreateView.as_view(), name='llantas-create'),
    path('inspecciones/llantas/<int:pk>/', LlantasInspeccionDetailView.as_view(), name='llantas-detail'),
    path('inspecciones/llantas/<int:pk>/editar/', LlantasInspeccionUpdateView.as_view(), name='llantas-update'),
    path('inspecciones/llantas/<int:pk>/eliminar/', LlantasInspeccionDeleteView.as_view(), name='llantas-delete'),

    # =============================================================
    # RUTAS DE API (PARA AUTOCOMPLETADO Y AJAX)
    # =============================================================
    path('api/search/unidades/', search_unidades_api, name='api-search-unidades'),
    path('api/search/tecnicos/', search_tecnicos_api, name='api-search-tecnicos'),
    path('api/get-unidad-tipo/', get_unidad_tipo_api, name='api-get-unidad-tipo'),
    
# --- Gestión de Ajustes de Inventario ---
    path('inventario/ajustes/', AjusteInventarioListView.as_view(), name='ajusteinventario-list'),
    path('inventario/ajustes/nuevo/', AjusteInventarioCreateView.as_view(), name='ajusteinventario-create'),
    path('inspecciones/llantas/exportar/', download_llantas_general_excel, name='llantas-export-excel'),
    path('revisiones/cancelar/<int:pk>/', cancelar_revision, name='cancelar-revision'),
    path('reportes/enviar-estado/', enviar_reporte_estado, name='enviar-reporte-estado'),
    path('cargas/diesel/exportar-excel/', download_cargadiesel_reporte, name='cargadiesel-export-excel'),    
    path('unidades/exportar-excel/', download_unidades_excel, name='unidades-export-excel'),
    path('revisiones/corregir-checklist-mal/', corregir_checklist_mal_view, name='corregir-checklist-mal'),
    path('inventario/compras/exportar-excel/', download_comprasuministro_excel, name='comprasuministro-export-excel'),
    path('api/checklist/corregir/<int:pk>/', api_corregir_falla_checklist, name='api-corregir-falla'),
    path('unidades/<int:pk>/reporte-correcciones-pdf/', download_correcciones_report_pdf, name='unidad-reporte-correcciones-pdf'), # <--- THIS LINE
    path('unidades/<int:pk>/reporte-correcciones-excel/', download_correcciones_report_excel, name='unidad-reporte-correcciones-excel'), # <-- And this one for Excel
    
    path('entregas/', EntregaSuministrosListView.as_view(), name='entrega-suministros-list'),
    path('entregas/nueva/', EntregaSuministrosCreateView.as_view(), name='entrega-suministros-create'),
    path('entregas/<int:pk>/editar/', EntregaSuministrosUpdateView.as_view(), name='entrega-suministros-update'),
    path('entregas/<int:pk>/eliminar/', EntregaSuministrosDeleteView.as_view(), name='entrega-suministros-delete'),
    path('api/search/operadores/', search_operadores_api, name='operador-search-api'),
]