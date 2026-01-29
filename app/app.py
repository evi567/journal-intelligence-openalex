"""
Aplicación Streamlit para recomendación de revistas científicas.
"""
import streamlit as st
import pandas as pd
import sys
import os
from sqlalchemy import text

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.load_openalex import load_works_and_sources
from ml.ranker import calculate_scores, get_top_recommendations
from ml.save_recommendations import save_query_and_recommendations
from db.connection import get_engine
import config


# Configuración de la página
st.set_page_config(
    page_title="Journal Intelligence",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)


def init_session_state():
    """Inicializa variables de sesión."""
    if 'recommendations' not in st.session_state:
        st.session_state.recommendations = None
    if 'query_executed' not in st.session_state:
        st.session_state.query_executed = False
    if 'last_query' not in st.session_state:
        st.session_state.last_query = ""


def get_source_detail(source_id):
    """
    Obtiene información detallada de una revista desde MySQL.
    
    Args:
        source_id (str): ID de la fuente
        
    Returns:
        dict: Diccionario con datos de la revista
    """
    try:
        engine = get_engine()
        df = pd.read_sql(
            text("SELECT * FROM sources WHERE source_id = :sid"),
            engine,
            params={"sid": source_id}
        )
        
        if df.empty:
            return None
        
        return df.iloc[0].to_dict()
        
    except Exception as e:
        st.error(f"Error al obtener detalles: {e}")
        return None


