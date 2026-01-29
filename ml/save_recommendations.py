"""
Módulo para guardar recomendaciones en MySQL.
"""
import pandas as pd
from datetime import datetime
import sys
import os
from sqlalchemy import text

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_engine


def save_query_and_recommendations(query_text, df_ranked):
    """
    Guarda una query y sus recomendaciones en MySQL.
    
    Args:
        query_text (str): Texto de la consulta realizada
        df_ranked (pd.DataFrame): DataFrame con recomendaciones rankeadas
        
    Returns:
        int: query_id generado
        
    Raises:
        Exception: Si falla el guardado
    """
    if df_ranked.empty:
        print("⚠️  No hay recomendaciones para guardar")
        return None
    
    print("Guardando recomendaciones en MySQL...")
    print("-" * 70)
    
    engine = get_engine()
    
    try:
        with engine.begin() as conn:
            # 1. Insertar query_run
            insert_query_sql = text("""
            INSERT INTO query_runs (query_text, created_at)
            VALUES (:query_text, :created_at)
            """)
            result = conn.execute(
                insert_query_sql,
                {'query_text': query_text, 'created_at': datetime.utcnow()}
            )
            query_id = result.lastrowid
            
            print(f"✅ Query guardada con ID: {query_id}")
            
            # 2. Borrar recomendaciones previas de esta query (por si existe)
            conn.execute(
                text("DELETE FROM recommendations WHERE query_id = :qid"),
                {"qid": query_id}
            )
            
            # 3. Preparar recomendaciones
            recommendations = []
            for _, row in df_ranked.iterrows():
                rec = {
                    'query_id': query_id,
                    'source_id': row['source_id'],
                    'rank_position': int(row['rank_position']),
                    'score': float(row['score']),
                    'why': row.get('why', '')[:1000],  # Limitar texto
                    'created_at': datetime.utcnow()
                }
                recommendations.append(rec)
            
            # 4. Insertar recomendaciones una a una (más estable)
            insert_sql = text("""
            INSERT INTO recommendations (query_id, source_id, rank_position, score, why, created_at)
            VALUES (:query_id, :source_id, :rank_position, :score, :why, :created_at)
            """)
            
            for rec in recommendations:
                conn.execute(insert_sql, rec)
            
            print(f"✅ {len(recommendations)} recomendaciones guardadas")
            print()
            
            return query_id
            
    except Exception as e:
        print(f"❌ Error al guardar recomendaciones: {e}")
        raise


def get_query_history(limit=10):
    """
    Obtiene el historial de queries realizadas.
    
    Args:
        limit (int): Número máximo de queries a retornar
        
    Returns:
        pd.DataFrame: Historial de queries
    """
    engine = get_engine()
    
    query = text(f"""
    SELECT 
        query_id,
        query_text,
        created_at,
        (SELECT COUNT(*) FROM recommendations WHERE query_id = q.query_id) as num_recommendations
    FROM query_runs q
    ORDER BY created_at DESC
    LIMIT {limit}
    """)
    
    df = pd.read_sql(query, engine)
    return df


def get_recommendations_by_query(query_id):
    """
    Obtiene las recomendaciones de una query específica.
    
    Args:
        query_id (int): ID de la query
        
    Returns:
        pd.DataFrame: Recomendaciones con información de las revistas
    """
    engine = get_engine()
    
    query = text(f"""
    SELECT 
        r.rank_position,
        r.source_id,
        s.display_name,
        r.score,
        r.why,
        s.type,
        s.publisher,
        s.works_count,
        s.cited_by_count,
        r.created_at
    FROM recommendations r
    LEFT JOIN sources s ON r.source_id = s.source_id
    WHERE r.query_id = {query_id}
    ORDER BY r.rank_position ASC
    """)
    
    df = pd.read_sql(query, engine)
    return df


if __name__ == "__main__":
    # Test
    print("Testing save_recommendations...")
    print()
    
    # Datos de prueba
    test_query = "test query for machine learning"
    test_recs = pd.DataFrame({
        'rank_position': [1, 2, 3],
        'source_id': ['S123', 'S456', 'S789'],
        'score': [0.95, 0.85, 0.75],
        'why': ['Reason 1', 'Reason 2', 'Reason 3']
    })
    
    try:
        query_id = save_query_and_recommendations(test_query, test_recs)
        print(f"\nQuery ID guardado: {query_id}")
        
        # Obtener historial
        print("\nHistorial de queries:")
        df_history = get_query_history(limit=5)
        print(df_history)
        
    except Exception as e:
        print(f"Error (esperado sin MySQL configurado): {e}")
