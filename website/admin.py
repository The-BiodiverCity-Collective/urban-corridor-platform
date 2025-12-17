from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin
from .models import *

class MyAdminSite(AdminSite):
    # Text to put at the end of each page"s <title>.
    site_title = "Urban Corridor Platform Admin"

    # Text to put in each page"s <h1> (and above login form).
    site_header = "Urban Corridor Platform Admin"

    # Text to put at the top of the admin index page.
    index_title = "Urban Corridor Platform"

admin_site = MyAdminSite()

class SearchAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    exclude = ["content_html"]

class VegTypeAdmin(admin.ModelAdmin):
    list_display = ["name"]
    autocomplete_fields = ["spaces"]

class DocAdmin(SearchAdmin):
    list_display = ["name", "author", "is_active", "include_in_site_analysis"]
    list_filter = ["is_active", "include_in_site_analysis"]

class SpaceAdmin(SearchAdmin):
    list_display = ["name", "source"]
    list_filter = ["source"]

class GardenAdmin(SearchAdmin):
    list_display = ["name", "is_active"]
    list_filter = ["is_active", "organizations", "source"]

class UserAdmin(admin.ModelAdmin):
     list_display = ["username", "email", "first_name", "date_joined", "is_staff", "is_active"]
     list_filter = ["is_staff", "is_active"]
     search_fields = ["username", "email"]

class SFAdmin(admin.ModelAdmin):
    search_fields = ["name"]
    list_display = ["name", "species_type", "icon"]
    list_filter = ["species_type", "site"]

class PageAdmin(admin.ModelAdmin):
    list_display = ["name", "site"]
    search_fields = ["name"]
    exclude = ["content_html"]
    list_filter = ["site", "is_active", "page_type", "site"]
    autocomplete_fields = ["photos"]

class PlantFormAdmin(admin.ModelAdmin):
     list_display = ["letter", "name", "description"]

admin_site.register(Photo, SearchAdmin)
admin_site.register(Page, PageAdmin)
admin_site.register(Garden, GardenAdmin)
admin_site.register(Document, DocAdmin)
admin_site.register(ReferenceSpace, SpaceAdmin)
admin_site.register(Event, SearchAdmin)
admin_site.register(Genus, SearchAdmin)
admin_site.register(Species, SearchAdmin)
admin_site.register(SpeciesFeatures, SFAdmin)
admin_site.register(Corridor, SearchAdmin)
admin_site.register(Redlist, SearchAdmin)
admin_site.register(Organization, SearchAdmin)
admin_site.register(VegetationType, VegTypeAdmin)
admin_site.register(GardenManager, SearchAdmin)
admin_site.register(Color, SearchAdmin)
admin_site.register(PlantForm, PlantFormAdmin)

admin_site.register(Newsletter)
admin_site.register(User, UserAdmin)
admin_site.register(Group)

admin_site.register(Language)
admin_site.register(Site)
admin_site.register(MapStyle)
