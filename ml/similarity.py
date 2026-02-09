"""
Módulo para calcular similitud entre revistas basado en perfiles numéricos.
"""
import pandas as pd
import numpy as np
import json
import requests
from datetime import datetime
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import text
import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_engine
import config


def search_openalex_sources(filter_param=None, search_param=None, per_page=20):
    """
    Busca sources en OpenAlex API.
    
    Args:
        filter_param (str): Parámetro filter (ej: "issn:12345678")
        search_param (str): Parámetro search (ej: "Nature")
        per_page (int): Resultados por página
        
    Returns:
        list: Lista de sources encontrados
    """
    try:
        base_url = config.OPENALEX_BASE_URL
        email = config.OPENALEX_EMAIL
        url = f"{base_url}/sources"
        
        params = {'per-page': per_page}
        if email:
            params['mailto'] = email
        if filter_param:
            params['filter'] = filter_param
        if search_param:
            params['search'] = search_param
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get('results', [])
    except Exception as e:
        print(f"  ⚠️  Error buscando en OpenAlex: {e}")
        return []


def upsert_source_to_mysql(source_data):
    """
    Guarda o actualiza un source en MySQL.
    
    Args:
        source_data (dict): Datos del source desde OpenAlex
        
    Returns:
        bool: True si se guardó exitosamente
    """
    try:
        engine = get_engine()
        
        # Extraer datos
        source_id = source_data.get('id', '').split('/')[-1]
        if not source_id:
            return False
        
        # Calcular año de referencia
        ref_year = datetime.utcnow().year - 4
        
        # Buscar datos del año de referencia
        works_ref_year = 0
        cites_ref_year = 0
        for year_entry in source_data.get('counts_by_year', []):
            if year_entry.get('year') == ref_year:
                works_ref_year = year_entry.get('works_count', 0) or 0
                cites_ref_year = year_entry.get('cited_by_count', 0) or 0
                break
        
        # Extraer métricas
        two_yr_mean_citedness = source_data.get('summary_stats', {}).get('2yr_mean_citedness', None)
        
        # Extraer topics
        topics = source_data.get("topics", []) or source_data.get("topic_share", []) or []
        topics_json = json.dumps(topics) if topics else None
        
        # Preparar datos
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
        }
        
        # UPSERT usando INSERT ... ON DUPLICATE KEY UPDATE
        with engine.begin() as conn:
            # Intentar INSERT primero
            try:
                df_source = pd.DataFrame([source_row])
                df_source.to_sql('sources', engine, if_exists='append', index=False, method='multi')
            except:
                # Si falla por duplicado, hacer UPDATE
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
                    'display_name': source_row['display_name'],
                    'issn_l': source_row['issn_l'],
                    'country_code': source_row['country_code'],
                    'publisher': source_row['publisher'],
                    'type_val': source_row['type'],
                    'works_count': source_row['works_count'],
                    'cited_by_count': source_row['cited_by_count'],
                    'ref_year': source_row['ref_year'],
                    'works_ref_year': source_row['works_ref_year'],
                    'cites_ref_year': source_row['cites_ref_year'],
                    'two_yr_mean_citedness': source_row['two_yr_mean_citedness'],
                    'topics_json': source_row['topics_json'],
                    'source_id': source_id
                })
        
        return True
    except Exception as e:
        print(f"  ⚠️  Error guardando source en MySQL: {e}")
        return False


