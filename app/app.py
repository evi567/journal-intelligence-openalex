"""
Aplicación Streamlit para recomendación de revistas científicas.
"""
import streamlit as st
import pandas as pd
import sys
import os
import traceback
from sqlalchemy import text

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl.load_openalex import load_works_and_sources
from ml.ranker import calculate_scores, get_top_recommendations
from ml.save_recommendations import save_query_and_recommendations
from ml.similarity import find_similar_sources, search_sources_by_issn, search_sources_by_name
from db.connection import get_engine
import config


# Configuración de la página
st.set_page_config(
    page_title="Journal Intelligence",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)


def extract_keywords(text, top_n=15):
    """
    Extrae keywords relevantes de un texto (abstract).
    
    Args:
        text (str): Texto a procesar
        top_n (int): Número de keywords a retornar
        
    Returns:
        list: Lista de keywords más frecuentes
    """
    import re
    import string
    from collections import Counter
    
    # Stopwords español
    stopwords_es = {
        'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se', 'no', 'haber',
        'por', 'con', 'su', 'para', 'como', 'estar', 'tener', 'le', 'lo', 'todo',
        'pero', 'más', 'hacer', 'o', 'poder', 'decir', 'este', 'ir', 'otro', 'ese',
        'la', 'si', 'me', 'ya', 'ver', 'porque', 'dar', 'cuando', 'él', 'muy',
        'sin', 'vez', 'mucho', 'saber', 'qué', 'sobre', 'mi', 'alguno', 'mismo',
        'yo', 'también', 'hasta', 'año', 'dos', 'querer', 'entre', 'así', 'primero',
        'desde', 'grande', 'eso', 'ni', 'nos', 'llegar', 'pasar', 'tiempo', 'ella',
        'sí', 'día', 'uno', 'bien', 'poco', 'deber', 'entonces', 'poner', 'cosa',
        'tanto', 'hombre', 'parecer', 'nuestro', 'tan', 'donde', 'ahora', 'parte',
        'después', 'vida', 'quedar', 'siempre', 'creer', 'hablar', 'llevar', 'dejar',
        'nada', 'cada', 'seguir', 'menos', 'nuevo', 'encontrar', 'algo', 'solo',
        'del', 'los', 'las', 'una', 'unos', 'unas', 'al'
    }
    
    # Stopwords inglés
    stopwords_en = {
        'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it',
        'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at', 'this', 'but',
        'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she', 'or', 'an', 'will',
        'my', 'one', 'all', 'would', 'there', 'their', 'what', 'so', 'up', 'out',
        'if', 'about', 'who', 'get', 'which', 'go', 'me', 'when', 'make', 'can',
        'like', 'time', 'no', 'just', 'him', 'know', 'take', 'people', 'into',
        'year', 'your', 'good', 'some', 'could', 'them', 'see', 'other', 'than',
        'then', 'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also',
        'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first', 'well',
        'way', 'even', 'new', 'want', 'because', 'any', 'these', 'give', 'day',
        'most', 'us', 'is', 'was', 'are', 'been', 'has', 'had', 'were', 'said',
        'did', 'having', 'may', 'should', 'am', 'being'
    }
    
    # Palabras de ruido específicas
    noise_words = {
        'paper', 'study', 'results', 'method', 'methods', 'introduction',
        'conclusion', 'analysis', 'research', 'data', 'approach', 'using',
        'based', 'new', 'also', 'may', 'can', 'abstract', 'article',
        'presented', 'propose', 'proposed', 'show', 'shown', 'however',
        'therefore', 'thus', 'moreover', 'furthermore', 'additionally'
    }
    
    all_stopwords = stopwords_es | stopwords_en | noise_words
    
    # Limpiar texto
    text = text.lower()
    
    # Eliminar URLs
    text = re.sub(r'http\S+|www\S+', '', text)
    
    # Eliminar puntuación
    text = re.sub(f'[{re.escape(string.punctuation)}]', ' ', text)
    
    # Eliminar números
    text = re.sub(r'\d+', '', text)
    
    # Tokenizar y filtrar
    tokens = [
        word for word in text.split()
        if len(word) >= 3 and word not in all_stopwords
    ]
    
    # Contar frecuencias
    word_freq = Counter(tokens)
    
    # Retornar top N keywords
    top_keywords = [word for word, _ in word_freq.most_common(top_n)]
    
    return top_keywords


