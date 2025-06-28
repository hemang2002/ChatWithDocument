from typing import Optional, List, Dict
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
from langchain_huggingface import HuggingFaceEmbeddings
from src.chunking import RAGChunker
from Configuration import config
import logging
import os

logger = logging.getLogger(__name__)

class FAISSVectorStore:


    def __init__(
        self,
        index_path: str,
        use_semantic_chunking: bool = None,
        embeddings: Optional[HuggingFaceEmbeddings] = None,
        chunker: Optional[RAGChunker] = None,
    ):
        """
        Initialize the FAISS vector store.
        
        Args:
            index_path (str): Path to store/load the FAISS index.
            use_semantic_chunking (bool): Whether to use semantic chunking.
            embeddings (Optional[HuggingFaceEmbeddings]): Embeddings model.
            chunker (Optional[RAGChunker]): Text chunker.
        """
        self.index_path = index_path
        self.use_semantic_chunking = use_semantic_chunking if use_semantic_chunking is not None else config.USER_SEMENTIC_CHUNKING

        try:
            self.embeddings = embeddings if embeddings else HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
            self.chunker = chunker if chunker else RAGChunker(
                chunk_size = config.CHUNK_SIZE,
                chunk_overlap = config.CHUNK_OVERLAP,
                use_semantic_chunking = self.use_semantic_chunking,
                embeddings = self.embeddings
            )
            self.vector_store = self.load_index()

        except Exception as e:
            logger.error(f"Error initializing FAISSVectorStore: {e}")
            raise


    def load_index(self) -> FAISS:
        """
        Load the FAISS index from the specified path.

        Returns:
            FAISS: Loaded FAISS index.
        """
        try:
            if os.path.exists(self.index_path):
                return FAISS.load_local(self.index_path, self.embeddings, allow_dangerous_deserialization=True)
            else:
                return FAISS.from_texts([""], self.embeddings)
        
        except Exception as e:
            logger.error(f"Error loading index: {e}")
            raise


    def add_documents(self, texts: List[str], metadatas: Optional[List[Dict]] = None) -> None:
        """
        Add documents to the FAISS index.

        Args:
            texts (List[str]): List of document texts.
            metadatas (Optional[List[Dict]]): List of metadata dictionaries.
        """
        try:
            metadatas = metadatas or [{} for _ in texts]
            if len(texts) != len(metadatas):
                raise ValueError("Number of texts and metadatas must match")

            if self.use_semantic_chunking:
                documents = [
                    Document(page_content=text, metadata=metadata)
                    for text, metadata in zip(texts, metadatas)
                ]
                chunks = self.chunker.chunk_documents(documents)
                self.vector_store.add_documents(chunks)
            else:
                self.vector_store.add_texts(texts, metadatas)
            self._save_index()
            logger.info("Documents added successfully.")

        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            raise


    def _save_index(self) -> None:
        """
        Save the FAISS index to the specified path.
        """
        try:
            os.makedirs(os.path.dirname(self.index_path), exist_ok = True)
            self.vector_store.save_local(self.index_path)
            logger.info("Index saved successfully.")
        except Exception as e:
            logger.error(f"Error saving index: {e}")
            raise


    def update_documents(self, doc_ids: List[str], texts: List[str], metadatas: Optional[List[Dict]] = None) -> None:
        """
        Update documents in the FAISS index.

        Args:
            doc_ids (List[str]): IDs of documents to update.
            texts (List[str]): Updated texts.
            metadatas (Optional[List[Dict]]): Updated metadata.
        """
        try:
            if not doc_ids or not texts:
                raise ValueError("Document IDs and texts cannot be empty")

            self.delete_documents(doc_ids)
            self.add_documents(texts, metadatas)
            logger.info("Index updated successfully.")
        except Exception as e:
            logger.error(f"Error updating index: {e}")
            raise


    def delete_documents(self, doc_ids: List[str]) -> None:
        """
        Delete documents from the FAISS index.

        Args:
            doc_ids (List[str]): IDs of documents to delete.
        """
        try:
            all_docs = self.vector_store.similarity_search("", k=1000)  
            remaining_docs = [
                doc for doc in all_docs
                if doc.metadata.get("doc_id") not in doc_ids
            ]
            self.vector_store = FAISS.from_documents(remaining_docs, self.embeddings)
            self._save_index()
            logger.info(f"Deleted documents with IDs: {doc_ids}")

        except Exception as e:
            logger.error(f"Error deleting documents: {e}")
            raise


    def search(self, query: str, k: int = 5, filter: Optional[Dict] = None) -> List[Document]:
        """
        Search for similar documents in the FAISS index with optional metadata filtering.

        Args:
            query (str): Query text.
            k (int): Number of similar documents to retrieve.
            filter (Optional[Dict]): Metadata filter (e.g., {"chat_id": "chat1"}).

        Returns:
            List[Document]: List of similar documents.
        """
        try:
            results = self.vector_store.similarity_search(query, k=k, filter=filter)
            return results
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []


    def similarity_search_with_score(self, query: str, k: int = 5, score_threshold: float = 0.2, filter: Optional[Dict] = None) -> List[tuple]:
        """
        Search for similar documents with similarity scores and optional metadata filtering.

        Args:
            query (str): Query text.
            k (int): Number of similar documents to retrieve.
            score_threshold (float): Minimum similarity score.
            filter (Optional[Dict]): Metadata filter (e.g., {"chat_id": "chat1"}).

        Returns:
            List[tuple]: List of (Document, score) tuples.
        """
        try:
            results = self.vector_store.similarity_search_with_score(query, k = k, filter = filter)
            return [(doc, score) for doc, score in results if score >= score_threshold]
        except Exception as e:
            logger.error(f"Error in similarity search with score: {e}")
            return []