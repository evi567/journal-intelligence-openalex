# 📚 Journal Intelligence
### *Sistema inteligente de recomendación de revistas científicas basado en OpenAlex*

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-FF4B4B?logo=streamlit&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0%2B-4479A1?logo=mysql&logoColor=white)
![OpenAlex](https://img.shields.io/badge/OpenAlex-API-orange)
![SJR](https://img.shields.io/badge/SCImago-JR-green)

---

## 🎯 ¿Qué es?

**Journal Intelligence** ayuda a investigadores a **decidir dónde publicar** y **encontrar artículos relevantes** usando datos de OpenAlex, algoritmos de ranking y métricas SJR. Recomienda revistas según el contenido de tu manuscrito o por similitud a revistas de referencia.

---

## ✨ ¿Qué obtienes?

### 🔍 **Búsqueda por Texto**
- Ingresa **título + abstract** o keywords libres
- Ranking de revistas con **cuartiles SJR** (Q1–Q4)
- Top artículos relacionados ordenados por **relevancia**
- Fallback automático: modo preciso → fulltext si 0 resultados

### 📰 **Búsqueda por Revista**
- Ingresa **ISSN** o nombre de revista de referencia
- Encuentra revistas **similares** por métricas (impacto, productividad, citas)
- Opción de similitud temática con topics de OpenAlex

---

## ⚡ Demo rápida (en 30 segundos)

Ya tienes MySQL y Python instalados? Perfecto:

```bash
git clone https://github.com/evi567/journal-intelligence-openalex.git
cd journal-intelligence-openalex
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
# Configura .env con tus credenciales MySQL
python db/init_db.py
streamlit run app/app.py
```

Abre `http://localhost:8501` → Ingresa título/abstract → **¡Revistas recomendadas!**

---

## 🏗️ Cómo funciona

```
OpenAlex API → ETL (extracción + normalización) → MySQL
              ↓
        Ranking/Similitud (scikit-learn) → Streamlit UI
```

**Pipeline:**
1. **OpenAlex**: Búsqueda de works/sources con Polite Pool
2. **ETL**: Query booleana, filtros, dedupe
3. **MySQL**: Persistencia (sources, works_sample, sjr_2024, queries)
4. **ML**: Score = 0.75×freq + 0.15×impacto + 0.05×works + 0.05×citas
5. **UI**: Streamlit con 2 tabs, filtros, cuartiles SJR

---

## 🛠️ Instalación (Windows)

### **Requisitos:** Python 3.10+, MySQL 8.0+, Git

```bash
# 1. Clonar repo
git clone https://github.com/evi567/journal-intelligence-openalex.git
cd journal-intelligence-openalex

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar .env
copy .env.example .env
# Edita .env con tus credenciales MySQL y email de OpenAlex
```

**Archivo `.env`:**
```ini
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DB=journal_intelligence
MYSQL_USER=root
MYSQL_PASSWORD=tu_password
OPENALEX_EMAIL=tu_email@ejemplo.com  # Importante: Polite Pool 10x más requests
```

```bash
# 5. Inicializar base de datos
python db/init_db.py

# 6. (Opcional) Cargar cuartiles SJR
# Descarga scimagojr 2024.csv de https://www.scimagojr.com/journalrank.php
# Colócalo en data/scimagojr 2024.csv
python -m etl.load_sjr_2024

# 7. Ejecutar app
streamlit run app/app.py
```

Abre `http://localhost:8501` 🎉

---

## 🎮 Uso

### **Tab 1: Buscar por Texto** 🔎
1. Ingresa **Título** (opcional) + **Abstract** (min 50 caracteres) o **Consulta libre**
2. Clic **"🚀 Recomendar Revistas"**
3. Resultados: top revistas con cuartil SJR, frecuencia, impacto + top artículos ordenados por relevancia
4. Filtros opcionales: incluir editorial/letter, incluir repos/preprints

### **Tab 2: Buscar por Revista** 📚
1. Ingresa **ISSN-L** (`1234-5678`) o **Título** parcial → Busca
2. Selecciona revista si hay múltiples → Clic **"🔗 Buscar Revistas Similares"**
3. Modo: solo métricas o métricas + temática (topics)

### **Configuración (Sidebar):**
- Per page: 50–200 (default 200)
- Max pages: 1–5 (default 2)
- Top N revistas: 5–20 (default 10)
- Keywords abstract: 5–20 (default 10)
- Debug query: muestra construcción de query

---

## 📊 Ranking Explicado

**Fórmula:**
```python
score = 0.75 × freq_norm + 0.15 × two_yr_norm + 0.05 × works_ref_norm + 0.05 × cites_ref_norm
```

| Métrica | Peso | Descripción |
|---------|------|-------------|
| **Frecuencia** | 75% | Apariciones en resultados OpenAlex para tu query |
| **Impacto 2yr** | 15% | Media de citas/trabajo últimos 2 años |
| **Works (ref)** | 5% | Trabajos hace 4 años (proxy actividad reciente) |
| **Citas (ref)** | 5% | Citas año referencia (proxy visibilidad) |

✅ Prioriza **relevancia temática directa** sobre revistas generalistas  
✅ Normalización max-scaling [0,1] antes de aplicar pesos  
✅ Evita recomendar revistas inactivas o descontinuadas

---

## 🧮 Similitud (Búsqueda por Revista)

**Features numéricas (5D):**
1. `two_yr_mean_citedness` → Impacto reciente
2. `works_ref_year` → Productividad referencia
3. `cites_ref_year` → Citas referencia
4. `works_count` → Productividad histórica
5. `cited_by_count` → Impacto histórico

**Proceso:**
- Z-score normalización (StandardScaler)
- Similitud coseno entre vectores
- Opcional: combina 70% numérico + 30% Jaccard (topics)

---

## 🏆 Cuartiles SJR

- **Match**: ISSN normalizado (sin guiones) JOIN con SJR CSV
- **Script**: `python -m etl.load_sjr_2024` carga ~24k revistas
- **Visualización**: Q1/Q2/Q3/Q4 o "-" si no hay match

---

## 📁 Componentes Principales

| Componente | Función |
|------------|---------|
| `etl/openalex_client.py` | Cliente API, retry, query booleana, fallback |
| `etl/load_openalex.py` | Pipeline ETL: works → sources → MySQL |
| `ml/ranker.py` | Algoritmo ranking (75/15/5/5) |
| `ml/similarity.py` | Similitud coseno + Jaccard |
| `db/` | Esquema MySQL, init, conexión |
| `app/app.py` | UI Streamlit (2 tabs) |

---

## 🔬 Casos de Uso

1. **Tesista**: Ingresa título/abstract → Recibe top 10 revistas con cuartiles
2. **Investigador**: Busca por tema → Obtiene top 50 artículos relevantes
3. **Grupo**: Tiene revista de referencia (ISSN) → Descubre revistas similares

---

## ⚠️ Limitaciones

- **Cobertura**: OpenAlex mejor en STEM; solo metadatos, no full-text
- **SJR**: Carga manual CSV, no API pública
- **Idioma**: Mejor en inglés (OpenAlex indexa principalmente EN)
- **Rate limit**: OpenAlex API (Polite Pool mejora 10x con email)

---

## 🚀 Mejoras Futuras

- Caché de búsquedas repetidas para mejorar rendimiento
- Exportar resultados a CSV/Excel desde la UI
- Traducción automática de queries ES→EN
- Dashboard de analytics (queries populares, tendencias)
- Integración con otras fuentes de métricas (JCR, Scopus)

---

## 📚 Stack

Python 3.10+ · Streamlit 1.28+ · MySQL 8.0+ · SQLAlchemy 2.x · pandas · scikit-learn · OpenAlex API · requests · python-dotenv

---

## 🤝 Contribuciones

Proyecto de **bootcamp Data & IA de Upgrade Hub**. Fork → Branch → Commit → PR bienvenidos.

---

## 📄 Licencia

Código abierto CC0. OpenAlex (CC0), SJR (uso educativo).

---

## 👨‍💻 Autor

**E. Becerra Rodero** - Bootcamp Data & IA 2026  
🐙 GitHub: [@evi567](https://github.com/evi567)

---

## 🙏 Agradecimientos

OpenAlex · SCImago · Streamlit · Bootcamp instructores y compañeros

---

<div align="center">

**⭐ Si te ha sido útil, considera dar una estrella al repo ⭐**

</div>
