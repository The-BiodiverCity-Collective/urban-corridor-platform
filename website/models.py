from django.db import models
from django.contrib.gis.db import models
from stdimage.models import StdImageField
from django.utils.text import slugify
from markdown import markdown
from django.utils.safestring import mark_safe
from django.conf import settings
import bleach
from unidecode import unidecode
from django.urls import reverse
import uuid
from django.utils.translation import gettext_lazy as _
import os
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.db.models import Q
import datetime
import requests

from django.utils import timezone

# To create the sample shapefile images
#import geopandas # TEMP DEACTIVATE DURING INSTALL ON SERVER
import contextily as ctx

# For our shapefile work
from django.contrib.gis.gdal import DataSource, OGRGeometry
from django.contrib.gis.gdal.srs import (AxisOrder, CoordTransform, SpatialReference)

# Import user
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
User = get_user_model()

class Language(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=5)

    def __str__(self):
        return self.name

class Site(models.Model):
    name = models.CharField(max_length=255)
    url = models.CharField(max_length=255)
    email = models.EmailField(null=True)
    language = models.ForeignKey(Language, on_delete=models.PROTECT)
    corridor = models.ForeignKey("Document", on_delete=models.PROTECT, null=True, blank=True, limit_choices_to={"doc_type":"CORRIDOR"}, related_name="primary_site")
    logo = StdImageField(upload_to="logos", variations={"thumbnail": (350, 350), "medium": (800, 600)}, null=True, blank=True)
    vegetation_types = models.ManyToManyField("VegetationType", blank=True, related_name="sites")
    meta_data = models.JSONField(null=True, blank=True)
    vegetation_types_map = models.ForeignKey("Document", on_delete=models.PROTECT, null=True, blank=True, related_name="primary_site_vegetation")

    def __str__(self):
        return self.name

    @property
    def lat(self):
        return self.meta_data["lat"]

    @property
    def lng(self):
        return self.meta_data["lng"]

