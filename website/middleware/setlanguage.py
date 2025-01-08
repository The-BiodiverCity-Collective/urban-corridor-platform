from django.utils import translation

def locale_middleware(get_response):

    def middleware(request):
        host = request.META.get("HTTP_HOST")
        host = host.lower()
        sites = {
            # Development environment
            "0.0.0.0:7777": "en_ZA",

            # Official sites
            "fynboscorridors.org": "en_ZA",

        }
        if host in sites:
           language_code = sites[host]
        else:
           language_code = "en_ZA"

        translation.activate(language_code)
        request.language = language_code
        return get_response(request)

    return middleware
