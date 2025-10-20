from django import template
from django.forms.models import model_to_dict

register = template.Library()

@register.filter
def get_fields_by_group(checklist_instance, group_name):
    # Definimos qué campos pertenecen a cada grupo
    field_groups = {
        'exterior': [
            'cristales', 'espejos', 'logos', 'num_economico', 'puertas', 'cofre', 'parrilla', 'defensas', 
            'faros', 'plafoneria', 'stops', 'direccionales', 'tapiceria', 'instrumentos', 'carroceria', 'piso', 
            'costados', 'escape', 'pintura', 'franjas', 'loderas', 'extintor', 'senalamientos', 'estado_general'
        ],
        'mecanica': [
            'motor', 'caja', 'diferenciales', 'suspension_delantera', 'suspension_trasera', 'fugas_combustible', 
            'fugas_aceite', 'estado_llantas', 'presion_llantas', 'purga_tanques', 'estado_balatas', 
            'amortiguadores_delanteros', 'amortiguadores_traseros', 'rines_aluminio', 'mangueras_servicio', 
            'tarjeta_llave', 'revision_fusibles', 'revision_luces', 'revision_cable_7vias', 'revision_fuga_aire'
        ]
    }
    
    fields_to_render = []
    
    # Obtenemos los campos del modelo que corresponden al grupo solicitado
    field_names = field_groups.get(group_name, [])

    for name in field_names:
        meta_field = checklist_instance._meta.get_field(name)
        value = getattr(checklist_instance, name)
        observation = getattr(checklist_instance, f"{name}_obs", None)
        
        fields_to_render.append({
            'label': meta_field.verbose_name.capitalize(),
            'value': value,
            'observation': observation,
        })
        
    return fields_to_render