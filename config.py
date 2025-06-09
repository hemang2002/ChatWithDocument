import os
import dotenv

dotenv.load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 200
USER_SEMENTIC_CHUNKING = True
INDEX_PATH = os.path.join(os.getcwd(), "data", "faiss_index")