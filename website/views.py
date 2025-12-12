from .forms import *
from .models import *
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.gis import geos
from django.contrib.gis.measure import D
from django.core import serializers
from django.core.files import File
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery, Value, CharField, Q, Count, Max
from django.forms import modelform_factory
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string, get_template
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from folium.plugins import Fullscreen

import folium
import io
import os
import pandas as pd
import random
import secrets
import shutil
import sys
import urllib.request, json 
import uuid
import wikipediaapi
import xml.etree.ElementTree as ET
import zipfile

# Quick debugging, sometimes it's tricky to locate the PRINT in all the Django 
# output in the console, so just using a simply function to highlight it better
def p(text):
    print("----------------------")
    print(text)
    print("----------------------")

# Also defined in context_processor for templates, but we need it sometimes in the Folium map configuration
SATELLITE_TILES = "https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}@2x.png?access_token=" + settings.MAPBOX_API_KEY
STREET_TILES = "https://api.mapbox.com/styles/v1/mapbox/streets-v11/tiles/{z}/{x}/{y}?access_token=" + settings.MAPBOX_API_KEY
LIGHT_TILES = "https://api.mapbox.com/styles/v1/mapbox/light-v10/tiles/{z}/{x}/{y}?access_token=" + settings.MAPBOX_API_KEY

COLOR_SCHEMES = {
    "moc": ["#144d58","#a6cee3","#33a02c","#b2df8a","#e31a1c","#fb9a99","#ff7f00","#fdbf6f","#6a3d9a","#cab2d6","#b15928","#ffff99"],
    "accent": ["#7fc97f","#beaed4","#fdc086","#ffff99","#386cb0","#f0027f","#bf5b17","#666666"],
    "dark": ["#1b9e77","#d95f02","#7570b3","#e7298a","#66a61e","#e6ab02","#a6761d","#666666"],
    "pastel": ["#fbb4ae","#b3cde3","#ccebc5","#decbe4","#fed9a6","#ffffcc","#e5d8bd","#fddaec","#f2f2f2"],
    "set": ["#e41a1c","#377eb8","#4daf4a","#984ea3","#ff7f00","#ffff33","#a65628","#f781bf","#999999"],
    "dozen": ["#8dd3c7","#ffffb3","#bebada","#fb8072","#80b1d3","#fdb462","#b3de69","#fccde5","#d9d9d9","#bc80bd","#ccebc5","#ffed6f"],
    "green": ["#005824", "#238b45", "#41ae76", "#66c2a4", "#99d8c9", "#ccece6", "#e5f5f9", "#f7fcfd"],
    "blue": ["#084594", "#2171b5", "#4292c6", "#6baed6", "#9ecae1", "#c6dbef", "#deebf7","#f7fbff"],
    "purple": ["#3f007d", "#54278f", "#6a51a3", "#807dba", "#9e9ac8", "#bcbddc", "#dadaeb", "#efedf5", "#fcfbfd"],
    "red": ["#7f0000", "#b30000", "#d7301f", "#ef6548", "#fc8d59", "#fdbb84", "#fdd49e", "#fee8c8", "#fff7ec"],
}

# This fetches the site the user is on
def get_site(request):
    try:
        if request.COOKIES.get("site"):
            return Site.objects.get(pk=request.COOKIES.get("site"))
        else:
            url = request.META.get("HTTP_HOST")
            url = url.lower()
            return Site.objects.get(url=url)
    except:
        return None

# This checks to make sure the garden either belongs to the logged-in user, or the user has the right cookie set
def get_garden(request, id):
    if request.user.is_authenticated:
        garden = Garden.objects_unfiltered.filter(pk=id, user=request.user)
        if garden:
            return garden[0]
    if "garden_id" in request.COOKIES and "garden_uuid" in request.COOKIES:
        garden = Garden.objects_unfiltered.filter(pk=request.COOKIES.get("garden_id"), is_user_created=True, user__isnull=True, uuid=request.COOKIES["garden_uuid"])
        if garden:
            return garden[0]
    if id == 0:
        messages.warning(request, _("Please create your own garden to get started."))
    else:
        messages.warning(request, _("Garden not found. Please log in to access your saved gardens."))
    return None

# To show the corridor by blacking out everything that is NOT the corridor, we need to 
# get the 'swapped around' coordinates and blacken those out. This function returns exactly that.
def get_swapped_corridor_coords(site):
    swapped_corridor_coords = None
    if site.corridor:
        corridor = ReferenceSpace.objects.filter(source=site.corridor)
        if corridor:
            corridor = corridor[0]
            corridor = json.loads(corridor.geometry.geojson)
            corridor = corridor["coordinates"][0]
            swapped_corridor_coords = [[y, x] for x, y in corridor] # This is needed for the hole punching to work
    return swapped_corridor_coords

# For a default log entry where we take the user and url from request
def log_action(request, action, name):
    Log.objects.create(action=action, name=name, url=request.get_full_path(), user=request.user)

# Regular views
def index(request):
    if "photos" in request.GET:
        import csv
        from django.core.files.uploadedfile import UploadedFile
        from dateutil.parser import parse
        with open(settings.MEDIA_ROOT + "/import/photos1000.csv", "r", encoding="utf-8-sig") as csvfile:
            contents = csv.DictReader(csvfile)
            for row in contents:
                path = settings.MEDIA_ROOT + "/" + row["image"]
                garden = row["garden_id"]
                try:
                    info = Garden.objects.get(original__contains={"id": garden})
                    print(info, row["image"])
                except:
                    pass
                if False:
                    g = Photo.objects.create(
                        description = row["description"],
                        position = row["position"],
                        author = row["author"],
                        date = parse(row["date"]),
                        upload_date = parse(row["upload_date"]),
                        image = UploadedFile(file=open(path, "rb")),
                        garden_id = row["garden_id"],
                    )

    if "photo_update" in request.GET:
        return None
        from dateutil.parser import parse
        a = Photo.objects.filter(old_id__isnull=False)
        for each in a:
            each.date = parse(each.original["created_at"])
            each.upload_date = parse(each.original["updated_at"])
            each.save()

    context = {
        #"garden": Garden.objects.filter(is_active=True).order_by("?")[0],
        "garden": Garden(),
    }
    site = get_site(request)
    if site.id == 2:
        return render(request, "fcc/index.html", context)
    else:
        return render(request, "index.html", context)

def design(request):
    return render(request, "design.html")

def map(request, id):
    info = get_object_or_404(Document, pk=id)
    site = get_site(request)
    spaces = info.spaces.all()

    features = []
    if info.spaces.all().count() == 1:
        # If this is only associated to a single space then we show that one
        space = info.spaces.all()[0]

    if spaces.count() > 500 and "show_all_spaces" not in request.GET:
        space_count = spaces.count()
        spaces = spaces[:500]

    simplify_factor = None
    geom_type = None

    size = 0
    # If the file is larger than 20/10/5MB, then we simplify
    if not "show_full" in request.GET:
        if size > 1024*1024*20:
            simplify_factor = 0.05
        elif size > 1024*1024*10:
            simplify_factor = 0.02
        elif size > 1024*1024*5:
            simplify_factor = 0.001

    colors = ["green", "blue", "red", "orange", "brown", "navy", "teal", "purple", "pink", "maroon", "chocolate", "gold", "ivory", "snow"]
    color_features = {}

    count = 0
    legend = {}
    show_individual_colors = False
    dataviz = Dataviz.objects.filter(shapefile=info, site=site)
    properties = None
    if dataviz:
        properties = dataviz[0]
        if properties.colors and properties.colors["option"] == "single":
            # One single color for everything on the map
            show_individual_colors = False
            color = properties.colors["color"]
        elif properties.colors and properties.colors["option"] == "assigned":
            # Colors are assigned by particular features, so we check what feature that is and we store the json with the associated colors
            show_individual_colors = True
            color_features = properties.colors["features"]
            get_feature = properties.colors["set_feature"]
        else:
            # Each space has an individual color
            show_individual_colors = True
    else:
        show_individual_colors = True

    # Awaiting embedding of SCHEME
    if show_individual_colors and False:
        s = properties["scheme"]
        colors = COLOR_SCHEMES[s]

    for each in spaces:
        geom_type = each.geometry.geom_type
        if simplify_factor:
            geo = each.geometry.simplify(simplify_factor)
        else:
            geo = each.geometry

        url = each.get_absolute_url

        # If we need separate colors we'll itinerate over them one by one
        if show_individual_colors:
            if color_features:
                relevant_feature = each.meta_data["features"][get_feature]
                if relevant_feature in color_features:
                    color = color_features[relevant_feature]
                else:
                    color = "purple"
            else:
                try:
                    color = colors[count]
                    count += 1
                except:
                    color = colors[0]
                    count = 0
            legend[color] = each.name

        content = ""
        content = content + f"<a href='{url}'>View details</a>"

        try:
            features.append({
                "type": "Feature",
                "geometry": json.loads(geo.json),
                "properties": {
                    "name": str(each),
                    "id": each.id,
                    "content": content,
                    "color": color if color else "",
                },
            })
        except Exception as e:
            messages.error(request, f"We had an issue reading one of the items which had an invalid geometry ({each}). Error: {str(e)}")

    data = {
        "type":"FeatureCollection",
        "features": features,
        "geom_type": geom_type,
    }

    context = {
        "info": info,
        "load_map": True,
        "load_leaflet_item": True,
        "load_datatables": True,
        "data": data,
        "properties": properties,
        "show_individual_colors": show_individual_colors,
        "colors": colors,
        "features": features,
        "mapstyle": properties.mapstyle if properties else None,
        "swapped_corridor_coords": get_swapped_corridor_coords(site),
    }

    return render(request, "map.html", context)

def space(request, id):
    info = get_object_or_404(ReferenceSpace, pk=id)
    geo = info.geometry

    if "download" in request.POST:
        response = HttpResponse(geo.geojson, content_type="application/json")
        response["Content-Disposition"] = f"attachment; filename=\"{info.name}.geojson\""
        return response

    map = folium.Map(
        location=[info.geometry.centroid[1], info.geometry.centroid[0]],
        zoom_start=14,
        scrollWheelZoom=False,
        tiles=STREET_TILES,
        attr="Mapbox",
    )

    folium.GeoJson(
        geo.geojson,
        name="geojson",
    ).add_to(map)

    if info.geometry.geom_type != "Point":
        # For a point we want to give some space around it, but polygons should be
        # an exact fit
        map.fit_bounds(map.get_bounds())

    Fullscreen().add_to(map)

    satmap = folium.Map(
        location=[info.geometry.centroid[1], info.geometry.centroid[0]],
        zoom_start=17,
        scrollWheelZoom=False,
        tiles=SATELLITE_TILES,
        attr="Mapbox",
    )

    folium.GeoJson(
        geo.geojson,
        name="geojson",
    ).add_to(satmap)

    if True:
        # For a point we want to give some space around it, but polygons should be
        # an exact fit, and we also want to show the outline of the polygon on the
        # satellite image
        satmap.fit_bounds(map.get_bounds())
        def style_function(feature):
            return {
                "fillOpacity": 0,
                "weight": 4,
            }
        folium.GeoJson(
            info.geometry.geojson,
            name="geojson",
            style_function=style_function,
        ).add_to(satmap)
    Fullscreen().add_to(satmap)

    context = {
        "info": info,
        "map": map._repr_html_(),
        "satmap": satmap._repr_html_(),
        "center": info.geometry.centroid,
    }
    return render(request, "space.html", context)


