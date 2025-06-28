from celery import Celery
from Configuration import config
from modules.database import generate_otp, send_otp
from src.indexers import FAISSVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
import os

app = Celery('tasks', broker=os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0'), backend=os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'))

embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
vector_store = FAISSVectorStore(
    index_path=config.INDEX_PATH,
    use_semantic_chunking=config.USER_SEMANTIC_CHUNKING,
    chunker=None,  # Will be initialized in task
    embeddings=embeddings
)

@app.task
def send_otp_task(email, phone):
    """Send OTP asynchronously."""
    otp = generate_otp()
    print(otp)
    send_otp(email, phone, otp)

@app.task
def index_document_task(file_id, text, chat_id, filename, source):
    """Index document in vector store asynchronously."""
    from src.chunking import RAGChunker
    chunker = RAGChunker(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        use_semantic_chunking=config.USER_SEMANTIC_CHUNKING,
        embeddings=embeddings
    )
    vector_store.chunker = chunker
    try:
        vector_store.add_documents(
            texts=[text],
            metadatas=[{
                'doc_id': file_id,
                'chat_id': chat_id,
                'filename': filename,
                'source': source
            }]
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error indexing document {file_id}: {str(e)}")
        raise