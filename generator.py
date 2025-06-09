from sys import intern
from config import GROQ_API_KEY
import config
from langchain_groq import ChatGroq
from typing import Optional, List
from langchain_core.prompts import PromptTemplate, prompt
from langchain_huggingface import HuggingFaceEmbeddings
from indexers import FAISSVectorStore
from chunking import RAGChunker
from tavily import TavilyClient
from langchain.docstore.document import Document
import warnings
import os
warnings.filterwarnings("ignore")


class ChatDocs:


    def __init__(
            self,
            llm_model: str = "qwen-qwq-32b",
            similarity_threshold: float = 0.7,
            use_semantic_chunking: bool = None,
            vector_store: Optional[FAISSVectorStore] = None,
            chunker: Optional[RAGChunker] = None,
            embeddings: Optional[HuggingFaceEmbeddings] = None,
        ):
        """
        Initialize the GroqAgent.
        Args:
            llm_model (str): LLM model name.
            similarity_threshold (float): Similarity threshold for vector store.
            use_semantic_chunking (bool): Whether to use semantic chunking.
            vector_store (Optional[FAISSVectorStore]): Vector store.
            chunker (Optional[RAGChunker]): Chunker.
            embeddings (Optional[HuggingFaceEmbeddings]): Embeddings.
        """

        self.__prompt = None
        
        try:
            self.similarity_threshold = similarity_threshold
            self.embeddings = embeddings if embeddings else HuggingFaceEmbeddings(model_name = config.EMBEDDING_MODEL)

            self.chunker = RAGChunker(
                chunk_size = config.CHUNK_SIZE,
                chunk_overlap = config.CHUNK_OVERLAP,
                use_semantic_chunking = use_semantic_chunking,
                embeddings = self.embeddings
            ) if chunker is None else chunker

            self.llm = ChatGroq(
                model_name = llm_model,
                temperature=0.3,
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
            print("Error initializing GroqAgent:", e)


    def find_similarity_score(self, input: str, k: int = 10) -> List[Document]:
        """
        Find similarity score between input and vector store.
        Args:
            input (str): Input text.
        Returns:
            List[Document]: List of similar documents.
        """
        return self.vector_store.vector_store.similarity_search_with_score(input, k = k, score_threshold = self.similarity_threshold)


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
    

    def get_faiss_results(self, query: str, k: int = 10) -> List[Document]:
        """
        Get results from the FAISS vector store.
        Args:
            query (str): Query to search.
            k (int): Number of results to return.
        Returns:
            List[Document]: List of similar documents.
        """
        return self.vector_store.search(query, k = k)


    def prompt_template(self) -> PromptTemplate:
        """
        Prompt template for the LLM.
        Returns:
            PromptTemplate: Prompt template.
        """
        return PromptTemplate(
            input_variables = ["input", "context"],
            template = """
                You are a helpful assistant.
                Answer the question based on the context below.
                If the context doesn't contain the answer, just say that you don't know.
                Don't try to make up an answer. If the answer is not contained within the context, say "I don't know."
                Context: {context}
                Question: {input}
            """
        )
    

    def find_content(self, query: str, k: int = 10) -> PromptTemplate:
        """
        Find content based on the query.
        Args:
            query (str): Query to search.
            k (int): Number of results to return.
        Returns:
            str: Content found.
        """
        try:
            result = self.get_faiss_results(query, k = k)
            context = ""
            max_score = 0.0
            if result:
                result_with_score = self.find_similarity_score(query, k = k)
                context = "\n".join([doc.page_content for doc, _ in result_with_score])
                max_score = max([score for _, score in result_with_score], default = 0.0)
            
            if not result or max_score < self.similarity_threshold:
                print("No results found in vector store. Searching internet...")
                internet_results = self.get_internet_results(query, k = k)
                if internet_results:
                    context += "\n\nWeb Search Results:\n" + internet_results
                else:
                    print("No results found in internet.")

            self.__prompt = self.prompt_template().format(
                input = query,
                context = context or "No results found."
            )

        except Exception as e:
            print("Error finding content:", e)


    def run(self) -> str:
        """
        Run the LLM.
        Returns:
            str: LLM output.
        """
        return self.llm.invoke(self.__prompt).content


def main():


    embeddings = HuggingFaceEmbeddings(model_name = config.EMBEDDING_MODEL)
    
    chunker = RAGChunker(
        chunk_size = config.CHUNK_SIZE,
        chunk_overlap = config.CHUNK_OVERLAP,
        use_semantic_chunking = True,
        embeddings = embeddings
    )

    vector_store = FAISSVectorStore(
        index_path=r"C:\Users\Hemang\Desktop\Hemang\Project\Master\Master\GIT_clones\Understanding-of-RAG--updating-and-filtering-data\data\faiss_index",
        use_semantic_chunking = True,
        chunker = chunker,
        embeddings = embeddings
    )

    sample_texts = [
        "Machine learning is a field of artificial intelligence that focuses on building systems that learn from data.",
        "Supervised learning involves training a model on labeled data."
    ]
    
    sample_metadatas = [
        {"doc_id": "doc1", "source": "ml_intro.txt"},
        {"doc_id": "doc2", "source": "ml_intro.txt"}
    ]
        
    vector_store.add_documents(sample_texts, sample_metadatas)

    rag_system = ChatDocs(
        llm_model = "qwen-qwq-32b",
        similarity_threshold = 0.7,
        use_semantic_chunking = True,
        vector_store = vector_store,
        chunker = chunker,
        embeddings = embeddings
    )

    rag_system.find_content("What is supervised learning?")
    print(rag_system.run())


if __name__ == "__main__":
    main()