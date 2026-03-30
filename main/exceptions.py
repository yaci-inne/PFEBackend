from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def _extract_message_and_details(data):
    if isinstance(data, dict):
        # Standard DRF uses "detail"; custom views often use "error"/"message".
        message = data.get("detail") or data.get("error") or data.get("message")
        details = data.get("details")

        if not message:
            # Validation payloads are often dicts of field -> errors.
            message = "Erreur de validation."
            details = data

        return str(message), details

    if isinstance(data, list):
        first = data[0] if data else "Erreur de validation."
        return str(first), data

    return str(data), None


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        return Response(
            {
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "Une erreur interne est survenue.",
                    "details": None,
                },
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    message, details = _extract_message_and_details(response.data)
    response.data = {
        "success": False,
        "error": {
            "code": f"HTTP_{response.status_code}",
            "message": message,
            "details": details,
        },
    }
    return response
