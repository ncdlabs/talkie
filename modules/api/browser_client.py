"""
Remote browser module API client.
"""

from __future__ import annotations

import logging
from typing import Callable

from modules.api.client import ModuleAPIClient

logger = logging.getLogger(__name__)


class RemoteBrowserHandler:
    """
    Remote browser handler via HTTP API.
    Implements the same interface as the browser handler function.
    """

    def __init__(self, client: ModuleAPIClient) -> None:
        self._client = client

    def __call__(
        self, utterance: str, set_web_mode: Callable[[bool], None]
    ) -> str | None:
        """
        Execute browser intent via remote server.
        Note: set_web_mode callback is executed locally since UI runs locally.
        """
        try:
            # The intent parsing should happen on the client side (where LLM is)
            # For now, we'll pass the utterance and let the server handle it
            # In practice, the client should parse intent first, then send to server
            response = self._client._request(
                "POST", "/execute", json_data={"utterance": utterance}
            )
            result = response.get("result")
            # Handle browse_on/browse_off locally
            if result and "browse mode is on" in result.lower():
                set_web_mode(True)
            elif result and "browse mode is off" in result.lower():
                set_web_mode(False)
            return result
        except Exception as e:
            logger.debug("Remote browser execute failed: %s", e)
            return None

    def execute_intent(self, intent: dict) -> dict | None:
        """
        Execute browser intent directly (when intent is already parsed).
        Returns full response dict with "result" and optionally "open_url" (for client to open locally).
        On error logs to debug and returns a dict with a user-friendly result message.
        """
        try:
            logger.debug(
                "Remote browser execute_intent: action=%r", intent.get("action")
            )
            out = self._client._request(
                "POST", "/execute", json_data={"intent": intent}
            )
            logger.debug("Remote browser execute_intent: success")
            return out
        except Exception as e:
            logger.exception("Remote browser execute_intent failed: %s", e)
            return {"result": "Could not complete that action."}
