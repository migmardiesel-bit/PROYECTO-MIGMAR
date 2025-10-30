from django import template
register = template.Library()

@register.filter
def get_attribute(obj, attr_name):
    """
    Obtiene un atributo de un objeto por su nombre.
    Esto es útil en la plantilla genérica para iterar sobre los 'headers'.
    """
    try:
        # Primero intenta obtener el atributo directamente
        attr = getattr(obj, attr_name)
        if callable(attr):
            return attr()
        return attr
    except AttributeError:
        # Si falla, intenta con get_..._display (para campos con 'choices')
        try:
            display_method = getattr(obj, f"get_{attr_name}_display")
            return display_method()
        except AttributeError:
            return None
