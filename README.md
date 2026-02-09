# 📚 Journal Intelligence
### *Sistema inteligente de recomendación de revistas científicas*

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B?logo=streamlit&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-4479A1?logo=mysql&logoColor=white)
![OpenAlex](https://img.shields.io/badge/OpenAlex-API-orange)
![SJR](https://img.shields.io/badge/SCImago-JR-green)

---

## 🎯 ¿Qué hace esta herramienta?

**Journal Intelligence** te ayuda a tomar decisiones informadas sobre dónde publicar tu investigación y cómo enriquecer tu manuscrito. Ofrece **tres casos de uso principales**:

### 1️⃣ **Recomendar revistas para publicar**
- Ingresa el título y/o abstract de tu investigación
- Obtén un ranking personalizado de revistas relevantes
- Visualiza cuartiles SJR, frecuencia de aparición y métricas de impacto normalizado
- Identifica las revistas más alineadas con tu temática

### 2️⃣ **Recuperar artículos relacionados para discusión/estado del arte**
- Encuentra automáticamente los artículos más citados y relevantes sobre tu tema
- Filtra por tipo (artículos, preprints, reviews)
- Accede directamente a OpenAlex para explorar cada trabajo
- Enriquece tu sección de literatura relacionada con fuentes actuales

### 3️⃣ **Buscar revistas similares a una de referencia**
- Identifica revistas con perfil similar a una que ya conoces
- Explora alternativas de publicación con métricas comparables
- Descubre opciones de la misma categoría o nicho académico
- Basado en similitud numérica (impacto, productividad, actividad reciente)

**✨ Por defecto, los resultados se filtran a `type=journal`**, evitando repositorios, eBooks y preprints en las recomendaciones principales. Puedes incluirlos opcionalmente con un checkbox.

---

## 🚀 Demo Rápida (Quickstart)

```bash
# 1. Clonar el proyecto y crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows | source venv/bin/activate en Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
copy .env.example .env
# Edita .env con tus credenciales de MySQL

# 4. Inicializar base de datos
python db/init_db.py

# 5. Lanzar la aplicación
streamlit run app/app.py
```

Abre tu navegador en `http://localhost:8501` y comienza a explorar.

---

## 🔧 Cómo Funciona

El sistema sigue un pipeline de datos completo desde la API hasta la interfaz de usuario:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│             │     │             │     │             │     │             │     │             │
│  OpenAlex   │────▶│  ETL Layer  │────▶│    MySQL    │────▶│  Ranking &  │────▶│  Streamlit  │
│   API       │     │  (Python)   │     │   Database  │     │  Similitud  │     │     UI      │
│             │     │             │     │             │     │   (ML)      │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
      │                    │                    │                    │                    │
   Polite Pool      Works + Sources      Persistencia       Score = 75/15/10        Tabs, tablas
   (con email)      JSON → DataFrame      Normalización      Cosine similarity     Cuartiles SJR
                    Enriquecimiento       ISSN matching      Z-score features      Filtros, debug
```

### Pasos del pipeline:

1. **OpenAlex API**: Consulta works relevantes según texto de búsqueda (usa Polite Pool con email)
2. **ETL Layer**: Extrae sources, normaliza datos, calcula frecuencias
3. **MySQL**: Almacena sources, works, queries, recommendations y cuartiles SJR
4. **Ranking/Similitud**: Aplica algoritmo de scoring (75% freq + 15% impacto + 10% actividad) o similitud coseno
5. **Streamlit UI**: Presenta resultados en tablas interactivas con filtros y detalles expandibles

---

## 🔍 Modos de Búsqueda

### **Modo 1: Búsqueda por Texto** 🔎

**Input:**
- Título de tu investigación (opcional)
- Abstract o resumen (opcional, mínimo 50 caracteres si no hay título)
- O consulta libre con keywords

**Proceso:**
- Extrae keywords y bigrams relevantes del texto
- Elimina stopwords (ES + EN) y términos genéricos
- Si detecta "editorial board", ancla la búsqueda con comillas
- Limita query a términos más relevantes (configurable 5-20 keywords de abstract)

**Output:**
- **Top N revistas recomendadas** (ranking por score 75/15/10)
  - Cuartil SJR (Q1/Q2/Q3/Q4 o "-")
  - Frecuencia de aparición en resultados
  - Impacto normalizado (2yr mean citedness)
  - Actividad reciente (works y citas del año de referencia)
- **Top artículos relacionados** (hasta 200, filtrados por tipo)
  - Título, año, citaciones
  - Enlaces directos a OpenAlex
  - Wordcloud de títulos (visualización opcional)

### **Modo 2: Búsqueda por Revista** 📚

**Input:**
- ISSN-L de la revista de referencia, O
- Título parcial/completo de la revista

**Proceso:**
- Busca en MySQL por ISSN normalizado (sin guiones)
- Si no existe, consulta OpenAlex API directamente
- Extrae features numéricas: impacto, productividad, actividad
- Normaliza con Z-score y calcula similitud coseno con todas las revistas

**Output:**
- **Top N revistas similares** (por similitud numérica descendente)
  - Similarity score (0-1)
  - Cuartil SJR
  - Métricas comparativas (two_yr_mean_citedness, works_ref_year, etc.)
- Opcionalmente: modo de similitud temática (Jaccard sobre topics)

---

## 📊 Algoritmo de Ranking

El score de recomendación prioriza **relevancia temática** y **métricas recientes** sobre impacto histórico:

```python
score = 0.75 * freq_norm + 0.15 * two_yr_norm + 0.10 * works_ref_norm
```

### Componentes:

| Peso | Componente          | Qué mide                                                                 | Por qué importa                                  |
|------|---------------------|--------------------------------------------------------------------------|--------------------------------------------------|
| 75%  | `freq_norm`         | Frecuencia de aparición de la revista en resultados de OpenAlex         | **Relevancia temática directa** para tu topic   |
| 15%  | `two_yr_norm`       | Impacto normalizado de 2 años (two_yr_mean_citedness)                   | Calidad reciente, no solo citas históricas      |
| 10%  | `works_ref_norm`    | Trabajos publicados en año de referencia (año actual - 4)                | Actividad editorial sostenida                    |

### Ventajas:
✅ **No sesga hacia revistas generalistas** (Nature, Science) si no son relevantes  
✅ **Prioriza journals activos** en tu área específica  
✅ **Valora impacto normalizado** (no solo volumen bruto de citas)  
✅ **Evita recomendar revistas inactivas o descontinuadas**

---

## 🧮 Algoritmo de Similitud

Para encontrar revistas con perfil comparable:

### **Features numéricas** (5 dimensiones):
1. `two_yr_mean_citedness` → Impacto normalizado reciente
2. `works_ref_year` → Productividad en año de referencia
3. `cites_ref_year` → Citas recibidas en año de referencia
4. `works_count` → Productividad histórica total
5. `cited_by_count` → Impacto histórico total

### **Normalización**:
- Z-score (StandardScaler) para eliminar diferencias de escala
- Todas las features quedan con media 0 y desviación estándar 1

### **Métrica de similitud**:
- **Similitud coseno** entre vectores normalizados
- Resultado: score entre 0 (ortogonales) y 1 (idénticas)

### **Modo temático opcional**:
- Similitud Jaccard sobre topics de OpenAlex
- Combina: `0.7 * similitud_numérica + 0.3 * similitud_temática`

---

## 🏆 Integración de SJR (Cuartiles)

El sistema integra **SCImago Journal Rank (SJR)** para mostrar cuartiles en todas las tablas:

### **Normalización de ISSN** (clave del match):

| Fuente     | Formato ISSN       | Ejemplo        |
|------------|--------------------|----------------|
| OpenAlex   | `issn_l` con guion | `1234-5678`    |
| SJR CSV    | Sin guiones, CSV   | `12345678,9876...` |

**Solución**: JOIN normalizado en SQL
```sql
LEFT JOIN sjr_2024 sjr
  ON REPLACE(s.issn_l, '-', '') = sjr.issn_norm
```

El script `etl/load_sjr_2024.py` normaliza ~40,000 ISSNs del CSV de SJR (~24,000 revistas).

### **Datos mostrados**:
- **Cuartil**: Q1 (top 25%), Q2, Q3, Q4 (bottom 25%) o "-" (sin datos)
- **SJR score**: Valor numérico del índice (visible en detalles expandibles)

Si una revista no tiene match por ISSN, se muestra "-" en lugar de cuartil.

---

## 📦 Instalación Completa

### **Requisitos previos**:
- Python 3.8+
- MySQL Server 8.0+ corriendo en `localhost:3306`
- Correo electrónico para OpenAlex Polite Pool (recomendado para mayor tasa de requests)

### **Paso 1: Entorno virtual**

```bash
# Clonar/descargar el proyecto
cd journal-intelligence-openalex

# Crear y activar entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

### **Paso 2: Dependencias**

```bash
pip install -r requirements.txt
```

**Dependencias principales:**
- `streamlit` → Interfaz web
- `pandas`, `numpy` → Manipulación de datos
- `sqlalchemy`, `pymysql` → Conexión a MySQL
- `requests` → Cliente OpenAlex API
- `scikit-learn` → Normalización y similitud
- `python-dotenv` → Variables de entorno
- `wordcloud`, `matplotlib` → Visualizaciones (opcionales)

### **Paso 3: Configurar `.env`**

```bash
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/Mac
```

Edita `.env` con tus credenciales:

```ini
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DB=journal_intelligence
MYSQL_USER=root
MYSQL_PASSWORD=tu_password_mysql
OPENALEX_EMAIL=tu_email@ejemplo.com  # ¡Importante para Polite Pool!
```

**⚠️ Nota**: Añadir tu email en `OPENALEX_EMAIL` te da acceso al **Polite Pool de OpenAlex**, que permite más requests/segundo y prioridad en la cola.

### **Paso 4: Inicializar base de datos**

```bash
python db/init_db.py
```

Este script:
- ✅ Crea la base de datos `journal_intelligence` (si no existe)
- ✅ Ejecuta `db/schema.sql` para crear las tablas:
  - `sources` → Revistas (con ISSN normalizado y type)
  - `works_sample` → Artículos relacionados
  - `sjr_2024` → Cuartiles de SCImago
  - `queries` y `recommendations` → Historial de búsquedas

### **Paso 5: (Opcional) Cargar cuartiles SJR**

Para mostrar cuartiles Q1/Q2/Q3/Q4 en los resultados:

1. **Descargar CSV de SCImago**:
   - Visita: `https://www.scimagojr.com/journalrank.php`
   - Selecciona "All subject areas" y año "2024"
   - Descarga `scimagojr 2024.csv`

2. **Colocar en carpeta `data/`**:
   ```bash
   # Copiar a la carpeta data del proyecto
   copy "ruta\al\scimagojr 2024.csv" "data\"
   ```

3. **Ejecutar script de carga**:
   ```bash
   python -m etl.load_sjr_2024
   ```

   El script:
   - ✅ Procesa ~24,000 revistas del CSV
   - ✅ Normaliza ~40,000 ISSNs (elimina guiones, separa múltiples)
   - ✅ Carga cuartiles y SJR scores en MySQL

---

## 🎮 Uso de la Aplicación

### **Lanzar Streamlit**:

```bash
streamlit run app/app.py
```

Abre tu navegador en `http://localhost:8501`

### **Interfaz de usuario**:

#### **Sidebar (Configuración)**:
- **Resultados por página**: 50-200 works por página de OpenAlex (default: 100)
- **Páginas máximas**: 1-5 páginas a consultar (default: 1)
- **Top N recomendaciones**: 5-20 revistas a mostrar (default: 10)
- **Keywords del abstract**: 5-20 términos a extraer del abstract (default: 10)
- **Debug query**: Muestra cómo se construye la query desde título/abstract

#### **Tab 1: Buscar por Texto** 🔎
1. Ingresa **Título** (opcional) y/o **Abstract** (min 50 caracteres si no hay título)
   - O usa **Consulta libre** con keywords directas
2. Clic en **"🚀 Recomendar Revistas"**
3. Se muestran:
   - **Top Revistas Recomendadas**: tabla con rank, nombre, frecuencia, cuartil SJR, métricas
   - **Top Artículos Relacionados**: títulos, años, citas, enlaces a OpenAlex
   - **Wordcloud** de títulos (si está instalado)
4. Selecciona una revista del dropdown para ver **detalles completos** (cuartil SJR, publisher, country, ISSN)

**Opciones de filtrado**:
- Checkbox: **"Incluir editorial/letter"** → Incluye paratext en artículos (default: OFF)
- Checkbox: **"Incluir repositorios/libros/preprints"** → Incluye sources no-journal (default: OFF)

#### **Tab 2: Buscar por Revista** 📚
1. Ingresa **ISSN-L** (formato `1234-5678`) o **Título** parcial
2. Clic en **"🔍 Buscar Revista"**
3. Si hay múltiples coincidencias, selecciona una del dropdown
4. Clic en **"🔗 Buscar Revistas Similares"**
5. Ajusta modo de similitud:
   - **Solo métricas numéricas** (default) → Similitud coseno sobre 5 features
   - **Métricas + temática** → Combina 70% numérico + 30% Jaccard topics
6. Se muestran **Top N revistas similares** con scores de similitud y cuartiles

---

## 💻 Uso Programático (Opcional)

Puedes ejecutar el pipeline desde Python sin la UI:

### **Búsqueda por texto**:

```python
from etl.load_openalex import load_works_and_sources
from ml.ranker import calculate_scores, get_top_recommendations
from ml.save_recommendations import save_query_and_recommendations

# Cargar datos (devuelve tupla: candidatos + works)
query = "machine learning editorial board impact factor"
df_candidates, df_works = load_works_and_sources(query, per_page=100, max_pages=2)

# Calcular scores
df_ranked = calculate_scores(df_candidates)

# Obtener top 10
df_top = get_top_recommendations(df_ranked, top_n=10)

# Guardar recomendaciones en MySQL
query_id = save_query_and_recommendations(query, df_top)

print(df_top[['rank_position', 'display_name', 'quartile', 'score']])
print(df_works[['title', 'cited_by_count', 'publication_year']].head(20))
```

### **Búsqueda por similitud**:

```python
from ml.similarity import find_similar_sources, search_sources_by_name, search_sources_by_issn

# Opción A: Buscar revista por nombre
df_search = search_sources_by_name("nature communications")
source_id = df_search.iloc[0]['source_id']

# Opción B: Buscar revista por ISSN
df_search = search_sources_by_issn("2041-1723")
source_id = df_search.iloc[0]['source_id']

# Encontrar similares (modo numérico)
df_similar = find_similar_sources(source_id, top_n=15, use_thematic=False)
print(df_similar[['display_name', 'similarity_score', 'quartile', 'two_yr_mean_citedness']])

# Modo temático (combina numérico + topics)
df_similar_thematic = find_similar_sources(source_id, top_n=15, use_thematic=True)
print(df_similar_thematic[['display_name', 'final_similarity', 'thematic_similarity']])
```

---

## 📁 Estructura del Proyecto

```
journal-intelligence-openalex/
│
├── app/                          # 🎨 Interfaz Streamlit
│   └── app.py                    # App principal con 2 tabs (texto/revista)
│
├── etl/                          # 📥 Capa ETL (Extract-Transform-Load)
│   ├── openalex_client.py        # Cliente API OpenAlex con Polite Pool
│   ├── load_openalex.py          # Pipeline: works → sources → MySQL
│   └── load_sjr_2024.py          # Pipeline: CSV SJR → MySQL (cuartiles)
│
├── db/                           # 🗄️ Base de datos
│   ├── schema.sql                # Esquema de tablas (sources, works_sample, sjr_2024, etc.)
│   ├── init_db.py                # Script de inicialización
│   └── connection.py             # Conexión SQLAlchemy con connection pooling
│
├── ml/                           # 🧠 Algoritmos de ranking y similitud
│   ├── ranker.py                 # Cálculo de scores (75/15/10)
│   ├── similarity.py             # Similitud coseno + Jaccard (opcional)
│   └── save_recommendations.py   # Persistencia de queries y resultados
│
├── notebooks/                    # 📓 Jupyter notebooks (análisis exploratorio)
│
├── tests/                        # 🧪 Tests unitarios
│   └── __init__.py
│
├── data/                         # 📊 Datos (CSV de SJR)
│   └── scimagojr 2024.csv        # Descargar de scimagojr.com
│
├── requirements.txt              # 📦 Dependencias Python
├── .env.example                  # 🔒 Template de variables de entorno
├── config.py                     # ⚙️ Configuración centralizada
└── README.md                     # 📖 Este archivo
```

---

## ⚠️ Limitaciones y Consideraciones

### **Sesgos de datos**:
- ❌ **OpenAlex no indexa full-text**: Solo metadatos (título, abstract, autores, citaciones). No hay análisis de contenido completo.
- ❌ **Cobertura variable**: OpenAlex tiene mejor cobertura en STEM que en humanidades/ciencias sociales.
- ⚠️ **Revistas sin ISSN**: No se pueden matchear con SJR para obtener cuartil (mostrarán "-").

### **Filtrado de ruido**:
- ✅ **Paratext filtrado por defecto**: Se excluyen "editorial", "letter", "correction" de los artículos relacionados.
- ✅ **Solo journals por defecto**: Se filtran repositorios, eBooks y preprints en recomendaciones (activable con checkbox).
- ⚠️ **Queries genéricas**: Términos muy amplios (e.g., "sustainability") pueden devolver revistas no relevantes. Solución: usa título + abstract específicos.

### **Limitaciones técnicas**:
- 🕐 **Rate limiting**: OpenAlex API tiene límites de requests/segundo (Polite Pool mejora esto).
- 💾 **MySQL local**: Requiere instancia MySQL corriendo (no usa bases cloud por defecto).
- 🔄 **Sin caché de works**: Cada búsqueda consulta OpenAlex en tiempo real (no se cachean artículos).

### **Mejoras sugeridas**:
- Implementar caché de works en MySQL para búsquedas repetidas
- Añadir análisis de co-autorías y redes de citación
- Integrar más fuentes de cuartiles (JCR, Scopus, etc.)
- Soporte para búsqueda multilingüe (actualmente optimizado para ES/EN)

---

## 🗺️ Roadmap

### **Versión 1.1** (próxima)
- [ ] Caché de works en MySQL para acelerar búsquedas repetidas
- [ ] Exportar resultados a CSV/Excel desde la UI
- [ ] Gráficos de distribución de cuartiles en resultados
- [ ] Filtro por país/publisher en resultados

### **Versión 1.2**
- [ ] Análisis de co-citación entre artículos
- [ ] Recomendación de autores/colaboradores potenciales
- [ ] Integración con Semantic Scholar API (datos complementarios)
- [ ] Soporte para comparar múltiples revistas lado a lado

### **Versión 2.0**
- [ ] Docker Compose para deployment fácil (MySQL + Streamlit)
- [ ] Autenticación de usuarios y guardado de favoritos
- [ ] Dashboard de analytics (queries más populares, revistas trending)
- [ ] API REST para integración con otros sistemas

---

## 🛠️ Troubleshooting

### **Error: Can't connect to MySQL server**

```
sqlalchemy.exc.OperationalError: (2003, "Can't connect to MySQL server on 'localhost'...")
```

**Soluciones**:
1. ✅ Verifica que MySQL esté corriendo: `mysql -u root -p`
2. ✅ Confirma usuario/password en `.env`
3. ✅ Asegúrate de que el puerto 3306 esté abierto
4. ✅ Si usas XAMPP/WAMP, verifica que MySQL esté iniciado en el panel de control

---

### **Error: 429 Too Many Requests (OpenAlex)**

```
requests.exceptions.HTTPError: 429 Client Error: Too Many Requests
```

**Soluciones**:
1. ✅ Agrega tu email en `OPENALEX_EMAIL` en `.env` para acceder al **Polite Pool**
2. ⏳ Espera 10-30 segundos y vuelve a intentar
3. 🔄 El código incluye reintentos automáticos con backoff exponencial
4. 📉 Reduce `max_pages` en sidebar (1-2 páginas en lugar de 5)

**Nota**: El Polite Pool de OpenAlex da **10x más requests/segundo** si incluyes un email válido.

---

### **Error: No module named 'wordcloud'**

```
ModuleNotFoundError: No module named 'wordcloud'
```

**Solución**:
```bash
pip install wordcloud matplotlib
```

Si falla en Windows, instala pre-compilados:
```bash
pip install pipwin
pipwin install wordcloud
```

---

### **Error: Empty DataFrame / No se encontraron resultados**

**Posibles causas**:
- 🔍 Query demasiado específica (prueba con keywords más generales)
- 🌐 OpenAlex no tiene datos para ese topic (verifica en openalex.org)
- 🚫 Filtros muy restrictivos (desactiva "Solo journals" temporalmente)

**Soluciones**:
1. Usa **consulta libre** en lugar de título/abstract
2. Prueba con keywords en inglés (mejor cobertura en OpenAlex)
3. Aumenta `max_pages` para obtener más works

---

### **Error: 'NoneType' object is not subscriptable**

**Causa**: Datos incompletos de OpenAlex (work sin título, source sin summary_stats, etc.)

**Solución**: El código ya incluye null-safety en versiones recientes. Si ocurre:
1. Actualiza a la última versión del código
2. Verifica traceback en la UI (se muestra automáticamente con `st.code()`)
3. Reporta el issue con la query que causó el error

---

### **Cuartiles no se muestran (aparece "-")**

**Causa**: La revista no tiene match con SJR por ISSN.

**Soluciones**:
1. ✅ Verifica que cargaste `scimagojr 2024.csv` con `python -m etl.load_sjr_2024`
2. 🔍 La revista puede no estar en SJR (revistas nuevas, de acceso no indizado, etc.)
3. 📋 Verifica ISSN en MySQL: `SELECT issn_l FROM sources WHERE source_id = 'S...'`

---

## 🤝 Contribuciones

Este proyecto es de código abierto con fines educativos. Contribuciones bienvenidas:

- 🐛 Reporta bugs abriendo un issue
- 💡 Sugiere features en la sección de issues
- 🔧 Envía pull requests con mejoras

---

## 📄 Licencia

Este proyecto es de código abierto para **fines educativos**.

**Fuentes de datos**:
- OpenAlex API → Licencia CC0 (dominio público)
- SCImago Journal Rank → Uso libre para investigación (citar fuente)

---

## 📚 Referencias

- **OpenAlex API**: `https://docs.openalex.org/`
- **SCImago Journal Rank**: `https://www.scimagojr.com/`
- **Streamlit Docs**: `https://docs.streamlit.io/`
- **SQLAlchemy Docs**: `https://docs.sqlalchemy.org/`

---

## 👤 Autor

Proyecto desarrollado como parte del Bootcamp de Data Science e IA.

**Contacto**: Ver `.env.example` para email de OpenAlex Polite Pool.

---

**⭐ Si te resulta útil este proyecto, dale una estrella en GitHub!**
