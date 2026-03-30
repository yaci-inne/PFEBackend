from http import HTTPStatus


class StandardizeApiErrorMiddleware:
    """
    Ensure every API error response follows:
    {
      "success": false,
      "error": { "code": "...", "message": "...", "details": ... }
    }
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if response.status_code < 400:
            return response

        if not hasattr(response, "data"):
            return response

        data = response.data
        if isinstance(data, dict) and isinstance(data.get("error"), dict) and data.get("success") is False:
            return response

        message = None
        details = None

        if isinstance(data, dict):
            if isinstance(data.get("error"), str):
                message = data["error"]
            elif isinstance(data.get("detail"), str):
                message = data["detail"]
            elif isinstance(data.get("message"), str):
                message = data["message"]

            details = data.get("details")
            if details is None and not message:
                details = data

        elif isinstance(data, list):
            message = str(data[0]) if data else None
            details = data
        elif data is not None:
            message = str(data)

        if not message:
            try:
                message = HTTPStatus(response.status_code).phrase
            except Exception:
                message = "Une erreur est survenue."

        response.data = {
            "success": False,
            "error": {
                "code": f"HTTP_{response.status_code}",
                "message": message,
                "details": details,
            },
        }
        return response
