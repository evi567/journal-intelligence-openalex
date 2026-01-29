"""
Pipeline ETL para cargar datos de OpenAlex a MySQL.
"""
import pandas as pd
from datetime import datetime
from collections import Counter
import sys
import os
from sqlalchemy import text

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.openalex_client import search_works_by_text, get_source
from db.connection import get_engine
import config


def extract_source_info(work):
    """
    Extrae información de la fuente (source) de un work.
    Prioriza primary_location y si no existe, busca en locations.
    """
    def _parse_source(src: dict):
        if not src:
            return None, None
        source_id_raw = src.get("id", "")
        source_id = source_id_raw.split("/")[-1] if source_id_raw else None
        source_name = src.get("display_name", "") or ""
        return (source_id, source_name) if source_id else (None, None)

    # 1) primary_location
    primary_location = work.get("primary_location") or {}
    src = (primary_location.get("source") or {})
    source_id, source_name = _parse_source(src)
    if source_id:
        return source_id, source_name

    # 2) fallback: locations
    for loc in work.get("locations") or []:
        src2 = (loc or {}).get("source") or {}
        source_id, source_name = _parse_source(src2)
        if source_id:
            return source_id, source_name

    return None, None


def load_works_and_sources(query_text, per_page=None, max_pages=None):
    """
    Pipeline completo: descarga works, extrae sources, upsert a MySQL.
    
    Args:
        query_text (str): Texto de búsqueda para OpenAlex
        per_page (int, optional): Works por página
        max_pages (int, optional): Páginas máximas a descargar
        
    Returns:
        pd.DataFrame: DataFrame con candidatos (source_id, freq, display_name)
        
    Raises:
        Exception: Si falla algún paso del pipeline
    """
    print("=" * 70)
    print(f"INICIANDO PIPELINE ETL - OpenAlex")
    print("=" * 70)
    print(f"Query: {query_text}")
    print()
    
    # Configuración
    per_page = per_page or config.DEFAULT_PER_PAGE
    max_pages = max_pages or config.DEFAULT_MAX_PAGES
    
    # Paso 1: Descargar works desde OpenAlex
    print("PASO 1: Descargando works desde OpenAlex...")
    print("-" * 70)
    try:
        works = search_works_by_text(query_text, per_page, max_pages)
        if not works:
            print("⚠️  No se encontraron works para esta query")
            return pd.DataFrame(columns=['source_id', 'freq', 'display_name'])
    except Exception as e:
        print(f"❌ Error al descargar works: {e}")
        raise
    
    print()
    
    # Paso 2: Extraer sources y contar frecuencias
    print("PASO 2: Extrayendo fuentes y calculando frecuencias...")
    print("-" * 70)
    source_ids = []
    source_names_map = {}
    
    for work in works:
        source_id, source_name = extract_source_info(work)
        if source_id:
            source_ids.append(source_id)
            source_names_map[source_id] = source_name
    
    source_counts = Counter(source_ids)
    print(f"✅ {len(source_counts)} fuentes únicas encontradas")
    print(f"   Top 3: {source_counts.most_common(3)}")
    print()
    
    # Paso 3: Upsert sources a MySQL
    print("PASO 3: Actualizando tabla 'sources' en MySQL...")
    print("-" * 70)
    engine = get_engine()
    sources_updated = 0
    source_display_name_map = {}
    
    for source_id in source_counts.keys():
        try:
            # Obtener info completa de OpenAlex
            source_data = get_source(source_id)
            source_display_name_map[source_id] = source_data.get('display_name', '') if source_data else ''
            if not source_data:
                continue
            
            # Preparar datos para MySQL
            source_row = {
                'source_id': source_id,
                'display_name': source_data.get('display_name', ''),
                'issn_l': source_data.get('issn_l', None),
                'country_code': source_data.get('country_code', None),
                'publisher': source_data.get('host_organization_name', None),
                'type': source_data.get('type', None),
                'works_count': source_data.get('works_count', 0),
                'cited_by_count': source_data.get('cited_by_count', 0),
                'updated_date': datetime.utcnow()
            }
            
            # UPSERT: insertar o actualizar si existe
            df_source = pd.DataFrame([source_row])
            df_source.to_sql(
                'sources',
                engine,
                if_exists='append',
                index=False,
                method='multi'
            )
            sources_updated += 1
            
        except Exception as e:
            # Si falla por duplicado, intentar update
            try:
                with engine.connect() as conn:
                    update_sql = f"""
                    UPDATE sources SET
                        display_name = '{source_data.get('display_name', '').replace("'", "''")}',
                        works_count = {source_data.get('works_count', 0)},
                        cited_by_count = {source_data.get('cited_by_count', 0)},
                        updated_date = NOW()
                    WHERE source_id = '{source_id}'
                    """
                    conn.execute(text(update_sql))
                    conn.commit()
                    sources_updated += 1
            except Exception as e2:
                print(f"  ⚠️  No se pudo actualizar source {source_id}: {e2}")
    
    print(f"✅ {sources_updated} sources actualizados/insertados")
    print()
    
    # Paso 4: Insertar works_sample
    print("PASO 4: Insertando works en tabla 'works_sample'...")
    print("-" * 70)
    works_data = []
    
    for work in works:
        source_id, source_name = extract_source_info(work)
        
        work_row = {
            'work_id': work.get('id', '').split('/')[-1],
            'title': work.get('title', '')[:1000],  # Limitar título
            'publication_year': work.get('publication_year', None),
            'cited_by_count': work.get('cited_by_count', 0),
            'source_id': source_id,
            'source_name': source_name[:500] if source_name else None
        }
        works_data.append(work_row)
    
    try:
        df_works = pd.DataFrame(works_data)
        # Eliminar duplicados por work_id
        df_works = df_works.drop_duplicates(subset=['work_id'])
        
        # Insertar (ignorar duplicados)
        df_works.to_sql(
            'works_sample',
            engine,
            if_exists='append',
            index=False,
            method='multi'
        )
        print(f"✅ {len(df_works)} works insertados")
    except Exception as e:
        print(f"⚠️  Algunos works ya existían (esto es normal): {e}")
    
    print()
    
    # Paso 5: Crear DataFrame de candidatos
    print("PASO 5: Generando DataFrame de candidatos...")
    print("-" * 70)
    candidates = []
    for source_id, freq in source_counts.items():
        candidates.append({
            'source_id': source_id,
            'freq': freq,
            'display_name': source_display_name_map.get(source_id) or source_names_map.get(source_id, '') or source_id
        })
    
    df_candidates = pd.DataFrame(candidates)
    df_candidates = df_candidates.sort_values('freq', ascending=False)
    
    print(f"✅ {len(df_candidates)} candidatos generados")
    print()
    print("=" * 70)
    print("PIPELINE COMPLETADO")
    print("=" * 70)
    
    return df_candidates


if __name__ == "__main__":
    # Test del pipeline
    query = "machine learning natural language processing"
    print(f"Testing pipeline con query: '{query}'")
    print()
    
    df = load_works_and_sources(query, per_page=100, max_pages=1)
    
    print("\nResultados:")
    print(df.head(10))