def maps(request):
    site = get_site(request)
    types = Document.DOC_TYPES
    parents = []
    hits = {}
    type_list = {}
    getcolors = {}
    relevant_types = ["STEPPING_STONES", "CONNECTORS", "TRANSPORT", "POTENTIAL", "CONTEXT"]

    for each in types:
        if each[0] in relevant_types:
            parents.append(each[0])
            hits[each[0]] = []
            type_list[each[0]] = each[1]

    documents = Document.objects.filter(site=site, is_active=True, doc_type__in=relevant_types, is_shapefile=True).order_by("doc_type")
    for each in documents:
        t = each.doc_type
        hits[t].append(each)
        getcolors[each.id] = each.color

    for each in parents:
        if not hits[each]:
            parents.remove(each)

    context = {
        "maps": documents,
        "load_map": True,
        "parents": parents,
        "hits": hits,
        "boundaries": ReferenceSpace.objects.get(pk=983170),
        "type_list": type_list,
        "getcolors": getcolors,
        "title": "Maps",
        "icons": {
            1: "leaf",
            2: "draw-square",
            3: "train",
            4: "map-marker",
            5: "info-circle",
        },
        "swapped_corridor_coords": get_swapped_corridor_coords(site),
    }
    return render(request, "maps.html", context)

def report(request, show_map=False, lat=False, lng=False, site_selection=False):

    if show_map and not "lat" in request.GET:
        map = folium.Map(
            location=[-34.070078, 18.571595],
            zoom_start=10,
            scrollWheelZoom=True,
            tiles=STREET_TILES,
            attr="Mapbox",
        )
        context = {
            "load_map": True,
            "site_selection": site_selection,
            "lat": -34.07,
            "lng": 18.57,
        }
        return render(request, "website/report.map.html", context)
    elif not "lat" in request.GET and not lat:
        context = {
            "site_selection": site_selection,
        }
        return render(request, "website/report.start.html", context)

    info = get_object_or_404(ReferenceSpace, pk=988911)
    schools = get_object_or_404(Document, pk=983409)
    cemeteries = get_object_or_404(Document, pk=983426)
    parks = get_object_or_404(Document, pk=983479)
    rivers = get_object_or_404(Document, pk=983382)
    
    railway = get_object_or_404(Document, pk=2)
    centers = get_object_or_404(Document, pk=983491)
    remnants = get_object_or_404(Document, pk=983097)
    gardens = get_object_or_404(Document, pk=1)
    vegetation = get_object_or_404(Document, pk=983172)
    boundaries = ReferenceSpace.objects.get(pk=983170)

    # These are the layers we open by default on the map
    open_these_layers = [schools.id, cemeteries.id, parks.id, rivers.id, railway.id, remnants.id, gardens.id, boundaries.id, centers.id]

    if "lat" in request.GET:
        lat = float(request.GET["lat"])
        lng = float(request.GET["lng"])
    else:
        lat = float(lat)
        lng = float(lng)

    if "next" in request.POST:
        response = redirect("rehabilitation_assessment")
        response.set_cookie("lat", lat)
        response.set_cookie("lng", lng)
        return response

    center = geos.Point(x=lng, y=lat, srid=4326)
    center.transform(3857) # Transform Projection to Web Mercator     
    radius = 1000 # Number of meters distance
    circle = center.buffer(radius) 
    circle.transform(4326) # Transform back to WGS84 to create geojson

    try:
        point = geos.Point(x=lng, y=lat)
        veg = vegetation.spaces.get(geometry__intersects=point)
        veg = veg.get_vegetation_type()
    except:
        veg = None

    #parks = parks.spaces.filter(geometry__within=circle)
    #remnants = remnants.spaces.filter(geometry__distance_lte=(center, D(km=3)))

    parks = parks.spaces.filter(Q(geometry__within=circle)|Q(geometry__intersects=circle))
    cemeteries = cemeteries.spaces.filter(Q(geometry__within=circle)|Q(geometry__intersects=circle))
    schools = schools.spaces.filter(Q(geometry__within=circle)|Q(geometry__intersects=circle))
    remnants = remnants.spaces.filter(Q(geometry__within=circle)|Q(geometry__intersects=circle))
    gardens = gardens.spaces.filter(Q(geometry__within=circle)|Q(geometry__intersects=circle))
    rivers = rivers.spaces.filter(Q(geometry__within=circle)|Q(geometry__intersects=circle))
    railway = railway.spaces.filter(Q(geometry__within=circle)|Q(geometry__intersects=circle))
    centers = centers.spaces.filter(Q(geometry__within=circle)|Q(geometry__intersects=circle))

    # We want to figure out what the total river and railway length (in m) in the circle is.
    # To do so we need to convert to a coordinate system that measures things in m
    # See: https://gis.stackexchange.com/questions/180776/get-linestring-length-in-meters-python-geodjango
    length = 0
    for each in rivers:
        geom = each.geometry
        geom = geom.intersection(circle)
        geom.transform(3857)
        length += geom.length

    railway_length = 0
    for each in railway:
        geom = each.geometry
        geom = geom.intersection(circle)
        geom.transform(3857)
        railway_length += geom.length

    expansion = {}
    expansion["count"] = schools.count() + cemeteries.count() + parks.count() + centers.count()
    if expansion["count"] <= 1:
        expansion["rating"] = 0
        expansion["label"] = "<span class='badge bg-danger'>poor</span>"
    elif expansion["count"] <= 3:
        expansion["rating"] = 1
        expansion["label"] = "<span class='badge bg-warning'>okay</span>"
    else:
        expansion["rating"] = 2
        expansion["label"] = "<span class='badge bg-success'>great</span>"
    expansion["label"] = mark_safe(expansion["label"])

    connectors = {}
    connectors["count"] = length + railway_length
    if connectors["count"] <= 200:
        connectors["rating"] = 0
        connectors["label"] = "<span class='badge bg-danger'>poor</span>"
    elif connectors["count"] <= 500:
        connectors["rating"] = 1
        connectors["label"] = "<span class='badge bg-warning'>okay</span>"
    else:
        connectors["rating"] = 2
        connectors["label"] = "<span class='badge bg-success'>great</span>"
    connectors["label"] = mark_safe(connectors["label"])

    existing = {}
    existing["count"] = remnants.count() + gardens.count()
    if existing["count"] <= 0:
        existing["rating"] = 0
        existing["label"] = "<span class='badge bg-danger'>poor</span>"
    elif existing["count"] <= 2:
        existing["rating"] = 1
        existing["label"] = "<span class='badge bg-warning'>okay</span>"
    else:
        existing["rating"] = 2
        existing["label"] = "<span class='badge bg-success'>great</span>"
    existing["label"] = mark_safe(existing["label"])

    types = Document.DOC_TYPES
    parents = []
    hits = {}
    type_list = {}
    getcolors = {}
    relevant_types = [1,2,3,4,5]
    for each in types:
        e = int(each)
        if e in relevant_types:
            parents.append(e)
            hits[e] = []
            type_list[e] = each.label

    documents = Document.objects.filter(is_active=True, include_in_site_analysis=True).order_by("type")
    for each in documents:
        t = each.type
        hits[t].append(each)
        getcolors[each.id] = each.color

    for each in parents:
        if not hits[each]:
            parents.remove(each)

    context = {
        "parks": parks,
        "cemeteries": cemeteries,
        "rivers": rivers,
        "railway": railway,
        "centers": centers,
        "remnants": remnants,
        "gardens": gardens,
        "schools": schools,
        "expansion": expansion,
        "connectors": connectors,
        "existing": existing,
        "veg": veg,
        "center": center,
        "lat": lat,
        "lng": lng,
        "site_selection": site_selection,
        "open_these_layers": open_these_layers,
        "river_length": length,
        "railway_length": railway_length,
        "maps": documents,
        "load_map": True,
        "parents": parents,
        "hits": hits,
        "boundaries": boundaries,
        "type_list": type_list,
        "getcolors": getcolors,
        "title": "Maps",
        "icons": {
            1: "leaf",
            2: "draw-square",
            3: "train",
            4: "map-marker",
            5: "info-circle",
        },
        "properties": {"map_layer_style": "light-v10"},
    }
    return render(request, "website/report.html", context)

def geojson(request, id):
    info = Document.objects.get(pk=id)
    features = []
    spaces = info.spaces.all()
    intersection = False

    if "space" in request.GET:
        spaces = spaces.filter(id=request.GET["space"])

    if "lat" in request.GET and "lng" in request.GET:
        lat = float(request.GET.get("lat"))
        lng = float(request.GET.get("lng"))
        center = geos.Point(x=lng, y=lat, srid=4326)
        center.transform(3857) # Transform Projection to Web Mercator     
        radius = 1000 # Number of meters distance
        circle = center.buffer(radius) 
        circle.transform(4326) # Transform back to WGS84 to create geojson
        intersection = True
        spaces = spaces.filter(Q(geometry__within=circle)|Q(geometry__intersects=circle))

    geom_type = None
    for each in spaces:
        if each.geometry:
            geom = each.geometry
            if intersection:
                geom = each.geometry.intersection(circle)
            url = each.get_absolute_url
            content = ""
            if each.photo:
                content = f"<a class='d-block' href='{url}'><img alt='{each.name}' src='{each.photo.image.thumbnail.url}' /></a><hr>"
            content = content + f"<a href='{url}'>View details</a>"
            content = content + f"<br><a href='/maps/{info.id}'>View source layer: <strong>{info}</strong></a>"
            if not geom_type:
                geom_type = geom.geom_type
            features.append({
                "type": "Feature",
                "geometry": json.loads(geom.json),
                "properties": {
                    "name": each.name,
                    "content": content,
                    "id": each.id,
                },
            })

    data = {
        "type":"FeatureCollection",
        "features": features,
        "geom_type": geom_type,
    }
    return JsonResponse(data)