class Page(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    content = models.TextField(null=True, blank=True)
    content_html = models.TextField(null=True, blank=True, help_text="Auto-generated - do NOT edit")
    image = StdImageField(upload_to="pages", variations={"thumbnail": (350, 350), "medium": (800, 600), "large": (1280, 1024)}, null=True, blank=True)
    position = models.PositiveSmallIntegerField(db_index=True)
    slug = models.SlugField(max_length=255)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, related_name="pages")
    is_active = models.BooleanField(default=True, db_index=True)
    date = models.DateField(null=True, blank=True)

    class PageType(models.IntegerChoices):
        REGULAR = 1, "Regular page"
        BLOG = 2, "Blog"
        EVENT = 3, "Event"
        TARGET = 4, "Target species"
        FEATURES = 5, "Site features"
    page_type = models.IntegerField(choices=PageType.choices, db_index=True, default=1)

    photos = models.ManyToManyField("Photo", blank=True)

    # This is relevant for the pages that are Target Species, which 
    # can be linked to multiple specific SpeciesFeatures (e.g. "Insect Supporting Gardens" can 
    # link to Butterflies, Bees, etc)
    features = models.ManyToManyField("SpeciesFeatures", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    FORMATS = (
        ("HTML", "HTML"),
        ("MARK", "Markdown"),
        ("MARK_HTML", "Markdown and HTML"),
    )
    format = models.CharField(max_length=9, choices=FORMATS)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        if self.page_type == 2:
            return "/blog/" + self.slug
        else:
            return "/about/" + self.slug

    def photo(self):
        if self.photos:
            return self.photos.all()[0]
        else:
            return None

    def get_content(self):
        # The content field is already sanitized, according to the settings (see the save() function below)
        # So when we retrieve the html content we can trust this is safe, and will mark it as such
        # We avoid using |safe in templates -- to centralize the effort to sanitize input
        if self.content:
            return mark_safe(self.content_html)
        else:
            return ""

    class Meta:
        ordering = ["position"]

    def save(self, *args, **kwargs):
        if not self.content:
            self.content_html = None
        elif self.format == "HTML":
            # Here it wouldn't hurt to apply bleach and take out unnecessary tags
            self.content_html = self.content
        elif self.format == "MARK_HTML":
            # Here it wouldn't hurt to apply bleach and take out unnecessary tags
            self.content_html = markdown(self.content)
        elif self.format == "MARK":
            self.content_html = markdown(bleach.clean(self.content))
        if not self.slug:
            self.slug = slugify(unidecode(self.name))
        super().save(*args, **kwargs)

class Organization(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(null=True, blank=True)
    logo = StdImageField(upload_to="pages", variations={"thumbnail": (350, 350), "medium": (800, 600), "large": (1280, 1024)}, delete_orphans=True)
    url = models.CharField(max_length=255, null=True, blank=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="organizations")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]

class Document(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    DOC_TYPES = [
        ("STEPPING_STONES", _("Existing stepping-stones")),
        ("CONNECTORS", _("Corridor connectors")),
        ("TRANSPORT", _("Transport")),
        ("POTENTIAL", _("Possible stepping-stones")),
        ("CONTEXT", _("Context")),
        ("TEACHING", _("Teaching resources")),
        ("GENERAL", _("General document repository")),
        ("CORRIDOR", _("Ecological corridor")),
        ("SPECIES_LIST", _("Species lists")),
    ]
    doc_type = models.CharField(choices=DOC_TYPES, db_index=True, max_length=20, default="GENERAL")
    author = models.CharField(max_length=255, null=True, blank=True)
    url = models.URLField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    color = models.CharField(max_length=50, null=True, blank=True, help_text="See https://htmlcolors.com/color-names for an overview of possible color names")
    meta_data = models.JSONField(null=True, blank=True, help_text="Only to be edited if you know what this does - otherwise, please do not change")
    is_active = models.BooleanField(default=True, db_index=True)
    is_shapefile = models.BooleanField(default=True, db_index=True)
    include_in_site_analysis = models.BooleanField(default=False, db_index=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, related_name="documents")
    cover_image = StdImageField(upload_to="covers", variations={"thumbnail": (300, 300), "medium": (700, 700)}, delete_orphans=True, null=True)

    temp_file = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name

    def get_file_size(self):    
        if self.file:
            return self.file.size/1024/1024
        else:
            return None

    @property
    def get_absolute_url(self):
        return "/maps/" + str(self.id)

    # Returns the opacity used for the background color in maps
    # Some layers, such as the boundary layer, should be fully 
    # transparent so we only see a border.
    @property
    def get_opacity(self):
        try:
            return self.meta_data["opacity"]
        except:
            return 0.4 # Default background color opacity in the maps

    # Shortcut to make it easier to access the properties
    @property
    def shpinfo(self):
        try:
            return self.meta_data["shapefile_info"]
        except:
            return None

    def get_gis_layer(self):
        # Here we try to get the .shp file and load it as a gdal layer
        try:
            file = self.attachments.filter(file__iendswith=".shp")
            file = file[0]
            filename = settings.MEDIA_ROOT + "/" + file.file.name
            datasource = DataSource(filename)
            return datasource[0]
        except Exception as e:
            print(str(e))
            return None

    def load_shapefile_info(self):
        layer = self.get_gis_layer()
        fields = layer.fields
        total_count = layer.num_feat
        shapefile_type = layer.geom_type.name

        if not self.meta_data:
            self.meta_data = {}

        self.meta_data["shapefile_info"] = {
            "fields": fields,
            "count": total_count,
            "type": shapefile_type,
        }

        self.save()
        return True

    def convert_shapefile(self):
        layer = self.get_gis_layer()
        fields = layer.fields
        total_count = layer.num_feat
        shapefile_type = layer.geom_type.name
        error = None

        if total_count > 1000 and not self.meta_data.get("skip_size_check"):
            error = "This file has too many objects. It needs to be verified by an administrator in order to be fully loaded into the system."
        elif "single_reference_space" in self.meta_data:
            # EXAMPLE: a shapefile containing all the water reticulation (piping) in the city
            # This is one single space, so we do not loop but instead create a single item
            # To do that, we get all the geos with get_geoms
            # (https://docs.djangoproject.com/en/3.1/ref/contrib/gis/gdal/#django.contrib.gis.gdal.Layer.get_geoms)
            # and then we loop over THOSE, and combine them, using the union function
            # (https://docs.djangoproject.com/en/3.1/ref/contrib/gis/geos/#django.contrib.gis.geos.GEOSGeometry.union)
            polygon = None
            ct = None
            if layer.srs.srid != 4326:
                # If this isn't WGS 84 then we need to convert the crs to this one
                try:
                    ct = CoordTransform(layer.srs, SpatialReference("WGS84"))
                except Exception as e:
                    error = "The following error occurred when trying to change the coordinate reference system: " + str(e)

            if not error:
                try:
                    for each in layer.get_geoms(True):
                        try:
                            if ct:
                                each.transform(ct)
                        except Exception as e:
                            error = "The following error occurred when trying to fetch the shapefile info: " + str(e)

                        if not polygon:
                            polygon = each
                        else:
                            try:
                                polygon = polygon.union(each)
                            except Exception as e:
                                error = "The following error occurred when trying to merge geometries: " + str(e)
                except Exception as e:
                    error = "The following error occurred when trying to get all the geometries: " + str(e)

            if not error:

                if shapefile_type == "Point25D" or shapefile_type == "LineString25D" or shapefile_type == "Polygon25D":
                    # This type has a "Z" geometry which needs to be changed to a 2-dimensional geometry
                    # See also https://stackoverflow.com/questions/35851577/strip-z-dimension-on-geodjango-force-2d-geometry
                    get_clone = polygon.clone()
                    polygon.coord_dim = 2
                    polygon = get_clone

                if polygon.hasz:
                    # Oddly enough the code above does not always work. Not yet sure why. I have had lines that were combined,
                    # into a multilinestring, and it seems like it is not possible (for Django?) to remove 3D from this
                    # kind of object. So we simply do another check to see if it 'has z'. BTW we can likely use hasz
                    # instead of shapefile_type == point25d etc but I only now learned about it. Something for later.
                    # https://docs.djangoproject.com/en/3.1/ref/contrib/gis/geos/#django.contrib.gis.geos.GEOSGeometry.hasz
                    error = "This shapefile includes data in 3D. We only store shapefiles with 2D data. Please remove the elevation data (Z coordinates). This can be done, for instance, using QGIS: https://docs.qgis.org/testing/en/docs/user_manual/processing_algs/qgis/vectorgeometry.html#drop-m-z-values"
                else:
                    space = ReferenceSpace.objects.create(
                        name = self.name,
                        geometry = polygon,
                        source = self,
                    )
        elif "group_spaces_by_name" in self.meta_data:
            # EXAMPLE: a shapefile containing land use data, in which there are many polygons indicating
            # a few different types (e.g. BUILT ENVIRONMENT, LAKES, AGRICULTURE). These should be saved
            # as individual reference spaces (so we can differentiate them), grouped by their name
            spaces = {}
            for each in layer:

                try:
                    if shapefile_type == "Point25D" or shapefile_type == "LineString25D" or shapefile_type == "Polygon25D":
                        # This type has a "Z" geometry which needs to be changed to a 2-dimensional geometry
                        # See also https://stackoverflow.com/questions/35851577/strip-z-dimension-on-geodjango-force-2d-geometry
                        get_clone = each.geom.clone()
                        get_clone.coord_dim = 2
                        geo = get_clone
                    else:
                        geo = each.geom
                except Exception as e:
                    error = "The following error occurred when trying to prepare the shapefile element: " + str(e)

                # We use WGS 84 (4326) as coordinate reference system, so we gotta convert to that
                # if it uses something else
                if layer.srs.srid != 4326:
                    try:
                        ct = CoordTransform(layer.srs, SpatialReference("WGS84"))
                        geo.transform(ct)
                    except Exception as e:
                        error = "The following error occurred when trying to change the coordinate reference system: " + str(e)

                name = each.get(self.meta_data["columns"]["name"])
                if not name:
                    name = _("Unnamed")

                # So what we do here is to check if this particular field (based on the name) already exists
                # If not, we create a new space in our dictionary with the geometry of this one.
                if name not in spaces:
                    spaces[name] = geo
                else:
                    # However, if it already exists then we use the union function to merge the geometry of this space
                    # with the existing info
                    try:
                        s = spaces[name]
                        spaces[name] = s.union(geo)
                    except Exception as e:
                        error = "The following error occurred when trying to merge geometries: " + str(e)

            if not error:
                for name,geo in spaces.items():
                    ReferenceSpace.objects.create(
                        name = name,
                        geometry = geo.wkt,
                        source = self,
                    )
        else:
            count = 0
            for each in layer:
                count += 1
                meta_data = {}

                # We'll get all the properties and we store this in the meta data of the new object
                for f in fields:
                    # We can't save datetime objects in json, so if it's a datetime then we convert to string
                    if f in self.meta_data["columns"]["import"]:
                        meta_data[f] = str(each.get(f)) if isinstance(each.get(f), datetime.date) else each.get(f)

                name = each.get(self.meta_data["columns"]["name"])

                try:
                    if shapefile_type == "Point25D" or shapefile_type == "LineString25D" or shapefile_type == "Polygon25D":
                        # This type has a "Z" geometry which needs to be changed to a 2-dimensional geometry
                        # See also https://stackoverflow.com/questions/35851577/strip-z-dimension-on-geodjango-force-2d-geometry
                        get_clone = each.geom.clone()
                        get_clone.coord_dim = 2
                        geo = get_clone
                    else:
                        geo = each.geom
                except Exception as e:
                    error = "The following error occurred when trying to obtain the shapefile geometry: " + str(e)

                # We use WGS 84 (4326) as coordinate reference system, so we gotta convert to that
                # if it uses something else
                if layer.srs.srid != 4326:
                    try:
                        ct = CoordTransform(layer.srs, SpatialReference("WGS84"))
                        geo.transform(ct)
                    except Exception as e:
                        error = "The following error occurred when trying to convert the coordinate reference system to WGS84: " + str(e)

                if not error:
                    geo = geo.wkt
                    space = ReferenceSpace.objects.create(
                        name = name,
                        geometry = geo,
                        source = self,
                        meta_data = {"features": meta_data},
                    )

        self.meta_data["processing_date"] = str(timezone.now())
        if error:
            self.meta_data["processing_error"] = error
        else:
            self.meta_data["processed"] = True
            self.meta_data.pop("processing_error", None)

        self.save()

        return True

    def create_shapefile_plot(self):
        success = False
        if not self.meta_data:
            self.meta_data = {}
        try:
            files = self.attachments.filter(Q(file__iendswith=".shp")|Q(file__iendswith=".shx")|Q(file__iendswith=".dbf")|Q(file__iendswith=".prj"))
            if files.count() < 4:
                self.meta_data["shapefile_plot_error"] = "No shapefile found! Make sure all required files are uploaded (.shp, .shx, .dbf, .prj)."
            elif files.count() > 4:
                self.meta_data["shapefile_plot_error"] = "Too many files found! Make sure one file is uploaded for all four required types (.shp, .shx, .dbf, .prj)."
            else:
                file = files.filter(file__iendswith=".shp")
                if not file:
                    self.meta_data["shapefile_plot_error"] = "No shapefile (.shp) found!"
                else:
                    file = file[0]
                    filename = settings.MEDIA_ROOT + "/" + file.file.name
                    df = geopandas.read_file(filename)
                    df = df.to_crs(epsg=3857)
                    ax = df.plot(alpha=0.5, edgecolor="k")
                    ctx.add_basemap(ax)
                    fig = ax.get_figure()
                    output = f"plots/{self.id}.png" 
                    fig.savefig(settings.MEDIA_ROOT + "/" + output)
                    self.meta_data["shapefile_plot"] = output
                    self.meta_data.pop("shapefile_plot_error", None)
                    success = True
            self.save()
        except Exception as e:
            self.meta_data["shapefile_plot_error"] = str(e)
            self.save()
        return True if success else False

class Attachment(models.Model):
    file = models.FileField(upload_to="files")
    attached_to = models.ForeignKey("Document", on_delete=models.CASCADE, related_name="attachments")

    def __str__(self):
        return os.path.basename(self.file.name)

    def extension(self):
        filename = self.file.name
        return filename.split(".")[-1]

    def get_icon(self):
        filename = self.file.name
        if filename.endswith(".dbf"):
            icon = "file-excel"
        elif filename.endswith(".shp"):
            icon = "layer-group"
        elif filename.endswith(".prj"):
            icon = "globe"
        elif filename.endswith("."):
            icon = "database"
        else:
            icon = "file"
        return icon

@receiver(post_delete, sender=Attachment)
def delete_file_on_model_delete(sender, instance, **kwargs):
    if os.path.isfile(instance.file.path):
        os.remove(instance.file.path)

class ReferenceSpace(models.Model):
    name = models.CharField(max_length=255, db_index=True, null=True)
    description = models.TextField(null=True, blank=True)
    geometry = models.GeometryField(null=True, blank=True)
    source = models.ForeignKey(Document, on_delete=models.CASCADE, null=True, blank=True, related_name="spaces")
    meta_data = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name if self.name else str(_("Unnamed object"))

    @property
    def get_absolute_url(self):
        if hasattr(self, "garden"):
            return f"/gardens/{self.id}/"
        else:
            return f"/space/{self.id}/"

    @property
    def get_lat(self):
        try:
            return self.geometry.centroid[1]
        except:
            return None

    @property
    def photo(self):
        if self.photos.all():
            return self.photos.all()[0]
        else:
            return None

    @property
    def thumbnail(self):
        if self.photos.all():
            return self.photos.all()[0].thumbnail
        else:
            return settings.MEDIA_URL + "placeholder.png"

    @property
    def get_lng(self):
        try:
            return self.geometry.centroid[0]
        except:
            return None

    def get_vegetation_type(self):
        v = VegetationType.objects.filter(spaces=self)
        return v[0] if v else None

    @property
    def suburb(self):
        if not self.geometry:
            return None
        suburb = ReferenceSpace.objects.filter(source_id=334434, geometry__intersects=self.geometry)
        if suburb:
            return suburb[0].name.title()
        else:
            return None
    
    def get_popup(self):
        content = f"<h4>{self.name}</h4>"
        if self.photo:
            content = content + f"<a class='d-block' href='{self.get_absolute_url}'><img alt='{self.name}' src='{self.photo.image.thumbnail.url}' /></a><hr>"
        content = content + f"<a href='{self.get_absolute_url}'>View details</a>"
        return mark_safe(content)

    class Meta:
        ordering = ["name"]

class ActiveRecordManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)

class Garden(ReferenceSpace):
    is_active = models.BooleanField(default=True, db_index=True)
    is_user_created = models.BooleanField(default=False, db_index=True)
    original = models.JSONField(null=True, blank=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE)

    contact_name = models.CharField(max_length=255, null=True)
    contact_phone = models.CharField(max_length=255, null=True)
    contact_email = models.CharField(max_length=255, null=True)

    class PhaseStatus(models.IntegerChoices):
        PENDING = 1, _("Pending")
        IN_PROGRESS = 2, _("In progress")
        COMPLETED = 3, _("Completed")

    phase_assessment = models.IntegerField(_("Initial ecological and social assessment"), choices=PhaseStatus.choices, db_index=True, null=True)
    phase_alienremoval = models.IntegerField(_("Alien removal"), choices=PhaseStatus.choices, db_index=True, null=True)
    phase_landscaping = models.IntegerField(_("Landscaping"), choices=PhaseStatus.choices, db_index=True, null=True)
    phase_pioneers = models.IntegerField(_("Planting of pioneer species"), choices=PhaseStatus.choices, db_index=True, null=True)
    phase_birdsinsects = models.IntegerField(_("Planting of bird and insect species"), choices=PhaseStatus.choices, db_index=True, null=True)
    phase_specialists = models.IntegerField(_("Planting of specialist species"), choices=PhaseStatus.choices, db_index=True, null=True)
    phase_placemaking = models.IntegerField(_("Placemaking"), choices=PhaseStatus.choices, db_index=True, null=True)

    organizations = models.ManyToManyField(Organization, blank=True)
    vegetation_type = models.ForeignKey("VegetationType", on_delete=models.CASCADE, null=True, blank=True, related_name="gardens")
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, null=True, blank=True)
    location_file = models.FileField(upload_to="gardenlocations", null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="gardens")
    targets = models.ManyToManyField("Page", blank=True, related_name="garden_targets")
    site_features = models.ManyToManyField("Page", blank=True, related_name="garden_site_features")

    objects = ActiveRecordManager()
    objects_unfiltered = models.Manager()

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        vegetation = Document.objects.get(pk=983172)
        veg = None
        if self.geometry:
            try:
                veg = vegetation.spaces.get(geometry__intersects=self.geometry.centroid)
                veg = veg.get_vegetation_type()
            except:
                veg = None
            self.vegetation_type = veg
        super().save(*args, **kwargs)

