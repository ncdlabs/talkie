"""
Browse command matcher: routing and first-command extraction for web mode.
Encapsulates "is this a browse command?" and "first single command" so the pipeline stays DRY.
"""

from __future__ import annotations


class BrowseCommandMatcher:
    """
    Determines if an utterance looks like a browse command (search, scroll, click, etc.)
    and extracts the first single command from compound utterances.
    """

    def _looks_like_search(self, s: str) -> bool:
        u = (s or "").strip().lower()
        if not u:
            return False
        # Relaxed: "search" with no space (e.g. "Search...topic"), and "searched for" (e.g. "I searched for X").
        if (
            u.startswith("search")
            or " searched for " in u
            or u.startswith("searched for ")
        ):
            return True
        return (
            "searching for " in u
            or "search for " in u
            or u.startswith("searching ")
            or " searching " in u
            or " search " in u
        )

    def _looks_like_store(self, s: str) -> bool:
        u = (s or "").strip().lower()
        if not u:
            return False
        return (
            "save page" in u
            or u == "save page"
            or u.startswith("save the page")
            or "store this page" in u
            or "store the page" in u
            or u.startswith("store page")
            or u == "store page"
            or u.startswith("store this")
        )

    def _looks_like_go_back(self, s: str) -> bool:
        u = (s or "").strip().lower()
        if not u:
            return False
        return (
            u == "back"
            or u.startswith("back ")
            or u.endswith(" back")
            or "go back" in u
            or u == "go back"
            or "previous page" in u
        )

    def _looks_like_click_or_select(self, s: str) -> bool:
        u = (s or "").strip().lower()
        if not u:
            return False
        # Require command at start to avoid mishears (e.g. "one here two click your free feedback")
        # matching; allow "open 1".."open N" and explicit open/click/select/link-for prefixes.
        if (
            u.startswith("open ")
            or u.startswith("open the ")
            or u.startswith("click")
            or u.startswith("select ")
            or u == "click"
            or u.startswith("the link for ")
            or u.startswith("link for ")
        ):
            return True
        return False

    def _looks_like_scroll(self, s: str) -> bool:
        u = (s or "").strip().lower()
        if not u:
            return False
        if u.startswith("scroll ") or u == "scroll":
            return True
        return (
            " scroll up" in u
            or " scroll down" in u
            or " scroll left" in u
            or " scroll right" in u
        )

    def _looks_like_mode_toggle(self, s: str) -> bool:
        u = (s or "").strip().lower()
        if not u:
            return False
        return (
            "start browsing" in u
            or "stop browsing" in u
            or u == "browse on"
            or u == "browse off"
            or u == "browse"
            or u.startswith("browse on")
            or u.startswith("browse off")
        )

    def _looks_like_close_tab(self, s: str) -> bool:
        u = (s or "").strip().lower()
        if not u:
            return False
        return (
            u == "close tab"
            or u == "close"
            or u.startswith("close tab ")
            or u.startswith("close ")
        )

    def _is_browse_command_single(self, s: str) -> bool:
        return (
            self._looks_like_search(s)
            or self._looks_like_store(s)
            or self._looks_like_go_back(s)
            or self._looks_like_click_or_select(s)
            or self._looks_like_scroll(s)
            or self._looks_like_mode_toggle(s)
            or self._looks_like_close_tab(s)
        )

    def is_browse_command(self, *candidates: str) -> bool:
        """Return True if any candidate (e.g. intent_sentence, text) matches a browse command."""
        for c in candidates:
            if c and self._is_browse_command_single((c or "").strip()):
                return True
        return False

    def starts_with_browse_command(self, utterance: str) -> bool:
        """
        True iff the utterance starts with a browse command prefix (search, open, click, etc.).
        In web mode we only act when this is True so we never run on echo/continuation
        (e.g. "to open a result one here, two click here").
        """
        u = (utterance or "").strip().lower()
        if not u:
            return False
        # Order longer prefixes first.
        prefixes = (
            "searching for ",
            "searched for ",
            "search for ",
            "searching ",
            "search ",
            "search",
            "save the page",
            "save page",
            "store this page",
            "store the page",
            "store page",
            "store this",
            "store ",
            "go back",
            "previous page",
            "open the ",
            "open ",
            "the link for ",
            "link for ",
            "click ",
            "click",
            "select ",
            "scroll up",
            "scroll down",
            "scroll left",
            "scroll right",
            "scroll ",
            "scroll",
            "start browsing",
            "stop browsing",
            "browse on",
            "browse off",
            "close tab",
            "close ",
            "close",
            "back ",
            "back",
        )
        for p in prefixes:
            if u.startswith(p):
                return True
        # "browse" alone (word boundary: followed by space or end)
        if u == "browse" or u.startswith("browse "):
            return True
        return False

    def is_scroll_or_go_back_only(self, utterance: str) -> bool:
        """True if the (first) command is only scroll or go_back. Used to allow these during post-TTS cooldown."""
        cmd = self.first_single_command(utterance or "").strip().lower()
        if not cmd:
            return False
        return self._looks_like_scroll(cmd) or self._looks_like_go_back(cmd)

    def is_open_number_only(self, utterance: str) -> bool:
        """True if the utterance is specifically 'open N' (open result by number). Used to allow open during cooldown."""
        u = (utterance or "").strip().lower()
        if not u or not (u.startswith("open ") or u.startswith("open the ")):
            return False
        rest = u.replace("open the ", "", 1).replace("open ", "", 1).strip().rstrip(".")
        if not rest:
            return False
        # Digit 1-10 (allow trailing period from STT)
        if rest.isdigit():
            n = int(rest)
            return 1 <= n <= 10
        # Word one..ten (STT often produces "open six" etc.)
        words = (
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
        )
        return rest in words

    def first_single_command(self, utterance: str, max_len: int = 80) -> str:
        """
        Web mode: one order, one command. Return first segment that is a browse command
        or first segment (capped at max_len). Splits on ". " or " and " when present.
        """
        u = (utterance or "").strip()
        if not u:
            return u
        for sep in (". ", " and "):
            if sep in u:
                parts = [p.strip() for p in u.split(sep, 1)]
                first = parts[0].strip() if parts else u
                if not first:
                    continue
                if (
                    self._looks_like_search(first)
                    or self._looks_like_store(first)
                    or self._looks_like_go_back(first)
                    or self._looks_like_click_or_select(first)
                    or self._looks_like_scroll(first)
                    or self._looks_like_close_tab(first)
                ):
                    return first[:max_len] if len(first) > max_len else first
                return first[:max_len] if len(first) > max_len else first
        return u[:max_len]