def species_overview(request, vegetation_type=None):

    site = get_site(request)
    samples = Species.objects.values_list("id", flat=True).filter(site=site, photo__isnull=False)
    genus = Genus.objects.filter(species__site=site)
    families = Family.objects.filter(species__site=site)
    species = Species.objects.filter(site=site)
    veg_types = VegetationType.objects.filter(sites=site).annotate(
        total=Count("species", filter=Q(species__site=site))
    ).filter(total__gt=0)

    if vegetation_type:
        vegetation_type = VegetationType.objects.get(slug=vegetation_type)
        species = species.filter(vegetation_types=vegetation_type)
        samples = samples.filter(vegetation_types=vegetation_type)

        genus = genus.annotate(total=Count("species", filter=Q(species__vegetation_types=vegetation_type))).filter(total__gt=0)
        families = families.annotate(total=Count("species", filter=Q(species__vegetation_types=vegetation_type))).filter(total__gt=0)
        features = SpeciesFeatures.objects.filter(species__vegetation_types=vegetation_type).distinct()
    else:
        genus = genus.annotate(total=Count("species"))
        families = families.annotate(total=Count("species"))
        features = SpeciesFeatures.objects.all()

    try:
        samples = Species.objects.filter(pk__in=random.sample(list(samples), 3))
    except:
        samples = None

    context = {
        "genus": genus,
        "family": families,
        "load_datatables": True,
        "samples": samples,
        "all": species.count(),
        "features": features,
        "vegetation_types": veg_types,
        "vegetation_type": vegetation_type,
        "veg_link": f"?vegetation_type={vegetation_type.id}" if vegetation_type else "",
        "menu": "species",
        "show_total_box": True,
        "page": "all_species",
    }
    return render(request, "species.overview.html", context)

def species_list(request, genus=None, family=None):
    site = get_site(request)
    species = Species.objects.filter(site=site)

    if genus:
        genus = get_object_or_404(Genus, pk=genus)
        species = species.filter(genus=genus)
        full_list = Genus.objects.all()
    if family:
        family = get_object_or_404(Family, pk=family)
        species = species.filter(family=family)
        full_list = Family.objects.all()

    vegetation_type = None
    if "vegetation_type" in request.GET:
        vegetation_type = VegetationType.objects.get(pk=request.GET["vegetation_type"])
        species = species.filter(vegetation_types=vegetation_type)

    full_list = full_list.annotate(total=Count("species"))
    context = {
        "load_datatables": True,
        "genus": genus,
        "family": family,
        "species_list": species,
        "full_list": full_list,
        "menu": "species",
    }
    return render(request, "species.all.html", context)

def species_full_list(request):
    site = get_site(request)
    species = Species.objects.filter(site=site)

    vegetation_type = None
    if "vegetation_type" in request.GET:
        vegetation_type = VegetationType.objects.get(pk=request.GET["vegetation_type"])
        species = species.filter(vegetation_types=vegetation_type)

    features = None
    if "feature" in request.GET:
        features = SpeciesFeatures.objects.filter(pk__in=request.GET.getlist("feature"))
        if request.GET.get("search") == "all":
            for each in features:
                species = species.filter(features=each)
        else:
            species = species.filter(features__in=features)

    species = species.distinct()

    info = None
    photo = None

    if "page" in request.GET:
        try:
            info = Page.objects.get(site=site, slug=request.GET["page"])
            photos = info.photos.all()
            if photos:
                photo = info.photos.all()[0]
        except:
            info = None

    context = {
        "species_list": species,
        "load_datatables": True,
        "features": features,
        "vegetation_type": vegetation_type,
        "menu": "species",
        "page": request.GET.get("page"),
        "info": info,
        "photo": photo,
    }
    return render(request, "species.all.html", context)

def rehabilitation_assessment(request, title="Assess and imagine"):
    if "next" in request.POST:
        if title == "Assess and imagine":
            return redirect("rehabilitation_plant_selection")
        elif title == "Design your garden":
            return redirect("rehabilitation_workplan")
        elif title == "Make a work plan":
            return redirect("rehabilitation_monitoring")
    context = {
        "title": title,
        "social": Page.objects.get(slug="social-assessment"),
        "ecological": Page.objects.get(slug="ecological-assessment"),
        "vision": Page.objects.get(slug="vision-and-mission"),
    }
    return render(request, "website/assessment.html", context)

def rehabilitation_design(request):
    context = {
        "info": Page.objects.get(slug="design-your-garden"),
    }
    return render(request, "website/design.html", context)

def rehabilitation_workplan(request):
    context = {
        "info": Page.objects.get(slug="workplan"),
    }
    return render(request, "website/workplan.html", context)

def rehabilitation_monitoring(request):
    context = {
        "info": Page.objects.get(slug="monitoring"),
    }
    return render(request, "website/monitoring.html", context)

def rehabilitation_plant_selection(request):
    context = {
    }
    return render(request, "website/assessment.html", context)

# Get species text in the local language, with English as a fall-back
def fetch_species_text(request, species):
    info = SpeciesText.objects.filter(language__code=request.language, species=species)
    if not info:
        info = SpeciesText.objects.filter(language_id=1, species=species)
    if info:
        return info[0]
    else:
        return SpeciesText()

def species(request, id):
    site = get_site(request)
    info = get_object_or_404(Species, pk=id)
    details = fetch_species_text(request, info)
    sources = SpeciesVegetationTypeLink.objects.filter(species=info, vegetation_type__sites=site)

    # Needs work
    garden = None
    if "garden" in request.COOKIES:
        cookie_garden = Garden.objects_unfiltered.filter(uuid=request.COOKIES["garden"])
        if cookie_garden:
            garden = cookie_garden[0]
    # END

    context = {
        "info": info,
        "details": details,
        "photos": Photo.objects.filter(species=info, position__gte=1),
        "title": info.name,
        "menu": "species",
        "sources": sources,
        "garden": garden,
    }

    return render(request, "species.html", context)

def species_sources(request):
    site = get_site(request)
    
    context = {
        "menu": "species",
        "documents": Document.objects.filter(site=site, doc_type="SPECIES_LIST"),
        "title": _("Species source document"),
        "page": "sources",
    }
    return render(request, "species.sources.html", context)

def species_source(request, id):
    site = get_site(request)
    info = Document.objects.get(site=site, doc_type="SPECIES_LIST", pk=id)
    species = Species.objects.filter(species_links__file__attached_to=info)

    context = {
        "menu": "species",
        "info": info,
        "species_list": species,
        "title": info.name,
    }

    return render(request, "species.source.html", context)

def gardens(request):
    site = get_site(request)
    gardens = Garden.objects.prefetch_related("organizations").filter(is_active=True, site=site)
    context = {
        "gardens": gardens,
        "info": Page.objects.get(pk=2),
        "load_datatables": True,
        "page": "gardens",
        "menu": "gardens",
    }
    return render(request, "gardens/index.html", context)

def gardens_map(request):
    site = get_site(request)
    gardens = Garden.objects.prefetch_related("organizations").filter(is_active=True, site=site)
    context = {
        "gardens": gardens,
        "info": Page.objects.get(pk=2),
        "page": "gardens_map",
        "load_map": True,
        "mapstyle": MapStyle.objects.get(pk=3),
        "swapped_corridor_coords": get_swapped_corridor_coords(site),
        "load_datatables": True,
        "menu": "gardens",
    }
    return render(request, "gardens/map.html", context)

def garden(request, id):
    info = Garden.objects_unfiltered.get(pk=id)
    show_garden = True

    if not info.is_active:
        show_garden = False
        if request.user.is_authenticated:
            show_garden = True
            if "activate" in request.POST:
                info.is_active = True
                info.save()
                messages.success(request, "Garden has been activated.")
                return redirect(reverse("garden", args=[info.id]))
        elif "uuid" in request.GET and request.GET.get("uuid") == str(info.uuid):
            show_garden = True

    if request.user.is_staff:
        if "delete" in request.POST:
            info.delete()
            messages.success(request, "The garden was removed.")
            return redirect("gardens")

    if not show_garden:
        raise Http404("This garden was not found.")

    try:
        photos = Photo.objects.filter(garden=info).exclude(id=info.photo.id).order_by("-date")[:12]
        photos = Photo.objects.filter(garden=info).order_by("-date")[:12]
    except:
        photos = None

    if info.geometry:
        map = folium.Map(
            zoom_start=14,
            scrollWheelZoom=False,
            location=[info.geometry.centroid[1],info.geometry.centroid[0]],
            tiles=STREET_TILES,
            attr="Mapbox",
        )

        folium.GeoJson(
            info.geometry.geojson,
            name="geojson",
        ).add_to(map)

        Fullscreen().add_to(map)

    context = {
        "map": map._repr_html_() if info.geometry else None,
        "info": info,
        "photos": photos,
        "title": info.name,
        "menu": "gardens",
    }
    return render(request, "gardens/garden.html", context)

def garden_form(request, id=None, token=None, uuid=None):

    info = None
    new_garden = True
    if id:
        if not request.user.is_authenticated:
            messages.warning(request, "You must be logged in to access that page.")
            return redirect("index")
        new_garden = False
        ModelForm = modelform_factory(Garden, fields=["name", "description", "phase_assessment", "phase_alienremoval", "phase_landscaping", "phase_pioneers", "phase_birdsinsects", "phase_specialists", "phase_placemaking", "organizations"])
        info = Garden.objects_unfiltered.get(pk=id)
        form = ModelForm(request.POST or None, instance=info)
    elif uuid:
        manager = GardenManager.objects.filter(garden__uuid=uuid, token=token)
        if not manager.exists():
            messages.error(request, "The link is invalid. Please select a garden and re-request a link or contact us if in doubt.")
            return redirect("gardens")
        elif manager[0].token_expiration_date < timezone.now():
            messages.error(request, "The link has expired. Please re-request a link a new below contact us if in doubt.")
            return redirect("garden_manager", manager[0].garden.id)
        else:
            info = manager[0].garden
            new_garden = False
            ModelForm = modelform_factory(Garden, fields=["name", "description", "phase_assessment", "phase_alienremoval", "phase_landscaping", "phase_pioneers", "phase_birdsinsects", "phase_specialists", "phase_placemaking"])
            form = ModelForm(request.POST or None, instance=info)
    else:
        labels = {
            "name": "Garden name",
        }
        ModelForm = modelform_factory(Garden, fields=["name", "description", "phase_assessment", "phase_alienremoval", "phase_landscaping", "phase_pioneers", "phase_birdsinsects", "phase_specialists", "phase_placemaking"], labels=labels)
        form = ModelForm(request.POST or None)

    if request.method == "POST":
        if "photographer" in request.POST:
            Photo.objects.create(
                description = request.POST.get("description"),
                author = request.POST.get("photographer"),
                image = request.FILES.get("photo"),
                garden = info,
            )
            messages.success(request, "The new photo has been added.")
            return redirect(request.get_full_path())
        elif form.is_valid():
            info = form.save()
            if request.POST.get("lat") and request.POST.get("lng"):
                try:
                    lat = float(request.POST.get("lat"))
                    lng = float(request.POST.get("lng"))
                    info.geometry = geos.Point(lng, lat)
                except:
                    pass
                info.save()
            if new_garden:
                info.is_active = False
                info.source_id = 8
                info.original = request.POST
                info.save()

                mailcontext = {
                    "info": info,
                    "uploader": request.POST.get("your_name"),
                    "email": request.POST.get("email"),
                    "phone": request.POST.get("phone"),
                    "link": reverse("garden", args=[info.id]) + "?uuid=" + str(info.uuid),
                }
                msg_html = render_to_string("mailbody/newgarden.html", mailcontext)
                msg_plain = render_to_string("mailbody/newgarden.txt", mailcontext)

                sender = f'"{site.name}" <{site.email}>'
                recipient = sender

                send_mail(
                    "New garden added: " + info.name,
                    msg_plain,
                    sender,
                    [recipient],
                    html_message=msg_html,
                )

                messages.success(request, "Thanks! We have received your garden details. We will review this and get back to you (might take a week or so, please stay tuned).")
                return redirect("index")
            else:

                if uuid:
                    mailcontext = {
                        "info": info,
                        "manager": manager[0],
                    }
                    msg_html = render_to_string("mailbody/gardenupdate.html", mailcontext)
                    msg_plain = render_to_string("mailbody/gardenupdate.txt", mailcontext)

                    sender = f'"{site.name}" <{site.email}>'
                    recipient = sender

                    send_mail(
                        "Garden updated: " + info.name,
                        msg_plain,
                        sender,
                        [recipient],
                        html_message=msg_html,
                    )

                messages.success(request, "Information was saved.")
                return redirect(info.get_absolute_url)
        else:
            messages.error(request, "We could not save your form, please fill out all fields")
    context = {
        "info": info,
        "form": GardenForm(),
    }
    return render(request, "garden.form.html", context)