def main():
    """Función principal de la aplicación."""
    init_session_state()
    
    # Header
    st.title("📚 Journal Intelligence")
    st.markdown("### Sistema de Recomendación de Revistas Científicas")
    st.markdown("Basado en datos de **OpenAlex**")
    st.divider()
    
    # Sidebar con información
    with st.sidebar:
        st.header("ℹ️ Información")
        st.markdown("""
        Esta aplicación te ayuda a encontrar las revistas más relevantes 
        para publicar tu investigación.
        
        **Cómo funciona:**
        1. Ingresa información sobre tu investigación
        2. El sistema busca en OpenAlex
        3. Genera un ranking basado en:
           - Frecuencia de aparición
           - Citas totales
           - Trabajos publicados
        """)
        
        st.divider()
        
        st.header("⚙️ Configuración")
        per_page = st.slider("Resultados por página", 50, 200, 100, 50)
        max_pages = st.slider("Páginas máximas", 1, 5, 1)
        top_n = st.slider("Top N recomendaciones", 5, 20, 10)
        
        st.divider()
        
        # Test de conexión
        if st.button("🔌 Test Conexión MySQL"):
            try:
                engine = get_engine()
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT VERSION()"))
                    version = result.fetchone()[0]
                st.success(f"✅ Conectado a MySQL {version}")
            except Exception as e:
                st.error(f"❌ Error de conexión: {e}")
    
    # Formulario de consulta
    st.header("🔍 Ingresa tu Consulta")
    
    col1, col2 = st.columns(2)
    
    with col1:
        title = st.text_input(
            "Título de tu investigación",
            placeholder="Ej: Machine Learning for Natural Language Processing"
        )
    
    with col2:
        abstract = st.text_area(
            "Abstract (opcional)",
            placeholder="Ej: This research explores the application of deep learning...",
            height=100
        )
    
    # O campo único
    st.markdown("**O usa un solo campo:**")
    query_text = st.text_area(
        "Consulta libre",
        placeholder="Ej: machine learning NLP transformers BERT sentiment analysis",
        height=80
    )
    
    # Botón de búsqueda
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 3])
    
    with col_btn1:
        search_button = st.button("🚀 Recomendar Revistas", type="primary", use_container_width=True)
    
    with col_btn2:
        if st.button("🗑️ Limpiar", use_container_width=True):
            st.session_state.recommendations = None
            st.session_state.query_executed = False
            st.session_state.last_query = ""
            st.rerun()
    
    # Procesar búsqueda
    if search_button:
        # Construir query final
        final_query = query_text.strip()
        if not final_query:
            parts = []
            if title.strip():
                parts.append(title.strip())
            if abstract.strip():
                parts.append(abstract.strip())
            final_query = " ".join(parts)
        
        if not final_query:
            st.warning("⚠️ Por favor ingresa al menos un texto de búsqueda")
        else:
            st.session_state.last_query = final_query
            
            with st.spinner("🔄 Buscando en OpenAlex y calculando recomendaciones..."):
                try:
                    # Pipeline ETL + ML
                    df_candidates = load_works_and_sources(
                        final_query,
                        per_page=per_page,
                        max_pages=max_pages
                    )
                    
                    if df_candidates.empty:
                        st.warning("⚠️ No se encontraron resultados para esta búsqueda")
                        st.session_state.recommendations = None
                    else:
                        # Calcular scores
                        df_ranked = calculate_scores(df_candidates)
                        
                        # Obtener top N
                        df_top = get_top_recommendations(df_ranked, top_n=top_n)
                        
                        # Guardar en MySQL
                        query_id = save_query_and_recommendations(final_query, df_top)
                        
                        # Guardar en sesión
                        st.session_state.recommendations = df_top
                        st.session_state.query_executed = True
                        
                        st.success(f"✅ {len(df_top)} recomendaciones generadas (Query ID: {query_id})")
                
                except Exception as e:
                    st.error(f"❌ Error durante el proceso: {e}")
                    st.session_state.recommendations = None
    
    # Mostrar resultados
    if st.session_state.query_executed and st.session_state.recommendations is not None:
        st.divider()
        st.header("📊 Resultados")
        
        df_recs = st.session_state.recommendations
        
        st.markdown(f"**Query ejecutada:** _{st.session_state.last_query}_")
        st.markdown(f"**Total de recomendaciones:** {len(df_recs)}")
        
        # Tabla de recomendaciones
        st.subheader("Top Revistas Recomendadas")
        
        # Preparar DataFrame para mostrar
        df_display = df_recs[[
            'rank_position', 'display_name', 'score', 'freq', 
            'works_count', 'cited_by_count', 'why'
        ]].copy()
        
        df_display.columns = [
            'Rank', 'Revista', 'Score', 'Frecuencia',
            'Trabajos', 'Citas', 'Por qué'
        ]
        
        # Formatear números
        df_display['Score'] = df_display['Score'].apply(lambda x: f"{x:.4f}")
        df_display['Trabajos'] = df_display['Trabajos'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "N/A")
        df_display['Citas'] = df_display['Citas'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "N/A")
        
        # Mostrar tabla
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            height=400
        )
        
        # Selector para ver detalle
        st.divider()
        st.subheader("🔎 Ver Detalle de una Revista")
        
        revista_options = df_recs.apply(
            lambda row: f"{int(row['rank_position'])}. {row['display_name']}", axis=1
        ).tolist()
        
        selected_revista = st.selectbox(
            "Selecciona una revista:",
            options=revista_options
        )
        
        if selected_revista:
            # Extraer el rank del texto seleccionado
            selected_rank = int(selected_revista.split('.')[0])
            selected_row = df_recs[df_recs['rank_position'] == selected_rank].iloc[0]
            source_id = selected_row['source_id']
            
            # Obtener detalles completos
            source_detail = get_source_detail(source_id)
            
            if source_detail:
                col_a, col_b = st.columns(2)
                
                with col_a:
                    st.markdown("**Información General**")
                    st.write(f"**Nombre:** {source_detail.get('display_name', 'N/A')}")
                    st.write(f"**Tipo:** {source_detail.get('type', 'N/A')}")
                    st.write(f"**Publisher:** {source_detail.get('publisher', 'N/A')}")
                    st.write(f"**País:** {source_detail.get('country_code', 'N/A')}")
                    st.write(f"**ISSN-L:** {source_detail.get('issn_l', 'N/A')}")
                
                with col_b:
                    st.markdown("**Métricas**")
                    st.metric("Score de Recomendación", f"{selected_row['score']:.4f}")
                    st.metric("Total de Trabajos", f"{int(source_detail.get('works_count', 0)):,}")
                    st.metric("Total de Citas", f"{int(source_detail.get('cited_by_count', 0)):,}")
                    st.metric("Frecuencia en Búsqueda", f"{int(selected_row['freq'])}")
                
                st.markdown("**Explicación de la Recomendación:**")
                st.info(selected_row['why'])
                
                # Última actualización
                if source_detail.get('updated_date'):
                    st.caption(f"Última actualización: {source_detail['updated_date']}")
            else:
                st.warning("No se encontraron detalles para esta revista")


if __name__ == "__main__":
    main()
