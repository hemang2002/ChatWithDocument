from typing import List, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain.docstore.document import Document
from Configuration import config
import logging
import warnings
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

class RAGChunker:


    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        use_semantic_chunking: bool = True,
        embeddings: Optional[HuggingFaceEmbeddings] = None,
    ):

        self.chunk_size = chunk_size
        self.chunk_overlap  = chunk_overlap
        self.use_semantic_chunking = use_semantic_chunking

        if self.use_semantic_chunking:
            try:
                self.text_splitter = SemanticChunker(
                    breakpoint_threshold_type = "percentile",
                    breakpoint_threshold_amount = 95,
                    embeddings = embeddings if embeddings else HuggingFaceEmbeddings(model_name = config.EMBEDDING_MODEL),
                )
            except:
                logger.error("Please install sentence_transformers package to use semantic chunking")

        else:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size = self.chunk_size,
                chunk_overlap  = self.chunk_overlap,
                length_function = len,
            )

                
    def chunk_text(self, text: str, metadata: Optional[dict] = None) -> list[Document]:
        """
        Chunk input text into smaller segments.

        Args:
            text (str): The input text to be chunked.
            metadata (dict): Metadata associated with the text.

        Returns:
            list: List of chunks.
        """
        try:
            if not text:
                return []
            
            doc = Document(page_content=text, metadata=metadata or {})
            
            if self.use_semantic_chunking:
                chunks = self.text_splitter.split_documents([doc])
            else:
                chunks = self.text_splitter.split_text([doc])

            return chunks
        except Exception as e:
            logger.error("Error in chunking text: ", e)


    def chunk_documents(self, documents: List[Document]) -> list[Document]:
        """
        Chunk input documents into smaller segments.

        Args:
            documents (list): List of documents to be chunked.

        Returns:
            list: List of chunks.
        """
        try:
            all_chunks = []
            for doc in documents:
                chunk = self.chunk_text(doc.page_content, doc.metadata)
                all_chunks.extend(chunk)
            logger.info("Total chunks: %s", len(all_chunks))
            return all_chunks

        except Exception as e:
            logger.error("Error in chunking documents: ", e)