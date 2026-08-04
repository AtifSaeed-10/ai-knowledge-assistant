from typing import List


def format_history(
    history: List[dict]
) -> str:
    """
    Convert messages into prompt format.
    """

    if not history:
        return "No previous conversation."


    formatted = []

    for message in history:

        role = message["role"].capitalize()

        formatted.append(
            f"{role}: {message['content']}"
        )


    return "\n".join(formatted)