def garden_manager(request, id):
    info = Garden.objects.get(pk=id)
    if "email" in request.POST:
        email = request.POST.get("email").lower().strip()
        manager = info.managers.filter(email=email)
        if manager:
            manager = manager[0]
            token = secrets.token_urlsafe()
            manager.token = token
            manager.token_expiration_date = timezone.now() + relativedelta(days=30)
            manager.save()
            link = reverse("garden_form", args=[info.uuid, token])
            link = request.build_absolute_uri(link)

            mailcontext = {
                "name": manager.name,
                "garden": info.name,
                "link": link,
            }
            msg_html = render_to_string("mailbody/managegarden.html", mailcontext)
            msg_plain = render_to_string("mailbody/managegarden.txt", mailcontext)

            sender = '"Fynbos Corridor Collaboration Website" <info@fynboscorridors.org>'
            recipient = f"{manager.name} <{manager.email}>"

            send_mail(
                "Manage garden information: " + info.name,
                msg_plain,
                sender,
                [recipient],
                html_message=msg_html,
            )
            messages.success(request, f"We have send you an e-mail link to modify the garden information. Please check your Notifications or Spam folder if you don't see this.")
        else:
            messages.error(request, f"Your e-mail address was not found. Are you sure this was registered? If so, please <a href='contact'>contact us</a> and we will correct this.")

    context = {
        "no_index": True,
        "info": info,
    }
    return render(request, "website/garden.manager.html", context)

def vegetation_types(request):
                
    site = get_site(request)
    info = site.vegetation_types_map
    spaces = info.spaces.all()

    # We want to redirect to a particular vegetation type. The ID of the Space is passed in the
    # url so we have to figure out to which vegetation type this corresponds
    if "redirect" in request.GET:
        space = spaces.get(pk=request.GET["redirect"])
        vegetation_type = VegetationType.objects.get(spaces=space)
        return redirect(vegetation_type.get_absolute_url())

    features = []
    simplify_factor = None

    colors = ["green", "blue", "red", "orange", "brown", "navy", "teal", "purple", "pink", "maroon", "chocolate", "gold", "ivory", "snow"]
    color_features = {}

    count = 0
    legend = {}
    properties = None
    show_individual_colors = True

    for each in spaces:
        geom_type = each.geometry.geom_type
        geo = each.geometry
        url = each.get_absolute_url

        # If we need separate colors we'll itinerate over them one by one
        if show_individual_colors:
            try:
                color = colors[count]
                count += 1
            except:
                color = colors[0]
                count = 0
            legend[color] = each.name

        content = ""
        content = content + f"<a href='?redirect={each.id}'>View details</a>"

        try:
            features.append({
                "type": "Feature",
                "geometry": json.loads(geo.json),
                "properties": {
                    "name": str(each),
                    "id": each.id,
                    "content": content,
                    "color": color if color else "",
                },
            })
        except Exception as e:
            messages.error(request, f"We had an issue reading one of the items which had an invalid geometry ({each}). Error: {str(e)}")

    data = {
        "type":"FeatureCollection",
        "features": features,
        "geom_type": geom_type,
    }

    context = {
        "all": VegetationType.objects.filter(site=site),
        "info": Page.objects.get(pk=1),
        "page": "vegetation_types",
        "menu": "maps",

        "load_map": True,
        "load_leaflet_item": True,
        "load_datatables": True,
        "data": data,
        "properties": properties,
        "show_individual_colors": show_individual_colors,
        "colors": colors,
        "features": features,
        "mapstyle": properties.mapstyle if properties else None,

    }
    return render(request, "fcc/vegetationtypes.html", context)

def vegetation_type(request, slug):

    info = get_object_or_404(VegetationType, slug=slug)

    if "download" in request.POST:
        geo = info.spaces.all()[0].geometry
        response = HttpResponse(geo.geojson, content_type="application/json")
        response["Content-Disposition"] = f"attachment; filename=\"{info.name}.geojson\""
        return response

    map = folium.Map(
        zoom_start=14,
        scrollWheelZoom=False,
        tiles=STREET_TILES,
        attr="Mapbox",
    )

    Fullscreen().add_to(map)

    for each in info.spaces.all():
        folium.GeoJson(
            each.geometry.geojson,
            name="geojson",
        ).add_to(map)

    map.fit_bounds(map.get_bounds())

    context = {
        "info": info,
        "map": map._repr_html_(),
        "menu": "maps",
        "page": "vegetation_types",
        "title": str(info),
    }
    return render(request, "fcc/vegetationtype.html", context)

def profile(request, section=None, lat=None, lng=None, id=None, subsection=None):

    vegetation = get_object_or_404(Document, pk=983172)
    veg = None
    link = None

    if "next" in request.POST:
        return redirect("rehabilitation_design")

    if not lat:
        lat = request.COOKIES.get("lat")
        lng = request.COOKIES.get("lng")

    if lat and lng:
        link = f"/profile/{lat},{lng}/"

    try:
        lat = float(lat)
        lng = float(lng)
        center = geos.Point(lng, lat)
        veg = vegetation.spaces.get(geometry__intersects=center)
        veg = VegetationType.objects.get(spaces=veg)
        suburb = ReferenceSpace.objects.filter(source_id=334434, geometry__intersects=center)
        species = Species.objects.filter(vegetation_types=veg)
        if suburb:
            suburb = suburb[0].name.title()
    except:
        messages.warning(request, f"We are unable to locate the relevant vegetation type. Please make sure to <a href='/fynbos-rehabilitation/site-selection/'>select a site on the map</a> first, so that we can load the relevant plant species for your chosen location.")
        suburb = None
        species = None

    context = {
        "lat": lat,
        "lng": lng,
        "link": link,
        "info": veg,
        "section": section,
        "subsection": subsection,
        "suburb": suburb,
        "page": Page.objects.get(slug="plant-selection"),
        "species": species,
    }

    if section == "plants":

        if subsection == "pioneers":
            context["title"] = "Pioneer species"
            species = species.filter(features__id=125)
            context["species_list"] = species

        elif subsection == "birds":
            context["title"] = "Bird-friendly species"
            context["sugarbird_list"] = species.filter(features__id__in=[111,113,114])
            context["sunbird_list"] = species.filter(features__id=133)
            context["bird_list"] = species.filter(features__id=109)

        elif subsection == "insects":
            context["title"] = "Insect-friendly species"
            context["bee_list"] = species.filter(features__id=110)
            context["monkeybeetle_list"] = species.filter(features__id=112)

        elif subsection == "edible":
            context["title"] = "Edible plant species"
            species = species.filter(features__id=123)
            context["species_list"] = species

        elif subsection == "medicinal":
            context["title"] = "Medicinal plant species"
            species = species.filter(features__id=115)
            context["species_list"] = species

        context["photos_first"] = True

    elif section == "nearby":
        
        files = {
            "schools": 983409,
            "cemeteries": 983426,
            "parks": 983479,
            "rivers": 983382,
            "remnants": 983097,
        }

        capetown = get_object_or_404(ReferenceSpace, pk=988911)
        source_document = get_object_or_404(Document, pk=files[subsection])

        center = geos.Point(x=lng, y=lat, srid=4326)
        center.transform(3857) # Transform Projection to Web Mercator     
        radius = 1000 # Number of meters distance
        circle = center.buffer(radius) 
        circle.transform(4326) # Transform back to WGS84 to create geojson

        layer = source_document.spaces.filter(Q(geometry__within=circle)|Q(geometry__intersects=circle))

        if not layer:
            radius = 2000 # Number of meters distance
            circle = center.buffer(radius) 
            circle.transform(4326) # Transform back to WGS84 to create geojson

            messages.warning(request, "We could not find anything in the regular area search, so we expanded our search to cover a wider area.")
            layer = source_document.spaces.filter(Q(geometry__within=circle)|Q(geometry__intersects=circle))

        map = folium.Map(
            location=[lat,lng],
            zoom_start=14,
            scrollWheelZoom=False,
            tiles=STREET_TILES,
            attr="Mapbox",
        )

        folium.GeoJson(
            circle.geojson,
            name="geojson",
        ).add_to(map)

        Fullscreen().add_to(map)

        satmap = folium.Map(
            location=[lat,lng],
            zoom_start=17,
            scrollWheelZoom=False,
            tiles=SATELLITE_TILES,
            attr="Mapbox",
        )

        def style_function(feature):
            return {
                "fillOpacity": 0,
                "weight": 4,
                "color": "#fff",
            }

        folium.GeoJson(
            circle.geojson,
            name="geojson",
            style_function=style_function,
        ).add_to(satmap)

        satmap.fit_bounds(map.get_bounds())
        Fullscreen().add_to(satmap)

        folium.GeoJson(
            capetown.geometry.geojson,
            name="geojson",
            style_function=style_function,
        ).add_to(satmap)

        for each in layer:
            geom = each.geometry.intersection(circle)

            folium.GeoJson(
                geom.geojson,
                name="geojson",
            ).add_to(map)

            folium.GeoJson(
                geom.geojson,
                name="geojson",
            ).add_to(satmap)

        context["map"] = map._repr_html_()
        context["satmap"] = satmap._repr_html_()
        context["layer"] = layer
        context["source"] = source_document

    return render(request, "website/profile.html", context)

def photos(request, garden=None, photo=None):
    photos = Photo.objects.filter(garden__isnull=False)
    if garden:
        photos = photos.filter(garden_id=garden)
        garden = Garden.objects.get(pk=garden)
    paginator = Paginator(photos, 60)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if photo:
        photo = photos.get(pk=photo)

    context = {
        "photos": page_obj,
        "photo": photo,
        "garden": garden,
    }
    return render(request, "website/photos.html", context)

