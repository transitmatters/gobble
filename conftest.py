import shutil
from pathlib import Path

def pytest_configure(config):
    """Create config/local.json from template if it doesn't exist, so tests can import modules."""
    root = Path(__file__).parent
    local = root / "config" / "local.json"
    template = root / "config" / "template.json"
    if not local.exists() and template.exists():
        shutil.copy(template, local)
