"""
Configuración global del proyecto.
Lee variables de entorno desde .env
"""
import os
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Configuración MySQL
MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
MYSQL_DB = os.getenv('MYSQL_DB', 'journal_intelligence')
MYSQL_USER = os.getenv('MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')

# Configuración OpenAlex
OPENALEX_EMAIL = os.getenv('OPENALEX_EMAIL', '')
OPENALEX_BASE_URL = 'https://api.openalex.org'

# String de conexión MySQL
MYSQL_CONNECTION_STRING = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@"
    f"{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
)

# Configuración de la aplicación
DEFAULT_PER_PAGE = 200
DEFAULT_MAX_PAGES = 2
TOP_SOURCES_LIMIT = 30  # Número máximo de sources a enriquecer con llamadas API completas
TOP_N_RECOMMENDATIONS = 10