def corridors_rivers_methodology(request):

    rivers = ReferenceSpace.objects.filter(source_id=983382, meta_data__poor_quality_river=True)
    river_segments = Document.objects.get(pk=5)
    river_buffer = Document.objects.get(pk=3)
    bionet_flat = Document.objects.get(pk=4)
    bionet_buffer = Document.objects.get(pk=6)

    context = {
        "rivers": rivers,
        "river_segments": river_segments.spaces.all()[0].geometry,
        "river_buffer": river_buffer.spaces.all()[0].geometry,
        "bionet_flat": bionet_flat.spaces.all()[0].geometry,
        "bionet_buffer": bionet_buffer.spaces.all()[0].geometry,
        "load_map": True,
        "lat": -33.9790,
        "lng": 18.5284,
        "corridors": Corridor.objects.all(),
        "page": "methodology",
        # Run this if the rivers should show, e.g. for screenshotting
        #"final_rivers": [989882, 990004, 990036, 989903, 990127, 989920, 989924, 990032, 990020],
    }
    return render(request, "website/corridors.rivers.methodology.html", context)

def update_map(request):

    rivers = ReferenceSpace.objects.filter(source_id=983382, meta_data__poor_quality_river=True)

    # ONCE OFF DOCUMENT CREATION

    river_segments = Document.objects.filter(name="Rivers with poor quality and not close to Bionet")
    if river_segments:
        river_segments = river_segments[0]
    else:
        river_segments = Document.objects.create(
            name = "Rivers with poor quality and not close to Bionet",
            content = "This document contains the rivers (with buffer) that are NOT close to bionet. It is used for our priority map. It can be auto-generated through code that is run in the priority_map() function in views.py. Do not edit this map manually.",
        )

    river_buffer = Document.objects.filter(name="Poor quality rivers with buffer")
    if river_buffer:
        river_buffer = river_buffer[0]
    else:
        river_buffer = Document.objects.create(
            name = "Poor quality rivers with buffer",
            content = "This document is generated by taking low-quality rivers and giving them a certain buffer. It is used for our priority map. It can be auto-generated through code that is run in the priority_map() function in views.py. Do not edit this map manually.",
        )

    bionet_flat = Document.objects.filter(name="Bionet - flat file")
    if bionet_flat:
        bionet_flat = bionet_flat[0]
    else:
        bionet_flat = Document.objects.create(
            name = "Bionet - flat file",
            content = "This document contains all of bionet, but all elements are grouped together. It is used for our priority map. It can be auto-generated through code that is run in the priority_map() function in views.py. Do not edit this map manually.",
        )

    bionet_buffer = Document.objects.filter(name="Bionet - with buffer")
    if bionet_buffer:
        bionet_buffer = bionet_buffer[0]
    else:
        bionet_buffer = Document.objects.create(
            name = "Bionet - with buffer",
            content = "This document contains all of bionet, but all elements are grouped together and given a buffer. It is used for our priority map. It can be auto-generated through code that is run in the priority_map() function in views.py. Do not edit this map manually.",
        )

    # MARK ALL THE RIVERS
    if "new_rivers" in request.GET:
        rivers = get_object_or_404(Document, pk=983382)
        badrivers = [
            "DIEP RIVER",
            "DIEPRIVIER",
            "EERSTE RIVER",
            "EERSTERIVIER",
            "ELSIESKRAAL",
            "ELSIESKRAAL CANAL",
            "extension of channel into Salt",
            "extension of Liesbeek into Salt",
            "KUILS RIVER",
            "KUILSRIVIER CHANNEL",
            "MOSSELBANK RIVER",
            "MOSSELBANKRIVIER",
            "SALT RIVER",
            "SAND RIVER",
            "SANDRIVIER",
            "SIR LOWRY'S PASS RIVER",
            "stream extension to Eerste River",
            "ZEEKOEVLEI",
            "ZEEKOEVLEI CANAL",
            "BIG LOTUS RIVER CANAL", # Manually added
            "BIG LOTUS RIVER/NYANGA CANAL", # Manually added
        ]
        a = []
        for each in rivers.spaces.all():
            if each.name in badrivers:
                each.meta_data = {"poor_quality_river": True}
                each.save()
        messages.success(request, f"New rivers are indexed! poor_quality_river=True in meta_data")

    if "update" in request.GET:
        from django.contrib.gis.db.models import Union
        from django.contrib.gis.db.models.functions import MakeValid

        combined = rivers.aggregate(union=Union("geometry"))
        geo = combined["union"]

        # Adding a buffer as per: https://gis.stackexchange.com/questions/228988/add-buffer-around-polygon-in-meters-using-geodjango
        distance = 400 # distance in meter
        buffer_width = distance / 40000000.0 * 360.0
        geo = geo.buffer(buffer_width)

        ReferenceSpace.objects.create(
            name = "Rivers with buffer",
            content = f"Automatically created from the original shapefile, by adding a {distance}m buffer.",
            source = river_buffer,
            geometry = geo,
        )
        messages.success(request, f"We created RIVERS WITH BUFFERS with {distance}m distance")

        bionet = Document.objects.get(pk=983134)

        spaces = bionet_flat.spaces.all()
        spaces.delete()

        # We had invalid geometry in the Bionet shapefile. It is now fixed, but if we 
        # have new geometry that is again invalid, then run this again:
        #bionet.spaces.all().update(geometry=MakeValid("geometry"))

        combined = bionet.spaces.all().aggregate(union=Union("geometry"))
        geo = combined["union"]

        ReferenceSpace.objects.create(
            name = "Bionet in a single layer",
            content = f"Automatically created from the original shapefile, unified into a single layer.",
            source = bionet_flat,
            geometry = geo,
        )
        messages.success(request, f"We created bionet as a single layer")

        space = bionet_flat.spaces.all()[0]
        geo = space.geometry
        distance = 400 # distance in meter
        buffer_width = distance / 40000000.0 * 360.0
        geo = geo.buffer(buffer_width)

        ReferenceSpace.objects.create(
            name = "Bionet with a buffer",
            content = f"Automatically created from the original shapefile, with a buffer of {buffer_width}m.",
            source = bionet_buffer,
            geometry = geo,
        )
        messages.success(request, f"We created BIONET WITH BUFFERS with {distance}m distance")

    #### END OF UPDATING CODE ####

    if "calculate_difference" in request.GET:
        geo_bionet = bionet_buffer.spaces.all()[0].geometry        
        geo_rivers = river_buffer.spaces.all()[0].geometry        

        spaces = river_segments.spaces.all()
        spaces.delete()

        geo = geo_rivers.difference(geo_bionet)
        ReferenceSpace.objects.create(
            name = "Rivers far from Bionet",
            content = f"Automatically created from the original shapefile.",
            source = river_segments,
            geometry = geo,
        )

    ### END OF SECOND UPDATING PART OF CODE

    return render(request, "website/map.update.html")

def page(request, slug, menu=None):

    if slug == "fynbos-rehabilitation":
        check = Page.objects.filter(slug=slug)
        if not check:
            Page.objects.create(name="Fynbos rehabilitation", position=0, format="MARK")

    if request.user.is_authenticated:
        info = get_object_or_404(Page, slug=slug)
        if not info.is_active:
            messages.warning(request, "This page is not currently published and not publicly available.")
    else:
        info = get_object_or_404(Page, slug=slug, is_active=True)

    context = {
        "info": info,
        "title": info.name,
        "menu": menu,
        "slug": slug,
    }
    return render(request, "page.html", context)

def corridors_rivers(request):
    context = {
        "info": Page.objects.get(slug="high-impact-strategic-river-corridors"),
        "corridors": Corridor.objects.all(),
    }
    return render(request, "website/corridors.rivers.html", context)

def corridor_rivers(request, id):
    context = {
        "info": get_object_or_404(Corridor, pk=id),
        "corridors": Corridor.objects.all(),
    }
    return render(request, "website/corridor.rivers.html", context)

def corridors_overview(request):
    context = {}
    return render(request, "website/corridors.overview.html", context)

def corridors(request):
    context = {
        "info": Page.objects.get(slug="fynbos-corridors"),
    }
    return render(request, "website/corridors.introduction.html", context)

def resources(request, slug=None):

    site = get_site(request)
    documents = Document.objects.filter(is_shapefile=False, site=site)
    if slug:
        documents = documents.filter(doc_type=slug.upper())

    context = {
        "documents": documents,
        "title": slug.capitalize(),
        "hide_main_container": True,
        "menu": "resources",
        "page": slug,
    }
    return render(request, "documents.html", context)

def user_login(request):
    redirect_url = "index"
    if request.GET.get("next"):
        redirect_url = request.GET.get("next")

    if request.user.is_authenticated:
        return redirect(redirect_url)

    if request.method == "POST":
        email = request.POST.get("email").lower()
        password = request.POST.get("password")
        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "You are logged in.")
            return redirect(redirect_url)
        else:
            messages.error(request, "We could not authenticate you, please try again.")

    context = {
    }
    return render(request, "website/login.html", context)

def user_logout(request):
    logout(request)
    messages.warning(request, "You are now logged out")

    if "next" in request.GET:
        return redirect(request.GET.get("next"))
    else:
        return redirect("index")

def newsletter(request):
    if request.POST and "email" in request.POST:
        Newsletter.objects.create(email=request.POST.get("email"))
        messages.success(request, "Thank you! You have been registered for our newsletter.")
    else:
        messages.warning(request, "We could not register you for our newsletter - please ensure you enter a valid email address. Try again in the footer below.")

    if "next" in request.POST:
        return redirect(request.POST.get("next"))
    else:
        return redirect("index")

def organizations(request):
    site = get_site(request)
    context = {
        "info": Page.objects.get(site=site, slug="our-organisations"),
        "organizations": Organization.objects.filter(site=site),
        "page": "organizations",
        "menu": "about",
    }
    return render(request, "organizations.html", context)

def newsletter(request):
    site = get_site(request)
    context = {
        "info": Page.objects.get(site=site, slug="newsletter"),
        "page": "newsletter",
        "menu": "about",
    }
    return render(request, "newsletter.html", context)

def documents(request):
    context = {
        "documents": Document.objects.filter(is_active=True, type__in=[6,7]).order_by("name"),
    }
    return render(request, "website/documents.html", context)

def blogs(request):
    site = get_site(request)
    context = {
        "blogs": Page.objects.filter(is_active=True, site=site, page_type=2).order_by("-date"),
        "info": Page.objects.get(site=site, slug="blog"),
        "menu": "resources",
        "page": "blog",
    }
    return render(request, "blogs.html", context)

def blog(request, slug):
    info = Page.objects.get(slug=slug, is_active=True, site=get_site(request))
    context = {
        "info": info,
        "menu": "resources",
        "page": "blog",
    }
    return render(request, "blog.html", context)

def events(request):
    site = get_site(request)
    context = {
        "events": Page.objects.filter(is_active=True, site=site, page_type=3).order_by("-date"),
        "info": Page.objects.get(site=site, slug="events"),
        "menu": "join",
        "page": "events",
    }
    return render(request, "events.html", context)

def event(request, slug):
    info = Page.objects.get(slug=slug, is_active=True, site=get_site(request))
    context = {
        "info": info,
        "menu": "join",
        "page": "event",
    }
    return render(request, "event.html", context)

