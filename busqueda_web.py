from duckduckgo_search import DDGS

def buscar_informacion(consulta):
    """
    Busca información en la web usando DuckDuckGo y devuelve un resumen de los resultados.
    """
    try:
        with DDGS() as ddgs:
            # Buscamos los primeros 3 resultados
            resultados = [r for r in ddgs.text(consulta, max_results=3)]

            if not resultados:
                return "No he encontrado información relevante en la web."

            # Construimos un texto concatenando los snippets de los resultados
            resumen = "\n".join([f"Fuente: {r['href']}\nContenido: {r['body']}" for r in resultados])
            return resumen
    except Exception as e:
        return f"Error al realizar la búsqueda web: {str(e)}"

if __name__ == "__main__":
    # Prueba rápida
    print(buscar_informacion("¿Cuál es el clima hoy en Madrid?"))
