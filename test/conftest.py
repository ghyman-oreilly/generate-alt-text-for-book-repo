import sys
import os
from pathlib import Path

# Get the absolute path to the project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Add virtual environment site-packages to path
venv_path = project_root / "venv39" / "lib" / "python3.9" / "site-packages"
if venv_path.exists():
    sys.path.insert(0, str(venv_path))

print("Python path:", sys.path)  # Debug print