class Event(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    content = models.TextField(null=True, blank=True)
    photo = models.ForeignKey("Photo", on_delete=models.CASCADE, null=True, blank=True, related_name="events")
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

class Genus(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Genera"

    def get_absolute_url(self):
        return reverse("genus", args=[self.id])

class Family(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]

    def get_absolute_url(self):
        return reverse("family", args=[self.id])

class Redlist(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=2)
    css = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def get_code(self):
        return mark_safe(f"<span class='badge bg-{self.css}'>{self.code}</span>")

    @property
    def formatted(self):
        return mark_safe(f"{self.get_code} {self.name}")

    class Meta:
        verbose_name_plural = "Redlist"

class VegetationType(models.Model):
    name = models.CharField(max_length=255, db_index=True)
    description = models.TextField(null=True, blank=True)
    redlist = models.ForeignKey(Redlist, on_delete=models.SET_NULL, null=True)
    slug = models.SlugField(max_length=255)
    spaces = models.ManyToManyField(ReferenceSpace, blank=True, limit_choices_to={"source_id": 983172})
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    meta_data = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("vegetation_type", args=[self.slug])

    class Meta:
        ordering = ["name"]

class SpeciesFeatures(models.Model):
    name = models.CharField(max_length=255, db_index=True)

    class SpeciesType(models.IntegerChoices):
        HABITAT = 5, "Habitats & soils"
        ANIMALS = 1, "Animal-friendly"
        SITE = 2, "Tolerances & suitability"
        GROWTH = 3, "Growth features"
        OTHER = 4, "Social features"
        ASPECT = 6, "Aspect"

    species_type = models.IntegerField(choices=SpeciesType.choices, db_index=True, default=0)
    site = models.ManyToManyField(Site, blank=True)
    icon = models.CharField(max_length=50, null=True, blank=True, help_text="Enter all the classes we need to add to the <i> tag")
    icon_svg = models.TextField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["species_type", "name"]

    @property
    def get_icon(self):
        colors = {
            1: "gray-800",
            2: "sky-700",
            3: "gray-800",
            4: "pink-700",
            5: "pink-700",
            6: "pink-700",
        }
        color = colors[self.species_type]
        color = ""
        if self.icon:
            return mark_safe(f'<i class="{self.icon} text-{color}" title="{self.name}"></i><span class="sr-only">{self.name}</span>')
        elif self.icon_svg:
            return mark_safe(self.icon_svg)
        else:
            return self.name

class Species(models.Model):
    name = models.CharField(max_length=255, unique=True, db_index=True)
    redlist = models.ForeignKey(Redlist, on_delete=models.CASCADE, null=True, blank=True)
    links = models.JSONField(null=True, blank=True)
    site = models.ManyToManyField(Site, blank=True)

    animals = models.JSONField(null=True, blank=True)
    soils = models.JSONField(null=True, blank=True)
    properties = models.JSONField(null=True, blank=True)

    genus = models.ForeignKey(Genus, on_delete=models.CASCADE, related_name="species")
    family = models.ForeignKey(Family, on_delete=models.CASCADE, null=True, blank=True, related_name="species")
    features = models.ManyToManyField(SpeciesFeatures, blank=True, related_name="species")
    vegetation_types = models.ManyToManyField(VegetationType, blank=True, related_name="species")
    photo = models.ForeignKey("Photo", on_delete=models.SET_NULL, null=True, blank=True, related_name="main_species")
    meta_data = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Species"

    @property
    def get_absolute_url(self):
        return reverse("species", args=[self.id])

    @property
    def get_photo_medium(self):
        if self.photo:
            return self.photo.image.medium.url
        else:
            return settings.MEDIA_URL + "placeholder.png"

    @property
    def thumbnail(self):
        if self.photo:
            return self.photo.thumbnail
        else:
            return settings.MEDIA_URL + "placeholder.png"

    @property
    def old(self):
        return self.meta_data.get("original")

    def get_links(self):
        return self.links
        links = {}
        original = self.meta_data.get("original")
        if original.get("link"):
            link = original.get("link")
            if "wikipedia" in link:
                links["Wikipedia"] = link
            elif "pza" in link:
                links["PlantZA"] = link
            elif "redlist" in link:
                links["Redlist"] = link
            else:
                links[link] = link

        if original.get("link_plantza"):
            links["PlantZA"] = original.get("link_plantza")

        if original.get("link_wikipedia"):
            links["Wikipedia"] = original.get("link_wikipedia")

        if original.get("link_extra"):
            links["More information"] = original.get("link_extra")

        if original.get("link_redlist"):
            links["Redlist"] = original.get("link_redlist")

        return links

    @property
    def name_en(self):
        try:
            return self.texts.get(language_id=1).common_name
        except:
            return None

    @property
    def inat_id(self):
        try:
            return self.meta_data["inat"]["id"]
        except:
            return None

    def get_taxa_info(self):

        error = None
        taxon_id = self.inat_id

        # If we don't have any info yet, then we need to look up the info by using the name
        if not taxon_id:

            inat_base_url = "https://api.inaturalist.org/v1/taxa"

            if not self.meta_data:
                self.meta_data = {}

            try:
                response = requests.get(inat_base_url, params={"q": self.name, "limit": 1})
                if response.status_code == 200:
                    data = response.json()
                    if "results" in data and data["results"]:
                        species_info = data["results"][0]
                        self.meta_data["inat"] = species_info
                        self.meta_data.pop("inat_error", None)
                        taxon_id = species_info["id"]

                        if not self.links:
                            self.links = [f"https://www.inaturalist.org/taxa/{taxon_id}"]
                        elif not any("inaturalist" in link for link in self.links):
                            self.links.append(f"https://www.inaturalist.org/taxa/{taxon_id}")
                        if not any("wikipedia.org" in link for link in self.links) and species_info["wikipedia_url"]:
                            self.links.append(species_info["wikipedia_url"])

                        self.save()
                    else:
                        error = "No information was returned"
                else:
                    error = f"Error: {response.status_code}"
            except Exception as e:
                error = f"An error occurred: {e}"

        # Once we have the taxon id, we can fetch the full info from iNat
        if taxon_id:
            base_url = f"https://api.inaturalist.org/v1/taxa/{taxon_id}"

            try:
                response = requests.get(base_url)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "results" in data and data["results"]:
                        info = data["results"][0]
                        self.meta_data["inat"] = info

                        # If no family is set, let's get if from iNat
                        if not self.family_id:
                            family = None
                            for each in info["ancestors"]:
                                if each["rank"] == "family":
                                    family = each["name"]
                            if family:
                                family, created = Family.objects.get_or_create(name=family)
                                self.family = family

                        # If there is no common name in EN, we save it
                        if "preferred_common_name" in info and info["preferred_common_name"] and not self.name_en:
                            species_text, created = SpeciesText.objects.get_or_create(species=self, language_id=1)
                            species_text.common_name = info["preferred_common_name"]
                            species_text.save()
                            
                        self.save()
                        self.load_inat_photos()
                        return True

                    else:
                        error = "No information was returned"
                else:
                    error = f"Error: {response.status_code}"
            except Exception as e:
                error = f"An error occurred: {e}"

        if error:
            self.meta_data["inat_error"] = error
            self.save()
            return False

    def load_inat_photos(self):

        # Remove existing photo if it's one of the pics we'll delete
        # For some reason we otherwise get an error further below
        if self.photo and self.photo.source == "inaturalist":
            self.photo = None
            self.save()

        Photo.objects.filter(species=self, source="inaturalist").delete()

        latest_position = Photo.objects.filter(species=self).order_by("-position")
        pos = 0
        if latest_position:
            pos = latest_position[0].position

        if self.inat_photos:
            for photo_detail in self.inat_photos:
                photo = photo_detail["photo"]

                if photo["license_code"]:
                    pos += 1

                    new_photo = Photo.objects.create(
                        author = photo["attribution"],
                        image_inat = photo,
                        license_code = photo["license_code"],
                        species = self,
                        position = pos,
                        source = "inaturalist",
                    )

                    if not self.photo_id:
                        self.photo = new_photo

            self.meta_data["pics_imported"] = True
            self.save()

    @property
    def inat_photos(self):
        try:
            return self.meta_data["inat"]["taxon_photos"]
        except:
            return None

    @property
    def get_sanbi_conservation_status(self):
        try:
            for each in self.meta_data["inat"]["conservation_statuses"]:
                if "SANBI" in each["authority"]:
                    return each["status"]
        except:
            return None

    @property
    def get_conservation_status(self):
        try:
            return self.meta_data["inat"]["conservation_status"]["status"]
        except:
            return None

class SpeciesText(models.Model):
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name="texts")
    language = models.ForeignKey(Language, on_delete=models.CASCADE)
    common_name = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    summary_wikipedia = models.TextField(null=True, blank=True)
    description_wikipedia = models.TextField(null=True, blank=True)
    alternative_names = models.CharField(max_length=255, null=True, blank=True)
    propagation_seed = models.TextField(null=True, blank=True)
    propagation_cutting = models.TextField(null=True, blank=True)

class SpeciesVegetationTypeLink(models.Model):
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name="species_links")
    vegetation_type = models.ForeignKey(VegetationType, on_delete=models.CASCADE)
    file = models.ForeignKey(Attachment, on_delete=models.CASCADE, related_name="species")

