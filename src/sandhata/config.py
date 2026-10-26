from pathlib import Path
import os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')
# Never export private graph state through inherited tracing environment settings.
os.environ['LANGCHAIN_TRACING_V2']='false'
os.environ['LANGSMITH_TRACING']='false'
DATA = Path(os.getenv('SANDHATA_DATA_DIR', str(ROOT / 'runtime' / 'data'))).resolve()
ISSUER = os.getenv('SANDHATA_OIDC_ISSUER', 'http://localhost:18180/realms/sandhata')
TENANT = os.getenv('SANDHATA_TENANT_ID', '00000000-0000-0000-0000-000000000001')
DATABASE_URL = os.getenv('SANDHATA_DATABASE_URL', '')
WORKER_DATABASE_URL = os.getenv('SANDHATA_WORKER_DATABASE_URL', DATABASE_URL)
MODEL_URL = os.getenv('SANDHATA_MODEL_BASE_URL', 'http://127.0.0.1:11434')
MODEL = os.getenv('SANDHATA_MODEL_NAME', 'gpt-oss:20b')
TIMEZONE = 'America/New_York'

class AppError(Exception):
    """A safe error message suitable for the UI; never includes raw provider errors."""

def require_config():
    if not DATABASE_URL:
        raise AppError('Run scripts/bootstrap_local.py and scripts/migrate.py before starting the app.')
