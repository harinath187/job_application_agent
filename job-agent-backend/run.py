"""
Entry point for the Job Agent API.
Run with: python run.py
"""
import subprocess
import sys


if __name__ == "__main__":
    try:
        # Run uvicorn with the FastAPI app
        subprocess.run(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "api.main:app",
                "--reload",
                "--host",
                "0.0.0.0",
                "--port",
                "8000"
            ],
            check=True
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"Error running server: {e}")
        sys.exit(1)
