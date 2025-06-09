from typing import Optional, List, Dict
import config
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
from langchain_huggingface import HuggingFaceEmbeddings
from chunking import RAGChunker
import config
import os


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
            embedding_model (str): HuggingFace embedding model name.
            chunk_size (int): Chunk size for text splitting.
            chunk_overlap (int): Chunk overlap for text splitting.
            use_semantic_chunking (bool): Whether to use semantic chunking.
        """

        self.index_path = index_path
        self.use_semantic_chunking = use_semantic_chunking if use_semantic_chunking else config.USER_SEMENTIC_CHUNKING

        try:
            self.embeddings = embeddings if embeddings else HuggingFaceEmbeddings(model_name = config.EMBEDDING_MODEL)
            self.chunker = RAGChunker(
                chunk_size = config.CHUNK_SIZE,
                chunk_overlap = config.CHUNK_OVERLAP,
                use_semantic_chunking = self.use_semantic_chunking,
                embeddings = self.embeddings
            ) if chunker is None else chunker
            self.vector_store = self.load_index()

        except Exception as e:
            print("Error initializing chunker in indexer:", e)


    def load_index(self) -> FAISS:
        """
        Load the FAISS index from the specified path.

        Returns:
            FAISS: Loaded FAISS index.
        """
        try:
            if os.path.exists(self.index_path):
                return FAISS.load_local(self.index_path, self.embeddings, allow_dangerous_deserialization = True)
            else:
                return FAISS.from_texts([""], self.embeddings)
        
        except Exception as e:
            print("Error loading index:", e)


    def add_documents(self, texts: List[str], metadatas: Optional[List[Dict]]) -> None:
        """
        Add a document to the FAISS index.

        Args:
            document (Document): Document to add.
        """
        try:
            metadatas = metadatas or [{} for _ in texts]
            if len(texts) != len(metadatas):
                raise ValueError("Number of texts and metadatas must match")

            if self.use_semantic_chunking:
                documents = [
                    Document(page_content = text, metadata = metadata)
                    for text, metadata in zip(texts, metadatas)
                ]
                chunks = self.chunker.chunk_documents(documents)
                self.vector_store.add_documents(chunks)
                self._save_index()
                print("Document added successfully.")

        except Exception as e:
            print("Error adding document:", e)


    def _save_index(self) -> None:
        """
        Save the FAISS index to the specified path.
        """
        try:
            os.makedirs(os.path.dirname(self.index_path), exist_ok = True)
            self.vector_store.save_local(self.index_path)
            print("Index saved successfully.")
        except Exception as e:
            print("Error saving index:", e)


    def update_documents(self, doc_ids: List[str], texts:List[str], metadatas: Optional[List[Dict]] = None) -> None:
        """
        Update the FAISS index with new documents.

        Args:
            doc_ids (List[str]): IDs of documents to update.
            texts (List[str]): Updated texts.
            metadatas (List[Dict], optional): Updated metadata.
        """
        try:
            if not doc_ids or not texts:
                raise ValueError("Document IDs cannot be empty")

            self.delete_documents(doc_ids)
            self.add_documents(texts, metadatas)
            print("Index updated successfully.")
        except Exception as e:
            print("Error updating index:", e)


    def delete_documents(self, doc_ids: List[str]) -> None:
        """
        Delete documents from the FAISS index.

        Args:
            doc_ids (List[str]): IDs of documents to delete.
        """
        try:
            all_docs = self.vector_store.similarity_search("", k = 1000)  
            
            remaining_docs = [
                doc for doc in all_docs
                if doc.metadata.get("doc_id") not in doc_ids
            ]

            self.vector_store = FAISS.from_documents(remaining_docs, self.embeddings)
            self._save_index()
            print(f"Deleted documents with IDs: {doc_ids}")

        except Exception as e:
            print("Error deleting documents:", e)


    def search(self, query: str, k: int = 5) -> List[Document]:
        """
        Search for similar documents in the FAISS index.

        Args:
            query (str): Query text.
            k (int): Number of similar documents to retrieve.

        Returns:
            List[Document]: List of similar documents.
        """
        try:
            result = self.vector_store.similarity_search(query, k = k)
            return result
        except Exception as e:
            print("Error searching documents:", e)
    

def main():
    """Example usage of FAISSVectorStore."""
    try:
        # Initialize vector store
        vector_store = FAISSVectorStore(
            index_path=r"C:\Users\Hemang\Desktop\Hemang\Project\Master\Master\GIT_clones\Understanding-of-RAG--updating-and-filtering-data\data\faiss_index",
            use_semantic_chunking = True
        )
        
        # Sample documents
        sample_texts = [
            "Machine learning is a field of artificial intelligence that focuses on building systems that learn from data.",
            "Supervised learning involves training a model on labeled data."
        ]
        sample_metadatas = [
            {"doc_id": "doc1", "source": "ml_intro.txt"},
            {"doc_id": "doc2", "source": "ml_intro.txt"}
        ]
        
        # Add documents
        vector_store.add_documents(sample_texts, sample_metadatas)
        print(1)
        # Search
        results = vector_store.search("What is machine learning?", k = 2)
        for i, doc in enumerate(results):
            print(f"\nResult {i + 1}:")
            print(f"Content: {doc.page_content[:100]}...")
            print(f"Metadata: {doc.metadata}")
        print(2)
        # Update a document
        vector_store.update_documents(
            doc_ids=["doc1"],
            texts=["Updated: Machine learning enables systems to learn from data automatically."],
            metadatas=[{"doc_id": "doc1", "source": "ml_intro_updated.txt"}]
        )
        print(3)
        # Delete a document
        vector_store.delete_documents(["doc1"])
        
    except Exception as e:
        print(f"Error in main execution: {str(e)}")

if __name__ == "__main__":
    main()