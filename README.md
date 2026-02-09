# 📚 Journal Intelligence
### *Sistema inteligente de recomendación de revistas científicas basado en OpenAlex*

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B?logo=streamlit&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-4479A1?logo=mysql&logoColor=white)
![OpenAlex](https://img.shields.io/badge/OpenAlex-API-orange)
![SJR](https://img.shields.io/badge/SCImago-JR-green)

---

## 🎯 ¿Qué es Journal Intelligence?

**Journal Intelligence** es un sistema de recomendación inteligente que ayuda a investigadores a **decidir dónde publicar su trabajo** y **encontrar artículos relevantes** para enriquecer su investigación. Utiliza datos abiertos de OpenAlex, métricas de impacto (SJR) y algoritmos de ranking/similitud para ofrecer recomendaciones personalizadas basadas en el contenido de tu manuscrito o una revista de referencia.

---

## ✨ Funcionalidades Clave

### 🔍 **1. Búsqueda por Texto (Título + Abstract)**
- **Modo Preciso**: Búsqueda en `title_and_abstract` de OpenAlex
- **Fallback Automático**: Si 0 resultados, reintenta con `fulltext` usando query booleana optimizada
- **Query Inteligente**: Extrae keywords/bigrams, filtra términos genéricos, limita a 15 tokens
- **Ranking Personalizado**: Calcula score basado en frecuencia (75%), impacto (15%) y actividad reciente (10%)

### 📰 **2. Búsqueda por Revista (ISSN/Título)**
- Busca revistas similares a una de referencia
- **Similitud Numérica**: Coseno sobre características normalizadas (impacto, productividad, citas)
- **Similitud Temática** (opcional): Jaccard sobre topics de OpenAlex
- Enriquecimiento con cuartiles SJR si disponible

### 📄 **3. Top Artículos Relacionados**
- Muestra artículos más relevantes al tema de búsqueda
- **Ordenamiento Inteligente**:
  - Modo preciso: Por `relevance_score` de OpenAlex
  - Modo fulltext: Score mixto (70% relevancia + 30% citas)
- Filtrado de tipos: solo artículos, preprints, reviews (excluye paratext/editorial)
- Filtro por source type: journals por defecto (opción de incluir repos/ebooks)

### 🏆 **4. Enriquecimiento SJR (SCImago Journal Rank)**
- Integración con cuartiles Q1/Q2/Q3/Q4
- Matching por ISSN normalizado
- Visualización con código de colores

---

## 🏗️ Arquitectura del Sistema

```
┌─────────────────┐
│   OpenAlex API  │  ← Búsqueda de works/sources (Polite Pool)
└────────┬────────┘
         │ JSON
         ▼
┌─────────────────┐
│   ETL Pipeline  │  ← Extracción, normalización, frecuencias
│  (openalex_     │     Query booleana, filtros, dedupe
│   client.py,    │
│   load_openalex)│
└────────┬────────┘
         │ DataFrames
         ▼
┌─────────────────┐
│  MySQL Database │  ← Persistencia (sources, works_sample,
│  (8.0+)         │     sjr_2024, queries, recommendations)
└────────┬────────┘
         │ SQL
         ▼
┌─────────────────┐
│  ML Ranking &   │  ← Score: 0.75*freq + 0.15*impact + 0.05*works + 0.05*cites
│  Similarity     │     Similitud: Coseno + Z-score (opcional Jaccard)
│  (ranker.py,    │
│   similarity.py)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Streamlit UI   │  ← Interfaz interactiva (tabs, filtros, debug,
│  (app.py)       │     wordcloud, cuartiles SJR)
└─────────────────┘
```

### **Componentes Principales:**

| Componente | Función |
|------------|---------|
| `etl/openalex_client.py` | Cliente API con retry, query booleana, fallback preciso→amplio |
| `etl/load_openalex.py` | Pipeline ETL: works → sources → MySQL (optimizado top 30 sources) |
| `ml/ranker.py` | Algoritmo de ranking con normalización Z-score |
| `ml/similarity.py` | Cálculo de similitud numérica/temática entre journals |
| `db/` | Esquema MySQL, init script, conexión SQLAlchemy |
| `app/app.py` | UI Streamlit con 2 tabs, filtros, debug mode |

---

## 📊 Ranking Explicado

El sistema calcula un **score compuesto** para cada revista candidata:

```python
score = 0.75 × freq_norm + 0.15 × two_yr_norm + 0.05 × works_ref_norm + 0.05 × cites_ref_norm
```

| Métrica | Peso | Descripción |
|---------|------|-------------|
| **Frecuencia** (`freq`) | **75%** | Veces que la revista aparece en resultados de OpenAlex para la query |
| **Impacto** (`two_yr_mean_citedness`) | **15%** | Media de citas por trabajo en últimos 2 años |
| **Trabajos (año ref)** (`works_ref_year`) | **5%** | Número de trabajos publicados hace 4 años (proxy actividad reciente) |
| **Citas (año ref)** (`cites_ref_year`) | **5%** | Citas recibidas en año de referencia (proxy visibilidad) |

> **Normalización**: Todas las métricas se normalizan a [0, 1] usando max-scaling antes de aplicar pesos.

**Explicación generada**:
```
Aparece 12 veces en los resultados | 450 trabajos (año ref), 8,932 citas (año ref)
```

---

## 🛠️ Instalación y Ejecución (Windows)

### **Requisitos Previos**
- Python 3.8+
- MySQL 8.0+ (instalado y corriendo)
- Git

### **1. Clonar el Repositorio**
```bash
git clone https://github.com/tu-usuario/journal-intelligence-openalex.git
cd journal-intelligence-openalex
```

### **2. Crear Entorno Virtual**
```bash
python -m venv venv
venv\Scripts\activate
```

### **3. Instalar Dependencias**
```bash
pip install -r requirements.txt
```

### **4. Configurar Variables de Entorno**
Crea un archivo `.env` en la raíz del proyecto:
```env
# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DB=journal_intelligence
MYSQL_USER=root
MYSQL_PASSWORD=tu_password_aqui

# OpenAlex (opcional pero recomendado para Polite Pool)
OPENALEX_EMAIL=tu_email@ejemplo.com
```

### **5. Inicializar Base de Datos**
```bash
python db/init_db.py
```

Esto creará las tablas: `sources`, `works_sample`, `sjr_2024`, `queries`, `recommendations`.

### **6. (Opcional) Cargar Datos SJR**
Si tienes un CSV con cuartiles SJR, colócalo en `data/sjr_2024.csv` con columnas:
- `issn_norm` (sin guiones)
- `quartile` (Q1, Q2, Q3, Q4)
- `sjr` (valor numérico)

El sistema lo cargará automáticamente.

### **7. Ejecutar la Aplicación**
```bash
streamlit run app/app.py
```

Abre tu navegador en `http://localhost:8501` 🎉

---

## 📸 Capturas de Pantalla

<!-- Placeholder: Agrega tus capturas aquí -->
![Búsqueda por texto](/assets/screenshot-text-search.png)
*Búsqueda por título + abstract con ranking de revistas*

![Top artículos relacionados](/assets/screenshot-top-articles.png)
*Top artículos ordenados por relevancia*

![Búsqueda por revista](/assets/screenshot-journal-search.png)
*Búsqueda de revistas similares por ISSN*

---

## ⚙️ Configuración Avanzada

### **Parámetros en `config.py`:**
```python
DEFAULT_PER_PAGE = 200        # Works por página de OpenAlex
DEFAULT_MAX_PAGES = 2         # Páginas máximas a descargar
TOP_SOURCES_LIMIT = 30        # Top sources a enriquecer con API (optimización)
```

### **Sidebar en Streamlit:**
- **Per page**: 50-200 (default 200)
- **Max pages**: 1-5 (default 2)
- **Top N revistas**: 5-20 (default 10)
- **Keywords del abstract**: 5-20 (default 10)
- **Modo de búsqueda**: Precisa (title+abstract) / Amplia (fulltext)
- **Debug query**: Muestra construcción de query final

---

## 🔬 Casos de Uso

### **Escenario 1: Tesista buscando dónde publicar**
1. Ingresa título y abstract de su tesis
2. Sistema extrae keywords, busca en OpenAlex
3. Recibe top 10 revistas con cuartiles SJR
4. Explora detalles: impacto, frecuencia, publisher

### **Escenario 2: Investigador escribiendo estado del arte**
1. Busca por tema ("machine learning neural networks")
2. Obtiene top 50 artículos más relevantes
3. Filtra solo articles/reviews
4. Accede a OpenAlex para leer abstracts

### **Escenario 3: Grupo explorando alternativas de publicación**
1. Tienen una revista de referencia (ISSN conocido)
2. Buscan revistas similares por métricas
3. Comparan cuartiles, impacto, productividad
4. Descubren opciones en su nicho académico

---

## ⚠️ Limitaciones y Mejoras Futuras

### **Limitaciones Actuales**
- **Cobertura**: Depende de la completitud de OpenAlex (no todas las revistas tienen todos los metadatos)
- **SJR**: Requiere carga manual de CSV actualizado (no hay API pública gratuita)
- **Idioma**: Funciona mejor con queries en inglés (OpenAlex indexa principalmente en inglés)

### **Mejoras Futuras**
- 🔄 **Caché inteligente**: Evitar llamadas API duplicadas almacenando results en Redis
- 📈 **Analytics dashboard**: Visualización de métricas de uso, queries populares, rendimiento
- 🌍 **Soporte multiidioma**: Traducción automática de queries ES→EN con detección de idioma
- 🤖 **Fine-tuning ranking**: Aprender pesos óptimos desde feedback de usuarios (ML supervisado)
- 📊 **Exportación**: Generar reportes PDF/Excel con resultados y gráficos
- 🔗 **Integración Scopus/WoS**: Enriquecer con métricas de otras fuentes (JCR, h-index)

---

## 📚 Stack Tecnológico

| Tecnología | Versión | Uso |
|------------|---------|-----|
| **Python** | 3.8+ | Lenguaje principal |
| **Streamlit** | 1.28+ | Framework UI interactivo |
| **MySQL** | 8.0+ | Base de datos relacional |
| **SQLAlchemy** | 2.x | ORM Python-MySQL |
| **pandas** | Latest | Manipulación de datos |
| **scikit-learn** | Latest | ML (coseno, normalización) |
| **OpenAlex API** | v1 | Fuente de datos académicos |
| **requests** | Latest | Cliente HTTP con retry |
| **python-dotenv** | Latest | Manejo de variables de entorno |

---

## 🤝 Contribuciones

Este es un proyecto de **bootcamp de Data & IA de Upgrade Hub**. Sugerencias y mejoras son bienvenidas:

1. Fork el proyecto
2. Crea una branch (`git checkout -b feature/mejora`)
3. Commit cambios (`git commit -m 'Add: nueva feature'`)
4. Push a branch (`git push origin feature/mejora`)
5. Abre un Pull Request

---

## 📄 Licencia

Este proyecto es de código abierto bajo licencia CC0.

---

## 👨‍💻 Autor

**E. Becerra Rodero** - Bootcamp Data & IA 2026

🐙 GitHub: [@evi567](https://github.com/evi567)

---

## 🙏 Agradecimientos

- **OpenAlex** por proporcionar datos académicos abiertos y de alta calidad
- **SCImago** por métricas SJR de revistas científicas
- **Streamlit** por facilitar la creación de interfaces interactivas
- **Bootcamp instructores y compañeros** por feedback y apoyo durante el desarrollo

---

<div align="center">

**⭐ Si te ha sido útil, considera dar una estrella al repo ⭐**

</div>

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
