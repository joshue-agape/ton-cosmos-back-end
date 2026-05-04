import os
import time
from typing import Optional
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi import APIRouter, HTTPException
from datetime import datetime, time as dt_time

from app.services.astrology_service import *
from app.services.pdf_service import *

router = APIRouter()

astrology_service = AstrologyService()
pdf_service = PDFService()

@router.get("/")
def health_check():
    """ TEST DE API """
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


# ========================= #
#  TEST SERVICE CREATE PDF  #
#========================== #
@router.post("/generate-report")
def testCreatePDF():
    data = {}

    safe_name = ("cosmos" or "user").replace(" ", "-")
    timestamp = datetime.now().strftime("%Y%m%d")
    output_filename = f"report-{safe_name}-{timestamp}.pdf"
    
    pdf_path = pdf_service.generate_astrological_report(
        template_name="premium_report_test",
        data=data,
        output_filename=output_filename
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