class Photo(models.Model):
    description = models.TextField(null=True, blank=True)
    image = StdImageField(upload_to="photos", variations={"thumbnail": (350, 350), "medium": (800, 600), "large": (1280, 1024)}, delete_orphans=True, null=True, blank=True)
    image_inat = models.JSONField(null=True, blank=True) #Dictionary with large_/small_/medium_/original_/square_url values
    position = models.PositiveSmallIntegerField(db_index=True, default=1)
    date = models.DateField(null=True)
    upload_date = models.DateTimeField(auto_now_add=True)
    author = models.CharField(max_length=255, db_index=True, null=True, blank=True)
    garden = models.ForeignKey(Garden, on_delete=models.CASCADE, null=True, blank=True, related_name="photos")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, null=True, blank=True, related_name="photos")
    species = models.ForeignKey(Species, on_delete=models.CASCADE, null=True, blank=True, related_name="photos")

    LICENSE_CHOICES = [
        ("cc0", _("Creative Commons Zero (CC0)")),
        ("cc-by", _("Creative Commons Attribution (CC BY)")),
        ("cc-by-sa", _("Creative Commons Attribution-ShareAlike (CC BY-SA)")),
        ("cc-by-nc", _("Creative Commons Attribution-NonCommercial (CC BY-NC)")),
        ("cc-by-nc-sa", _("Creative Commons Attribution-NonCommercial-ShareAlike (CC BY-NC-SA)")),
        ("cc-by-nc-nd", _("Creative Commons Attribution-NonCommercial-NoDerivs (CC BY-NC-ND)")),
        ("cc-by-nd", _("Creative Commons Attribution-NoDerivs (CC BY-ND)")),
        ("all-rights-reserved", _("All Rights Reserved")),
    ]
    license_code = models.CharField(max_length=20, choices=LICENSE_CHOICES, null=True, blank=True)

    SOURCE_CHOICES = [
        ("upload", "Uploaded photo"),
        ("inaturalist", "iNaturalist"),
    ]
    source = models.CharField(max_length=11, choices=SOURCE_CHOICES)

    def __str__(self):
        return f"Photo {self.id}"

    @property
    def credit(self):
        return self.author

    @property
    def thumbnail(self):
        if self.source == "inaturalist":
            return self.image_inat["small_url"]
        else:
            return self.image.thumbnail.url

    @property
    def medium(self):
        if self.source == "inaturalist":
            return self.image_inat["medium_url"]
        else:
            return self.image.medium.url

    @property
    def large(self):
        if self.source == "inaturalist":
            return self.image_inat["large_url"]
        else:
            return self.image.large.url

    class Meta:
        ordering = ["position", "date"]

