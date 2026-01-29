"""
Script para inicializar la base de datos MySQL.
Crea la BD si no existe y ejecuta el schema.sql
"""
import pymysql
import sys
import os

# Agregar el directorio raíz al path para importar config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


def create_database():
    """
    Crea la base de datos si no existe.
    """
    try:
        # Conectar sin especificar la base de datos
        connection = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # Crear base de datos si no existe
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {config.MYSQL_DB} "
                          f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"✅ Base de datos '{config.MYSQL_DB}' verificada/creada")
        
        connection.close()
        return True
        
    except pymysql.Error as e:
        print(f"❌ Error al crear la base de datos:")
        print(f"   {e}")
        print("\n💡 Verifica que:")
        print("   1. MySQL esté corriendo en localhost:3306")
        print("   2. Las credenciales en .env sean correctas")
        print("   3. El usuario tenga permisos para crear bases de datos")
        return False


def execute_schema():
    """
    Ejecuta el archivo schema.sql para crear las tablas.
    """
    try:
        # Conectar a la base de datos específica
        connection = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DB,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        # Leer schema.sql
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # Ejecutar cada statement
        statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
        
        with connection.cursor() as cursor:
            for statement in statements:
                if statement:
                    cursor.execute(statement)
            connection.commit()
        
        print("✅ Tablas creadas/verificadas:")
        print("   - sources")
        print("   - works_sample")
        print("   - query_runs")
        print("   - recommendations")
        
        connection.close()
        return True
        
    except pymysql.Error as e:
        print(f"❌ Error al ejecutar schema.sql:")
        print(f"   {e}")
        return False
    except FileNotFoundError:
        print(f"❌ Archivo schema.sql no encontrado en {schema_path}")
        return False


def main():
    """
    Función principal para inicializar la BD.
    """
    print("=" * 60)
    print("INICIALIZACIÓN DE BASE DE DATOS - Journal Intelligence")
    print("=" * 60)
    print()
    
    # Paso 1: Crear base de datos
    print("Paso 1/2: Creando base de datos...")
    if not create_database():
        sys.exit(1)
    print()
    
    # Paso 2: Crear tablas
    print("Paso 2/2: Creando tablas desde schema.sql...")
    if not execute_schema():
        sys.exit(1)
    print()
    
    print("=" * 60)
    print("✅ Inicialización completada exitosamente!")
    print("=" * 60)
    print("\nPuedes ahora ejecutar la aplicación con:")
    print("  streamlit run app/app.py")


if __name__ == "__main__":
    main()
