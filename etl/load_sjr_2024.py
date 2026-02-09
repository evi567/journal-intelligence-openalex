"""
Script ETL para cargar datos de SCImago Journal Rank (SJR) 2024 a MySQL.
"""
import pandas as pd
import re
import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_engine
from sqlalchemy import text


def normalize_issn(issn_str):
    """
    Normaliza un ISSN eliminando guiones y espacios.
    
    Args:
        issn_str (str): ISSN en cualquier formato
        
    Returns:
        str: ISSN normalizado (8 dígitos) o None si inválido
    """
    if pd.isna(issn_str) or not issn_str:
        return None
    
    # Quitar espacios y guiones
    normalized = str(issn_str).strip().replace('-', '').replace(' ', '')
    
    # Validar que sea exactamente 8 dígitos
    if re.match(r'^\d{8}$', normalized):
        return normalized
    
    return None


def explode_issn_field(df):
    """
    Explota el campo ISSN que puede contener múltiples ISSNs separados por coma.
    
    Args:
        df (pd.DataFrame): DataFrame con columna 'Issn' que puede tener múltiples valores
        
    Returns:
        pd.DataFrame: DataFrame con una fila por ISSN normalizado
    """
    records = []
    
    for _, row in df.iterrows():
        issn_field = row.get('Issn', '')
        
        if pd.isna(issn_field) or not issn_field:
            continue
        
        # Separar por coma (puede haber ISSN print y electrónico)
        issn_list = str(issn_field).split(',')
        
        for issn in issn_list:
            issn_norm = normalize_issn(issn)
            
            if issn_norm:
                # Crear registro con ISSN normalizado
                record = {
                    'issn_norm': issn_norm,
                    'title': row.get('Title', ''),
                    'sjr': row.get('SJR', None),
                    'quartile': row.get('SJR Best Quartile', None)
                }
                records.append(record)
    
    return pd.DataFrame(records)


def convert_sjr_value(sjr_str):
    """
    Convierte el valor de SJR del formato europeo (coma decimal) a float.
    
    Args:
        sjr_str (str): Valor de SJR como string (ej: "145,004")
        
    Returns:
        float: Valor numérico o None
    """
    if pd.isna(sjr_str) or not sjr_str:
        return None
    
    try:
        # Reemplazar coma por punto
        sjr_clean = str(sjr_str).replace(',', '.')
        return float(sjr_clean)
    except:
        return None


def load_sjr_csv(csv_path):
    """
    Carga y procesa el CSV de SJR 2024.
    
    Args:
        csv_path (str): Ruta al archivo CSV de SJR
        
    Returns:
        pd.DataFrame: DataFrame procesado y listo para insertar
    """
    print("=" * 70)
    print("CARGANDO SJR 2024")
    print("=" * 70)
    print(f"Archivo: {csv_path}")
    print()
    
    # Leer CSV (importante: separador es punto y coma)
    print("PASO 1: Leyendo CSV...")
    print("-" * 70)
    df = pd.read_csv(csv_path, sep=';', encoding='utf-8')
    print(f"✅ {len(df)} registros leídos")
    print(f"   Columnas: {list(df.columns)}")
    print()
    
    # Convertir SJR a float
    print("PASO 2: Convirtiendo valores de SJR...")
    print("-" * 70)
    df['SJR'] = df['SJR'].apply(convert_sjr_value)
    valid_sjr = df['SJR'].notna().sum()
    print(f"✅ {valid_sjr} valores de SJR convertidos")
    print()
    
    # Explotar ISSNs
    print("PASO 3: Normalizando y explotando ISSNs...")
    print("-" * 70)
    df_exploded = explode_issn_field(df)
    print(f"✅ {len(df_exploded)} ISSNs normalizados")
    print(f"   Original: {len(df)} revistas → Explotado: {len(df_exploded)} ISSNs")
    print()
    
    # Eliminar duplicados (en caso de que el mismo ISSN aparezca en múltiples revistas)
    print("PASO 4: Eliminando duplicados...")
    print("-" * 70)
    before = len(df_exploded)
    df_exploded = df_exploded.drop_duplicates(subset=['issn_norm'], keep='first')
    after = len(df_exploded)
    print(f"✅ {before - after} duplicados eliminados ({after} únicos)")
    print()
    
    return df_exploded


