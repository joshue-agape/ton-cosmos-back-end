import os
import time
from datetime import datetime, time as dt_time
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from app.schemas.order import *
from app.services.astrology_service import *
from app.services.email_service import *
from app.services.pdf_service import *
from app.services.stripe_service import *

router = APIRouter()
astrology_service = AstrologyService()
email_service = EmailService()
pdf_service = PDFService()
stripe_service = StripeService()

@router.get("/")
def health_check():
    return {"status": "ok"}


# ======================== #
#  TEST SERVICE ASTROLOGY  #
#========================= #
class BodyTest(BaseModel):
    birth_date: datetime
    birth_time: Optional[dt_time] = None
    latitude: float
    longitude: float


@router.post("/get-full-chart")
def testCalcule(body: BodyTest):
    start_time = time.perf_counter()
    birth_datetime = body.birth_date
    
    if birth_datetime.tzinfo is not None:
        birth_datetime = birth_datetime.replace(tzinfo=None)

    if body.birth_time is not None:
        birth_datetime = birth_datetime.replace(
            hour=body.birth_time.hour,
            minute=body.birth_time.minute,
            second=body.birth_time.second,
            microsecond=body.birth_time.microsecond
        )

    chart = astrology_service.get_full_chart(
        birth_datetime,
        body.latitude,
        body.longitude
    )

    print("Delay =", round(time.perf_counter() - start_time, 3), "s")

    return chart


# =========================== #
#  TEST SERVICE EMAIL SENDER  #
#============================ #
@router.post("/send-email")
def send_email(background_tasks: BackgroundTasks):
    background_tasks.add_task(
        email_service.send_email,
        "joshuedev.dark@gmail.com",
        "Test Email",
        "test_email",
        {
            "name": "Josh",
            "email": "joshuedev.dark@gmail.com",
            "message": "Hello background"
        }
    )

    return {"success": True}


# ========================= #
#  TEST SERVICE CREATE PDF  #
#========================== #
@router.post("/generate-report")
def testCreatePDF():
    data = {
        "name": "Josh Agape",
        "birth_date": "2001-11-27",
        "sun_sign": "Sagittaire",
        "moon_sign": "Bélier",
        "message": "Voici votre rapport astrologique généré avec succès"
    }

    pdf_path = pdf_service.generate_astrological_report(
        template_name="test_report",
        data=data,
        output_filename="test_report.pdf"
    )

    return {
        "success": True,
        "pdf_path": pdf_path
    }
    

@router.get("/get-pdf/{pdf_name}")
def get_pdf(pdf_name: str):
    file_path = os.path.join("static/reports", pdf_name)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="PDF introuvable"
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=pdf_name
    )
