from django.conf import settings
import random
from website.models import Site, Page

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
    # garden is being actively managed.
    garden = request.COOKIES.get("garden_id", 0)
    garden_name = request.COOKIES.get("garden_name", None)
    garden_active = request.COOKIES.get("garden_active", None)

    join_menu = {
        "Create or register your garden": [
            {"title": "Private garden", "icon": "fa-map-marker-plus", "slug": "private-garden"},
            {"title": "Public garden", "icon": "fa-map-marker-plus", "slug": "public-garden"},
            {"title": "Corporate garden", "icon": "fa-map-marker-plus", "slug": "corporate-garden"},
            {"title": "Recruit others to register", "icon": "fa-map-marker-plus", "slug": "recruit-others-to-register"},
        ],
        "Join our community": [
            {"title": "Sign up for training", "icon": "fa-chalkboard-teacher", "slug": "sign-up-for-training"},
            {"title": "Start a volunteer group", "icon": "fa-users", "slug": "start-a-volunteer-group"},
            {"title": "Adopt a park / street", "icon": "fa-tree-alt", "slug": "adopt-a-park-street"},
            {"title": "Join our professional network", "icon": "fa-user-tie", "slug": "join-our-professional-network"},
            {"title": "Become a corridor champion", "icon": "fa-user-crown", "slug": "become-a-corridor-champion"},
        ],
        "Partner with us": [
            {"title": "Champion an animal", "icon": "fa-turtle", "slug": "champion-an-animal"},
            {"title": "Share your garden designs", "icon": "fa-ruler", "slug": "share-your-garden-designs"},
            {"title": "Share your knowledge", "icon": "fa-chalkboard-teacher", "slug": "share-your-knowledge"},
            {"title": "Give us feedback on the tool", "icon": "fa-comments", "slug": "give-us-feedback-on-the-tool"},
            {"title": "Start a corridor in your area", "icon": "fa-map-marker-plus", "slug": "start-a-corridor-in-your-area"},
        ],
        "Sponsor our work": [
            {"title": "Sponsor training", "icon": "fa-graduation-cap", "slug": "sponsor-training"},
            {"title": "Sponsor design", "icon": "fa-object-group", "slug": "sponsor-design"},
            {"title": "Sponsor the online tool", "icon": "fa-desktop", "slug": "sponsor-the-online-tool"},
            {"title": "Sponsor a public space", "icon": "fa-users-class", "slug": "sponsor-a-public-space"},
            {"title": "Sponsor an entire corridor!", "icon": "fa-draw-polygon", "slug": "sponsor-an-entire-corridor"},
        ],
    }

    return {
        "DEBUG": settings.DEBUG,
        "WORK_OFFLINE": True if work_offline else False,
        "SITE": site,
        "SITES": sites,
        "GARDEN": garden,
        "GARDEN_NAME": garden_name,
        "GARDEN_ACTIVE": garden_active,
        "NURSERIES": Page.objects.filter(site=site, page_type=Page.PageType.NURSERY),
        "JOIN_MENU": join_menu,
    }
