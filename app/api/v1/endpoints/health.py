import os
import asyncio
from typing import Optional
from pydantic import BaseModel
from fastapi.responses import FileResponse, Response
from fastapi import APIRouter, Body, HTTPException
from datetime import datetime, time as dt_time

from app.services.astrology_service import AstrologyService
from app.services.pdf_service import PDFService
from app.services.claude_service import AIService

router = APIRouter()

# Initialisation des services
astrology_service = AstrologyService()
pdf_service = PDFService()
claude_service = AIService()


@router.get("/")
async def health_check():
    return {"status": "ok", "service": "Indira Astro API"}

class BodyTest(BaseModel):
    birth_date: datetime
    birth_time: Optional[dt_time] = None
    latitude: float
    longitude: float

@router.post("/get-full-chart")
async def get_chart_endpoint(body: BodyTest):
    start_time = asyncio.get_event_loop().time()
    
    birth_datetime = body.birth_date
    
    if birth_datetime.tzinfo is not None:
        birth_datetime = birth_datetime.replace(tzinfo=None)

    if body.birth_time is not None:
        birth_datetime = datetime.combine(birth_datetime.date(), body.birth_time)

    chart = await astrology_service.get_full_chart(
        birth_datetime,
        body.latitude,
        body.longitude
    )

    duration = round(asyncio.get_event_loop().time() - start_time, 3)
    print(f"Calcul Indira terminé en : {duration}s")

    return chart


@router.post("/get-ia-response")
async def test_generate_ia():
    claude_ai = await claude_service.test_claude_connection()
    return claude_ai


@router.post("/generate-report")
async def generate_report_endpoint():
    data = {}

    safe_name = "cosmos-user"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    output_filename = f"report-{safe_name}-{timestamp}.pdf"
    
    pdf_path = await pdf_service.generate_astrological_report(
        template_name="premium_report_test",
        data=data,
        output_filename=output_filename
    )

    return {
        "success": True,
        "pdf_path": pdf_path,
        "filename": output_filename
    }
    

@router.get("/get-pdf/{pdf_name}")
async def get_pdf(pdf_name: str):
    file_path = os.path.join("static/reports", pdf_name)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail="Le rapport demandé est introuvable."
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=pdf_name
    )


@router.post("/get-svg-map")
async def get_svg_map(chart: dict = Body(...)):
    svg = await claude_service.GenerateSVGMap(chart)
    return Response(content=svg, media_type="image/svg+xml")
