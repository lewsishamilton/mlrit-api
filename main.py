import io
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx

from scraper import (
    fetch_student_details,
    fetch_student_photo_bytes,
    check_portal_connectivity
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("mlrit_api")

app = FastAPI(
    title="MLRIT Student Details API",
    description="Headless API for extracting student profile information from the MLRIT Exam Portal.",
    version="1.1.0"
)

# Enable CORS for all origins (allows web and mobile applications to consume this API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StudentRequest(BaseModel):
    roll_no: str = Field(..., examples=["25R21A05LL"], description="Student Hall Ticket / Roll Number")
    password: Optional[str] = Field(None, examples=["25R21A05LL"], description="Password (defaults to Roll Number if omitted)")
    include_photo_base64: bool = Field(False, description="Whether to include data URI Base64 photo string")


class StudentResponse(BaseModel):
    success: bool
    roll_no: str
    name: Optional[str] = None
    branch: Optional[str] = None
    semester: Optional[str] = None
    batch: Optional[str] = None
    admission_date: Optional[str] = None
    dob: Optional[str] = None
    caste_category: Optional[str] = None
    father_name: Optional[str] = None
    mother_name: Optional[str] = None
    student_email: Optional[str] = None
    parent_mobile: Optional[str] = None
    aadhar_no: Optional[str] = None
    apaar_id: Optional[str] = None
    photo_url: Optional[str] = None
    photo_base64: Optional[str] = None


@app.api_route("/", methods=["GET", "HEAD"], tags=["General"])
async def root():
    return {
        "service": "MLRIT Student Portal API",
        "status": "online",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "get_student": "/student/{roll_no}",
            "post_student": "/student",
            "get_student_photo": "/student/{roll_no}/photo",
            "health_check": "/health"
        }
    }


@app.api_route("/health", methods=["GET", "HEAD"], tags=["General"], summary="Portal Connectivity Health Check")
async def health_check():
    """Diagnose network connectivity between this server and the MLRIT Exam Portal."""
    return await check_portal_connectivity()


@app.api_route(
    "/student/{roll_no}",
    methods=["GET", "HEAD"],
    response_model=StudentResponse,
    tags=["Student Information"],
    summary="Get Student Details by Roll Number",
    responses={
        200: {"description": "Student details retrieved successfully."},
        401: {"description": "Invalid Roll Number or Password."},
        502: {"description": "MLRIT Portal is unreachable or returned an error."},
        504: {"description": "Connection to MLRIT portal timed out."},
    }
)
async def get_student(
    roll_no: str,
    password: Optional[str] = Query(None, description="Password (defaults to roll_no if omitted)"),
    include_photo_base64: bool = Query(False, description="Set to true to embed photo in base64 format")
):
    try:
        data = await fetch_student_details(
            roll_no=roll_no,
            password=password,
            include_photo_base64=include_photo_base64
        )
        return data
    except ValueError as e:
        logger.warning(f"Auth failed for roll {roll_no}: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as e:
        logger.error(f"Timeout reaching MLRIT portal for roll {roll_no}: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                "Connection to MLRIT exam portal timed out. The college portal server is either unreachable "
                "or dropping traffic from this server's IP address (geo-blocking / datacenter firewall). "
                "Check /health endpoint for diagnostics or configure PORTAL_PROXY."
            )
        )
    except httpx.ConnectError as e:
        logger.error(f"Connection failed to MLRIT portal for roll {roll_no}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"Failed to connect to MLRIT portal: connection was refused or dropped by firewall. "
                "Check /health for diagnostics or configure PORTAL_PROXY."
            )
        )
    except httpx.HTTPError as e:
        logger.error(f"HTTP network error for roll {roll_no}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Network error while communicating with MLRIT portal: {type(e).__name__} ({str(e)})"
        )
    except RuntimeError as e:
        logger.error(f"Scraper error for roll {roll_no}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error for roll {roll_no}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected server error: {type(e).__name__} - {str(e)}"
        )


@app.post(
    "/student",
    response_model=StudentResponse,
    tags=["Student Information"],
    summary="Query Student Details (POST body)",
    responses={
        200: {"description": "Student details retrieved successfully."},
        401: {"description": "Invalid credentials."},
        502: {"description": "MLRIT Portal is unreachable."},
        504: {"description": "Portal connection timed out."}
    }
)
async def post_student(req: StudentRequest):
    try:
        data = await fetch_student_details(
            roll_no=req.roll_no,
            password=req.password,
            include_photo_base64=req.include_photo_base64
        )
        return data
    except ValueError as e:
        logger.warning(f"Auth failed for roll {req.roll_no}: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as e:
        logger.error(f"Timeout reaching MLRIT portal for roll {req.roll_no}: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                "Connection to MLRIT exam portal timed out. The college portal server is either unreachable "
                "or dropping traffic from this server's IP address. Check /health for diagnostics."
            )
        )
    except httpx.HTTPError as e:
        logger.error(f"Network error for roll {req.roll_no}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Network error while communicating with MLRIT portal: {type(e).__name__} ({str(e)})"
        )
    except RuntimeError as e:
        logger.error(f"Scraper error for roll {req.roll_no}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error for roll {req.roll_no}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected server error: {type(e).__name__} - {str(e)}"
        )


@app.api_route(
    "/student/{roll_no}/photo",
    methods=["GET", "HEAD"],
    tags=["Student Information"],
    summary="Stream Student Photo as JPEG",
    responses={
        200: {"content": {"image/jpeg": {}}, "description": "Student photo binary"},
        404: {"description": "Photo not found"}
    }
)
async def get_student_photo(
    roll_no: str,
    password: Optional[str] = Query(None, description="Password (defaults to roll_no)")
):
    try:
        img_bytes = await fetch_student_photo_bytes(roll_no=roll_no, password=password)
        return Response(content=img_bytes, media_type="image/jpeg")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching photo for {roll_no}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    print(f"Starting server on http://0.0.0.0:{port} ...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
