import os
from pathlib import Path
from typing import List
import chromadb
from chromadb.utils import embedding_functions
from langchain_community.document_loaders import TextLoader, PyPDFLoader, UnstructuredMarkdownLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Configuración
BASE = Path(__file__).parent
KNOWLEDGE_DIR = BASE / "knowledge"
DB_DIR = BASE / "ryuko_knowledge_db"

# Usamos un modelo de embedding local y ligero
# Esto convierte texto en vectores matemáticos sin usar internet.
embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

class ConocimientoLocal:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=str(DB_DIR))
        self.collection = self.client.get_or_create_collection(
            name="ryuko_knowledge",
            embedding_function=embedding_func
        )

    def indexar_documentos(self):
        """Escanea la carpeta /knowledge y guarda el contenido en la base de datos vectorial."""
        if not KNOWLEDGE_DIR.exists():
            KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
            return "Carpeta /knowledge creada. Añade archivos para indexar."

        documentos = []
        for archivo in KNOWLEDGE_DIR.iterdir():
            try:
                if archivo.suffix == ".txt":
                    loader = TextLoader(str(archivo), encoding="utf-8")
                    documentos.extend(loader.load())
                elif archivo.suffix == ".pdf":
                    loader = PyPDFLoader(str(archivo))
                    documentos.extend(loader.load())
                elif archivo.suffix == ".md":
                    loader = UnstructuredMarkdownLoader(str(archivo))
                    documentos.extend(loader.load())
            except Exception as e:
                print(f"Error cargando {archivo.name}: {e}")

        if not documentos:
            return "No se encontraron documentos compatibles en /knowledge."

        # Dividimos los textos en trozos pequeños para que el modelo no se pierda
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks = text_splitter.split_documents(documentos)

        # Guardamos en ChromaDB
        for i, chunk in enumerate(chunks):
            self.collection.add(
                documents=[chunk.page_content],
                ids=[f"doc_{os.urandom(4).hex()}_{i}"]
            )

        return f"Indexados {len(chunks)} fragmentos de conocimiento."

    def consultar(self, pregunta: str, n_resultados: int = 3):
        """Busca la información más relevante en la base de datos."""
        try:
            resultados = self.collection.query(
                query_texts=[pregunta],
                n_results=n_resultados
            )
            # Unimos los fragmentos encontrados en un solo texto de contexto
            if resultados and resultados['documents']:
                contexto = "\n---\n".join(resultados['documents'][0])
                return contexto
        except Exception as e:
            print(f"Error en consulta RAG: {e}")
        return None

# Instancia global
brain = ConocimientoLocal()
