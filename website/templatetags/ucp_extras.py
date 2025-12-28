from django import template
from django.template.defaulttags import register
import json
from urllib.parse import urlparse

register = template.Library()

@register.filter
def get_item(dictionary, key):
    try:
        if dictionary.get(key) is not None:
            return dictionary.get(key)
        elif dictionary.get(str(key)) is not None:
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

@register.filter
def multiply(value1, value2):
  return value1*value2

@register.filter
def color_calculator(points):
    if points < 30:
        return "red-600"
    elif points < 60:
        return "orange-600"
    elif points < 80:
        return "yellow-600"
    elif points < 100:
        return "lime-600"
    elif points == 100:
        return "lime-900"


