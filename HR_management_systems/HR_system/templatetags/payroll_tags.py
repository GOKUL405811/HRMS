from django import template

register = template.Library()

@register.filter
def join_ids(payrolls):
    """Return comma-separated payroll IDs"""
    return ",".join(str(p.id) for p in payrolls)
