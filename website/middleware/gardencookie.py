class GardenCookieMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if getattr(request, "_set_garden_cookie", False):
            response.set_cookie("garden_uuid", getattr(request, "_garden_uuid"))
            response.set_cookie("garden_id", getattr(request, "_garden_id"))
            response.set_cookie("garden_name", getattr(request, "_garden_name"))

        return response
