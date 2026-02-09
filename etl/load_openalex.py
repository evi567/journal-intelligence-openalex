"""
Pipeline ETL para cargar datos de OpenAlex a MySQL.
"""
import pandas as pd
from datetime import datetime
from collections import Counter
import sys
import os
import json
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


def load_works_and_sources(query_text, per_page=None, max_pages=None, search_mode="title_abstract", top_sources_limit=None):
    """
    Pipeline completo: descarga works, extrae sources, upsert a MySQL.
    Incluye fallback automático de title_abstract a fulltext si 0 resultados.
    
    Args:
        query_text (str): Texto de búsqueda para OpenAlex
        per_page (int, optional): Works por página
        max_pages (int, optional): Páginas máximas a descargar
        search_mode (str, optional): "title_abstract" (preciso, default) o "fulltext" (amplio)
        top_sources_limit (int, optional): Número máximo de sources a enriquecer con llamadas API (default: config.TOP_SOURCES_LIMIT)
        
    Returns:
        tuple: (df_candidates, df_works, did_fallback)
            - df_candidates: DataFrame con candidatos (source_id, freq, display_name)
            - df_works: DataFrame con works (work_id, title, publication_year, cited_by_count, source_name, openalex_url)
            - did_fallback: bool indicando si se hizo fallback automático a fulltext
        
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
    top_sources_limit = top_sources_limit or config.TOP_SOURCES_LIMIT
    
    # Paso 1: Descargar works desde OpenAlex
    print("PASO 1: Descargando works desde OpenAlex...")
    print("-" * 70)
    try:
        # search_works_by_text ahora retorna tupla (works, did_fallback)
        works, did_fallback = search_works_by_text(query_text, per_page, max_pages, search_mode)
        
        if not works:
            print("⚠️  No se encontraron works para esta query")
            df_candidates_empty = pd.DataFrame(columns=['source_id', 'freq', 'display_name'])
            df_works_empty = pd.DataFrame(columns=['work_id', 'title', 'publication_year', 'cited_by_count', 'source_name', 'type', 'openalex_url'])
            return df_candidates_empty, df_works_empty, did_fallback
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
    
    # Paso 3: Upsert sources a MySQL (solo top sources)
    print("PASO 3: Actualizando tabla 'sources' en MySQL...")
    print("-" * 70)
    engine = get_engine()
    sources_updated = 0
    source_display_name_map = {}
    
    # Ordenar sources por frecuencia descendente y tomar solo top N
    top_sources = source_counts.most_common(top_sources_limit)
    print(f"  Enriqueciendo solo los top {len(top_sources)} sources por frecuencia (de {len(source_counts)} totales)")
    print(f"  Esto acelera el proceso evitando llamadas API innecesarias.\n")
    
    for source_id, freq in top_sources:
        try:
            # Obtener info completa de OpenAlex
            source_data = get_source(source_id)
            source_display_name_map[source_id] = source_data.get('display_name', '') if source_data else ''
            if not source_data:
                continue
            
            # Calcular año de referencia (4 años atrás)
            ref_year = datetime.utcnow().year - 4
            
            # Buscar datos del año de referencia en counts_by_year
            ref_year_data = None
            works_ref_year = 0  # Default 0 en lugar de None
            cites_ref_year = 0  # Default 0 en lugar de None
            for year_entry in source_data.get('counts_by_year', []):
                if year_entry.get('year') == ref_year:
                    ref_year_data = year_entry
                    works_ref_year = year_entry.get('works_count', 0) or 0
                    cites_ref_year = year_entry.get('cited_by_count', 0) or 0
                    break
            
            # Extraer two_yr_mean_citedness
            summary_stats = source_data.get('summary_stats') or {}
            two_yr_mean_citedness = summary_stats.get('2yr_mean_citedness')
            
            # Extraer topics para similitud temática (preparación)
            topics = source_data.get("topics", []) or source_data.get("topic_share", []) or []
            topics_json = json.dumps(topics) if topics else None
            
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
                'ref_year': ref_year,
                'two_yr_mean_citedness': two_yr_mean_citedness,
                'works_ref_year': works_ref_year,
                'cites_ref_year': cites_ref_year,
                'topics_json': topics_json,
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
            # Si falla por duplicado, intentar update completo
            if source_data:  # Evitar error si source_data es None
                try:
                    # UPDATE parametrizado con TODAS las columnas
                    with engine.begin() as conn:
                        update_sql = text("""
                        UPDATE sources SET
                            display_name = :display_name,
                            issn_l = :issn_l,
                            country_code = :country_code,
                            publisher = :publisher,
                            type = :type_val,
                            works_count = :works_count,
                            cited_by_count = :cited_by_count,
                            ref_year = :ref_year,
                            works_ref_year = :works_ref_year,
                            cites_ref_year = :cites_ref_year,
                            two_yr_mean_citedness = :two_yr_mean_citedness,
                            topics_json = :topics_json,
                            updated_date = NOW()
                        WHERE source_id = :source_id
                        """)
                        
                        conn.execute(update_sql, {
                            'display_name': source_data.get('display_name', ''),
                            'issn_l': source_data.get('issn_l', None),
                            'country_code': source_data.get('country_code', None),
                            'publisher': source_data.get('host_organization_name', None),
                            'type_val': source_data.get('type', None),
                            'works_count': source_data.get('works_count', 0),
                            'cited_by_count': source_data.get('cited_by_count', 0),
                            'ref_year': ref_year,
                            'works_ref_year': works_ref_year,
                            'cites_ref_year': cites_ref_year,
                            'two_yr_mean_citedness': two_yr_mean_citedness,
                            'topics_json': topics_json,
                            'source_id': source_id
                        })
                        sources_updated += 1
                except Exception as e2:
                    print(f"  ⚠️  No se pudo actualizar source {source_id}: {e2}")
            else:
                print(f"  ⚠️  source_data es None para {source_id}, no se puede actualizar")
    
    # Para sources no enriquecidos, usar display_name de source_names_map
    for source_id in source_counts.keys():
        if source_id not in source_display_name_map:
            source_display_name_map[source_id] = source_names_map.get(source_id, '') or source_id
    
    print(f"✅ {sources_updated} sources enriquecidos con llamadas API completas")
    print(f"   {len(source_counts) - sources_updated} sources adicionales usan display_name básico")
    print()
    
    # Paso 4: Insertar works_sample y preparar DataFrame de works
    print("PASO 4: Insertando works en tabla 'works_sample'...")
    print("-" * 70)
    # NOTA: Si la columna 'type' no existe en works_sample, ejecutar manualmente:
    # ALTER TABLE works_sample ADD COLUMN type VARCHAR(50) NULL;
    
    works_data = []
    
    for work in works:
        source_id, source_name = extract_source_info(work)
        work_id = work.get('id', '').split('/')[-1]
        
        # work_row para DB (sin relevance_score)
        work_row = {
            'work_id': work_id,
            'title': (work.get('title') or '')[:1000],  # Limitar título
            'publication_year': work.get('publication_year', None),
            'cited_by_count': work.get('cited_by_count', 0),
            'source_id': source_id,
            'source_name': source_name[:500] if source_name else None,
            'type': work.get('type'),  # Añadir tipo de trabajo
            'openalex_url': f"https://openalex.org/{work_id}" if work_id else None,
            'relevance_score': work.get('relevance_score')  # Mantener para df_works (display)
        }
        works_data.append(work_row)
    
    try:
        df_works = pd.DataFrame(works_data)
        # Eliminar duplicados por work_id
        df_works = df_works.drop_duplicates(subset=['work_id'])
        
        # Insertar en DB (sin 'openalex_url' ni 'relevance_score')
        df_works_insert = df_works.drop(columns=['openalex_url', 'relevance_score'])
        df_works_insert.to_sql(
            'works_sample',
            engine,
            if_exists='append',
            index=False,
            method='multi'
        )
        print(f"✅ {len(df_works)} works insertados")
    except Exception as e:
        print(f"⚠️  Algunos works ya existían (esto es normal): {e}")
        # Asegurar que df_works existe aunque falle la inserción
        if 'df_works' not in locals():
            df_works = pd.DataFrame(works_data)
            df_works = df_works.drop_duplicates(subset=['work_id'])
    
    print()
    
    # Paso 5: Crear DataFrame de candidatos
    print("PASO 5: Generando DataFrame de candidatos y works top...")
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
    
    # Preparar DataFrame de works top con ordenamiento inteligente
    df_works_top = df_works.copy()
    
    # FILTRO EXTRA: Si hubo fallback a fulltext, preferir works de journals
    if did_fallback:
        print("  Aplicando filtro: preferir works de journals (fulltext mode)")
        # Filtrar works que no tienen source_name o source_id
        df_works_top = df_works_top[df_works_top['source_id'].notna()]
        print(f"  → {len(df_works_top)} works con source válido")
    
    # ORDENAMIENTO INTELIGENTE POR RELEVANCIA
    # Verificar si existe relevance_score y tiene valores
    has_relevance = 'relevance_score' in df_works_top.columns and df_works_top['relevance_score'].notna().any()
    
    if has_relevance and did_fallback:
        # MODO FULLTEXT: Score mixto 70% relevancia + 30% citas
        print("  Ordenando por score mixto (70% relevancia + 30% citas)")
        
        # Normalizar relevance_score y cited_by_count
        max_rel = df_works_top['relevance_score'].max()
        max_cites = df_works_top['cited_by_count'].max()
        
        df_works_top['rel_norm'] = df_works_top['relevance_score'] / max_rel if max_rel > 0 else 0
        df_works_top['cites_norm'] = df_works_top['cited_by_count'] / max_cites if max_cites > 0 else 0
        
        # Score mixto
        df_works_top['work_score'] = 0.7 * df_works_top['rel_norm'].fillna(0) + 0.3 * df_works_top['cites_norm'].fillna(0)
        
        # Ordenar por work_score DESC
        df_works_top = df_works_top.sort_values('work_score', ascending=False)
        
    elif has_relevance:
        # MODO PRECISO: Ordenar por relevance_score (primario) y cited_by_count (desempate)
        print("  Ordenando por relevance_score (primario) + cited_by_count (desempate)")
        df_works_top = df_works_top.sort_values(
            ['relevance_score', 'cited_by_count'],
            ascending=[False, False],
            na_position='last'
        )
    else:
        # FALLBACK: Si no hay relevance_score, ordenar solo por citas
        print("  Ordenando por cited_by_count (fallback)")
        df_works_top = df_works_top.sort_values(
            ['cited_by_count', 'publication_year'],
            ascending=[False, False]
        )
    
    # Seleccionar columnas finales (incluyendo relevance_score si existe)
    base_columns = ['work_id', 'title', 'publication_year', 'cited_by_count', 'source_name', 'type', 'openalex_url']
    if has_relevance:
        base_columns.insert(4, 'relevance_score')  # Insertar después de publication_year
    
    df_works_top = df_works_top[base_columns]
    
    print(f"✅ {len(df_candidates)} candidatos generados")
    print(f"✅ {len(df_works_top)} works disponibles")
    print()
    print("=" * 70)
    print("PIPELINE COMPLETADO")
    print("=" * 70)
    
    return df_candidates, df_works_top, did_fallback


if __name__ == "__main__":
    # Test del pipeline
    query = "machine learning natural language processing"
    print(f"Testing pipeline con query: '{query}'")
    print()
    
    df_candidates, df_works = load_works_and_sources(query, per_page=100, max_pages=1)
    
    print("\nResultados - Candidatos:")
    print(df_candidates.head(10))
    
    print("\nResultados - Top Works:")
    print(df_works.head(10))