def extract_keywords_and_bigrams(text, top_unigrams=10, top_bigrams=5):
    """
    Extrae keywords (unigramas) y bigramas relevantes de un texto.
    100% NULL-SAFE: SIEMPRE retorna (list, list), nunca None.
    
    Args:
        text (str): Texto a procesar
        top_unigrams (int): Número de unigramas a retornar
        top_bigrams (int): Número de bigramas a retornar
        
    Returns:
        tuple: (list de unigramas, list de bigramas) - NUNCA None
    """
    import re
    import string
    from collections import Counter
    
    # NULL-SAFE: Verificar entrada
    if text is None or not isinstance(text, str):
        return ([], [])
    
    # NULL-SAFE: Verificar texto vacío después de strip
    text = text.strip()
    if not text:
        return ([], [])
    
    # Stopwords español
    stopwords_es = {
        'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se', 'no', 'haber',
        'por', 'con', 'su', 'para', 'como', 'estar', 'tener', 'le', 'lo', 'todo',
        'pero', 'más', 'hacer', 'o', 'poder', 'decir', 'este', 'ir', 'otro', 'ese',
        'la', 'si', 'me', 'ya', 'ver', 'porque', 'dar', 'cuando', 'él', 'muy',
        'sin', 'vez', 'mucho', 'saber', 'qué', 'sobre', 'mi', 'alguno', 'mismo',
        'yo', 'también', 'hasta', 'año', 'dos', 'querer', 'entre', 'así', 'primero',
        'desde', 'grande', 'eso', 'ni', 'nos', 'llegar', 'pasar', 'tiempo', 'ella',
        'sí', 'día', 'uno', 'bien', 'poco', 'deber', 'entonces', 'poner', 'cosa',
        'tanto', 'hombre', 'parecer', 'nuestro', 'tan', 'donde', 'ahora', 'parte',
        'después', 'vida', 'quedar', 'siempre', 'creer', 'hablar', 'llevar', 'dejar',
        'nada', 'cada', 'seguir', 'menos', 'nuevo', 'encontrar', 'algo', 'solo',
        'del', 'los', 'las', 'una', 'unos', 'unas', 'al'
    }
    
    # Stopwords inglés
    stopwords_en = {
        'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it',
        'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at', 'this', 'but',
        'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she', 'or', 'an', 'will',
        'my', 'one', 'all', 'would', 'there', 'their', 'what', 'so', 'up', 'out',
        'if', 'about', 'who', 'get', 'which', 'go', 'me', 'when', 'make', 'can',
        'like', 'time', 'no', 'just', 'him', 'know', 'take', 'people', 'into',
        'year', 'your', 'good', 'some', 'could', 'them', 'see', 'other', 'than',
        'then', 'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also',
        'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first', 'well',
        'way', 'even', 'new', 'want', 'because', 'any', 'these', 'give', 'day',
        'most', 'us', 'is', 'was', 'are', 'been', 'has', 'had', 'were', 'said',
        'did', 'having', 'may', 'should', 'am', 'being'
    }
    
    # Palabras de ruido específicas (SIN 'editorial', 'board' - son importantes para dominio académico)
    noise_words = {
        'paper', 'study', 'results', 'method', 'methods', 'introduction',
        'conclusion', 'analysis', 'research', 'data', 'approach', 'using',
        'based', 'new', 'also', 'may', 'can', 'abstract', 'article',
        'presented', 'propose', 'proposed', 'show', 'shown', 'however',
        'therefore', 'thus', 'moreover', 'furthermore', 'additionally'
    }
    
    all_stopwords = stopwords_es | stopwords_en | noise_words
    
    # Limpiar texto
    text = text.lower()
    
    # Eliminar URLs
    text = re.sub(r'http\S+|www\S+', '', text)
    
    # Eliminar puntuación
    text = re.sub(f'[{re.escape(string.punctuation)}]', ' ', text)
    
    # Eliminar números
    text = re.sub(r'\d+', '', text)
    
    # Tokenizar y filtrar
    tokens = [
        word for word in text.split()
        if len(word) >= 3 and word not in all_stopwords
    ]
    
    # NULL-SAFE: Si no hay tokens después de limpiar, retornar vacío
    if not tokens:
        return ([], [])
    
    # Contar frecuencias de unigramas
    unigram_freq = Counter(tokens)
    top_unigrams_list = [word for word, _ in unigram_freq.most_common(top_unigrams)]
    
    # Generar bigramas (pares de palabras consecutivas)
    bigrams = []
    # NULL-SAFE: Solo si hay al menos 2 tokens
    if len(tokens) >= 2:
        for i in range(len(tokens) - 1):
            word1, word2 = tokens[i], tokens[i + 1]
            # Filtrar si alguna palabra está en stopwords
            if word1 not in all_stopwords and word2 not in all_stopwords:
                bigram = f"{word1} {word2}"
                bigrams.append(bigram)
    
    # Contar frecuencias de bigramas
    bigram_freq = Counter(bigrams)
    top_bigrams_list = [bigram for bigram, _ in bigram_freq.most_common(top_bigrams)]
    
    # Forzar inclusión de "editorial board" si aparece en el texto original
    text_lower = text.lower()
    if 'editorial board' in text_lower or 'editorial boards' in text_lower:
        if 'editorial board' not in top_bigrams_list:
            # Añadir al principio si no está
            top_bigrams_list.insert(0, 'editorial board')
    
    # GARANTIZAR que siempre retorna listas, nunca None
    return (top_unigrams_list if top_unigrams_list else [], 
            top_bigrams_list if top_bigrams_list else [])