class Corridor(models.Model):
    name = models.CharField(max_length=255)
    general_description = models.TextField(null=True, blank=True)
    social_description = models.TextField(null=True, blank=True)
    image = StdImageField(upload_to="corridors", variations={"thumbnail": (350, 350), "medium": (800, 600), "large": (1280, 1024)}, delete_orphans=True)
    wards = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]

    @property
    def get_absolute_url(self):
        return f"/corridors/rivers/{self.id}/"

    def get_image_size(self):
        return self.image.size/1024

class Newsletter(models.Model):
    email = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

    class Meta:
        ordering = ["email"]

class GardenSpecies(models.Model):
    garden = models.ForeignKey(Garden, on_delete=models.CASCADE, related_name="plants")
    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name="garden_plants")
    created_at = models.DateTimeField(auto_now_add=True)
    STATUS_OPTIONS = [
        ("PRESENT", _("Currently present")),
        ("FUTURE", _("Future wish-list")),
    ]
    status = models.CharField(choices=STATUS_OPTIONS, db_index=True, max_length=10)

    class Meta:
        unique_together = ["garden", "species"]

class GardenManager(models.Model):
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255)
    garden = models.ForeignKey(Garden, on_delete=models.CASCADE, related_name="managers")
    creation_date = models.DateTimeField(auto_now_add=True)
    token = models.CharField(max_length=255, null=True, blank=True)
    token_expiration_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} manages {self.garden}"

    class Meta:
        ordering = ["garden", "name"]

