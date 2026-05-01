from typing import Any
from fastapi.responses import JSONResponse


class ServiceResponse:
    @staticmethod
    def success(
        data: Any = None,
        message: str = "Success",
        status_code: int = 200
    ):
        return JSONResponse(
            content={
                "success": True,
                "status_code": status_code,
                "message": message,
                "data": data
            }
        )

    @staticmethod
    def error(
        message: str = "Error",
        status_code: int = 400,
        data: Any = None
    ):
        return JSONResponse(
            content={
                "success": False,
                "status_code": status_code,
                "message": message,
                "data": data
            }
        )
