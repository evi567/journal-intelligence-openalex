"""
Cliente para interactuar con la API de OpenAlex.
Incluye manejo de errores y reintentos con backoff.
"""
import requests
import backoff
import sys
import os

# Agregar el directorio raíz al path para importar config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config


class OpenAlexClient:
    """Cliente para la API de OpenAlex con manejo de reintentos."""
    
    def __init__(self, email=None):
        """
        Inicializa el cliente.
        
        Args:
            email (str, optional): Email para el polite pool de OpenAlex
        """
        self.base_url = config.OPENALEX_BASE_URL
        self.email = email or config.OPENALEX_EMAIL
        self.session = requests.Session()
        
        # Headers para todas las requests
        if self.email:
            self.session.headers.update({'User-Agent': f'mailto:{self.email}'})
    
    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.RequestException, requests.exceptions.HTTPError),
        max_tries=3,
        max_time=30
    )
    def _make_request(self, url, params=None):
        """
        Realiza una request HTTP con reintentos automáticos.
        
        Args:
            url (str): URL completa a consultar
            params (dict, optional): Parámetros de la query
            
        Returns:
            dict: JSON response
            
        Raises:
            requests.exceptions.HTTPError: Si la request falla después de reintentos
        """
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    
    def search_works_by_text(self, query_text, per_page=200, max_pages=2):
        """
        Busca trabajos (works) en OpenAlex por texto.
        
        Args:
            query_text (str): Texto de búsqueda (título, abstract, etc.)
            per_page (int): Resultados por página (máx 200)
            max_pages (int): Número máximo de páginas a descargar
            
        Returns:
            list: Lista de works (diccionarios)
            
        Raises:
            Exception: Si la búsqueda falla
        """
        try:
            url = f"{self.base_url}/works"
            all_works = []
            
            for page in range(1, max_pages + 1):
                params = {
                    'search': query_text,
                    'per-page': min(per_page, 200),  # OpenAlex máx 200
                    'page': page,
                    'mailto': self.email
                }
                
                print(f"  Descargando página {page}/{max_pages}...")
                
                try:
                    data = self._make_request(url, params)
                    results = data.get('results', [])
                    
                    if not results:
                        print(f"  No hay más resultados en página {page}")
                        break
                    
                    all_works.extend(results)
                    
                    # Info de metadatos
                    meta = data.get('meta', {})
                    total_count = meta.get('count', 0)
                    print(f"  → {len(results)} works descargados (total disponible: {total_count})")
                    
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 429:
                        print(f"  ⚠️  Rate limit alcanzado en página {page}. Deteniendo descarga.")
                        break
                    raise
            
            print(f"✅ Total descargado: {len(all_works)} works")
            return all_works
            
        except Exception as e:
            print(f"❌ Error al buscar works en OpenAlex: {e}")
            raise
    
    def get_source(self, source_id):
        """
        Obtiene información detallada de una fuente/revista por su ID.
        
        Args:
            source_id (str): ID de OpenAlex de la fuente (ej: 'S12345678')
            
        Returns:
            dict: Información de la fuente, o None si no se encuentra
        """
        try:
            # El source_id ya viene como URL completa o como ID
            if source_id.startswith('http'):
                # Extraer el ID del URL
                source_id = source_id.split('/')[-1]
            
            url = f"{self.base_url}/sources/{source_id}"
            params = {'mailto': self.email} if self.email else {}
            
            data = self._make_request(url, params)
            return data
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"  ⚠️  Fuente {source_id} no encontrada")
                return None
            print(f"  ❌ Error al obtener fuente {source_id}: {e}")
            return None
        except Exception as e:
            print(f"  ❌ Error inesperado al obtener fuente {source_id}: {e}")
            return None


# Funciones de conveniencia para usar sin instanciar la clase

def search_works_by_text(query_text, per_page=200, max_pages=2):
    """
    Busca trabajos en OpenAlex (función de conveniencia).
    
    Args:
        query_text (str): Texto de búsqueda
        per_page (int): Resultados por página
        max_pages (int): Páginas máximas a descargar
        
    Returns:
        list: Lista de works
    """
    client = OpenAlexClient()
    return client.search_works_by_text(query_text, per_page, max_pages)


def get_source(source_id):
    """
    Obtiene una fuente de OpenAlex (función de conveniencia).
    
    Args:
        source_id (str): ID de la fuente
        
    Returns:
        dict: Información de la fuente
    """
    client = OpenAlexClient()
    return client.get_source(source_id)


if __name__ == "__main__":
    # Test del cliente
    print("Testing OpenAlex Client...")
    print("=" * 60)
    
    # Test 1: Buscar works
    print("\n1. Buscando works sobre 'machine learning'...")
    works = search_works_by_text("machine learning", per_page=50, max_pages=1)
    print(f"   Resultados: {len(works)} works")
    
    if works:
        print(f"\n   Primer resultado:")
        print(f"   - Título: {works[0].get('title', 'N/A')}")
        print(f"   - Año: {works[0].get('publication_year', 'N/A')}")
        
        # Test 2: Obtener source del primer work
        primary_location = works[0].get('primary_location', {})
        if primary_location and primary_location.get('source'):
            source_id = primary_location['source'].get('id', '').split('/')[-1]
            print(f"\n2. Obteniendo información de la fuente {source_id}...")
            source = get_source(source_id)
            if source:
                print(f"   - Nombre: {source.get('display_name', 'N/A')}")
                print(f"   - Tipo: {source.get('type', 'N/A')}")
                print(f"   - Works: {source.get('works_count', 0)}")
