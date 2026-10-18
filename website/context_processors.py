from django.conf import settings
import random
from website.models import Site, Page
from website.views import get_garden
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

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
    garden = None
    garden_id = request.COOKIES.get("garden_id", 0)
    if garden_id:
        garden = get_garden(request, garden_id)
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

    bg = None
    if site.id == 1:
        bg = random.randint(1, 10)
        bg = f"/media/bg/braam/{bg}.jpg?rf"


    steps = [
        {
            "id": 1,
            "label": _("Create your garden"),
            "url": reverse("planner", args=[garden_id]),
            "progress_key": "created",
            "group": _("Plan your garden"),
        },
        {
            "id": 2,
            "label": _("Set location"),
            "url": reverse("planner_location", args=[garden_id]),
            "progress_key": "location",
            "group": _("Plan your garden"),
        },
        {
            "id": 3,
            "label": _("Features and targets"),
            "url": reverse("planner_site", args=[garden_id]),
            "progress_key": "features",
            "group": _("Plan your garden"),
        },
        {
            "id": 4,
            "label": _("Select plants"),
            "url": reverse("planner_plants", args=[garden_id]),
            "progress_key": "plants",
            "group": _("Plan your garden"),
        },
        {
            "id": 5,
            "label": _("Commitments"),
            "url": reverse("planner_requirements", args=[garden_id]),
            "progress_key": "requirements",
            "group": _("Sign up"),
        },
        {
            "id": 6,
            "label": _("Garden profile"),
            "url": reverse("planner_profile", args=[garden_id]),
            "progress_key": "profile",
            "group": _("Sign up"),
        },
        {
            "id": 7,
            "label": _("Upload photos"),
            "url": reverse("planner_profile_photos", args=[garden_id]),
            "progress_key": "photos",
            "group": _("Sign up"),
        },
        {
            "id": 8,
            "label": _("Join the corridor"),
            "url": reverse("planner_activate", args=[garden_id]),
            "progress_key": "joined",
            "group": _("Sign up"),
        },
    ]

    return {
        "DEBUG": settings.DEBUG,
        "WORK_OFFLINE": True if work_offline else False,
        "SITE": site,
        "SITES": sites,

        # Let's fix this please, such as mess
        "MY_GARDEN": garden,
        "GARDEN": garden_id,
        "PROGRESS": garden.progress if garden else None,

        "NURSERIES": Page.objects.filter(site=site, page_type=Page.PageType.NURSERY),
        "JOIN_MENU": join_menu,
        "BG": bg,
        "STEPS": steps,
    }
