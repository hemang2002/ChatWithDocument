from math import log
from Configuration import config
from langchain_groq import ChatGroq
from typing import Optional, List
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from src.indexers import FAISSVectorStore
from src.chunking import RAGChunker
from tavily import TavilyClient
from langchain.docstore.document import Document
import warnings
import logging
import os
warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

class ChatDocs:


    def __init__(
        self,
        llm_model: str = "qwen-qwq-32b",
        similarity_threshold: float = 0.5,
        use_semantic_chunking: bool = None,
        vector_store: Optional[FAISSVectorStore] = None,
        embeddings: Optional[HuggingFaceEmbeddings] = None,
    ):
        """
        Initialize the GroqAgent.
        Args:
            llm_model (str): LLM model name.
            similarity_threshold (float): Similarity threshold for vector store.
            use_semantic_chunking (bool): Whether to use semantic chunking.
            vector_store (Optional[FAISSVectorStore]): Vector store.
            embeddings (Optional[HuggingFaceEmbeddings]): Embeddings.
        """
        self.__prompt = None
        os.environ["LANGCHAIN_API_KEY"] = os.environ.get("LANGSMITH_API_KEY")
        os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_PROJECT"] = "ChatDoc"
        try:
            self.similarity_threshold = similarity_threshold
            self.embeddings = embeddings if embeddings else HuggingFaceEmbeddings(model_name = config.EMBEDDING_MODEL)

            self.chunker = RAGChunker(
                chunk_size = config.CHUNK_SIZE,
                chunk_overlap = config.CHUNK_OVERLAP,
                use_semantic_chunking = use_semantic_chunking,
                embeddings = self.embeddings
            ) if vector_store is None else vector_store.chunker

            self.llm = ChatGroq(
                model_name = llm_model,
                temperature = 0.3,
                groq_api_key = config.GROQ_API_KEY,
            )

            self.vector_store = vector_store if vector_store else FAISSVectorStore(
                index_path = config.INDEX_PATH,
                use_semantic_chunking = use_semantic_chunking if use_semantic_chunking else config.USER_SEMENTIC_CHUNKING,
                embeddings = self.embeddings,
                chunker = self.chunker
            )
            os.environ["TAVILY_API_KEY"] = os.environ.get('TAVILY_API_KEY')
            self.tool = TavilyClient()

        except Exception as e:
            logger.error("Error initializing GroqAgent:", e)


    def find_similarity_score(self, input: str, k: int = 10, chat_id: Optional[str] = None) -> List[Document]:
        """
        Find similarity score between input and vector store, filtered by chat_id.
        Args:
            input (str): Input text.
            k (int): Number of results to return.
            chat_id (Optional[str]): Chat ID to filter documents.
        Returns:
            List[Document]: List of similar documents.
        """
        # Assume FAISSVectorStore supports metadata filtering
        filter_dict = {"chat_id": chat_id} if chat_id else None
        results = self.vector_store.vector_store.similarity_search_with_score(input, k = k, score_threshold = self.similarity_threshold, filter = filter_dict)
        if not filter_dict:
            return results
        return [(doc, score) for doc, score in results if doc.metadata.get("chat_id") == chat_id]


    def get_internet_results(self, query: str, k: int = 10) -> List[Document]:
        """
        Get results from the internet.
        Args:
            query (str): Query to search.
            k (int): Number of results to return.
        Returns:
            List[Document]: List of similar documents.
        """
        return self.tool.search(
            query,
            search_depth = "advanced",
            max_result = 10,
            k = k
        )
    

    def get_faiss_results(self, query: str, k: int = 10, chat_id: Optional[str] = None) -> List[Document]:
        """
        Get results from the FAISS vector store, filtered by chat_id.
        Args:
            query (str): Query to search.
            k (int): Number of results to return.
            chat_id (Optional[str]): Chat ID to filter documents.
        Returns:
            List[Document]: List of similar documents.
        """
        filter_dict = {"chat_id": chat_id} if chat_id else None
        results = self.vector_store.search(query, k = k, filter = filter_dict)
        if not filter_dict:
            return results
        return [doc for doc in results if doc.metadata.get("chat_id") == chat_id]


    def prompt_template(self) -> PromptTemplate:
        """
        Prompt template for the LLM.
        Returns:
            PromptTemplate: Prompt template.
        """
        return PromptTemplate(
            input_variables=["input", "context"],
            template="""
                You are a helpful assistant.
                Answer the question based on the context below.
                If the context doesn't contain the answer, just say that you don't know.
                If the answer is not contained within the context, say "I don't know."
                Context: {context}
                Question: {input}
            """
        )


    def find_content(self, query: str, k: int = 5, chat_id: Optional[str] = None) -> PromptTemplate:
        """
        Find content based on the query, filtered by chat_id.
        Args:
            query (str): Query to search.
            k (int): Number of results to return.
            chat_id (Optional[str]): Chat ID to filter documents.
        Returns:
            PromptTemplate: Formatted prompt with context.
        """
        try:
            result = self.get_faiss_results(query, k = k, chat_id = chat_id)
            context = "\n".join([doc.page_content for doc in result])
            # context = ""
            # max_score = 0.0
            # if result:
            #     result_with_score = self.find_similarity_score(query, k = k, chat_id = chat_id)
            #     context = "\n".join([doc.page_content for doc in result_with_score])
            #     max_score = max([score for _, score in result_with_score], default = 0.0)
            
            # if not result or max_score < self.similarity_threshold:
            #     print("No results found in vector store. Searching internet...")
            #     internet_results = self.get_internet_results(query, k = k)
            #     if internet_results:
            #         context += "\n\nWeb Search Results:\n" + json.dumps(internet_results, indent=4)
            #     else:
            #         print("No results found in internet.")

            self.__prompt = self.prompt_template().format(
                input = query,
                context = context or "No results found."
            )

        except Exception as e:
            logger.error("Error finding content: %s", e)
            self.__prompt = self.prompt_template().format(
                input = query,
                context = "Error retrieving documents."
            )


    def run(self) -> str:
        """
        Run the LLM.
        Returns:
            str: LLM output.
        """
        return self.llm.invoke(self.__prompt).content