def extract_top_topics(topics_json, top_k=10):
    """
    Extrae los top K topic IDs de un JSON de topics.
    
    Args:
        topics_json (str): JSON string con lista de topics
        top_k (int): Número de topics a extraer
        
    Returns:
        set: Conjunto de topic IDs (ej: {'T10521', 'T11234'})
    """
    if not topics_json or pd.isna(topics_json):
        return set()
    
    try:
        topics = json.loads(topics_json)
        if not isinstance(topics, list):
            return set()
        
        # Extraer IDs de topics (formato: "https://openalex.org/T10521" -> "T10521")
        topic_ids = set()
        for topic in topics[:top_k]:
            if isinstance(topic, dict):
                topic_id = topic.get('id', '')
                if topic_id:
                    # Extraer parte final del URL
                    topic_id = topic_id.split('/')[-1]
                    if topic_id.startswith('T'):
                        topic_ids.add(topic_id)
        
        return topic_ids
    except (json.JSONDecodeError, TypeError, AttributeError):
        return set()


def jaccard_similarity(set1, set2):
    """
    Calcula la similitud de Jaccard entre dos conjuntos.
    
    Args:
        set1 (set): Primer conjunto
        set2 (set): Segundo conjunto
        
    Returns:
        float: Similitud Jaccard (0.0 a 1.0)
    """
    if not set1 or not set2:
        return 0.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0