# Restoration Garden Manager
def planner(request, id=None):
    info = Page.objects.get(slug="planner", is_active=True, site=get_site(request))
    garden = None

    if not id and "garden_uuid" in request.COOKIES and not "new" in request.GET:
        cookie_garden = Garden.objects_unfiltered.filter(uuid=request.COOKIES["garden"])
        if cookie_garden:
            cookie_garden = cookie_garden[0]
            garden = get_garden(request, cookie_garden.id)

    if id:
        garden = get_garden(request, id)

    if request.method == "POST" and "garden" in request.POST:
        garden = Garden.objects.create(
            name = request.POST["garden"],
            is_user_created = True,
            is_active = False,
            site = get_site(request),
        )

        response = redirect(reverse("planner_location", args=[garden.id]) + "?new_garden")
        response.set_cookie("garden_uuid", garden.uuid)
        response.set_cookie("garden_id", garden.id)
        return response

    context = {
        "page_info": info,
        "page": "dashboard",
        "menu": "planner",
        "garden": garden,
    }
    return render(request, "planner/index.html", context)

def planner_location(request, id):

    site = get_site(request)

    if not (garden := get_garden(request, id)):
        return redirect("planner")

    if "lat" in request.GET and "lng" in request.GET:
        lat = float(request.GET.get("lat"))
        lng = float(request.GET.get("lng"))
        garden.geometry = geos.Point(lng, lat)
        garden.save()
        messages.success(request, _("Your garden location was saved."))
        if "new_garden" in request.GET:
            return redirect(reverse("planner_site", args=[garden.id]) + "?new_garden")
        else:
            return redirect(reverse("planner", args=[garden.id]))

    map = folium.Map(
        location=[site.lat, site.lng],
        zoom_start=10,
        scrollWheelZoom=True,
        tiles=STREET_TILES,
        attr="Mapbox",
    )

    if garden.geometry:
        folium.Marker(
            location=[garden.geometry.centroid.y, garden.geometry.centroid.x],
            popup=_("Garden location"),
            icon=folium.Icon(color="blue")
        ).add_to(map)

    context = {
        "menu": "planner",
        "page": "location",
        "load_map": True,
        "lat": site.lat,
        "lng": site.lng,
        "info": Page.objects.get(site=site, slug="planner-location"),
        "garden": garden,
    }
    return render(request, "planner/location.html", context)

def planner_target_species(request, id):

    site = get_site(request)
    targets = Page.objects.filter(site=site, page_type=Page.PageType.TARGET)

    if not (garden := get_garden(request, id)):
        return redirect("planner")

    if request.method == "POST":
        if "target" in request.POST:
            for each in targets.filter(pk__in=request.POST.getlist("target")):
                garden.targets.add(each)
            garden.save()
            messages.success(request, "Your target animal species have been saved. Explore our tools below to learn more about how to start and improve your garden!")
            return redirect(reverse("planner", args=[garden.id]))

    context = {
        "menu": "join",
        "page": Page.objects.get(site=site, slug="planner-target-species"),
        "targets": targets,
        "garden": garden,
    }
    return render(request, "planner/target_species.html", context)

def planner_site(request, id):

    site = get_site(request)
    features = Page.objects.filter(site=site, page_type=Page.PageType.FEATURES)

    if not (garden := get_garden(request, id)):
        return redirect("planner")

    if request.method == "POST" and "feature" in request.POST:
        for each in features.filter(pk__in=request.POST.getlist("feature")):
            garden.site_features.add(each)
        garden.save()
        messages.success(
            request, 
            "<i class='fa fa-check mr-2'></i>" + \
            _("Your site features have been saved.")
        )

        if "new_garden" in request.GET:
            return redirect(reverse("planner_target_species", args=[garden.id]) + "?new_garden")
        else:
            return redirect(reverse("planner", args=[garden.id]))

    context = {
        "menu": "join",
        "page": Page.objects.get(site=site, slug="planner-site"),
        "garden": garden,
        "features": features,
    }
    return render(request, "planner/site.html", context)


