import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import openai
import pypdf
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from tqdm import tqdm

from prompts.prompt_manager import PromptManager
from metadata_utils import get_source_metadata_map, seed_metadata_from_json, load_source_text

from utils.preprocess import extract_text_from_pdf, clean_basic_artifacts, clean_structure
from utils.timing import measure_time
from databases import (
    ChunkRecord,
    ChromaHistoryStore,
    ChromaVectorStore,
    SupabaseHistoryStore,
    SupabaseVectorStore,
)
from history_manager import HistoryManager

class RAGPipeline:
    def __init__(
        self, 
        chunk_size=500, 
        chunk_overlap=100, 
        dict_source_id_path="assets/dict_source_id.json", 
        enable_timing=False,
        collection_name="houmy_sources",
        history_collection_name: str = "houmy_history",
        embedding_model="text-embedding-3-large",
        embedding_dimensions=1536,
        test_with_chromadb: bool = False,
        supabase_dsn: Optional[str] = None,
    ):

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.enable_timing = enable_timing
        self.collection_name = collection_name
        self.history_collection_name = history_collection_name
        self.embedding_model = embedding_model
        self.embedding_dimensions = embedding_dimensions
        self.test_with_chromadb = test_with_chromadb
        self.supabase_dsn = supabase_dsn or os.getenv("SUPABASE_DB_URL")
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.embeddings = OpenAIEmbeddings(
            api_key=os.getenv("OPENAI_API_KEY"),
            model=embedding_model,
            dimensions=embedding_dimensions
        )
        self.prompt_manager = PromptManager()
        self.dict_source_id_path = dict_source_id_path
        self.source_metadata = get_source_metadata_map()
        history_store = None
        if not self.source_metadata and self.dict_source_id_path:
            seeded = seed_metadata_from_json(self.dict_source_id_path)
            if seeded:
                self.source_metadata = get_source_metadata_map()

        if not self.source_metadata:
            raise RuntimeError(
                "Source metadata not found. Seed the SourceMetadata table before using RAGPipeline."
            )

        if self.test_with_chromadb:
            print("Using ChromaDB as vector store")
            chroma_dir = os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db")
            self.vector_store = ChromaVectorStore(collection_name, chroma_dir)
            self.chroma_client = self.vector_store.client
            self.collection = self.vector_store.collection
            try:
                history_store = ChromaHistoryStore(
                    self.history_collection_name, chroma_dir
                )
            except Exception as exc:
                print(f"[RAG WARNING] Failed to initialise Chroma history store: {exc}")
        else:
            print(f"Using Supabase as vector store with DSN: {self.supabase_dsn}")
            if not self.supabase_dsn:
                raise RuntimeError(
                    "SUPABASE_DB_URL must be set when test_with_chromadb is False."
                )
            self.vector_store = SupabaseVectorStore(self.supabase_dsn, embedding_dimensions)
            self.chroma_client = None
            self.collection = None
            try:
                history_store = SupabaseHistoryStore(self.supabase_dsn)
            except Exception as exc:
                print(f"[RAG WARNING] Failed to initialise Supabase history store: {exc}")

        # Text splitter for chunking documents
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=[". ", " ", ""]
        )

        self.history_manager = None
        if history_store is not None:
            self.history_manager = HistoryManager(
                embeddings=self.embeddings,
                openai_client=self.openai_client,
                history_store=history_store,
            )

    def set_timing_enabled(self, enabled: bool):
        """Toggle timing functionality on/off"""
        self.enable_timing = enabled
        print(f"Timing {'enabled' if enabled else 'disabled'}")

    def is_timing_enabled(self) -> bool:
        """Check if timing is currently enabled"""
        return self.enable_timing

    def refresh_source_metadata(self) -> None:
        """Reload source metadata from the database so new entries are discoverable."""
        self.source_metadata = get_source_metadata_map()

    def extract_text_from_pdf(self, source_id: str) -> bool:
        """Extract text from a source"""
        assert source_id in self.source_metadata, f"Source ID {source_id} not found in SourceMetadata table"
        text_content = extract_text_from_pdf(self.source_metadata[source_id]["filepath_raw"])
        text_content = clean_basic_artifacts(text_content)
        text_content = clean_structure(text_content)
        text_content = text_content.replace("\n", "")
        return text_content
    
    def get_text_content(self, source_id: str) -> str:
        """Get text content from a source"""
        assert source_id in self.source_metadata, f"Source ID {source_id} not found in SourceMetadata table"
        filepath = self.source_metadata[source_id]["filepath_raw"]
        return load_source_text(filepath)
    
    def process_source(self, source_id: str) -> bool:
        """Process a source file and store embeddings"""
        assert source_id in self.source_metadata, f"Source ID {source_id} not found in SourceMetadata table"
        try:
            # Extract text from PDF
            text_content = self.get_text_content(source_id)
            if not text_content:
                return False
            
            # Split text into chunks
            raw_chunks = self.text_splitter.split_text(text_content)

            chunk_payloads: List[ChunkRecord] = []
            for i, chunk in tqdm(
                enumerate(raw_chunks),
                total=len(raw_chunks),
                desc="Processing source",
            ):
                embedding = self.embeddings.embed_query(chunk)
                chunk_payloads.append(
                    {
                        "chunk_id": f"{source_id}_{i}",
                        "chunk_index": i,
                        "content": chunk,
                        "embedding": embedding,
                        "token_count": len(chunk.split()),
                    }
                )

            self.vector_store.store_chunks(source_id, chunk_payloads)
            return True
            
        except Exception as e:
            print(f"Error processing source {source_id}: {e}")
            return False
    
    def process_sources(self, source_ids: List[str], max_workers: int = 4) -> bool:
        """Process multiple sources with multi-threading"""
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.process_source, source_id) for source_id in source_ids]
            return all(future.result() for future in futures)

    def _extract_text_from_pdf(self, file_path: str) -> str:
        """Extract text content from PDF file"""
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                text_content = ""
                
                for page in pdf_reader.pages:
                    text_content += page.extract_text() + "\n"
                
                return text_content
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return ""
    
    def search_documents(
        self,
        query: str,
        limit: int = 5,
        source_ids: Optional[List[str]] = None,
        min_relevance_score: float = 0.05,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict]:
        """Search for relevant documents using semantic similarity"""
        try:
            start_total = time.perf_counter() if self.enable_timing else None
            times = {} if self.enable_timing else None
            
            # Get query embedding
            embedding_to_use = query_embedding
            if embedding_to_use is None:
                if self.enable_timing:
                    start = time.perf_counter()
                embedding_to_use = self.embeddings.embed_query(query)
                if self.enable_timing:
                    times['embedding_generation'] = time.perf_counter() - start
            elif self.enable_timing:
                times['embedding_generation'] = 0.0
            
            if self.enable_timing:
                start = time.perf_counter()
            final_results = self.vector_store.query(
                query_embedding=embedding_to_use,
                limit=limit,
                source_ids=source_ids,
                min_relevance=min_relevance_score,
            )
            if self.enable_timing:
                times['vector_store_query'] = time.perf_counter() - start
                times['total_time'] = time.perf_counter() - start_total
                print("Search performance breakdown:")
                print(f"  Embedding generation: {times['embedding_generation']:.4f}s")
                print(f"  Vector store query: {times['vector_store_query']:.4f}s")
                print(f"  Total time: {times['total_time']:.4f}s")
                print(f"  Results found: {len(final_results)}")
            
            return final_results
            
        except Exception as e:
            print(f"Error searching documents: {e}")
            return []

    @measure_time("Generate Response")
    def generate_response(
        self,
        query: str,
        context_docs: List[Dict],
        layer_config: Optional[Dict[str, Dict[str, Any]]] = None,
        language: str = "English",
        session_id: Optional[str] = None,
        max_tokens: int = 1500, # currently not used; might be used in future
        enable_timing: bool = False,
        stream: bool = False,
        domain: Optional[str] = None,
    ):
        """Generate AI response using RAG pipeline for all domains"""
        try:
            # Build layered prompt content
            system_prompt, user_prompt, _prompt_meta = self.prompt_manager.build_prompt_messages(
                query=query,
                language=language,
                context_docs=context_docs,
                domain=domain,
                source_metadata=self.source_metadata,
                layer_config=layer_config,
            )
            if not user_prompt:
                raise ValueError("Unable to generate user prompt from PromptManager.")

            # Prepare sources for response
            print(f"[RAG DEBUG] Preparing sources for response, context_docs: {len(context_docs)} docs")
            print(f"[RAG DEBUG] context_docs type: {type(context_docs)}, value: {context_docs}")
            
            sources = []
            try:
                for doc in context_docs:
                    meta = self.source_metadata.get(doc["source_id"], {})
                    source_info = {
                        "source_id": doc["source_id"],
                        "display_name": meta.get("display_name", doc["source_id"]),
                        "purchase_link": meta.get("purchase_link", ""),
                        "page_number": doc["page_number"],
                        "excerpt": doc["content"][:200] + "..." if len(doc["content"]) > 200 else doc["content"],
                        "relevance_score": doc["relevance_score"]
                    }
                    sources.append(source_info)
            except Exception as e:
                print(f"[RAG ERROR] Error preparing sources: {e}")
                import traceback
                traceback.print_exc()
                sources = []
            
            print(f"[RAG DEBUG] Final sources count: {len(sources)}")

            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})

            if stream:
                # Return streaming generator
                return self._generate_streaming_response(
                    messages=messages,
                    sources=sources,
                    session_id=session_id,
                )
            
            # Make OpenAI API call (non-streaming)
            api_params = {
                "model": "ggpt-4o-mini",
                "messages": messages,
            }
            if max_tokens is not None:
                api_params["max_completion_tokens"] = max_tokens
                
            response = self.openai_client.chat.completions.create(**api_params)
            
            # Extract response
            ai_response = response.choices[0].message.content
            tokens_used = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return {
                "response": ai_response,
                "sources": sources,
                "tokens_used": tokens_used,
                "session_id": session_id or str(uuid.uuid4())
            }
            
        except Exception as e:
            print(f"Error generating response: {e}")
            return {
                "response": "I apologize, but I encountered an error while processing your request.",
                "sources": [],
                "tokens_used": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "reasoning_tokens": 0,
                    "total_tokens": 0
                },
                "session_id": session_id or str(uuid.uuid4())
            }

    @measure_time("Generate Streaming Response")
    def _generate_streaming_response(
        self,
        messages: List[Dict[str, str]],
        sources: List[Dict],
        session_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ):
        """Return raw OpenAI stream and metadata for frontend handling"""
        try:
            print(f"[RAG DEBUG] _generate_streaming_response called with {len(sources)} sources")
            
            # Only set max_completion_tokens if max_tokens is provided
            api_params = {
                "model": "gpt-4o-mini",
                "messages": messages,
                "stream": True
            }
            if max_tokens is not None:
                api_params["max_completion_tokens"] = max_tokens
                
            response = self.openai_client.chat.completions.create(**api_params)
            
            return {
                "stream": response,
                "sources": sources,
                "session_id": session_id or str(uuid.uuid4())
            }
            
        except Exception as e:
            print(f"[RAG ERROR] Exception in _generate_streaming_response: {e}")
            import traceback
            traceback.print_exc()
            raise e
    
    @measure_time("RAG Chat")
    def chat(
        self,
        message: str,
        language: str = "English",
        source_ids: Optional[List[str]] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        stream: bool = False,
        domain: Optional[str] = None,
        min_relevance_score: Optional[float] = None,
        max_tokens: Optional[int] = None,
        layer_config: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """Main chat interface combining search and generation"""
        print(f"[RAG DEBUG] chat() called with domain={domain}, source_ids={source_ids}, message={message[:50]}...")
        
        try:
            query_embedding: Optional[List[float]] = None
            prompt_layers = layer_config

            if self.history_manager and user_id:
                query_embedding, history_records, history_text = self.history_manager.prepare_history_context(
                    message=message,
                    user_id=user_id,
                )
                print(f"[RAG DEBUG] Retrieved {len(history_records)} history records for context")
                prompt_layers = self.history_manager.apply_history_layer(layer_config, history_text)

            if prompt_layers is None:
                prompt_layers = layer_config

            if source_ids is None or len(source_ids) == 0:
                print(f"[RAG DEBUG] No sources selected - returning empty context")
                # No sources selected - return empty context
                relevant_docs = []
            else:
                print(f"[RAG DEBUG] Searching documents with source_ids: {source_ids}")
                relevance_threshold = (
                    min_relevance_score if min_relevance_score is not None else 0.05
                )

                relevant_docs = self.search_documents(
                    message,
                    limit=10,
                    source_ids=source_ids,
                    min_relevance_score=relevance_threshold,
                    query_embedding=query_embedding,
                )
                print(f"[RAG DEBUG] Found {len(relevant_docs)} relevant docs")

            print(f"[RAG DEBUG] Calling generate_response with {len(relevant_docs)} docs")
            # Generate response using retrieved context
            return self.generate_response(
                query=message,
                language=language,
                context_docs=relevant_docs,
                session_id=session_id,
                stream=stream,
                domain=domain,
                max_tokens=max_tokens,
                layer_config=prompt_layers,
            )
        except Exception as e:
            print(f"[RAG ERROR] Exception in chat(): {e}")
            import traceback
            traceback.print_exc()
            raise

    def record_turn_history(
        self,
        *,
        user_id: Optional[str],
        session_id: Optional[str],
        user_message: str,
        assistant_message: str,
    ) -> Optional[str]:
        """Proxy to HistoryManager for persisting chat turns."""

        if not self.history_manager:
            return None

        return self.history_manager.record_turn_history(
            user_id=user_id,
            session_id=session_id,
            user_message=user_message,
            assistant_message=assistant_message,
        )

    def clear_user_history(self, user_id: str) -> None:
        if not self.history_manager:
            return
        self.history_manager.purge_user_history(user_id)
