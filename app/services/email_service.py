import aiosmtplib
from email.message import EmailMessage
from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateNotFound

from app.core.config import settings


class EmailService:
    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader("app/templates"),
            autoescape=select_autoescape(["html", "xml"])
        )


    def render_template(self, template_name: str, data: dict) -> str:
        try:
            template = self.env.get_template(f"emails/{template_name}.html")
            return template.render(**data)

        except TemplateNotFound:
            raise Exception(f"Email template '{template_name}' not found")

        except Exception as e:
            raise Exception(f"Template rendering error: {str(e)}")


    async def send_email(self, to: str, subject: str, template_name: str, data: dict):
        try:
            html_content = self.render_template(template_name, data)

            message = EmailMessage()
            message["From"] = f"{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM}>"
            message["To"] = to
            message["Subject"] = subject

            message.set_content("This is a fallback email")
            message.add_alternative(html_content, subtype="html")

            await aiosmtplib.send(
                message,
                hostname=settings.MAIL_HOST,
                port=settings.MAIL_PORT,
                username=settings.MAIL_USERNAME,
                password=settings.MAIL_PASSWORD,
                start_tls=True,
            )

            return {
                "success": True,
                "message": "Email sent successfully"
            }

        except aiosmtplib.SMTPException as e:
            return {
                "success": False,
                "message": "SMTP error while sending email"
            }

        except ConnectionError as e:
            return {
                "success": False,
                "message": "Connection error while sending email"
            }

        except Exception as e:
            return {
                "success": False,
                "message": "Unexpected error while sending email"
            }
            