def find_similar_sources(source_id, top_n=10, use_thematic=False):
    """
    Encuentra revistas similares basándose en perfil numérico y opcionalmente temático.
    
    Usa las siguientes métricas para calcular similitud:
    - two_yr_mean_citedness: Impacto normalizado (2 años)
    - works_ref_year: Actividad reciente
    - cites_ref_year: Citas recientes
    - works_count: Productividad total (opcional)
    - cited_by_count: Impacto total (opcional)
    - topics_json: Temas (si use_thematic=True)
    
    Método:
    1. Normalización (z-score)
    2. Similitud de coseno (numérica)
    3. Similitud Jaccard (temática, si use_thematic=True)
    4. Combinación: 0.7*numeric + 0.3*thematic (si use_thematic=True)
    5. Retorna top N más similares
    
    Args:
        source_id (str): ID de la revista de referencia
        top_n (int): Número de revistas similares a retornar
        use_thematic (bool): Si True, usa similitud temática además de numérica
        
    Returns:
        pd.DataFrame: DataFrame con columnas ['source_id', 'display_name', 'similarity', 'why']
        
    Raises:
        ValueError: Si source_id no existe en la base de datos
        Exception: Si hay error en el proceso
    """
    print(f"Buscando revistas similares a: {source_id}")
    if use_thematic:
        print("  🎯 Usando similitud numérica + temática")
    else:
        print("  📈 Usando solo similitud numérica")
    print("-" * 70)
    
    engine = get_engine()
    
    # 1. Obtener datos de la revista de referencia
    query_ref = """
    SELECT 
        s.source_id,
        s.display_name,
        s.two_yr_mean_citedness,
        s.works_ref_year,
        s.cites_ref_year,
        s.works_count,
        s.cited_by_count,
        s.type,
        s.publisher,
        s.country_code,
        s.issn_l,
        s.topics_json,
        sjr.quartile,
        sjr.sjr
    FROM sources s
    LEFT JOIN sjr_2024 sjr
        ON REPLACE(s.issn_l, '-', '') = sjr.issn_norm
    WHERE s.source_id = %s
    """
    
    df_ref = pd.read_sql(query_ref, engine, params=(source_id,))
    
    if df_ref.empty:
        raise ValueError(f"No se encontró la revista con source_id: {source_id}")
    
    # 2. Obtener todas las revistas para comparación
    query_all = """
    SELECT 
        s.source_id,
        s.display_name,
        s.two_yr_mean_citedness,
        s.works_ref_year,
        s.cites_ref_year,
        s.works_count,
        s.cited_by_count,
        s.type,
        s.publisher,
        s.country_code,
        s.issn_l,
        s.topics_json,
        sjr.quartile,
        sjr.sjr
    FROM sources s
    LEFT JOIN sjr_2024 sjr
        ON REPLACE(s.issn_l, '-', '') = sjr.issn_norm
    WHERE s.source_id != %s
    """
    
    df_all = pd.read_sql(query_all, engine, params=(source_id,))
    
    if df_all.empty:
        print("⚠️  No hay otras revistas en la base de datos para comparar")
        return pd.DataFrame(columns=['source_id', 'display_name', 'similarity', 'why'])
    
    # 3. Definir features para similitud
    feature_cols = [
        'two_yr_mean_citedness',
        'works_ref_year',
        'cites_ref_year',
        'works_count',
        'cited_by_count'
    ]
    
    # Combinar ref + all para normalizar juntos
    df_combined = pd.concat([df_ref, df_all], ignore_index=True)
    
    # Rellenar NaN con 0
    for col in feature_cols:
        df_combined[col] = df_combined[col].fillna(0)
    
    # 4. Normalizar features (z-score)
    scaler = StandardScaler()
    features_normalized = scaler.fit_transform(df_combined[feature_cols])
    
    # Separar ref de las demás
    ref_features = features_normalized[0:1]  # Primera fila (la referencia)
    all_features = features_normalized[1:]   # Resto
    
    # 5. Calcular similitud de coseno
    similarities = cosine_similarity(ref_features, all_features)[0]
    
    # 6. Añadir similitudes al DataFrame
    df_all['numeric_similarity'] = similarities
    
    # 7. Calcular similitud temática si está activada
    if use_thematic:
        # Extraer topics de la referencia
        ref_topics = extract_top_topics(df_ref.iloc[0]['topics_json'], top_k=10)
        
        # Calcular similitud Jaccard para cada revista
        thematic_sims = []
        topic_overlaps = []
        for idx, row in df_all.iterrows():
            candidate_topics = extract_top_topics(row['topics_json'], top_k=10)
            jaccard_sim = jaccard_similarity(ref_topics, candidate_topics)
            thematic_sims.append(jaccard_sim)
            
            # Guardar overlap para explicación
            overlap = len(ref_topics & candidate_topics)
            topic_overlaps.append(overlap)
        
        df_all['thematic_similarity'] = thematic_sims
        df_all['topic_overlap'] = topic_overlaps
        
        # Guardar similitud numérica base
        df_all['similarity_score'] = df_all['numeric_similarity']
        
        # Combinar similitudes: 70% numérica + 30% temática
        df_all['final_similarity'] = 0.7 * df_all['numeric_similarity'] + 0.3 * df_all['thematic_similarity']
        
        # Ordenar por similitud final
        sort_column = 'final_similarity'
    else:
        # Solo similitud numérica
        df_all['similarity_score'] = df_all['numeric_similarity']
        df_all['thematic_similarity'] = None
        df_all['final_similarity'] = None
        df_all['topic_overlap'] = 0
        
        # Ordenar por similitud numérica
        sort_column = 'similarity_score'
    
    # 8. Ordenar por similitud descendente
    df_similar = df_all.sort_values(sort_column, ascending=False).head(top_n)
    
    # Mantener columna 'similarity' para compatibilidad
    df_similar['similarity'] = df_similar[sort_column]
    
    # 8. Generar explicación
    ref_row = df_ref.iloc[0]
    ref_topics_for_explain = extract_top_topics(ref_row['topics_json'], top_k=10)
    df_similar['why'] = df_similar.apply(
        lambda row: generate_similarity_explanation(row, ref_row, use_thematic, ref_topics_for_explain), 
        axis=1
    )
    
    # 9. Seleccionar columnas finales
    base_columns = [
        'source_id', 'display_name', 'similarity_score', 'why',
        'two_yr_mean_citedness', 'works_ref_year', 'cites_ref_year',
        'works_count', 'cited_by_count', 'type', 'publisher', 'country_code',
        'quartile', 'sjr', 'issn_l', 'similarity'
    ]
    
    # Añadir columnas de similitud temática si están disponibles
    if use_thematic:
        base_columns.insert(3, 'thematic_similarity')
        base_columns.insert(4, 'final_similarity')
    
    result = df_similar[base_columns].copy()
    
    # Agregar rank
    result.insert(0, 'rank_position', range(1, len(result) + 1))
    
    print(f"✅ {len(result)} revistas similares encontradas")
    print(f"   Similitud promedio: {result['similarity'].mean():.4f}")
    print(f"   Similitud máxima: {result['similarity'].max():.4f}")
    print()
    
    return result