def shapefile_zip(request, id):
    info = Document.objects.get(pk=id)

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        attachments = Attachment.objects.filter(attached_to=info)
        
        for attachment in attachments:
            file_to_add = attachment.file
            zip_file.writestr(file_to_add.name, file_to_add.read())
    
    # Set the buffer's position to the beginning so it can be read from the start
    zip_buffer.seek(0)
    
    response = HttpResponse(zip_buffer, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{info.name}.zip"'
    
    return response

def set_cookie(request):
    response = redirect(request.GET["redirect"])
    response.set_cookie("site", request.GET["site"])
    return response

def favicon(request):
    site = get_site(request)
    logo = site.logo.thumbnail.path
    with open(logo, "rb") as logo_file:
        return HttpResponse(logo_file.read(), content_type="image/png")

# CONTROL PANEL

@staff_member_required
def controlpanel(request):
    context = {
        "controlpanel": True,
        "menu": "index",
    }
    return render(request, "controlpanel/index.html", context)

@staff_member_required
def controlpanel_pages(request):

    site = get_site(request)
    page_type = int(request.GET["type"])
    pages = Page.objects.filter(site=site, page_type=page_type)

    context = {
        "controlpanel": True,
        "menu": "pages",
        "page_type": page_type,
        "pages": pages,
        "title": Page.PageType(page_type).label,
    }
    return render(request, "controlpanel/pages.html", context)

@staff_member_required
def controlpanel_page(request, id=None):

    menu = "pages"
    info = Page()
    if id:
        info = Page.objects.get(pk=id)
        action = Log.LogAction.UPDATE
        page_type = info.page_type
    else:
        page_type = int(request.GET["type"])

    site = get_site(request)
    action = Log.LogAction.CREATE

    if "delete_photo" in request.GET:
        photo = Photo.objects.get(pk=request.GET["delete_photo"])
        info.photos.remove(photo)
        messages.success(request, "Photo was removed from the page.")
        return redirect(request.path)

    if request.method == "POST":

        if "photo" in request.POST:
            info.photos.add(Photo.objects.get(pk=request.POST["photo"]))
            messages.success(request, "Photo was added to the page.")
            return redirect(request.get_full_path())

        info.name = request.POST["name"]
        info.content = request.POST.get("description")
        info.slug = request.POST.get("slug")
        info.position = 0
        info.page_type = page_type
        info.format = "HTML"
        info.is_active = True if request.POST.get("is_active") == "1" else False
        if "date" in request.POST and request.POST["date"]:
            info.date = request.POST["date"]
        if request.FILES.get("image"):
            info.image = request.FILES.get("image")
        info.site = site

        info.save()
        log_action(request, action, f"Page: {info.name}")
        messages.success(request, _("Information was saved."))
        if request.GET.get("redirect"):
            return redirect(request.GET.get("redirect"))
        else:
            return redirect(reverse("controlpanel_pages") + "?type=" + str(page_type))

    context = {
        "controlpanel": True,
        "menu": menu,
        "info": info,
        "title": Page.PageType(page_type).label,
        "quill": True,
        "page_type": page_type,
    }
    return render(request, "controlpanel/page.html", context)


@staff_member_required
def controlpanel_gardens(request):

    site = get_site(request)
    gardens = Garden.objects.filter(site=site)

    context = {
        "controlpanel": True,
        "menu": "gardens",
        "gardens": gardens,
        "load_datatables": True,
    }
    return render(request, "controlpanel/gardens.html", context)

@staff_member_required
def controlpanel_garden(request, id=None):

    info = Garden()
    if id:
        info = Garden.objects.get(pk=id)
        action = Log.LogAction.UPDATE

    site = get_site(request)
    action = Log.LogAction.CREATE

    if request.method == "POST":
        info.name = request.POST["name"]
        info.contact_name = request.POST.get("contact_name")
        info.contact_email = request.POST.get("contact_email")
        info.contact_phone = request.POST.get("contact_phone")
        info.description = request.POST.get("description")
        info.is_active = True if request.POST.get("is_active") == "1" else False
        info.site = site

        uploaded_file = request.FILES.get("file")
        if uploaded_file:
            info.location_file = uploaded_file

        info.save()
        log_action(request, action, f"Garden: {info.name}")

        messages.success(request, _("Information was saved."))

        if uploaded_file:
            try:
                location_file_path = info.location_file.path
                directory = f"/tmp/kmz_extracted_{info.id}"
                with zipfile.ZipFile(location_file_path, "r") as kmz:
                    kmz.extractall(directory)

                # Find the KML file in the extracted contents
                kml_file_path = None
                for file in os.listdir(directory):
                    if file.endswith(".kml"):
                        kml_file_path = os.path.join(directory, file)
                        break

                # Read the KML file and extract geometry
                if kml_file_path:

                    tree = ET.parse(kml_file_path)
                    root = tree.getroot()

                    # Extract coordinates from KML (assuming simple KML with <coordinates> tag)
                    coordinates = root.findall('.//{http://www.opengis.net/kml/2.2}coordinates')[0].text.strip().split()

                    # Convert to a list of tuples of coordinates
                    coords = [(float(c.split(',')[0]), float(c.split(',')[1])) for c in coordinates]

                    # Create geometry (assuming it's a polygon)
                    polygon = geos.Polygon(coords)

                    # Save the geometry in the model
                    info.geometry = polygon
                    info.save()
                else:
                    messages.warning(request, _("No KML file found. Is this a valid KMZ file?"))

            except Exception as e:

                messages.warning(request, _("We were unable to save the coordinates, please make sure it is a valid KMZ file. Error:") + str(e))

        return redirect(reverse("controlpanel_gardens"))

    context = {
        "controlpanel": True,
        "menu": "gardens",
        "info": info,
        "title": _("Edit garden") + ": " + info.name if info.id else _("Add garden"),
    }
    return render(request, "controlpanel/garden.html", context)

@staff_member_required
def controlpanel_garden_photos(request, id):

    info = Garden.objects.get(pk=id)
    position = Photo.objects.filter(garden=info).aggregate(Max("position"))["position__max"]
    if not position:
        position = 0

    if request.method == "POST":
        for each in request.FILES.getlist("photos"):
            position += 1
            # Try to get the date from the EXIF data
            image_file = each.read()
            image = Image.open(io.BytesIO(image_file))
            exif_data = image._getexif()
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == "DateTimeOriginal":
                        # Convert the EXIF date string to a datetime object
                        try:
                            photo_date = timezone.datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                        except ValueError:
                            photo_date = timezone.now()  # Fallback to today's date if parsing fails
                            messages.warning(request, f"Photo date was not found for {each.name} - using today's date. Please change if needed.")

            else:
                photo_date = timezone.now()
                messages.warning(request, f"Photo date was not found for {each.name} - using today's date. Please change if needed.")

            Photo.objects.create(
                author = request.POST["author"],
                description = request.POST.get("description"),
                image = each,
                date = photo_date,
                position = position,
                garden = info,
                source = "upload",
                license_code = request.POST["license"],
            )

        messages.success(request, _("Photos have been added."))
        return redirect(request.get_full_path())

    context = {
        "controlpanel": True,
        "menu": "gardens",
        "info": info,
        "title": _("Edit photos") + ": " + info.name,
        "licenses": Photo.LICENSE_CHOICES,
    }
    return render(request, "controlpanel/garden.photos.html", context)

@staff_member_required
def controlpanel_garden_photo(request, garden, id):
    site = get_site(request)
    info = Photo.objects.get(pk=id, garden__site=site)

    if "delete" in request.POST:
        url = reverse("controlpanel_garden_photos", args=[info.garden.id])
        log_action(request, Log.LogAction.DELETE, f"Photo #{info.id}")
        info.delete()
        messages.success(request, _("The photo was deleted"))
        return redirect(url)
    elif request.method == "POST":
        info.description = request.POST.get("description")
        info.author = request.POST.get("author")
        info.position = request.POST.get("position")
        info.license_code = request.POST["license"]
        info.save()
        messages.success(request, _("The information was saved."))
        log_action(request, Log.LogAction.UPDATE, f"Photo #{info.id}")

    context = {
        "info": info,
        "licenses": Photo.LICENSE_CHOICES,
        "controlpanel": True,
        "menu": "gardens",
    }
    return render(request, "controlpanel/photo.html", context)

@staff_member_required
def controlpanel_documents(request):

    site = get_site(request)
    documents = Document.objects.filter(site=site, is_shapefile=False)
    if "type" in request.GET and request.GET["type"]:
        documents = documents.filter(doc_type=request.GET["type"])

    context = {
        "controlpanel": True,
        "menu": "documents",
        "documents": documents,
        "title": _("Documents"),
        "doc_types": [
            ("CONTEXT", _("Context")),
            ("TEACHING", _("Teaching resources")),
            ("GENERAL", _("General document repository")),
            ("SPECIES_LIST", _("Species lists")),
        ],
    }
    return render(request, "controlpanel/documents.html", context)

@staff_member_required
def controlpanel_document(request, id=None):

    info = Document()
    if id:
        info = Document.objects.get(pk=id)
        action = Log.LogAction.UPDATE

    site = get_site(request)
    action = Log.LogAction.CREATE

    if request.method == "POST":
        info.name = request.POST["name"]
        info.author = request.POST["author"]
        info.url = request.POST.get("url")
        info.doc_type = request.POST["doc_type"]
        info.description = request.POST.get("description")
        info.is_active = True if request.POST.get("is_active") == "1" else False
        info.is_shapefile = False
        info.site = site
        if request.FILES.get("cover"):
            info.cover_image = request.FILES.get("cover")
        info.save()
        log_action(request, action, f"Document: {info.name}")

        uploaded_files = request.FILES.getlist("file")

        if uploaded_files:
            info.attachments.all().delete()

            for uploaded_file in uploaded_files:
                Attachment.objects.create(file=uploaded_file, attached_to=info)

        messages.success(request, "Information was saved.")
        if info.doc_type == "SPECIES_LIST":
            return redirect(reverse("controlpanel_document", args=[info.id]))
        else:
            return redirect(reverse("controlpanel_documents"))

    context = {
        "controlpanel": True,
        "menu": "documents",
        "info": info,
        "doc_types": Document.DOC_TYPES,
    }
    return render(request, "controlpanel/document.html", context)

@staff_member_required
def controlpanel_document_species(request, id):
    info = Document.objects.get(pk=id)
    file_info = Attachment.objects.get(attached_to=info, pk=request.GET["file"])
    site = get_site(request)

    file = file_info.file
    df = pd.read_excel(file, sheet_name=0)

    if request.method == "POST":
        vegetation_type = VegetationType.objects.get(pk=request.POST["vegetation_type"])
        SpeciesVegetationTypeLink.objects.filter(file=file_info).delete()

        try:
            #for _,row in df.iterrows(): this gave an error so renamed to below; check that this is indeed right
            for unused_var,row in df.iterrows():

                name = row["Name"].strip()

                # Only process if there are at least 2 words
                if len(name.split()) >= 2:

                    genus = Genus.objects.filter(name=name.split()[0])
                    if genus:
                        genus = genus[0]
                    else:
                        genus = Genus.objects.create(name=name.split()[0])

                    species = Species.objects.filter(name=name)
                    if species:
                        species = species[0]
                    else:
                        species = Species.objects.create(
                            name = name,
                            genus = genus,
                        )

                    # We store this link in a table so we can trace it back...
                    SpeciesVegetationTypeLink.objects.create(
                        species = species,
                        vegetation_type = vegetation_type,
                        file = file_info,
                    )

                    # And we mark the actual species as belonging to this vegetation type
                    species.vegetation_types.add(vegetation_type)

                    # And make sure this is activated for the current site
                    species.site.add(site)

            messages.success(request, "The species were linked to the selected vegetation type.")
            return redirect(reverse("controlpanel_specieslist") + "?file=" + request.GET["file"])

        except Exception as e:
            error = _("There was a problem with this file. Are you sure it is formatted correctly? See below the error: ") + str(e)
            messages.error(request, error)

    results = []
    alerts = []
    error = None
    try:
        for index, row in df.iterrows():
            # We take the name row, and we check if each species exists. We then add a column with the result.
            name = row["Name"]
            if name: # Check how to deal with NaN fields of empty rows TODO
                name_words = name.split()

                if len(name_words) < 2:
                    alerts.append(_("Species names must contain genus + species. This row is invalid and will NOT be added."))
                    results.append("✖️")
                else:
                    alerts.append("")
                    exists = Species.objects.filter(name=name.strip()).exists()
                results.append("✓" if exists else "✖️")

        df["Exists"] = results
        df["Details"] = alerts
        df = df.fillna("")
        html_table = df.to_html(classes="table", escape=False)

    except Exception as e:
        error = _("There was a problem with your file. TIP: Make sure the 'Name' column is present.")
        messages.error(request, error)
        error = _("Specific error: ") + str(e)
        messages.error(request, error)

    context = {
        "controlpanel": True,
        "menu": "documents",
        "info": info,
        "file": file,
        "df": mark_safe(html_table) if not error else None,
        "vegetation_types": VegetationType.objects.all(),
    }
    return render(request, "controlpanel/document.species.html", context)

@staff_member_required
def controlpanel_ajax_get_inat_data(request, id):
    info = Species.objects.get(pk=id)
    inat_info = info.get_taxa_info()
    success = False
    error = None
    if inat_info:
        success = True
    else:
        info = Species.objects.get(pk=id)
        error = info.meta_data["inat_error"]

    return JsonResponse({"success": success, "error": error})

@staff_member_required
def controlpanel_ajax_get_wikipedia(request, id):
    info = Species.objects.get(pk=id)
    success = False
    error = None
    description = None
    summary = None
    description = None
    language = Language.objects.get(name="English")

    try:
        url = info.meta_data["inat"]["wikipedia_url"]
        if url:
            title = url.split("/")[-1] #Get the page title from the URL
            wiki_wiki = wikipediaapi.Wikipedia("Urban Corridor Platform (info@fynboscorridors.org)", "en")
            page = wiki_wiki.page(title)

            if page.exists():
                species_text, created = SpeciesText.objects.get_or_create(
                    species=info,
                    language=language
                )
                if page.summary:
                    species_text.summary_wikipedia = page.summary
                success = True
                species_text.description_wikipedia = page.text
                species_text.save()
                description = page.text
                summary = page.summary
            else:
                error = "Page does not exist"
        else:
            error = _("No wikipedia page found in the species profile")
    except Exception as e:
        error = str(e)

    return JsonResponse({"success": success, "error": error, "description": description, "summary": summary})

@staff_member_required
def controlpanel_shapefiles(request):

    site = get_site(request)
    files = Document.objects.filter(is_shapefile=True, site=site)

    context = {
        "controlpanel": True,
        "menu": "shapefiles",
        "shapefiles": files,
        "title": _("Shapefiles"),
    }

    return render(request, "controlpanel/shapefiles.html", context)

@staff_member_required
def controlpanel_shapefile(request, id):
    site = get_site(request)
    info = Document.objects.filter(Q(site=site) | Q(site__isnull=True)).get(pk=id, is_shapefile=True)

    if "create_shapefile_plot" in request.POST:
        plot = info.create_shapefile_plot()
        if plot:
            messages.success(request, "Plot image was created.")
        else:
            messages.error(request, "There was a problem creating the plot.")
        return redirect(request.get_full_path())
    elif "clip" in request.POST:
        clip_boundaries = ReferenceSpace.objects.get(pk=request.POST["clip"])
        info.meta_data["clip"] = request.POST["clip"]
        info.save()

        # First we delete the spaces that are outside the clipped area
        spaces = info.spaces.exclude(Q(geometry__within=clip_boundaries.geometry)|Q(geometry__intersects=clip_boundaries.geometry))
        total_to_delete = int(spaces.count())
        spaces.delete()

        # And then we cut off those that cross boundaries
        intersecting = info.spaces.filter(geometry__intersects=clip_boundaries.geometry)
        for each in intersecting:
            sliced_geometry = each.geometry.intersection(clip_boundaries.geometry)
            each.geometry = sliced_geometry
            each.save()

        messages.success(request, f"Borders were clipped to {clip_boundaries.name}; {total_to_delete} spaces were removed and {intersecting.count()} spaces were clipped.")
        return redirect(request.get_full_path())
    elif "convert_shapefile" in request.POST:
        if info.shpinfo["count"] > 1000:
            # There is a way to limit processing items with 1000 records. However, for now if people
            # see the alert and accept it, we automatically override this limit. Later we can restrict
            # who can automatically do that and who can't
            info.meta_data["skip_size_check"] = True
            info.save()
        return redirect(reverse("controlpanel_shapefile_classify", args=[info.id]))
    elif "load_shapefile_info" in request.POST:
        info.load_shapefile_info()
        messages.success(request, "Shapefile info was loaded.")
        return redirect(request.get_full_path())

    size_in_bytes = 0
    # If we have spaces, let's see what the size of them is...
    if info.spaces.count():
        serialized_data = serializers.serialize("json", info.spaces.all())
        size_in_bytes = sys.getsizeof(serialized_data)

    clip_boundaries = None
    if info.meta_data and info.meta_data.get("clip"):
        try:
            clip_boundaries = ReferenceSpace.objects.get(pk=info.meta_data["clip"])
        except Exception as e:
            messages.warning(request, "We could not clip the shapefile - error: " + str(e))

    context = {
        "controlpanel": True,
        "menu": "shapefiles",
        "info": info,
        "size_in_bytes": size_in_bytes,
        "corridors": ReferenceSpace.objects.filter(source__doc_type="CORRIDOR"),
        "clip_boundaries": clip_boundaries,
        "load_form": True,
    }
    return render(request, "controlpanel/shapefile.html", context)

@staff_member_required
def controlpanel_shapefile_form(request, id=None):
    site = get_site(request)
    info = Document()
    action = Log.LogAction.CREATE

    if id:
        info = Document.objects.filter(Q(site=site) | Q(site__isnull=True)).get(pk=id, is_shapefile=True)
        action = Log.LogAction.UPDATE

    if request.method == "POST":
        info.name = request.POST["name"]
        info.author = request.POST["author"]
        info.url = request.POST.get("url")
        info.color = request.POST.get("color")
        info.doc_type = request.POST["doc_type"]
        info.description = request.POST.get("description")
        info.include_in_site_analysis = True if request.POST.get("include_in_site_analysis") else False
        info.is_active = True if request.POST.get("is_active") == "1" else False
        info.site = site
        if not info.meta_data:
            info.meta_data = {}
        else:
            # Remove any settings that might exist
            info.meta_data.pop("single_reference_space", None)
            info.meta_data.pop("group_spaces_by_name", None)

        info.save()
        log_action(request, action, f"Shapefile: {info.name}")

        uploaded_files = request.FILES.getlist("file")

        if uploaded_files:
            info.attachments.all().delete()

            for uploaded_file in uploaded_files:
                # If it's a zip, we extract all files and save them separately...
                if uploaded_file.name.endswith(".zip"):
                    with zipfile.ZipFile(uploaded_file, "r") as zip_ref:
                        
                        # Extract all the contents into a temporary directory
                        my_uuid = uuid.uuid4()
                        temp_dir = "/tmp/" + f"{info.id}-{my_uuid}/"
                        os.makedirs(temp_dir, exist_ok=True)
                        #zip_ref.extractall(temp_dir)

                        for file in zip_ref.namelist():
                            extracted_filename = os.path.basename(file)
                            zip_ref.extract(file, temp_dir)

                            # We move all files into the main directory
                            if file != extracted_filename:
                                os.rename(os.path.join(temp_dir, file), os.path.join(temp_dir, extracted_filename))

                        # Loop through all extracted files
                        for filename in os.listdir(temp_dir):
                            file_path = os.path.join(temp_dir, filename)
                            if os.path.isfile(file_path):
                                with open(file_path, "rb") as f:
                                    attachment = Attachment()
                                    attachment.attached_to = info
                                    attachment.file.save(filename, File(f), save=True)

                    for filename in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, filename)
                        
                        # Check if it's a file and remove it
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                        # If it's a directory, recursively remove it
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)

                    os.rmdir(temp_dir)

                else:
                    Attachment.objects.create(file=uploaded_file, attached_to=info)

        messages.success(request, "Information was saved.")
        return redirect(reverse("controlpanel_shapefiles"))

    context = {
        "controlpanel": True,
        "menu": "shapefiles",
        "info": info,
        "load_form": True,
        "doc_types": Document.DOC_TYPES,
    }
    return render(request, "controlpanel/shapefile.form.html", context)