class Log(models.Model):

    class LogAction(models.IntegerChoices):
        CREATE = 1, _("Create")
        UPDATE = 2, _("Update")
        DELETE = 3, _("Delete")

    action = models.IntegerField(choices=LogAction.choices, db_index=True, default=1)
    name = models.CharField(max_length=500)
    url = models.CharField(max_length=1500, null=True, blank=True)
    details = models.TextField(null=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="logs")
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date"]

    def delete(self, *args, **kwargs):
        # We should never delete log objects, so overriding this here
        return False

class MapStyle(models.Model):
    name = models.CharField(max_length=100)
    tilelayer = models.CharField(max_length=1500)
    attribution = models.CharField(max_length=1500)
    style = models.CharField(max_length=500)
    image = models.ImageField(upload_to="mapstyle")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]

    @property
    def get_tilelayer(self):
        s = self.tilelayer
        return s.replace("__MAPBOX_API_KEY__", settings.MAPBOX_API_KEY)

class Dataviz(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    shapefile = models.ForeignKey(Document, on_delete=models.CASCADE)
    mapstyle = models.ForeignKey(MapStyle, on_delete=models.CASCADE, null=True)
    colors = models.JSONField(null=True)
    opacity = models.PositiveSmallIntegerField(null=True)
    fill_opacity = models.PositiveSmallIntegerField(null=True)
    line_width = models.PositiveSmallIntegerField(null=True)

    def __str__(self):
        return f"Dataviz for {self.shapefile.name}"

class FileLog(models.Model):
    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    file = models.ForeignKey(Attachment, on_delete=models.CASCADE)
    features = models.ManyToManyField(SpeciesFeatures, blank=True, related_name="log")
    created_at = models.DateTimeField(auto_now_add=True)
    meta_data = models.JSONField(null=True, blank=True)
