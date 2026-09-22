from typing import List

from config import MEMORY_WINDOW
from .store import load_conversation


def get_history(
    conversation_id: str
) -> List[dict]:
    """
    Returns recent messages only.
    """

    history = load_conversation(
        conversation_id
    )

    return history[-MEMORY_WINDOW:]