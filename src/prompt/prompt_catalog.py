import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from src.uuid_util.is_valid_uuid import is_valid_uuid

logger = logging.getLogger(__name__)

@dataclass
class PromptItem:
    """Dataclass to hold a single prompt with tags, UUID, and any extra fields."""
    id: str
    prompt: str
    tags: List[str] = field(default_factory=list)
    extras: Dict[str, Any] = field(default_factory=dict)

class PromptCatalog:
    """
    A catalog of PromptItem objects, keyed by UUID.
    Supports loading from one or more JSONL files, each containing
    one JSON object per line.
    """
    def __init__(self):
        self._catalog: Dict[str, PromptItem] = {}

    def load(self, filepath: str) -> None:
        """
        Load prompts from a JSONL file. Each line is expected to have
        fields like 'id', 'prompt', 'tags', etc.
        Logs an error if 'id' or 'prompt' is missing/empty, then skips that row.
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error in {filepath} at line {line_num}: {e}")
                    continue

                pid = data.get('id')
                prompt_text = data.get('prompt')

                if not pid:
                    logger.error(f"Missing 'id' field in {filepath} at line {line_num}. Skipping row.")
                    continue
                if not prompt_text:
                    logger.error(f"Missing or empty 'prompt' for ID '{pid}' in {filepath} at line {line_num}. Skipping row.")
                    continue

                if not is_valid_uuid(pid):
                    logger.error(f"Invalid UUID in {filepath} at line {line_num}: {pid}. Skipping row.")
                    continue

                tags = data.get('tags', [])
                extras = {k: v for k, v in data.items() if k not in ('id', 'prompt', 'tags')}

                if self._catalog.get(pid):
                    logger.error(f"Duplicate UUID found in {filepath} at line {line_num}: {pid}. Skipping row.")
                    continue

                item = PromptItem(id=pid, prompt=prompt_text, tags=tags, extras=extras)
                self._catalog[pid] = item

    def find(self, prompt_id: str) -> Optional[PromptItem]:
        """Retrieve a PromptItem by its ID (UUID). Returns None if not found."""
        if not is_valid_uuid(prompt_id):
            raise ValueError(f"Invalid UUID: {prompt_id}")
        return self._catalog.get(prompt_id)

    def find_by_tag(self, tag: str) -> List[PromptItem]:
        """
        Return a list of all PromptItems that contain the given tag
        (case-sensitive match).
        """
        return [item for item in self._catalog.values() if tag in item.tags]

    def all(self) -> List[PromptItem]:
        """Return a list of all PromptItems in the order they were inserted."""
        return list(self._catalog.values())
