"""Context Engineering service - optimizing what information reaches the LLM."""

from typing import List, Dict, Any, Optional
import re


class ContextEngineer:
    """
    Context Engineering focuses on WHAT information to provide, not HOW to ask.

    Key principles:
    1. Relevance ranking: Order by importance
    2. Deduplication: Remove redundant information
    3. Compression: Keep signal, remove noise
    4. Enrichment: Add structured metadata
    5. Adaptive assembly: Match context to query type
    """

    def __init__(
        self,
        max_context_tokens: int = 3000,
        min_relevance_score: float = 0.3,
        enable_deduplication: bool = True,
        enable_compression: bool = True,
    ):
        """
        Initialize context engineer.

        Args:
            max_context_tokens: Maximum tokens for context
            min_relevance_score: Minimum relevance threshold
            enable_deduplication: Remove duplicate content
            enable_compression: Compress redundant information
        """
        self.max_context_tokens = max_context_tokens
        self.min_relevance_score = min_relevance_score
        self.enable_deduplication = enable_deduplication
        self.enable_compression = enable_compression

    def engineer_context(
        self,
        query: str,
        raw_documents: List[Dict[str, Any]],
        query_type: Optional[str] = None,
        source_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Engineer optimal context from raw search results.

        Args:
            query: User query
            raw_documents: Raw search results
            query_type: Type of query (factual, conversational, analytical, etc.)
            source_metadata: Metadata about sources

        Returns:
            Engineered context with optimized documents and metadata
        """
        # Step 1: Detect query type if not provided
        if query_type is None:
            query_type = self._detect_query_type(query)

        # Step 2: Filter by relevance
        filtered_docs = self._filter_by_relevance(raw_documents)

        # Step 3: Deduplicate if enabled
        if self.enable_deduplication:
            filtered_docs = self._deduplicate_documents(filtered_docs)

        # Step 4: Rank by importance (relevance + recency + source quality)
        ranked_docs = self._rank_documents(filtered_docs, query, source_metadata)

        # Step 5: Compress if enabled
        if self.enable_compression:
            ranked_docs = self._compress_documents(ranked_docs, query)

        # Step 6: Assemble context based on query type
        assembled_docs = self._assemble_by_query_type(ranked_docs, query_type)

        # Step 7: Fit within token budget
        final_docs = self._fit_token_budget(assembled_docs)

        # Step 8: Enrich with metadata
        enriched_docs = self._enrich_metadata(final_docs, source_metadata)

        return {
            "documents": enriched_docs,
            "query_type": query_type,
            "context_stats": {
                "original_count": len(raw_documents),
                "filtered_count": len(filtered_docs),
                "final_count": len(enriched_docs),
                "estimated_tokens": self._estimate_tokens(enriched_docs),
            }
        }

    def _detect_query_type(self, query: str) -> str:
        """Detect the type of query to optimize context assembly."""
        query_lower = query.lower()

        # Question patterns
        if any(q in query_lower for q in ["what", "which", "who", "when", "where"]):
            return "factual"
        elif any(q in query_lower for q in ["how", "why"]):
            return "explanatory"
        elif any(q in query_lower for q in ["compare", "difference", "versus", "vs"]):
            return "analytical"
        elif any(q in query_lower for q in ["should", "recommend", "suggest", "advice"]):
            return "advisory"
        elif "?" not in query and len(query.split()) < 5:
            return "search"
        else:
            return "conversational"

    def _filter_by_relevance(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter documents by minimum relevance score."""
        return [
            doc for doc in documents
            if doc.get("relevance_score", 0) >= self.min_relevance_score
        ]

    def _deduplicate_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate or highly similar content."""
        if not documents:
            return documents

        unique_docs = []
        seen_content = set()

        for doc in documents:
            # Create normalized fingerprint
            content = doc.get("content", "")
            fingerprint = self._create_fingerprint(content)

            if fingerprint not in seen_content:
                seen_content.add(fingerprint)
                unique_docs.append(doc)

        return unique_docs

    def _create_fingerprint(self, text: str) -> str:
        """Create a fingerprint for deduplication."""
        # Normalize: lowercase, remove extra spaces, keep first 200 chars
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        return normalized[:200]

    def _rank_documents(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        source_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Rank documents by composite score:
        - Relevance score (primary)
        - Source authority (if available)
        - Recency (if available)
        """
        source_metadata = source_metadata or {}

        def calculate_rank_score(doc: Dict[str, Any]) -> float:
            relevance = doc.get("relevance_score", 0.0)

            # Source authority boost
            source_id = doc.get("source_id", "")
            source_info = source_metadata.get(source_id, {})
            authority_boost = 0.1 if source_info.get("is_authoritative") else 0.0

            # Recency boost (if timestamp available)
            recency_boost = 0.0

            return relevance + authority_boost + recency_boost

        # Sort by rank score descending
        ranked = sorted(documents, key=calculate_rank_score, reverse=True)

        # Add rank position to each doc
        for i, doc in enumerate(ranked):
            doc["rank_position"] = i + 1

        return ranked

    def _compress_documents(
        self,
        documents: List[Dict[str, Any]],
        query: str,
    ) -> List[Dict[str, Any]]:
        """
        Compress documents by focusing on query-relevant sentences.
        Keep full context but prioritize relevant excerpts.
        """
        compressed = []
        query_terms = set(query.lower().split())

        for doc in documents:
            content = doc.get("content", "")

            # Split into sentences
            sentences = re.split(r'[.!?]+', content)

            # Score sentences by query term overlap
            scored_sentences = []
            for sentence in sentences:
                if not sentence.strip():
                    continue
                sentence_terms = set(sentence.lower().split())
                overlap = len(query_terms & sentence_terms)
                scored_sentences.append((overlap, sentence.strip()))

            # Sort by relevance, keep top sentences + some context
            scored_sentences.sort(reverse=True, key=lambda x: x[0])

            # Keep full content but mark important excerpts
            compressed_doc = doc.copy()
            compressed_doc["important_excerpts"] = [
                s[1] for s in scored_sentences[:3]  # Top 3 relevant sentences
            ]
            compressed.append(compressed_doc)

        return compressed

    def _assemble_by_query_type(
        self,
        documents: List[Dict[str, Any]],
        query_type: str,
    ) -> List[Dict[str, Any]]:
        """Assemble context differently based on query type."""

        if query_type == "factual":
            # For factual queries: prioritize top 3 most relevant
            return documents[:3]

        elif query_type == "explanatory":
            # For how/why: need more comprehensive context
            return documents[:5]

        elif query_type == "analytical":
            # For comparisons: include diverse sources
            return self._diversify_sources(documents)[:5]

        elif query_type == "advisory":
            # For advice: authoritative sources first
            return documents[:4]

        else:  # conversational, search
            # General: balanced approach
            return documents[:4]

    def _diversify_sources(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure diverse source representation."""
        seen_sources = set()
        diversified = []

        for doc in documents:
            source_id = doc.get("source_id")
            if source_id not in seen_sources:
                diversified.append(doc)
                seen_sources.add(source_id)
            elif len(diversified) < 3:  # Allow some duplicates if too few
                diversified.append(doc)

        return diversified

    def _fit_token_budget(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fit documents within token budget."""
        fitted = []
        token_count = 0

        for doc in documents:
            doc_tokens = self._estimate_doc_tokens(doc)

            if token_count + doc_tokens <= self.max_context_tokens:
                fitted.append(doc)
                token_count += doc_tokens
            else:
                # Try to fit truncated version
                remaining_tokens = self.max_context_tokens - token_count
                if remaining_tokens > 100:  # If at least 100 tokens left
                    truncated_doc = self._truncate_document(doc, remaining_tokens)
                    fitted.append(truncated_doc)
                break

        return fitted

    def _estimate_tokens(self, documents: List[Dict[str, Any]]) -> int:
        """Estimate total tokens for documents."""
        return sum(self._estimate_doc_tokens(doc) for doc in documents)

    def _estimate_doc_tokens(self, doc: Dict[str, Any]) -> int:
        """Estimate tokens for a single document (rough: 1 token ≈ 4 chars)."""
        content = doc.get("content", "")
        return len(content) // 4

    def _truncate_document(self, doc: Dict[str, Any], max_tokens: int) -> Dict[str, Any]:
        """Truncate document to fit token budget."""
        truncated = doc.copy()
        content = doc.get("content", "")
        max_chars = max_tokens * 4

        if len(content) > max_chars:
            truncated["content"] = content[:max_chars] + "..."
            truncated["truncated"] = True

        return truncated

    def _enrich_metadata(
        self,
        documents: List[Dict[str, Any]],
        source_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Enrich documents with source metadata."""
        source_metadata = source_metadata or {}
        enriched = []

        for doc in documents:
            enriched_doc = doc.copy()
            source_id = doc.get("source_id", "")

            if source_id in source_metadata:
                meta = source_metadata[source_id]
                enriched_doc["source_name"] = meta.get("display_name", source_id)
                enriched_doc["source_type"] = meta.get("type", "unknown")
                enriched_doc["source_authority"] = meta.get("is_authoritative", False)

            enriched.append(enriched_doc)

        return enriched


def create_context_summary(engineered_context: Dict[str, Any]) -> str:
    """Create a human-readable summary of engineered context."""
    docs = engineered_context["documents"]
    stats = engineered_context["context_stats"]
    query_type = engineered_context["query_type"]

    summary = f"""Context Engineering Summary:
- Query Type: {query_type}
- Documents: {stats['original_count']} → {stats['final_count']} (filtered & optimized)
- Estimated Tokens: {stats['estimated_tokens']}
- Top Sources: {', '.join([d.get('source_name', d.get('source_id', 'Unknown'))[:20] for d in docs[:3]])}
"""
    return summary