def insert_to_mysql(df, engine):
    """
    Inserta datos de SJR a MySQL con upsert.
    
    Args:
        df (pd.DataFrame): DataFrame con datos procesados
        engine: SQLAlchemy engine
    """
    print("PASO 5: Insertando en MySQL...")
    print("-" * 70)
    
    # Verificar que la tabla existe
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) as count 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'sjr_2024'
        """))
        table_exists = result.fetchone()[0] > 0
        
        if not table_exists:
            print("⚠️  La tabla sjr_2024 no existe. Creándola...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS sjr_2024 (
                  issn_norm VARCHAR(16) PRIMARY KEY,
                  title VARCHAR(500) NULL,
                  sjr FLOAT NULL,
                  quartile VARCHAR(5) NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """))
            conn.commit()
            print("✅ Tabla creada")
    
    # Insertar datos (batch upsert)
    inserted = 0
    updated = 0
    errors = 0
    
    for _, row in df.iterrows():
        try:
            with engine.connect() as conn:
                # Intentar insertar
                insert_sql = text("""
                    INSERT INTO sjr_2024 (issn_norm, title, sjr, quartile)
                    VALUES (:issn_norm, :title, :sjr, :quartile)
                    ON DUPLICATE KEY UPDATE
                        title = VALUES(title),
                        sjr = VALUES(sjr),
                        quartile = VALUES(quartile)
                """)
                
                result = conn.execute(insert_sql, {
                    'issn_norm': row['issn_norm'],
                    'title': row['title'][:500] if pd.notna(row['title']) else None,
                    'sjr': row['sjr'],
                    'quartile': row['quartile'] if pd.notna(row['quartile']) else None
                })
                conn.commit()
                
                if result.rowcount == 1:
                    inserted += 1
                else:
                    updated += 1
                    
        except Exception as e:
            errors += 1
            if errors <= 5:  # Mostrar solo los primeros 5 errores
                print(f"  ⚠️  Error con ISSN {row['issn_norm']}: {e}")
    
    print(f"✅ Insertados: {inserted}")
    print(f"✅ Actualizados: {updated}")
    if errors > 0:
        print(f"⚠️  Errores: {errors}")
    print()


def load_sjr_to_mysql(csv_path):
    """
    Pipeline completo para cargar SJR 2024 a MySQL.
    
    Args:
        csv_path (str): Ruta al archivo CSV de SJR
    """
    # Cargar y procesar CSV
    df_processed = load_sjr_csv(csv_path)
    
    if df_processed.empty:
        print("❌ No hay datos para insertar")
        return
    
    # Obtener engine
    engine = get_engine()
    
    # Insertar a MySQL
    insert_to_mysql(df_processed, engine)
    
    print("=" * 70)
    print("CARGA COMPLETADA")
    print("=" * 70)
    
    # Estadísticas finales
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) as total FROM sjr_2024"))
        total = result.fetchone()[0]
        
        result = conn.execute(text("SELECT COUNT(*) as q1 FROM sjr_2024 WHERE quartile = 'Q1'"))
        q1 = result.fetchone()[0]
        
        result = conn.execute(text("SELECT COUNT(*) as q2 FROM sjr_2024 WHERE quartile = 'Q2'"))
        q2 = result.fetchone()[0]
        
        result = conn.execute(text("SELECT COUNT(*) as q3 FROM sjr_2024 WHERE quartile = 'Q3'"))
        q3 = result.fetchone()[0]
        
        result = conn.execute(text("SELECT COUNT(*) as q4 FROM sjr_2024 WHERE quartile = 'Q4'"))
        q4 = result.fetchone()[0]
    
    print(f"\nEstadísticas finales:")
    print(f"  Total de ISSNs: {total}")
    print(f"  Q1: {q1}")
    print(f"  Q2: {q2}")
    print(f"  Q3: {q3}")
    print(f"  Q4: {q4}")


if __name__ == "__main__":
    # Configurar ruta al CSV
    # Ajustar según dónde tengas el archivo
    csv_file = "scimagojr 2024.csv"
    
    # Buscar en diferentes ubicaciones posibles
    possible_paths = [
        csv_file,
        os.path.join("data", csv_file),
        os.path.join("..", "data", csv_file),
        os.path.join(os.path.dirname(__file__), "..", "data", csv_file)
    ]
    
    csv_path = None
    for path in possible_paths:
        if os.path.exists(path):
            csv_path = path
            break
    
    if csv_path:
        print(f"Archivo encontrado: {csv_path}\n")
        load_sjr_to_mysql(csv_path)
    else:
        print("❌ Error: No se encontró el archivo 'scimagojr 2024.csv'")
        print("\nBusca el archivo en:")
        for p in possible_paths:
            print(f"  - {os.path.abspath(p)}")
        print("\nColócalo en alguna de estas ubicaciones y vuelve a ejecutar.")
