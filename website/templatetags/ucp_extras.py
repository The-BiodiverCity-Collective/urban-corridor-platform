from django import template
from django.template.defaulttags import register
import json
from urllib.parse import urlparse

register = template.Library()

@register.filter
def get_item(dictionary, key):
    try:
        if dictionary.get(key):
            return dictionary.get(key)
        elif dictionary.get(str(key)):
            return dictionary.get(str(key))
        else:
            return ""
    except:
        return ""

@register.filter
def json_dumps(string):
    if string:
        return json.dumps(string)

@register.filter
def domain(url):
    try:
        parsed_url = urlparse(url)
        return parsed_url.netloc
    except Exception as e:
        return ""
