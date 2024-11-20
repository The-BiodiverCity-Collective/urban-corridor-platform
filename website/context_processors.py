from django.conf import settings
import random
from website.models import Site

def site(request):

    work_offline = False
    try:
        if settings.WORK_OFFLINE:
            work_offline = True
    except:
        work_offline = False

    url = request.META.get("HTTP_HOST")
    url = url.lower()

    return {
        "DEBUG": settings.DEBUG,
        "WORK_OFFLINE": True if work_offline else False,
        "MAPBOX_API_KEY": "pk.eyJ1IjoiY29tbXVuaXRyZWUiLCJhIjoiY2lzdHZuanl1MDAwODJvcHR1dzU5NHZrbiJ9.0ETJ3fXYJ_biD7R7FiwAEg",
        "SITE": Site.objects.get(url=url),
    }
