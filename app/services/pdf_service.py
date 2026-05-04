import os
from weasyprint import HTML
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from datetime import datetime

class PDFService:
    def __init__(self):
        template_path = os.path.join(os.path.dirname(__file__), "../templates")
        self.env = Environment(loader=FileSystemLoader(template_path))


    def render_template(self, template_name: str, data: dict) -> str:
        try:
            template = self.env.get_template(f"reports_pdf/{template_name}.html")
            return template.render(**data, generated_at=datetime.now().strftime("%d/%m/%Y"))

        except TemplateNotFound:
            raise Exception(f"Report template '{template_name}' not found")

        except Exception as e:
            raise Exception(f"Template rendering error: {str(e)}")


    def generate_astrological_report(self, template_name: str, data: dict, output_filename: str) -> str:
        try:
            output_dir = "static/reports"
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            pdf_path = os.path.join(output_dir, output_filename)

            html_content = self.render_template(template_name, data)

            HTML(string=html_content, base_url=".").write_pdf(pdf_path)
            
            return pdf_path

        except Exception as e:
            print(f"Erreur lors de la génération du PDF : {str(e)}")
            raise e
        