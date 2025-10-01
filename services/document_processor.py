"""Document processing service for RAG pipeline."""

from typing import List, Dict
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings

from utils.preprocess import extract_text_from_pdf, clean_basic_artifacts, clean_structure
from exceptions import DocumentProcessingError, PDFExtractionError, ChunkingError, EmbeddingGenerationError


class DocumentProcessor:
    """Handles document extraction, chunking, and embedding generation."""

    def __init__(
        self,
        embeddings: OpenAIEmbeddings,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ):
        """
        Initialize document processor.

        Args:
            embeddings: OpenAI embeddings instance
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
        """
        self.embeddings = embeddings
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=[". ", " ", ""]
        )

    def extract_text_from_source(self, filepath: str) -> str:
        """
        Extract and clean text from a PDF file.

        Args:
            filepath: Path to PDF file

        Returns:
            Cleaned text content

        Raises:
            PDFExtractionError: If extraction fails
        """
        try:
            text = extract_text_from_pdf(filepath)
            text = clean_basic_artifacts(text)
            text = clean_structure(text)
            return text
        except Exception as e:
            raise PDFExtractionError(
                f"Failed to extract text from {filepath}",
                details={"filepath": filepath, "error": str(e)}
            ) from e

    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks.

        Args:
            text: Input text

        Returns:
            List of text chunks

        Raises:
            ChunkingError: If chunking fails
        """
        try:
            if not text or not text.strip():
                raise ValueError("Text is empty")

            chunks = self.text_splitter.split_text(text)

            if not chunks:
                raise ValueError("No chunks generated from text")

            return chunks
        except Exception as e:
            raise ChunkingError(
                "Failed to chunk text",
                details={"text_length": len(text), "error": str(e)}
            ) from e

    def generate_embeddings(self, chunks: List[str]) -> List[List[float]]:
        """
        Generate embeddings for text chunks.

        Args:
            chunks: List of text chunks

        Returns:
            List of embedding vectors

        Raises:
            EmbeddingGenerationError: If embedding generation fails
        """
        try:
            if not chunks:
                raise ValueError("No chunks provided for embedding")

            embeddings = []
            for chunk in chunks:
                embedding = self.embeddings.embed_query(chunk)
                embeddings.append(embedding)

            return embeddings
        except Exception as e:
            raise EmbeddingGenerationError(
                "Failed to generate embeddings",
                details={"num_chunks": len(chunks), "error": str(e)}
            ) from e

    def generate_single_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text

        Returns:
            Embedding vector

        Raises:
            EmbeddingGenerationError: If embedding generation fails
        """
        try:
            return self.embeddings.embed_query(text)
        except Exception as e:
            raise EmbeddingGenerationError(
                "Failed to generate embedding",
                details={"text_length": len(text), "error": str(e)}
            ) from e

    def process_document(
        self,
        filepath: str
    ) -> tuple[str, List[str], List[List[float]]]:
        """
        Complete document processing pipeline.

        Args:
            filepath: Path to document file

        Returns:
            Tuple of (text, chunks, embeddings)

        Raises:
            DocumentProcessingError: If any step fails
        """
        try:
            # Extract text
            text = self.extract_text_from_source(filepath)

            # Chunk text
            chunks = self.chunk_text(text)

            # Generate embeddings
            embeddings = self.generate_embeddings(chunks)

            return text, chunks, embeddings

        except (PDFExtractionError, ChunkingError, EmbeddingGenerationError):
            # Re-raise specific errors
            raise
        except Exception as e:
            raise DocumentProcessingError(
                f"Document processing failed for {filepath}",
                details={"filepath": filepath, "error": str(e)}
            ) from e
