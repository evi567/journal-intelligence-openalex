# Journal Intelligence - OpenAlex

Sistema de recomendación de revistas científicas basado en datos de OpenAlex.

## Descripción

Este proyecto permite:
- Ingestar datos desde la API de OpenAlex (works y sources)
- Persistir información en MySQL local
- Generar recomendaciones de revistas basadas en consultas de texto
- Visualizar rankings y detalles de revistas mediante una interfaz Streamlit

## Requisitos Previos

- Python 3.8+
- MySQL Server 8.0+ corriendo en localhost:3306
- Cuenta de correo para usar OpenAlex Polite Pool (opcional pero recomendado)

## Instalación

### 1. Clonar/Descargar el proyecto

```bash
cd journal-intelligence-openalex
```

### 2. Crear entorno virtual

```bash
python -m venv venv
venv\Scripts\activate  # En Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Copia `.env.example` a `.env` y edita los valores:

```bash
copy .env.example .env
```

Edita `.env` con tus credenciales de MySQL:

```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DB=journal_intelligence
MYSQL_USER=root
MYSQL_PASSWORD=tu_password
OPENALEX_EMAIL=tu_email@ejemplo.com
```

### 5. Inicializar la base de datos

```bash
python db/init_db.py
```

Este script:
- Crea la base de datos `journal_intelligence` (si no existe)
- Ejecuta `db/schema.sql` para crear las tablas necesarias

## Uso

### 1. Ejecutar la aplicación Streamlit

```bash
streamlit run app/app.py
```

La aplicación abrirá en tu navegador (por defecto en http://localhost:8501)

### 2. Usar la interfaz

1. **Ingresar consulta**: Escribe el título y/o abstract de tu investigación
2. **Obtener recomendaciones**: Haz clic en "Recomendar Revistas"
3. **Ver resultados**: Se mostrará un ranking de las 10 mejores revistas
4. **Ver detalles**: Selecciona una revista para ver información completa

### 3. Uso programático (opcional)

Puedes ejecutar el pipeline manualmente:

```python
from etl.load_openalex import load_works_and_sources
from ml.ranker import calculate_scores
from ml.save_recommendations import save_query_and_recommendations

# Cargar datos
query = "machine learning natural language processing"
df_candidates = load_works_and_sources(query)

# Calcular scores
df_ranked = calculate_scores(df_candidates)

# Guardar recomendaciones
save_query_and_recommendations(query, df_ranked)
```

## Estructura del Proyecto

```
journal-intelligence-openalex/
├── app/                    # Aplicación Streamlit
│   └── app.py
├── etl/                    # Ingesta de datos
│   ├── openalex_client.py  # Cliente API OpenAlex
│   └── load_openalex.py    # Pipeline de carga
├── db/                     # Base de datos
│   ├── schema.sql          # Esquema de tablas
│   ├── init_db.py          # Inicialización
│   └── connection.py       # Conexión SQLAlchemy
├── ml/                     # Ranking y ML
│   ├── ranker.py           # Cálculo de scores
│   └── save_recommendations.py
├── notebooks/              # Jupyter notebooks (opcional)
├── tests/                  # Tests (vacío)
├── data/                   # Datos temporales
├── requirements.txt
├── .env.example
├── config.py
└── README.md
```

## Cálculo del Score

El score de recomendación se calcula como:

```
score = 0.6 * freq_norm + 0.2 * log(cited_by_count + 1) + 0.2 * log(works_count + 1)
```

Donde:
- `freq_norm`: frecuencia normalizada de la revista en los resultados de búsqueda
- `cited_by_count`: total de citas recibidas por la revista
- `works_count`: total de trabajos publicados en la revista

## Troubleshooting

### Error de conexión a MySQL

```
sqlalchemy.exc.OperationalError: (2003, "Can't connect to MySQL server...")
```

Soluciones:
- Verifica que MySQL esté corriendo
- Confirma usuario/password en `.env`
- Asegúrate de que el puerto 3306 esté abierto

### Error al llamar a OpenAlex

```
requests.exceptions.HTTPError: 429 Client Error: Too Many Requests
```

Soluciones:
- Agrega tu email en `OPENALEX_EMAIL` en `.env` para usar Polite Pool
- Espera unos segundos y vuelve a intentar
- El código incluye reintentos automáticos con backoff

## Licencia

Este proyecto es de código abierto para fines educativos.
