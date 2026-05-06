import os
import aiosmtplib
from email.message import EmailMessage
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound
from app.core.config import settings
from typing import Dict, Any, Optional


class EmailService:
    def __init__(self):
        template_path = os.path.join(os.path.dirname(__file__), "../templates")
        self.env = Environment(
            loader=FileSystemLoader(template_path),
            autoescape=select_autoescape(["html", "xml"])
        )


    def _render_template(self, template_name: str, data: Dict[str, Any]) -> str:
        try:
            template = self.env.get_template(f"emails/{template_name}.html")
            return template.render(**data)
        except TemplateNotFound:
            raise Exception(f"Email template '{template_name}' not found")
        except Exception as e:
            raise Exception(f"Template rendering error: {str(e)}")
        
    
    async def send_email(
        self, 
        to: str, 
        subject: str, 
        template_name: str, 
        data: Dict[str, Any], 
        attachment_path: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            html_content = self._render_template(template_name, data)

            message = EmailMessage()
            message["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
            message["To"] = to
            message["Subject"] = subject

            message.set_content("Veuillez consulter cet email dans un client supportant le HTML.")
            message.add_alternative(html_content, subtype="html")

            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, "rb") as f:
                    file_data = f.read()
                    file_name = os.path.basename(attachment_path)
                
                message.add_attachment(
                    file_data,
                    maintype="application",
                    subtype="pdf",
                    filename=file_name
                )

            await aiosmtplib.send(
                message,
                hostname=settings.MAIL_HOST,
                port=settings.MAIL_PORT,
                username=settings.MAIL_USERNAME,
                password=settings.MAIL_PASSWORD,
                start_tls=settings.MAIL_STARTTLS,
                use_tls=settings.MAIL_SSL,
            )
            
            return {"success": True, "message": "Email envoyé avec succès"}

        except aiosmtplib.SMTPException as e:
            print(f"SMTP Error: {e}")
            return {"success": False, "message": f"Erreur SMTP: {str(e)}"}
        except Exception as e:
            print(f"Unexpected Email Error: {e}")
            return {"success": False, "message": f"Erreur inattendue: {str(e)}"}
