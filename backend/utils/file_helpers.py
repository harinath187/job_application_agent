"""
File handling utilities for upload, storage, and retrieval operations.
"""
import re
from pathlib import Path
from typing import Tuple


OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"
RESUMES_DIR = OUTPUTS_DIR / "resumes"
COVER_LETTERS_DIR = OUTPUTS_DIR / "cover_letters"


def init_directories() -> None:
    """Initialize output directories if they don't exist."""
    RESUMES_DIR.mkdir(parents=True, exist_ok=True)
    COVER_LETTERS_DIR.mkdir(parents=True, exist_ok=True)


def get_output_path(folder: str, filename: str) -> str:
    """
    Build full file path for output folder.
    
    Args:
        folder: Folder name ("resumes" or "cover_letters")
        filename: Filename
    
    Returns:
        Full path as string
    """
    if folder == "resumes":
        target_dir = RESUMES_DIR
    elif folder == "cover_letters":
        target_dir = COVER_LETTERS_DIR
    else:
        target_dir = OUTPUTS_DIR / folder
    
    target_dir.mkdir(parents=True, exist_ok=True)
    return str(target_dir / filename)


def sanitise_filename(name: str) -> str:
    """
    Sanitise filename by removing special characters.
    
    Args:
        name: Original filename or string
    
    Returns:
        Sanitised filename (lowercase, underscores for spaces, alphanumeric only)
    """
    # Replace spaces with underscores
    name = name.replace(" ", "_")
    # Remove special characters, keep only alphanumeric, underscores, hyphens
    name = re.sub(r"[^a-z0-9_\-]", "", name.lower())
    # Remove multiple consecutive underscores
    name = re.sub(r"_+", "_", name)
    return name


def save_upload(file_bytes: bytes, filename: str) -> str:
    """
    Save uploaded file to resumes output directory.
    
    Args:
        file_bytes: File content as bytes
        filename: Original filename
    
    Returns:
        Full path to saved file
    """
    RESUMES_DIR.mkdir(parents=True, exist_ok=True)
    filepath = RESUMES_DIR / filename
    filepath.write_bytes(file_bytes)
    return str(filepath)


def validate_file_path(filepath: str) -> bool:
    """
    Validate that a file path is safe and doesn't attempt path traversal.
    
    Args:
        filepath: File path to validate (relative to OUTPUTS_DIR)
    
    Returns:
        True if safe, False otherwise
    """
    # Reject paths with parent directory references
    if ".." in filepath:
        return False
    
    # Join with OUTPUTS_DIR and validate it's still within outputs
    try:
        full_path = OUTPUTS_DIR / filepath
        abs_path = full_path.resolve()
        outputs_abs = OUTPUTS_DIR.resolve()
        # Check if the resolved path is within outputs directory
        abs_path.relative_to(outputs_abs)
        return True
    except (ValueError, RuntimeError):
        return False


def get_relative_path(filepath: str) -> str:
    """
    Convert an absolute file path to a relative path from OUTPUTS_DIR.
    Returns just the filename if the file is in a direct subdirectory of OUTPUTS_DIR.
    
    Args:
        filepath: Absolute file path
    
    Returns:
        Relative path from OUTPUTS_DIR
    """
    try:
        abs_path = Path(filepath).resolve()
        outputs_abs = OUTPUTS_DIR.resolve()
        relative = abs_path.relative_to(outputs_abs)
        return str(relative).replace("\\", "/")  # Use forward slashes for web paths
    except (ValueError, RuntimeError):
        # If not within OUTPUTS_DIR, return filename only
        return Path(filepath).name
