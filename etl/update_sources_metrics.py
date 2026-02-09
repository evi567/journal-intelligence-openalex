"""
Script para actualizar métricas faltantes en revistas existentes.
Actualiza: two_yr_mean_citedness, works_ref_year, cites_ref_year
"""
import sys
import os
from datetime import datetime
from sqlalchemy import text

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.openalex_client import get_source
from db.connection import get_engine


def update_sources_with_missing_metrics():
    """
    Actualiza revistas en sources que tienen métricas faltantes.
    """
    print("=" * 70)
    print("ACTUALIZANDO MÉTRICAS FALTANTES EN SOURCES")
    print("=" * 70)
    print()
    
    engine = get_engine()
    
    # Paso 1: Obtener revistas con métricas faltantes
    print("PASO 1: Identificando revistas con métricas faltantes...")
    print("-" * 70)
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT source_id, display_name
            FROM sources
            WHERE two_yr_mean_citedness IS NULL 
               OR works_ref_year IS NULL 
               OR cites_ref_year IS NULL
        """))
        
        sources_to_update = result.fetchall()
    
    if not sources_to_update:
        print("✅ No hay revistas con métricas faltantes")
        return
    
    print(f"✅ {len(sources_to_update)} revistas necesitan actualización")
    print()
    
    # Paso 2: Actualizar cada revista
    print("PASO 2: Actualizando revistas desde OpenAlex...")
    print("-" * 70)
    
    updated_count = 0
    error_count = 0
    ref_year = datetime.utcnow().year - 4
    
    for source_id, display_name in sources_to_update:
        try:
            print(f"  Procesando: {display_name} ({source_id})...", end=" ")
            
            # Obtener datos completos de OpenAlex
            source_data = get_source(source_id)
            
            if not source_data:
                print("❌ No encontrado en OpenAlex")
                error_count += 1
                continue
            
            # Buscar datos del año de referencia en counts_by_year
            works_ref_year = None
            cites_ref_year = None
            for year_entry in source_data.get('counts_by_year', []):
                if year_entry.get('year') == ref_year:
                    works_ref_year = year_entry.get('works_count')
                    cites_ref_year = year_entry.get('cited_by_count')
                    break
            
            # Extraer two_yr_mean_citedness
            two_yr_mean_citedness = source_data.get('summary_stats', {}).get('2yr_mean_citedness')
            
            # Actualizar en MySQL
            with engine.connect() as conn:
                update_sql = text("""
                    UPDATE sources SET
                        two_yr_mean_citedness = :two_yr,
                        works_ref_year = :works_ref,
                        cites_ref_year = :cites_ref,
                        works_count = :works_count,
                        cited_by_count = :cited_count,
                        updated_date = NOW()
                    WHERE source_id = :source_id
                """)
                
                conn.execute(update_sql, {
                    'two_yr': two_yr_mean_citedness,
                    'works_ref': works_ref_year,
                    'cites_ref': cites_ref_year,
                    'works_count': source_data.get('works_count', 0),
                    'cited_count': source_data.get('cited_by_count', 0),
                    'source_id': source_id
                })
                conn.commit()
            
            updated_count += 1
            print("✅")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            error_count += 1
    
    print()
    print("-" * 70)
    print(f"✅ {updated_count} revistas actualizadas")
    if error_count > 0:
        print(f"⚠️  {error_count} revistas con errores")
    print()
    
    # Paso 3: Verificar resultados
    print("PASO 3: Verificando actualización...")
    print("-" * 70)
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) as total
            FROM sources
            WHERE two_yr_mean_citedness IS NULL 
               OR works_ref_year IS NULL 
               OR cites_ref_year IS NULL
        """))
        
        remaining = result.fetchone()[0]
    
    print(f"Revistas con métricas faltantes restantes: {remaining}")
    print()
    
    print("=" * 70)
    print("ACTUALIZACIÓN COMPLETADA")
    print("=" * 70)


if __name__ == "__main__":
    import time
    
    print("Este script actualizará todas las revistas con métricas faltantes.")
    print("Puede tardar varios minutos dependiendo de cuántas revistas necesiten actualización.")
    print()
    
    response = input("¿Continuar? (s/n): ")
    
    if response.lower() in ['s', 'si', 'yes', 'y']:
        start_time = time.time()
        update_sources_with_missing_metrics()
        elapsed = time.time() - start_time
        print(f"\nTiempo total: {elapsed:.2f} segundos")
    else:
        print("Actualización cancelada")
