"""
Módulo para calcular scores/rankings de revistas.
"""
import pandas as pd
import numpy as np
import sys
import os

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_engine


def calculate_scores(df_candidates):
    """
    Calcula scores de recomendación para cada revista candidata.
    
    Fórmula:
        score = 0.6 * freq_norm + 0.2 * log(cited_by_count + 1) + 0.2 * log(works_count + 1)
    
    Args:
        df_candidates (pd.DataFrame): DataFrame con columnas ['source_id', 'freq', ...]
        
    Returns:
        pd.DataFrame: DataFrame con columnas adicionales ['score', 'why', 'rank_position']
    """
    if df_candidates.empty:
        return df_candidates
    
    # Asegurar que existe la columna display_name
    if 'display_name' not in df_candidates.columns:
        df_candidates['display_name'] = ''
    
    print("Calculando scores de recomendación...")
    print("-" * 70)
    
    # Obtener engine para consultas a MySQL
    engine = get_engine()
    
    # Enriquecer con datos de MySQL (incluye LEFT JOIN con SJR)
    source_ids = df_candidates['source_id'].tolist()
    source_ids_str = "','".join(source_ids)
    
    query = f"""
    SELECT 
        s.source_id,
        s.display_name,
        s.works_count,
        s.cited_by_count,
        s.two_yr_mean_citedness,
        s.works_ref_year,
        s.cites_ref_year,
        s.type,
        s.publisher,
        s.country_code,
        s.issn_l,
        sjr.quartile,
        sjr.sjr
    FROM sources s
    LEFT JOIN sjr_2024 sjr
        ON REPLACE(s.issn_l, '-', '') = sjr.issn_norm
    WHERE s.source_id IN ('{source_ids_str}')
    """
    
    df_sources = pd.read_sql(query, engine)
    
    # Merge con candidatos
    df = df_candidates.merge(df_sources, on='source_id', how='left', suffixes=('_original', ''))
    
    # Rellenar NaN y manejar display_name correctamente
    df['works_count'] = df['works_count'].fillna(0)
    df['cited_by_count'] = df['cited_by_count'].fillna(0)
    df['two_yr_mean_citedness'] = df['two_yr_mean_citedness'].fillna(0)
    df['works_ref_year'] = df['works_ref_year'].fillna(0)
    df['cites_ref_year'] = df['cites_ref_year'].fillna(0)
    
    # Asegurar display_name: priorizar el de MySQL (sin sufijo), luego el original
    if 'display_name' not in df.columns:
        if 'display_name_original' in df.columns:
            df['display_name'] = df['display_name_original']
        else:
            df['display_name'] = ''
    # Si display_name tiene NaN, rellenar con display_name_original si existe
    if 'display_name_original' in df.columns:
        df['display_name'] = df['display_name'].fillna(df['display_name_original'])
    df['display_name'] = df['display_name'].fillna('')
    
    # Normalizar frecuencia (0-1)
    max_freq = df['freq'].max()
    df['freq_norm'] = df['freq'] / max_freq if max_freq > 0 else 0
    
    # Normalizar two_yr_mean_citedness
    max_two_yr = df['two_yr_mean_citedness'].max()
    df['two_yr_norm'] = df['two_yr_mean_citedness'] / max_two_yr if max_two_yr > 0 else 0
    
    # Normalizar works_ref_year
    max_works_ref = df['works_ref_year'].max()
    df['works_ref_norm'] = df['works_ref_year'] / max_works_ref if max_works_ref > 0 else 0
    
    # Normalizar cites_ref_year
    max_cites_ref = df['cites_ref_year'].max()
    df['cites_ref_norm'] = df['cites_ref_year'] / max_cites_ref if max_cites_ref > 0 else 0
    
    # Score final (nueva fórmula: incluye citas del año de referencia)
    df['score'] = (
        0.75 * df['freq_norm'] +
        0.15 * df['two_yr_norm'] +
        0.05 * df['works_ref_norm'] +
        0.05 * df['cites_ref_norm']
    )
    
    # Generar explicación 'why'
    df['why'] = df.apply(lambda row: generate_explanation(row), axis=1)
    
    # Ordenar por score descendente y asignar rank
    df = df.sort_values('score', ascending=False)
    df['rank_position'] = range(1, len(df) + 1)
    
    # Limpiar columnas intermedias
    columns_to_keep = [
        'rank_position', 'source_id', 'display_name', 'score', 'why',
        'freq', 'works_count', 'cited_by_count', 'two_yr_mean_citedness',
        'works_ref_year', 'cites_ref_year', 'type', 'publisher', 'country_code',
        'quartile', 'sjr', 'issn_l'
    ]
    df = df[[col for col in columns_to_keep if col in df.columns]]
    
    print(f"✅ Scores calculados para {len(df)} revistas")
    print(f"   Top score: {df['score'].max():.4f}")
    print(f"   Score promedio: {df['score'].mean():.4f}")
    print()
    
    return df


def generate_explanation(row):
    """
    Genera una explicación breve del por qué de la recomendación.
    Muestra cuántas veces aparece la revista en los resultados y actividad reciente.
    
    Args:
        row (pd.Series): Fila del DataFrame con datos de una revista
        
    Returns:
        str: Texto explicativo con frecuencia y métricas clave
    """
    freq = int(row.get("freq", 0) or 0)
    works_ref = int(row.get("works_ref_year", 0) or 0)
    cites_ref = int(row.get("cites_ref_year", 0) or 0)
    
    # Parte principal: frecuencia
    if freq == 1:
        base_text = "Aparece 1 vez en los resultados"
    else:
        base_text = f"Aparece {freq} veces en los resultados"
    
    # Añadir actividad reciente si hay datos
    activity_parts = []
    if works_ref > 0:
        activity_parts.append(f"{works_ref} trabajos (año ref)")
    if cites_ref > 0:
        activity_parts.append(f"{cites_ref} citas (año ref)")
    
    if activity_parts:
        return f"{base_text} | {', '.join(activity_parts)}"
    else:
        return base_text


def get_top_recommendations(df_ranked, top_n=10):
    """
    Obtiene las top N recomendaciones.
    
    Args:
        df_ranked (pd.DataFrame): DataFrame con scores calculados
        top_n (int): Número de recomendaciones a retornar
        
    Returns:
        pd.DataFrame: Top N revistas
    """
    return df_ranked.head(top_n)


if __name__ == "__main__":
    # Test del ranker
    print("Testing ranker...")
    print()
    
    # Crear datos de prueba
    test_data = {
        'source_id': ['S1', 'S2', 'S3'],
        'freq': [10, 5, 3],
        'display_name': ['Journal A', 'Journal B', 'Journal C']
    }
    df_test = pd.DataFrame(test_data)
    
    print("Datos de entrada:")
    print(df_test)
    print()
    
    # Este test fallará sin datos en MySQL, pero muestra el uso
    try:
        df_ranked = calculate_scores(df_test)
        print("\nResultados:")
        print(df_ranked)
    except Exception as e:
        print(f"Error (esperado sin MySQL configurado): {e}")
