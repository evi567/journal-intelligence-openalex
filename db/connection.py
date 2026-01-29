"""
Módulo para gestionar la conexión a MySQL usando SQLAlchemy.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
import sys
import os

# Agregar el directorio raíz al path para importar config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def get_engine():
    """
    Crea y retorna un engine de SQLAlchemy para MySQL.
    
    Returns:
        sqlalchemy.engine.Engine: Engine configurado para MySQL
        
    Raises:
        OperationalError: Si no se puede conectar a MySQL
    """
    try:
        engine = create_engine(
            config.MYSQL_CONNECTION_STRING,
            echo=False,  # Cambiar a True para debug SQL
            pool_pre_ping=True,  # Verifica conexión antes de usar
            pool_recycle=3600  # Recicla conexiones cada hora
        )
        
        # Probar la conexión
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        return engine
        
    except OperationalError as e:
        print(f"❌ Error al conectar a MySQL:")
        print(f"   Host: {config.MYSQL_HOST}:{config.MYSQL_PORT}")
        print(f"   Database: {config.MYSQL_DB}")
        print(f"   User: {config.MYSQL_USER}")
        print(f"\n   Detalle del error: {e}")
        print("\n💡 Verifica que:")
        print("   1. MySQL esté corriendo")
        print("   2. Las credenciales en .env sean correctas")
        print("   3. La base de datos exista (ejecuta db/init_db.py primero)")
        raise


def test_connection():
    """
    Prueba la conexión a MySQL y muestra información.
    
    Returns:
        bool: True si la conexión es exitosa, False en caso contrario
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute("SELECT VERSION()")
            version = result.fetchone()[0]
            print(f"✅ Conexión exitosa a MySQL {version}")
            print(f"   Database: {config.MYSQL_DB}")
            return True
    except Exception as e:
        print(f"❌ Fallo en la conexión: {e}")
        return False


if __name__ == "__main__":
    # Test de conexión
    test_connection()
