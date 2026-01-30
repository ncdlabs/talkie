"""
Remote RAG module API client.
"""

from __future__ import annotations

import logging
from pathlib import Path

from modules.api.client import ModuleAPIClient

logger = logging.getLogger(__name__)


class RemoteRAGService:
    """
    Remote RAG service via HTTP API.
    Implements the same interface as RAGService.
    """

    def __init__(self, client: ModuleAPIClient) -> None:
        self._client = client

    def ingest(self, paths: list[Path]) -> None:
        """Ingest documents via remote server."""
        try:
            path_strings = [str(p) for p in paths]
            response = self._client._request(
                "POST", "/ingest", json_data={"paths": path_strings}
            )
            logger.info(
                "Ingested %d documents", response.get("ingested_count", len(paths))
            )
        except Exception as e:
            logger.exception("Remote RAG ingest failed: %s", e)
            raise

    def ingest_text(self, source: str, text: str) -> None:
        """Ingest text via remote server."""
        try:
            self._client._request(
                "POST", "/ingest_text", json_data={"source": source, "text": text}
            )
        except Exception as e:
            logger.exception("Remote RAG ingest_text failed: %s", e)
            raise

    def retrieve(
        self, query: str, top_k: int | None = None, min_query_length: int | None = None
    ) -> str:
        """Retrieve context via remote server."""
        try:
            data: dict[str, int | str] = {"query": query}
            if top_k is not None:
                data["top_k"] = top_k
            if min_query_length is not None:
                data["min_query_length"] = min_query_length
            response = self._client._request("POST", "/retrieve", json_data=data)
            return response.get("context", "")
        except Exception as e:
            logger.debug("Remote RAG retrieve failed: %s", e)
            return ""

    def get_document_qa_top_k(self) -> int:
        """Get document QA top_k setting."""
        # This would need to be stored or retrieved from config
        # For now, return a default
        return 8

    def list_indexed_sources(self) -> list[str]:
        """List indexed sources via remote server."""
        try:
            response = self._client._request("GET", "/sources")
            return response.get("sources", [])
        except Exception as e:
            logger.debug("Remote RAG list_indexed_sources failed: %s", e)
            return []

    def remove_from_index(self, source: str) -> None:
        """Remove source from index via remote server."""
        try:
            self._client._request("DELETE", f"/sources/{source}")
        except Exception as e:
            logger.exception("Remote RAG remove_from_index failed: %s", e)
            raise

    def clear_index(self) -> None:
        """Clear entire index via remote server."""
        try:
            self._client._request("POST", "/clear")
        except Exception as e:
            logger.exception("Remote RAG clear_index failed: %s", e)
            raise

    def has_documents(self) -> bool:
        """Check if documents exist via remote server."""
        try:
            response = self._client._request("GET", "/has_documents")
            return bool(response.get("has_documents", False))
        except Exception as e:
            logger.debug("Remote RAG has_documents failed: %s", e)
            return False
