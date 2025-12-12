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
    
    if "site" in request.COOKIES:
        site = Site.objects.get(id=request.COOKIES["site"])
    else:
        site = Site.objects.get(url=url)

    sites = None
    if settings.DEBUG:
        sites = Site.objects.all()

    # If this user is managing a garden, we can get that ID and use it to create planner-related
    # URLs. However, we want the URL to use 0 as a variable so it doesn't fail to work if no 
    # garden is being actively managed
    garden = request.COOKIES.get("garden_id", 0)

    return {
        "DEBUG": settings.DEBUG,
        "WORK_OFFLINE": True if work_offline else False,
        "MAPBOX_API_KEY": "pk.eyJ1IjoiY29tbXVuaXRyZWUiLCJhIjoiY2lzdHZuanl1MDAwODJvcHR1dzU5NHZrbiJ9.0ETJ3fXYJ_biD7R7FiwAEg",
        "SITE": site,
        "SITES": sites,
        "GARDEN": garden,
    }