@staff_member_required
def controlpanel_shapefile_dataviz(request, id):
    site = get_site(request)
    shapefile = Document.objects.filter(Q(site=site) | Q(site__isnull=True)).get(pk=id, is_shapefile=True)

    info = Dataviz.objects.get_or_create(site=site, shapefile=shapefile)
    info = info[0]
    
    if request.method == "POST":
        info.colors = {
            "option": request.POST.get("colors"),
            "color": request.POST.get("color"),
        }
        if "color_set_feature" in request.POST:
            info.colors["set_feature"] = request.POST["color_set_feature"]
        if "color_features" in request.POST:
            try:
                info.colors["features"] = json.loads(request.POST["color_features"])
            except json.JSONDecodeError:
                messages.warning(request, "JSON object is not valid and was not saved")
        info.mapstyle_id = request.POST.get("mapstyle")
        info.opacity = request.POST.get("opacity")
        info.fill_opacity = request.POST.get("fill_opacity")
        info.line_width = request.POST.get("line_width")

        info.save()

        messages.success(request, "Information was saved.")
        return redirect(request.get_full_path())

    context = {
        "controlpanel": True,
        "menu": "shapefiles",
        "info": info,
        "load_form": True,
        "styles": MapStyle.objects.all(),
    }
    return render(request, "controlpanel/shapefile.dataviz.html", context)

@staff_member_required
def controlpanel_shapefile_classify(request, id):
    site = get_site(request)
    info = Document.objects.filter(Q(site=site) | Q(site__isnull=True)).get(pk=id, is_shapefile=True)
    layer = info.get_gis_layer()

    if request.method == "POST":
        import_columns = []
        if not "columns" in info.meta_data:
            info.meta_data["columns"] = {}

        for field in layer[0].fields:
            setting = request.POST.get(f"action[{field}]")

            if setting == "primary":
                info.meta_data["columns"]["name"] = field
            elif setting == "import":
                import_columns.append(field)

            info.meta_data["columns"]["import"] = import_columns
        info.meta_data["clip"] = request.POST.get("clip")

        info.meta_data.pop("single_reference_space", None)
        info.meta_data.pop("group_spaces_by_name", None)

        if request.POST["processing"] == "single_reference_space":
            info.meta_data["single_reference_space"] = True
        elif request.POST["processing"] == "group_spaces_by_name":
            info.meta_data["group_spaces_by_name"] = True

        info.save()

        info.spaces.all().delete()
        info.convert_shapefile()
        messages.success(request, "Shapefile data was imported into the system")
        return redirect(reverse("controlpanel_shapefile", args=[info.id]))

    context = {
        "controlpanel": True,
        "menu": "shapefiles",
        "info": info,
        "layer": layer,
    }
    return render(request, "controlpanel/shapefile.classify.html", context)

@staff_member_required
def controlpanel_specieslist(request):

    site = get_site(request)
    species = Species.objects.filter(site=site)
    if "file" in request.GET:
        species = species.filter(species_links__file_id=request.GET["file"])
    elif "site" in request.GET:
        site = Site.objects.get(pk=request.GET["site"])
        species = species.filter(site=site)

    if "name" in request.GET:
        name = request.GET["name"].strip()
        species = Species.objects.filter(name__icontains=name)

    context = {
        "controlpanel": True,
        "menu": "species",
        "species": species,
        "title": _("Species list"),
        "load_datatables": True,
    }

    description_subquery = SpeciesText.objects.filter(
        species=OuterRef("pk"),
        language=Language.objects.get(name="English")
    ).values("description_wikipedia")[:1]  # Get the first matching description

    description_subquery_en = SpeciesText.objects.filter(
        species=OuterRef("pk"),
        language=Language.objects.get(name="English")
    ).values("description")[:1]  # Get the first matching description

    if "descriptions" in request.GET:
        context["languages"] = Language.objects.all()
        context["species"] = species.annotate(
            description_wikipedia = Subquery(description_subquery, output_field=CharField()),
            description = Subquery(description_subquery_en, output_field=CharField())
        )
        return render(request, "controlpanel/speciesdescriptions.html", context)
    else:
        return render(request, "controlpanel/specieslist.html", context)

# Used while we migrate from the old system
# Can be removed after completing migrations
def temp_html_fix_text(s):
    import html
    import re
    if not s:
        return s
    s = html.unescape(s)

    # Step 2: Remove <br /> tags using regex
    s = re.sub(r'<br\s*/?>', '', s)
    return s

@staff_member_required
def controlpanel_species(request, id=None):

    if id:
        info = Species.objects.get(pk=id)
    else:
        info = Species()

    languages = Language.objects.all()

    if request.method == "POST":

        if "delete" in request.POST:
            info.delete()
            messages.success(request, "Species was removed from the database")
            return redirect(reverse("controlpanel_specieslist"))

        if id:
            info.features.clear()
            info.vegetation_types.clear()

        info.name = request.POST["name"].strip()
        info.genus_id = request.POST.get("genus")
        info.family_id = request.POST.get("family")
        links = [link.strip() for link in request.POST.getlist("links") if link.strip()]
        info.links = links if links else None

        if not info.genus_id and request.POST.get("new_genus"):
            info.genus = Genus.objects.create(name=request.POST.get("new_genus"))
        elif not info.genus_id:
            name = info.name
            info.genus = Genus.objects.create(name=name.split()[0])

        if not info.family_id and request.POST.get("new_family"):
            info.family = Family.objects.create(name=request.POST.get("new_family"))

        info.save()

        if not id:
            info.get_taxa_info()
            messages.success(request, "Species was added and data retrieved from iNat. Add more info below.")
            return redirect(reverse("controlpanel_species", args=[info.id]))

        else:

            info.features.add(*SpeciesFeatures.objects.filter(id__in=request.POST.getlist("features")))
            info.vegetation_types.add(*VegetationType.objects.filter(id__in=request.POST.getlist("vegetation_types")))

            for language in languages:
                common_name = request.POST.get(f"common_name_{language.id}")
                description = request.POST.get(f"description_{language.id}")
                seed = request.POST.get(f"propagation_seed_{language.id}")
                cutting = request.POST.get(f"propagation_cutting_{language.id}")

                species_text, created = SpeciesText.objects.get_or_create(
                    species=info,
                    language=language
                )

                if common_name or description or seed or cutting:
                    species_text.common_name = common_name
                    species_text.description = description
                    species_text.propagation_seed = seed
                    species_text.propagation_cutting = cutting
                    species_text.save()
                else:
                    species_text.delete()

        messages.success(request, "Information was saved.")

    # Put all the text inside a dictionary so we can retrieve it and fill inputs/textareas
    texts = {}
    if info.id:
        for each in info.texts.all():
            texts[each.language.id] = { 
                "description": each.description, 
                "description_wikipedia": each.description_wikipedia,
                "name": each.common_name, 
                "seed": each.propagation_seed, 
                "cutting": each.propagation_cutting,
                "alternatives": each.alternative_names,
            }

    try:
        inat = json.dumps(info.meta_data["inat"], indent=2)
    except:
        inat = None

    context = {
        "controlpanel": True,
        "menu": "species",
        "genus_list": Genus.objects.all(),
        "family_list": Family.objects.all(),
        "features_list": SpeciesFeatures.objects.all(),
        "vegetation_types_list": VegetationType.objects.all(),
        "info": info,
        "languages": languages,
        "texts": texts,
        "title": info.name if info.name else "Add new species",
        "inat": inat,
    }

    return render(request, "controlpanel/species.html", context)

@staff_member_required
def controlpanel_photos(request):

    site = get_site(request)
    photos = None

    if "id" in request.GET:
        table = request.GET["table"]
        if table == "garden":
            photos = Photo.objects.filter(garden_id=request.GET["id"])
        if table == "species":
            photos = Photo.objects.filter(species_id=request.GET["id"])
        if table == "page":
            info = Page.objects.get(id=request.GET["id"], site=site)
            photos = info.photos.all()

    context = {
        "controlpanel": True,
        "menu": "photos",
        "gardens": Garden.objects.filter(site=site),
        "species": Species.objects.all(),
        "pages": Page.objects.filter(site=site),
        "photos": photos
    }
    return render(request, "controlpanel/photos.html", context)

@staff_member_required
def controlpanel_photo(request, id):

    site = get_site(request)
    info = Photo.objects.get(pk=id)

    context = {
        "controlpanel": True,
        "menu": "photos",
        "info": info,
    }
    return render(request, "controlpanel/photo.html", context)
