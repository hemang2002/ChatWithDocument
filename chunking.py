from typing import List, Optional
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
from langchain.docstore.document import Document
import warnings
warnings.filterwarnings("ignore")


class RAGChunker:


    def __init__(
        self,
        chunk_size = 500,
        chunk_overlap  = 50,
        use_semantic_chunking = True,
        embedding_model = "sentence-transformers/all-MiniLM-L6-v2",
    ):

        self.chunk_size = chunk_size
        self.chunk_overlap  = chunk_overlap
        self.use_semantic_chunking = use_semantic_chunking
        self.embedding_model = embedding_model

        if self.use_semantic_chunking:
            try:
                self.embeddings = HuggingFaceEmbeddings(model_name=self.embedding_model)
                self.text_splitter = SemanticChunker(
                    breakpoint_threshold_type = "percentile",
                    breakpoint_threshold_amount = 95,
                    embeddings = self.embeddings,
                )
            except:
                print("Please install sentence_transformers package to use semantic chunking")

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
            print("Error in chunking text: ", e)


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
            print("Total chunks: ", len(all_chunks))
            return all_chunks

        except Exception as e:
            print("Error in chunking documents: ", e)