# main/services/pdf_generator.py
import os
from django.conf import settings
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from io import BytesIO
from django.core.files.base import ContentFile

class PDFGenerator:
    @staticmethod
    def generate_cv_pdf(cv_data):
        """
        Génère un PDF à partir des données du CV
        cv_data: dictionnaire contenant toutes les infos du CV
        """
        # Rendre le template HTML avec les données
        html_string = render_to_string('cv_template.html', {
            'cv': cv_data,
            'MEDIA_URL': settings.MEDIA_URL,
        })
        
        # Convertir HTML en PDF
        result = BytesIO()
        pdf = pisa.pisaDocument(BytesIO(html_string.encode('UTF-8')), result)
        
        if not pdf.err:
            return result.getvalue()
        return None
    
    @staticmethod
    def save_pdf_to_model(cv_instance, pdf_content):
        """Sauvegarde le PDF généré dans l'instance du CV"""
        filename = f"cv_{cv_instance.cvId}_{cv_instance.nom_complet.replace(' ', '_')}.pdf"
        cv_instance.fichier_pdf.save(filename, ContentFile(pdf_content), save=True)