def init_session_state():
    """Inicializa variables de sesión."""
    if 'recommendations' not in st.session_state:
        st.session_state.recommendations = None
    if 'query_executed' not in st.session_state:
        st.session_state.query_executed = False
    if 'last_query' not in st.session_state:
        st.session_state.last_query = ""
    if 'similar_results' not in st.session_state:
        st.session_state.similar_results = None
    if 'selected_source_id' not in st.session_state:
        st.session_state.selected_source_id = None
    if 'top_works' not in st.session_state:
        st.session_state.top_works = None
    if 'search_results' not in st.session_state:
        st.session_state.search_results = None


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
        st.code(traceback.format_exc())
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
        
        **Dos modos de búsqueda:**
        1. **Por texto:** Busca revistas relevantes según tu tema
        2. **Por revista:** Encuentra revistas similares a una específica
        
        **Algoritmo de ranking:**
        - 75% Frecuencia de aparición
        - 15% Impacto normalizado (2yr citedness)
        - 5% Trabajos del año de referencia
        - 5% Citas del año de referencia
        """)
        
        st.divider()
        
        st.header("⚙️ Configuración")
        per_page = st.slider("Resultados por página", 50, 200, 100, 50)
        max_pages = st.slider("Páginas máximas", 1, 5, 1)
        top_n = st.slider("Top N recomendaciones", 5, 20, 10)
        abstract_keywords = st.slider("Keywords del abstract", 5, 20, 10, help="Número de keywords extraídas del abstract al construir la query")
        
        st.divider()
        
        # Debug opcional
        st.header("🐛 Debug")
        debug_query = st.checkbox("🛠️ Debug query", value=False)
        
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
                st.code(traceback.format_exc())
    
    # Tabs principales
    tab1, tab2 = st.tabs(["🔍 Buscar por Texto", "📚 Buscar por Revista"])
    
    # ========== TAB 1: Búsqueda por Texto ==========
    with tab1:
        search_by_text_tab(per_page, max_pages, top_n, debug_query, abstract_keywords)
    
    # ========== TAB 2: Búsqueda por Revista ==========
    with tab2:
        search_by_journal_tab(top_n)


def search_by_text_tab(per_page, max_pages, top_n, debug_query=False, abstract_keywords=10):
    """Tab para búsqueda por texto."""
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
        # 1) Normalizar inputs (evitar .strip() sobre None)
        title = (title or "").strip()
        abstract = (abstract or "").strip()
        query_text = (query_text or "").strip()
        
        # 2) Validación de inputs
        if not query_text:
            # Si no hay consulta libre, validar title/abstract
            if not title and not abstract:
                st.warning("⚠️ Escribe una consulta libre, o rellena título y/o abstract.")
                st.stop()
            
            if not title and len(abstract) < 50:
                st.warning("⚠️ El abstract es muy corto. Añade un título o escribe un resumen más largo (≥ 50 caracteres).")
                st.stop()
        
        # Construir query final
        final_query = query_text
        
        # Variables para debug
        title_uni, title_bi, abs_uni, abs_bi = [], [], [], []
        
        if not final_query:
            # Si no hay query_text, construir desde title/abstract con keywords y bigrams
            all_terms = []
            has_editorial_board = False
            
            # Detectar si aparece "editorial board" en el texto original
            combined_text = f"{title} {abstract}".lower()
            if 'editorial board' in combined_text or 'editorial boards' in combined_text:
                has_editorial_board = True
            
            if title:
                # Extraer keywords y bigrams del título
                title_uni, title_bi = extract_keywords_and_bigrams(
                    title, 
                    top_unigrams=8, 
                    top_bigrams=3
                )
                # NULL-SAFE: Convertir None a listas vacías (redundante pero seguro)
                title_uni = title_uni if title_uni is not None and isinstance(title_uni, list) else []
                title_bi = title_bi if title_bi is not None and isinstance(title_bi, list) else []
                
                all_terms.extend(title_bi)   # Primero bigramas
                all_terms.extend(title_uni)  # Luego unigramas
            
            if abstract:
                # Extraer keywords y bigrams del abstract
                abs_uni, abs_bi = extract_keywords_and_bigrams(
                    abstract, 
                    top_unigrams=abstract_keywords, 
                    top_bigrams=5
                )
                # NULL-SAFE: Convertir None a listas vacías (redundante pero seguro)
                abs_uni = abs_uni if abs_uni is not None and isinstance(abs_uni, list) else []
                abs_bi = abs_bi if abs_bi is not None and isinstance(abs_bi, list) else []
                
                all_terms.extend(abs_bi)   # Primero bigramas
                all_terms.extend(abs_uni)  # Luego unigramas
            
            # Eliminar keywords demasiado genéricas
            generic_keywords = {
                'objective', 'study', 'results', 'using', 'approach', 'scale', 
                'across', 'major', 'publishers', 'publisher', 'open', 'role', 
                'roles', 'size', 'sustainability', 'ebook', 'ebooks', 'repository',
                'repositories', 'dataset', 'datasets'
            }
            
            # Normalizar "editorial boards" -> "editorial board" y filtrar genéricas
            normalized_terms = []
            for term in all_terms:
                if term:  # Verificar que no sea None o vacío
                    term_lower = term.lower()
                    # Saltar keywords genéricas
                    if term_lower in generic_keywords:
                        continue
                    # Saltar si es "editorial board" (se añadirá con comillas)
                    if 'editorial board' in term_lower:
                        continue
                    # Normalizar plural
                    if 'editorial boards' in term_lower:
                        term = term_lower.replace('editorial boards', 'editorial board')
                    normalized_terms.append(term)
            
            # Eliminar duplicados preservando el orden
            seen = set()
            unique_terms = []
            for term in normalized_terms:
                if term and term not in seen:  # Verificar que term no sea None o vacío
                    seen.add(term)
                    unique_terms.append(term)
            
            # Si se detectó "editorial board", construir query especial
            if has_editorial_board:
                # Añadir "editorial board" con comillas al inicio
                # Limitar el resto a máximo 10 términos
                final_query = '"editorial board" ' + " ".join(unique_terms[:10])
            else:
                # Query normal: máximo 25 tokens o 200 caracteres
                final_query = " ".join(unique_terms[:25])
            
            # Limitar longitud total
            if len(final_query) > 200:
                # NULL-SAFE: Cortar en espacio, proteger si no hay espacios
                parts = final_query[:200].rsplit(' ', 1)
                final_query = parts[0] if parts else final_query[:200]
            
            # Fallback: si no se pudo construir query con keywords, usar texto original recortado
            if not final_query:
                if title:
                    final_query = title[:200]
                elif abstract:
                    final_query = abstract[:200]
        
        if not final_query:
            st.warning("⚠️ Por favor ingresa al menos un texto de búsqueda")
        else:
            st.session_state.last_query = final_query
            
            # Debug: Mostrar información de construcción de query
            if debug_query and (title or abstract) and not query_text:
                with st.expander("🐛 Debug: Construcción de Query", expanded=True):
                    st.write("**Final Query:**", final_query)
                    st.write("**Título - Unigramas:**", title_uni)
                    st.write("**Título - Bigramas:**", title_bi)
                    st.write("**Abstract - Unigramas:**", abs_uni)
                    st.write("**Abstract - Bigramas:**", abs_bi)
                    st.write("**Longitud final:**", len(final_query), "caracteres")
            
            # Mostrar query construida (si no es consulta libre)
            if not query_text and (title or abstract):
                st.caption(f"📌 Query construida: {final_query[:150]}..." if len(final_query) > 150 else f"📌 Query construida: {final_query}")
            
            with st.spinner("🔄 Buscando en OpenAlex y calculando recomendaciones..."):
                try:
                    # Pipeline ETL + ML (ahora devuelve tupla)
                    df_candidates, df_works = load_works_and_sources(
                        final_query,
                        per_page=per_page,
                        max_pages=max_pages
                    )
                    
                    if df_candidates.empty:
                        st.warning("⚠️ No se encontraron resultados para esta búsqueda")
                        st.session_state.recommendations = None
                        st.session_state.top_works = None
                    else:
                        # Calcular scores
                        df_ranked = calculate_scores(df_candidates)
                        
                        # Obtener top N
                        df_top = get_top_recommendations(df_ranked, top_n=top_n)
                        
                        # Guardar en MySQL
                        query_id = save_query_and_recommendations(final_query, df_top)
                        
                        # Guardar en sesión
                        st.session_state.recommendations = df_top
                        st.session_state.top_works = df_works.head(200)  # Top 200 works (para tener suficientes después del filtrado)
                        st.session_state.query_executed = True
                        
                        st.success(f"✅ {len(df_top)} recomendaciones y {len(df_works)} artículos encontrados")
                
                except Exception as e:
                    st.error(f"❌ Error durante el proceso: {e}")
                    st.code(traceback.format_exc())
                    st.session_state.recommendations = None
                    st.session_state.top_works = None
    
    # Mostrar resultados
    if st.session_state.query_executed and st.session_state.recommendations is not None:
        st.divider()
        st.header("📊 Resultados")
        
        df_recs = st.session_state.recommendations
        
        # Mostrar query ejecutada en expander
        with st.expander("🔍 Ver query ejecutada"):
            st.code(st.session_state.last_query, language="text")
        
        # CAMBIO 2: Checkbox para filtrar solo journals
        include_all_types = st.checkbox(
            "📚 Incluir repositorios / libros / preprints",
            value=False,
            help="Por defecto solo se muestran journals. Activa para incluir otros tipos de fuentes."
        )
        
        # Aplicar filtro si es necesario
        if not include_all_types and 'type' in df_recs.columns:
            df_recs_filtered = df_recs[df_recs['type'] == 'journal'].copy()
            if df_recs_filtered.empty:
                st.warning("⚠️ No se encontraron journals en los resultados. Activa el checkbox para ver otros tipos.")
            else:
                df_recs = df_recs_filtered
        
        st.markdown(f"**Total de recomendaciones:** {len(df_recs)}")
        
        # Tabla de recomendaciones
        st.subheader("Top Revistas Recomendadas")
        
        # Preparar DataFrame para mostrar (métricas recientes + cuartil)
        columns_to_show = ['rank_position', 'display_name', 'freq']
        
        # Añadir quartile si existe
        if 'quartile' in df_recs.columns:
            columns_to_show.append('quartile')
        
        columns_to_show.extend(['two_yr_mean_citedness', 'works_ref_year', 'cites_ref_year'])
        
        # Filtrar solo las columnas que existen
        available_columns = [col for col in columns_to_show if col in df_recs.columns]
        df_display = df_recs[available_columns].copy()
        
        # Renombrar columnas
        column_names = {
            'rank_position': 'Rank',
            'display_name': 'Revista',
            'freq': 'Artículos (en resultados)',
            'quartile': 'Cuartil',
            'two_yr_mean_citedness': '2yr Citedness',
            'works_ref_year': 'Trabajos (año ref)',
            'cites_ref_year': 'Citas (año ref)'
        }
        df_display.columns = [column_names.get(col, col) for col in df_display.columns]
        
        # Formatear números
        if 'Cuartil' in df_display.columns:
            df_display['Cuartil'] = df_display['Cuartil'].fillna('-')
        if '2yr Citedness' in df_display.columns:
            df_display['2yr Citedness'] = df_display['2yr Citedness'].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) and x > 0 else "N/A"
            )
        if 'Trabajos (año ref)' in df_display.columns:
            df_display['Trabajos (año ref)'] = df_display['Trabajos (año ref)'].apply(
                lambda x: f"{int(x)}" if pd.notna(x) and x > 0 else "N/A"
            )
        if 'Citas (año ref)' in df_display.columns:
            df_display['Citas (año ref)'] = df_display['Citas (año ref)'].apply(
                lambda x: f"{int(x)}" if pd.notna(x) and x > 0 else "N/A"
            )
        
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
                    
                    # Enlace a OpenAlex
                    source_id = selected_row['source_id']
                    openalex_url = f"https://openalex.org/{source_id}"
                    st.markdown(f"🔗 **[Ver revista en OpenAlex]({openalex_url})**")
                    
                    # Mostrar cuartil y SJR si están disponibles
                    quartile = selected_row.get('quartile') or source_detail.get('quartile')
                    sjr_value = selected_row.get('sjr') or source_detail.get('sjr')
                    
                    if quartile and pd.notna(quartile):
                        st.write(f"**Cuartil SJR:** {quartile}")
                    if sjr_value and pd.notna(sjr_value):
                        st.write(f"**SJR:** {sjr_value:.3f}")
                
                with col_b:
                    st.markdown("**Métricas**")
                    st.metric("Score de Recomendación", f"{selected_row['score']:.4f}")
                    st.metric("Total de Trabajos", f"{int(source_detail.get('works_count', 0)):,}")
                    st.metric("Total de Citas", f"{int(source_detail.get('cited_by_count', 0)):,}")
                    st.metric("Artículos en Resultados", f"{int(selected_row['freq'])}")
                
                # st.markdown("**Explicación de la Recomendación:**")
                # st.info(selected_row['why'])
                
                # Última actualización
                if source_detail.get('updated_date'):
                    st.caption(f"Última actualización: {source_detail['updated_date']}")
            else:
                st.warning("No se encontraron detalles para esta revista")
        
        # Nueva sección: Top Artículos Relacionados
        if st.session_state.top_works is not None and not st.session_state.top_works.empty:
            st.divider()
            st.subheader("📄 Top Artículos Relacionados")
            
            # Checkbox para incluir editorial/letter
            include_editorial_letter = st.checkbox(
                "Incluir editorial/letter (menos recomendado)", 
                value=False,
                help="Si se activa, se mostrarán también editoriales y cartas al editor"
            )
            
            df_works_display = st.session_state.top_works.copy()
            
            # Normalizar columnas antes de filtrar
            if 'type' in df_works_display.columns:
                df_works_display['type'] = df_works_display['type'].astype(str).str.strip().str.lower()
            df_works_display['title'] = df_works_display['title'].astype(str)
            
            # Filtrar por tipos permitidos
            if 'type' in df_works_display.columns:
                # Allowlist de tipos válidos (OpenAlex usa "article", no "journal-article")
                allowed_types = {"article", "preprint", "review"}
                
                # Si el usuario quiere, incluir editorial/letter
                if include_editorial_letter:
                    allowed_types = allowed_types | {"editorial", "letter", "erratum"}
                
                # Filtrar: solo tipos permitidos Y excluir paratext explícitamente
                df_works_filtered = df_works_display[
                    (df_works_display['type'].isin(allowed_types)) & 
                    (df_works_display['type'] != 'paratext') &
                    (df_works_display['type'] != 'nan')  # Excluir 'nan' como string
                ].copy()
                
                # Filtro adicional por título (por si acaso)
                excluded_prefixes = [
                    "editorial board", "statement", 
                    "front matter", "table of contents"
                ]
                for prefix in excluded_prefixes:
                    df_works_filtered = df_works_filtered[
                        ~df_works_filtered['title'].str.lower().str.startswith(prefix, na=False)
                    ]
            else:
                # Filtro heurístico por título si no existe columna 'type'
                excluded_prefixes = [
                    "editorial board", "editorial", "statement", 
                    "letter", "front matter", "table of contents"
                ]
                df_works_filtered = df_works_display.copy()
                for prefix in excluded_prefixes:
                    df_works_filtered = df_works_filtered[
                        ~df_works_filtered['title'].str.lower().str.startswith(prefix, na=False)
                    ]
            
            # Ordenar por citas (desc) y luego año (desc)
            df_works_filtered = df_works_filtered.sort_values(
                by=['cited_by_count', 'publication_year'],
                ascending=[False, False]
            )
            
            # Mostrar explicación del filtrado
            st.caption("ℹ️ Filtrado para excluir paratext/editorials. Ordenados por citas (desc) y año (desc).")
            
            # Preparar DataFrame para visualización
            columns_to_show = ['title', 'publication_year', 'cited_by_count', 'source_name']
            if 'type' in df_works_filtered.columns:
                columns_to_show.append('type')
            
            df_works_show = df_works_filtered[columns_to_show].copy()
            
            # Renombrar columnas
            column_names = {
                'title': 'Título',
                'publication_year': 'Año',
                'cited_by_count': 'Citas',
                'source_name': 'Revista',
                'type': 'Tipo'
            }
            df_works_show.columns = [column_names.get(col, col) for col in df_works_show.columns]
            
            # Formatear
            df_works_show['Citas'] = df_works_show['Citas'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "0")
            df_works_show['Año'] = df_works_show['Año'].apply(lambda x: str(int(x)) if pd.notna(x) else "N/A")
            df_works_show['Revista'] = df_works_show['Revista'].fillna('N/A')
            if 'Tipo' in df_works_show.columns:
                df_works_show['Tipo'] = df_works_show['Tipo'].fillna('N/A')
            
            # Mostrar tabla
            st.dataframe(
                df_works_show,
                use_container_width=True,
                hide_index=True,
                height=400
            )
            
            # Nube de palabras de títulos
            st.divider()
            st.subheader("☁️ Nube de palabras (títulos de artículos)")
            
            # Controles
            col_wc1, col_wc2 = st.columns([2, 1])
            with col_wc1:
                max_words = st.slider("Número máximo de palabras", 50, 150, 100, 10)
            with col_wc2:
                st.write("")  # Espaciador
            
            # Stopwords en español e inglés
            stopwords_es = {
                'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se', 'no', 'haber',
                'por', 'con', 'su', 'para', 'como', 'estar', 'tener', 'le', 'lo', 'todo',
                'pero', 'más', 'hacer', 'o', 'poder', 'decir', 'este', 'ir', 'otro', 'ese',
                'la', 'si', 'me', 'ya', 'ver', 'porque', 'dar', 'cuando', 'él', 'muy',
                'sin', 'vez', 'mucho', 'saber', 'qué', 'sobre', 'mi', 'alguno', 'mismo',
                'yo', 'también', 'hasta', 'año', 'dos', 'querer', 'entre', 'así', 'primero',
                'desde', 'grande', 'eso', 'ni', 'nos', 'llegar', 'pasar', 'tiempo', 'ella',
                'sí', 'día', 'uno', 'bien', 'poco', 'deber', 'entonces', 'poner', 'cosa',
                'tanto', 'hombre', 'parecer', 'nuestro', 'tan', 'donde', 'ahora', 'parte',
                'después', 'vida', 'quedar', 'siempre', 'creer', 'hablar', 'llevar', 'dejar',
                'nada', 'cada', 'seguir', 'menos', 'nuevo', 'encontrar', 'algo', 'solo',
                'del', 'los', 'las', 'una', 'unos', 'unas', 'al', 'del'
            }
            
            stopwords_en = {
                'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it',
                'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at', 'this', 'but',
                'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she', 'or', 'an', 'will',
                'my', 'one', 'all', 'would', 'there', 'their', 'what', 'so', 'up', 'out',
                'if', 'about', 'who', 'get', 'which', 'go', 'me', 'when', 'make', 'can',
                'like', 'time', 'no', 'just', 'him', 'know', 'take', 'people', 'into',
                'year', 'your', 'good', 'some', 'could', 'them', 'see', 'other', 'than',
                'then', 'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also',
                'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first', 'well',
                'way', 'even', 'new', 'want', 'because', 'any', 'these', 'give', 'day',
                'most', 'us', 'is', 'was', 'are', 'been', 'has', 'had', 'were', 'said',
                'did', 'having', 'may', 'should', 'am', 'being', 'were'
            }
            
            # Palabras de ruido específicas
            noise_words = {
                'editorial', 'board', 'letter', 'statement', 'study', 'analysis', 'review',
                'article', 'paper', 'research', 'using', 'based', 'case', 'role'
            }
            
            all_stopwords = stopwords_es | stopwords_en | noise_words
            
            # Extraer y limpiar títulos
            import re
            import string
            
            titles_text = ' '.join(df_works_filtered['title'].astype(str).tolist())
            
            # Limpiar y tokenizar
            titles_text = titles_text.lower()
            titles_text = re.sub(f'[{re.escape(string.punctuation)}]', ' ', titles_text)  # Eliminar puntuación
            titles_text = re.sub(r'\d+', '', titles_text)  # Eliminar números
            
            # Tokenizar y filtrar
            tokens = [
                word for word in titles_text.split()
                if len(word) >= 3 and word not in all_stopwords
            ]
            
            # Contar frecuencias
            from collections import Counter
            word_freq = Counter(tokens)
            
            # Intentar generar WordCloud
            try:
                from wordcloud import WordCloud
                import matplotlib.pyplot as plt
                
                if word_freq:
                    # Generar WordCloud
                    wordcloud = WordCloud(
                        width=800,
                        height=400,
                        background_color='white',
                        max_words=max_words,
                        colormap='viridis',
                        relative_scaling=0.5,
                        min_font_size=10
                    ).generate_from_frequencies(word_freq)
                    
                    # Mostrar
                    fig, ax = plt.subplots(figsize=(12, 6))
                    ax.imshow(wordcloud, interpolation='bilinear')
                    ax.axis('off')
                    st.pyplot(fig)
                    plt.close()
                else:
                    st.info("No hay suficientes palabras para generar la nube.")
                    
            except ImportError:
                st.warning("⚠️ El paquete 'wordcloud' no está instalado. Instálalo con:")
                st.code("pip install wordcloud", language="bash")
                
                # Fallback: tabla de frecuencias
                if word_freq:
                    st.info("📊 Mostrando top 20 palabras más frecuentes como alternativa:")
                    top_words = word_freq.most_common(20)
                    df_words = pd.DataFrame(top_words, columns=['Palabra', 'Frecuencia'])
                    st.dataframe(df_words, use_container_width=True, hide_index=True)
            
            # Selector para ver trabajo individual
            st.divider()
            st.subheader("🔗 Ver Artículo en OpenAlex")
            
            work_options = df_works_filtered.apply(
                lambda row: f"{row['title'][:80]}... ({row.get('publication_year', 'N/A')})", 
                axis=1
            ).tolist()
            
            selected_work = st.selectbox(
                "Selecciona un artículo:",
                options=work_options,
                key="work_selector"
            )
            
            if selected_work:
                work_idx = work_options.index(selected_work)
                work_row = df_works_filtered.iloc[work_idx]
                
                col_w1, col_w2 = st.columns([3, 1])
                
                with col_w1:
                    st.markdown(f"**Título:** {work_row['title']}")
                    st.markdown(f"**Revista:** {work_row.get('source_name', 'N/A')}")
                
                with col_w2:
                    st.metric("Año", work_row.get('publication_year', 'N/A'))
                    st.metric("Citas", f"{int(work_row['cited_by_count']):,}")
                
                # Link a OpenAlex
                if pd.notna(work_row.get('openalex_url')):
                    st.markdown(f"🔗 **[Ver en OpenAlex]({work_row['openalex_url']})**")


def search_by_journal_tab(top_n):
    """Tab para búsqueda por revista y similares."""
    st.header("📚 Buscar Revistas Similares")
    
    st.markdown("""
    Encuentra revistas similares a una específica basándose en:
    - Impacto normalizado (2yr mean citedness)
    - Actividad reciente (trabajos y citas)
    - Perfil numérico global
    """)
    
    st.divider()
    
    # Formulario de búsqueda
    st.subheader("1️⃣ Encuentra la revista de referencia")
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        issn_input = st.text_input(
            "ISSN-L (opcional)",
            placeholder="Ej: 0028-0836"
        )
    
    with col_b:
        title_input = st.text_input(
            "Título de revista (opcional)",
            placeholder="Ej: Nature"
        )
    
    # Botones de búsqueda
    col_btn1, col_btn2 = st.columns([1, 4])
    
    with col_btn1:
        search_journal_btn = st.button("🔎 Buscar Revista", type="primary", use_container_width=True)
    
    with col_btn2:
        if st.button("🗑️ Limpiar Búsqueda", use_container_width=True):
            st.session_state.similar_results = None
            st.session_state.selected_source_id = None
            st.rerun()
    
    # Procesar búsqueda de revista
    if search_journal_btn:
        if not issn_input.strip() and not title_input.strip():
            st.warning("⚠️ Por favor ingresa ISSN o título de revista")
        else:
            try:
                # Búsqueda por ISSN tiene prioridad
                if issn_input.strip():
                    st.info("🔍 Buscando en base de datos local...")
                    df_found = search_sources_by_issn(issn_input.strip())
                    search_type = "ISSN"
                else:
                    st.info("🔍 Buscando en base de datos local...")
                    df_found = search_sources_by_name(title_input.strip(), limit=20)
                    search_type = "título"
                
                # Convertir a lista de diccionarios para evitar problemas con tipos
                if not df_found.empty:
                    results_list = df_found.to_dict('records')
                    st.session_state.search_results = results_list
                    
                    if len(results_list) == 1:
                        # Una sola coincidencia - selección automática
                        st.session_state.selected_source_id = str(results_list[0]['source_id'])
                        st.session_state.search_results = None
                        st.success(f"✅ Revista encontrada: {results_list[0]['display_name']}")
                    else:
                        # Múltiples coincidencias
                        st.success(f"✅ Se encontraron {len(results_list)} revistas. Selecciona una abajo:")
                else:
                    # No se encontró nada ni en MySQL ni en OpenAlex
                    if issn_input.strip():
                        st.warning(f"⚠️ No se encontró el ISSN {issn_input} en la base local ni en OpenAlex")
                    else:
                        st.warning(f"⚠️ No se encontraron revistas con {search_type}: {title_input}")
                    st.session_state.search_results = None
            
            except Exception as e:
                st.error(f"❌ Error en la búsqueda: {str(e)}")
                st.code(traceback.format_exc())
                st.session_state.search_results = None
    
    # Mostrar selector si hay resultados múltiples
    if st.session_state.get('search_results'):
        results = st.session_state.search_results
        
        # Crear opciones de forma segura
        options = []
        options_map = {}
        
        for item in results:
            try:
                display_name = str(item.get('display_name', 'Sin nombre'))
                source_id = str(item.get('source_id', ''))
                if source_id:
                    label = f"{display_name} ({source_id})"
                    options.append(label)
                    options_map[label] = source_id
            except Exception as e:
                continue
        
        if options:
            selected_option = st.selectbox(
                "Selecciona una revista:",
                options=options,
                key="journal_selector"
            )
            
            if st.button("✅ Confirmar selección", key="confirm_journal"):
                st.session_state.selected_source_id = options_map[selected_option]
                st.session_state.search_results = None
                st.success(f"✅ Revista seleccionada: {selected_option}")
                st.rerun()
    
    # Si hay una revista seleccionada, mostrar botón para buscar similares
    if st.session_state.selected_source_id:
        st.divider()
        st.subheader("2️⃣ Buscar revistas similares")
        
        # Mostrar info de la revista seleccionada
        source_detail = get_source_detail(st.session_state.selected_source_id)
        
        if source_detail:
            st.info(f"**Revista seleccionada:** {source_detail.get('display_name', 'N/A')}")
            
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("Trabajos", f"{int(source_detail.get('works_count', 0)):,}")
            with col_m2:
                st.metric("Citas", f"{int(source_detail.get('cited_by_count', 0)):,}")
            with col_m3:
                citedness = source_detail.get('two_yr_mean_citedness', 0)
                st.metric("2yr Citedness", f"{citedness:.2f}" if citedness else "N/A")
            with col_m4:
                works_ref = source_detail.get('works_ref_year', 0)
                st.metric("Trabajos recientes", f"{int(works_ref)}" if works_ref else "N/A")
        
        # Checkbox para similitud temática
        use_thematic = st.checkbox("Usar similitud temática (topics)", value=False)
        
        # Botón para buscar similares
        if st.button("🚀 Buscar Revistas Similares", type="primary", use_container_width=True):
            with st.spinner("🔄 Calculando similitudes..."):
                try:
                    df_similar = find_similar_sources(
                        st.session_state.selected_source_id, 
                        top_n=top_n,
                        use_thematic=use_thematic
                    )
                    
                    if df_similar.empty:
                        st.warning("⚠️ No se encontraron revistas similares")
                    else:
                        st.session_state.similar_results = df_similar
                        st.success(f"✅ {len(df_similar)} revistas similares encontradas")
                
                except Exception as e:
                    st.error(f"❌ Error al calcular similitudes: {e}")
                    st.code(traceback.format_exc())
    
    # Mostrar resultados de similitud
    if st.session_state.similar_results is not None:
        st.divider()
        st.header("📊 Revistas Similares")
        
        df_similar = st.session_state.similar_results
        
        # Tabla de resultados
        st.subheader("Resultados")
        
        # Preparar columnas (similitud + métricas recientes + cuartil)
        columns_to_show = [
            'rank_position', 'display_name'
        ]
        
        # Añadir columnas de similitud según el tipo
        if 'final_similarity' in df_similar.columns and df_similar['final_similarity'].notna().any():
            # Modo temático: mostrar las 3 similitudes
            columns_to_show.extend(['final_similarity', 'similarity_score', 'thematic_similarity'])
        elif 'similarity_score' in df_similar.columns:
            # Modo numérico: solo similarity_score
            columns_to_show.append('similarity_score')
        
        if 'quartile' in df_similar.columns:
            columns_to_show.append('quartile')
        
        columns_to_show.extend([
            'two_yr_mean_citedness', 'works_ref_year', 'cites_ref_year'
        ])
        
        # Filtrar solo columnas existentes
        available_columns = [col for col in columns_to_show if col in df_similar.columns]
        df_display = df_similar[available_columns].copy()
        
        # Renombrar columnas
        column_names = {
            'rank_position': 'Rank',
            'display_name': 'Revista',
            'final_similarity': 'Similitud',
            'similarity_score': 'Sim. numérica',
            'thematic_similarity': 'Sim. temática',
            'quartile': 'Cuartil',
            'two_yr_mean_citedness': '2yr Citedness',
            'works_ref_year': 'Trabajos (año ref)',
            'cites_ref_year': 'Citas (año ref)'
        }
        df_display.columns = [column_names.get(col, col) for col in df_display.columns]
        
        # Formatear scores de similitud a 3 decimales
        for sim_col in ['Similitud', 'Sim. numérica', 'Sim. temática']:
            if sim_col in df_display.columns:
                df_display[sim_col] = df_display[sim_col].apply(
                    lambda x: f"{x:.3f}" if pd.notna(x) else "-"
                )
        
        # Formatear números
        if 'Cuartil' in df_display.columns:
            df_display['Cuartil'] = df_display['Cuartil'].fillna('-')
        if '2yr Citedness' in df_display.columns:
            df_display['2yr Citedness'] = df_display['2yr Citedness'].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) and x > 0 else "N/A"
            )
        if 'Trabajos (año ref)' in df_display.columns:
            df_display['Trabajos (año ref)'] = df_display['Trabajos (año ref)'].apply(
                lambda x: f"{int(x)}" if pd.notna(x) and x > 0 else "N/A"
            )
        if 'Citas (año ref)' in df_display.columns:
            df_display['Citas (año ref)'] = df_display['Citas (año ref)'].apply(
                lambda x: f"{int(x)}" if pd.notna(x) and x > 0 else "N/A"
            )
        
        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            height=400
        )
        
        # Selector para ver detalle
        st.divider()
        st.subheader("🔎 Ver Detalle")
        
        similar_options = df_similar.apply(
            lambda row: f"{int(row['rank_position'])}. {row['display_name']}", axis=1
        ).tolist()
        
        selected_similar = st.selectbox(
            "Selecciona una revista similar:",
            options=similar_options,
            key="similar_detail_selector"
        )
        
        if selected_similar:
            selected_rank = int(selected_similar.split('.')[0])
            selected_row = df_similar[df_similar['rank_position'] == selected_rank].iloc[0]
            source_id = selected_row['source_id']
            
            # Obtener detalles completos
            detail = get_source_detail(source_id)
            
            if detail:
                col_x, col_y = st.columns(2)
                
                with col_x:
                    st.markdown("**Información General**")
                    st.write(f"**Nombre:** {detail.get('display_name', 'N/A')}")
                    st.write(f"**Tipo:** {detail.get('type', 'N/A')}")
                    st.write(f"**Publisher:** {detail.get('publisher', 'N/A')}")
                    st.write(f"**País:** {detail.get('country_code', 'N/A')}")
                    st.write(f"**ISSN-L:** {detail.get('issn_l', 'N/A')}")
                    
                    # Enlace a OpenAlex
                    source_id = selected_row['source_id']
                    openalex_url = f"https://openalex.org/{source_id}"
                    st.markdown(f"🔗 **[Ver revista en OpenAlex]({openalex_url})**")
                    
                    # Cuartil y SJR
                    quartile = selected_row.get('quartile') or detail.get('quartile')
                    sjr_value = selected_row.get('sjr') or detail.get('sjr')
                    if quartile and pd.notna(quartile):
                        st.write(f"**Cuartil SJR:** {quartile}")
                    if sjr_value and pd.notna(sjr_value):
                        st.write(f"**SJR:** {sjr_value:.3f}")
                
                with col_y:
                    st.markdown("**Métricas Recientes**")
                    
                    # 2yr Citedness
                    citedness = selected_row.get('two_yr_mean_citedness') or detail.get('two_yr_mean_citedness', 0)
                    st.metric("2yr Citedness", f"{citedness:.2f}" if citedness else "N/A")
                    
                    # Trabajos año referencia
                    works_ref = selected_row.get('works_ref_year') or detail.get('works_ref_year', 0)
                    from datetime import datetime
                    ref_year = datetime.utcnow().year - 4
                    st.metric(f"Trabajos ({ref_year})", f"{int(works_ref)}" if works_ref else "N/A")
                    
                    # Citas año referencia
                    cites_ref = selected_row.get('cites_ref_year') or detail.get('cites_ref_year', 0)
                    st.metric(f"Citas ({ref_year})", f"{int(cites_ref)}" if cites_ref else "N/A")
                
                # st.markdown("**Explicación:**")
                # st.info(selected_row['why'])


if __name__ == "__main__":
    main()