def generate_similarity_explanation(row, ref_row, use_thematic=False, ref_topics=None):
    """
    Genera explicación basada en similitud de perfil numérico y/o temático.
    
    Args:
        row (pd.Series): Revista candidata similar
        ref_row (pd.Series): Revista de referencia
        use_thematic (bool): Si se usó similitud temática
        ref_topics (set): Topics de la revista de referencia
        
    Returns:
        str: Texto explicativo de la similitud
    """
    if use_thematic and 'topic_overlap' in row and ref_topics:
        overlap = int(row.get('topic_overlap', 0))
        total_topics = len(ref_topics)
        if overlap > 0 and total_topics > 0:
            return f"Perfil numérico similar (impacto y actividad recientes). Comparten {overlap}/{total_topics} topics principales"
    
    return "Perfil numérico similar (impacto y actividad recientes)"


def search_sources_by_issn(issn):
    """
    Busca revistas por ISSN-L. Si no encuentra en MySQL, busca en OpenAlex.
    
    Args:
        issn (str): ISSN a buscar (con o sin guiones)
        
    Returns:
        pd.DataFrame: DataFrame con revistas encontradas
    """
    engine = get_engine()
    
    # Normalizar ISSN: extraer solo dígitos y X
    issn_clean = ''.join(c for c in issn.upper() if c.isdigit() or c == 'X')
    
    # Si tiene 8 caracteres, formatear como XXXX-XXXX para OpenAlex
    if len(issn_clean) == 8:
        issn_dash = f"{issn_clean[:4]}-{issn_clean[4:]}"
    else:
        issn_dash = issn_clean
    
    print(f"\n🔍 Buscando ISSN: {issn_dash} (normalizado: {issn_clean})")
    
    # Buscar en MySQL usando ISSN normalizado (sin guion)
    query = """
    SELECT 
        s.source_id,
        s.display_name,
        s.issn_l,
        s.type,
        s.publisher,
        s.country_code,
        s.works_count,
        s.cited_by_count,
        s.two_yr_mean_citedness,
        sjr.quartile,
        sjr.sjr
    FROM sources s
    LEFT JOIN sjr_2024 sjr
        ON REPLACE(s.issn_l, '-', '') = sjr.issn_norm
    WHERE REPLACE(s.issn_l, '-', '') = %s
    """
    
    print("  💾 Consultando base de datos local...")
    df = pd.read_sql(query, engine, params=(issn_clean,))
    
    if not df.empty:
        print(f"  ✅ Encontrado en MySQL: {len(df)} resultado(s)")
        return df
    
    # Si no hay resultados en MySQL, buscar en OpenAlex por external ID
    print(f"  ⚠️  No se encontró ISSN {issn_dash} en MySQL.")
    print(f"  🌐 Consultando OpenAlex: /sources/issn:{issn_dash}")
    
    try:
        base_url = config.OPENALEX_BASE_URL
        email = config.OPENALEX_EMAIL
        
        # Usar endpoint directo: /sources/issn:XXXX-XXXX
        url = f"{base_url}/sources/issn:{issn_dash}"
        
        params = {}
        if email:
            params['mailto'] = email
        
        response = requests.get(url, params=params, timeout=30)
        
        # Manejar diferentes status codes
        if response.status_code == 404:
            print(f"  ❌ ISSN {issn_dash} no encontrado en OpenAlex (404)")
            return pd.DataFrame()
        
        if response.status_code != 200:
            print(f"  ❌ Error HTTP {response.status_code} desde OpenAlex")
            print(f"  Response body: {response.text[:500]}")
            return pd.DataFrame()
        
        # Respuesta 200: parsear el source
        source_data = response.json()
        
        if not source_data or not source_data.get('id'):
            print(f"  ❌ OpenAlex devolvió respuesta vacía para ISSN {issn_dash}")
            return pd.DataFrame()
        
        print(f"  ✅ Encontrado source en OpenAlex: {source_data.get('display_name', 'Sin nombre')}")
        print(f"  💾 Guardando en MySQL...")
        
        # UPSERT del source encontrado
        try:
            if upsert_source_to_mysql(source_data):
                print(f"  ✅ Source guardado en MySQL")
            else:
                print(f"  ⚠️  No se pudo guardar el source")
        except Exception as e:
            print(f"  ⚠️  Error guardando source: {e}")
        
        # IMPORTANTE: Volver a consultar MySQL después del upsert
        print("  🔄 Re-consultando MySQL...")
        df = pd.read_sql(query, engine, params=(issn_clean,))
        
        if not df.empty:
            print(f"  ✅ Éxito: {len(df)} resultado(s) ahora disponible(s)")
        else:
            print(f"  ⚠️  Advertencia: UPSERT exitoso pero la re-consulta no devolvió resultados")
        
        return df
        
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Error de red con OpenAlex: {e}")
        raise
    except Exception as e:
        print(f"  ❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        raise
    return df


def search_sources_by_name(name, limit=20):
    """
    Busca revistas por nombre (búsqueda parcial). Si no encuentra en MySQL, busca en OpenAlex.
    
    Args:
        name (str): Texto a buscar en display_name
        limit (int): Número máximo de resultados
        
    Returns:
        pd.DataFrame: DataFrame con revistas encontradas
    """
    engine = get_engine()
    
    # Búsqueda case-insensitive con LIKE
    query = f"""
    SELECT 
        s.source_id,
        s.display_name,
        s.issn_l,
        s.type,
        s.publisher,
        s.country_code,
        s.works_count,
        s.cited_by_count,
        s.two_yr_mean_citedness,
        sjr.quartile,
        sjr.sjr
    FROM sources s
    LEFT JOIN sjr_2024 sjr
        ON REPLACE(s.issn_l, '-', '') = sjr.issn_norm
    WHERE LOWER(s.display_name) LIKE LOWER(%s)
    ORDER BY s.works_count DESC
    LIMIT {limit}
    """
    
    search_pattern = f"%{name}%"
    df = pd.read_sql(query, engine, params=(search_pattern,))
    
    # Si no hay resultados en MySQL, buscar en OpenAlex
    if df.empty:
        print(f"  No se encontró '{name}' en MySQL. Buscando en OpenAlex...")
        sources = search_openalex_sources(search_param=name, per_page=limit)
        
        if sources:
            print(f"  ✓ Encontrados {len(sources)} sources en OpenAlex. Guardando en MySQL...")
            for source_data in sources:
                upsert_source_to_mysql(source_data)
            
            # Volver a consultar MySQL
            df = pd.read_sql(query, engine, params=(search_pattern,))
    
    return df


if __name__ == "__main__":
    # Test del módulo
    print("Testing similarity module...")
    print()
    
    # Test 1: Búsqueda por nombre
    print("Test 1: Búsqueda por nombre")
    df_search = search_sources_by_name("nature")
    print(f"Encontradas {len(df_search)} revistas con 'nature'")
    if not df_search.empty:
        print(df_search[['source_id', 'display_name']].head())
    print()
    
    # Test 2: Similitud (requiere source_id válido en MySQL)
    # Descomenta cuando tengas datos:
    # source_id_test = "S123456789"
    # df_similar = find_similar_sources(source_id_test, top_n=5)
    # print(df_similar[['rank_position', 'display_name', 'similarity']])
