"""
Download API route - Serves generated resumes and cover letters.
"""
import logging
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from utils.file_helpers import validate_file_path, OUTPUTS_DIR


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["download"])


@router.get("/download")
async def download_file(file: str = Query(..., description="Filename to download")) -> FileResponse:
    """
    Download a generated file (resume or cover letter).
    
    Args:
        file: Filename to download
    
    Returns:
        FileResponse with the file
    """
    try:
        # Validate filename to prevent path traversal
        if not validate_file_path(file):
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        # Build full filepath
        filepath = OUTPUTS_DIR / file
        
        # Double-check file exists and is within outputs directory
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not filepath.is_file():
            raise HTTPException(status_code=400, detail="Not a valid file")
        
        # Verify it's within outputs directory (additional safety check)
        try:
            filepath.relative_to(OUTPUTS_DIR.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        # Determine content type based on file extension
        suffix = filepath.suffix.lower()
        if suffix == ".pdf":
            media_type = "application/pdf"
        elif suffix == ".docx":
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        else:
            media_type = "application/octet-stream"
        
        logger.info(f"Downloading file: {filepath}")
        
        return FileResponse(
            path=filepath,
            media_type=media_type,
            filename=filepath.name
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail="Error downloading file")
