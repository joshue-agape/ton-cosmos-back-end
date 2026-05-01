from typing import Optional
from sqlalchemy.orm import Session
from app.models.report import AstrologicalReport
from app.schemas.report import *

class ReportRepository:
    def __init__(self, db: Session):
        self.db = db


    # ========================================================= #
    """ Initialise une entrée de rapport liée à une commande. """
    def create(self, report_data: ReportCreate) -> AstrologicalReport:
        db_report = AstrologicalReport(**report_data)
        self.db.add(db_report)
        self.db.commit()
        self.db.refresh(db_report)
        return db_report


    # ========================================================== #
    """ Récupère le rapport associé à une commande spécifique. """
    def get_by_order_id(self, order_id: int) -> Optional[AstrologicalReport]:
        return self.db.query(AstrologicalReport).filter(
            AstrologicalReport.order_id == order_id
        ).first()


    # ========================================================================== #
    """ Sauvegarde les données éphémérides et le texte généré par l'IA Claude. """
    def update_content(self, report_id: int, astral_data: dict, ai_content: dict) -> Optional[AstrologicalReport]:
        db_report = self.db.query(AstrologicalReport).get(report_id)
        if db_report:
            db_report.astral_data_json = astral_data
            db_report.ai_content_json = ai_content
            self.db.commit()
            self.db.refresh(db_report)
        return db_report


    # ================================================================================= #
    """ Enregistre le lien du PDF final et la durée de génération pour le monitoring. """
    def finalize_pdf(self, report_id: int, pdf_url: str, pdf_name: str, duration: int) -> Optional[AstrologicalReport]:
        db_report = self.db.query(AstrologicalReport).get(report_id)
        if db_report:
            db_report.pdf_url = pdf_url
            db_report.pdf_name = pdf_name
            db_report.generation_duration = duration
            self.db.commit()
            self.db.refresh(db_report)
        return db_report


    # ==================================================================================== #
    """ Enregistre les erreurs de génération pour le dashboard admin de Joseph. """
    def log_error(self, report_id: int, error_message: str) -> None:
        db_report = self.db.query(AstrologicalReport).get(report_id)
        if db_report:
            db_report.error_log = error_message
            self.db.commit()