import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = "abc"#os.environ.get('SECRET_KEY', os.urandom(24).hex())
    TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

    LLM_MODEL = os.environ.get('LLM_MODEL', 'qwen-qwq-32b')
    EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
    CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE', 500))
    CHUNK_OVERLAP = int(os.environ.get('CHUNK_OVERLAP', 200))
    USER_SEMANTIC_CHUNKING = os.environ.get('USER_SEMANTIC_CHUNKING', True)
    INDEX_PATH = os.environ.get('INDEX_PATH', os.path.join(os.getcwd(), 'data', 'faiss_index'))
    SIMILARITY_THRESHOLD = float(os.environ.get('SIMILARITY_THRESHOLD', 0.7))

    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'data', 'input_data'))
    ALLOWED_EXTENSIONS = set(os.environ.get('ALLOWED_EXTENSIONS', 'pdf,doc,docx').split(','))
    JWT_COOKIE_NAME = os.environ.get('JWT_COOKIE_NAME', 'jwt_token')
    
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_USER = os.environ.get('DB_USER')
    DB_NAME = os.environ.get('DB_NAME', 'document_chat')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_HOST = os.environ.get('DB_HOST')

    def validate(self):
        """Validate required configuration variables."""
        required = ['DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_NAME', 'DB_PORT']
        missing = [var for var in required if not getattr(self, var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        if not self.TAVILY_API_KEY or not self.GROQ_API_KEY:
            raise ValueError("TAVILY_API_KEY and GROQ_API_KEY are required")

config = Config()
config.validate()