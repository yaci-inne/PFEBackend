# backend/health_views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from SPARQLWrapper import SPARQLWrapper, JSON
import json

@require_http_methods(["GET"])
def health_check(request):
    """Health check endpoint for Render"""
    return JsonResponse({
        'status': 'healthy',
        'debug': settings.DEBUG,
        'database': 'connected' if check_database() else 'error',
        'sparql_endpoint': settings.SPARQL_ENDPOINT,
        'environment': 'production' if not settings.DEBUG else 'development'
    })

def check_database():
    """Vérifie la connexion à la base de données"""
    from django.db import connection
    try:
        connection.ensure_connection()
        return True
    except Exception:
        return False

@csrf_exempt
@require_http_methods(["GET", "POST"])
def test_sparql(request):
    """Test SPARQL endpoint"""
    try:
        sparql = SPARQLWrapper(settings.SPARQL_ENDPOINT)
        
        if settings.SPARQL_USERNAME and settings.SPARQL_PASSWORD:
            sparql.setCredentials(settings.SPARQL_USERNAME, settings.SPARQL_PASSWORD)
        
        if request.method == "POST":
            data = json.loads(request.body)
            query = data.get('query', '')
        else:
            query = """
            SELECT ?s ?p ?o WHERE {
              ?s ?p ?o
            } LIMIT 5
            """
        
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()
        
        return JsonResponse({
            'success': True,
            'data': results,
            'endpoint': settings.SPARQL_ENDPOINT
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'endpoint': settings.SPARQL_ENDPOINT
        }, status=500)