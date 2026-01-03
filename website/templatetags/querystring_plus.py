from django import template

register = template.Library()

# Django overwrites multiple params that have the same name, using the regular querystring function
# E.g. ?feature=10&feature=11 will change to ?feature=10 when querystring is used. So we need this
# for the photo tabs that depend on this being preserved quite a bit.

@register.simple_tag(takes_context=True)
def querystring_plus(context, **kwargs):
    request = context["request"]
    q = request.GET.copy()

    for key, value in kwargs.items():
        if value is None:
            q.pop(key, None)
        elif isinstance(value, (list, tuple)):
            q.setlist(key, value)
        else:
            q[key] = value

    encoded = q.urlencode()
    return f"?{encoded}" if encoded else ""
