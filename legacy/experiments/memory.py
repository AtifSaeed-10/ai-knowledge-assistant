from typing import Dict, List

from config import MEMORY_WINDOW


# Temporary in-memory storage
# Later this can be replaced with Redis/Postgres
_conversations: Dict[str, List[dict]] = {}


def get_history(conversation_id: str) -> List[dict]:
    """
    Returns recent conversation history.
    """

    history = _conversations.get(
        conversation_id,
        []
    )

    return history[-MEMORY_WINDOW:]


def add_message(
    conversation_id: str,
    role: str,
    content: str
):
    """
    Stores one conversation message.
    """

    if conversation_id not in _conversations:
        _conversations[conversation_id] = []

    _conversations[conversation_id].append(
        {
            "role": role,
            "content": content
        }
    )


def format_history(history: List[dict]) -> str:
    """
    Converts conversation history into prompt-ready text.
    """

    if not history:
        return "No previous conversation."

    formatted = []

    for message in history:
        role = message["role"].capitalize()
        content = message["content"]

        formatted.append(
            f"{role}: {content}"
        )

    return "\n".join(formatted)


def clear_memory(conversation_id: str):
    """
    Clears one conversation.
    """

    if conversation_id in _conversations:
        del _conversations[conversation_id]


if __name__ == "__main__":

    add_message(
        "test",
        "user",
        "What is RAG?"
    )

    add_message(
        "test",
        "assistant",
        "RAG is retrieval augmented generation"
    )

    history = get_history("test")

    print(history)

    print("\nFormatted:")
    print(format_history(history))