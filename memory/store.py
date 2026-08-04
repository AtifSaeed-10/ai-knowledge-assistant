from typing import Dict, List


# Temporary storage
# Later replace with Redis/PostgreSQL

_conversations: Dict[str, List[dict]] = {}


def save_message(
    conversation_id: str,
    role: str,
    content: str
):
    """
    Store one message.
    """

    if conversation_id not in _conversations:
        _conversations[conversation_id] = []

    _conversations[conversation_id].append(
        {
            "role": role,
            "content": content
        }
    )


def load_conversation(
    conversation_id: str
) -> List[dict]:
    """
    Return complete conversation.
    """

    return _conversations.get(
        conversation_id,
        []
    )


def delete_conversation(
    conversation_id: str
):
    """
    Delete conversation memory.
    """

    if conversation_id in _conversations:
        del _conversations[conversation_id]