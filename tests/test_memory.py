from memory import (
    add_message,
    get_history,
    clear_memory
)


def test_conversation_memory():

    conversation_id = "test_chat"


    # Clean previous test
    clear_memory(conversation_id)


    # User message 1
    add_message(
        conversation_id,
        "user",
        "What is machine learning?"
    )


    # Assistant response 1
    add_message(
        conversation_id,
        "assistant",
        "Machine learning is learning from data."
    )


    # User message 2
    add_message(
        conversation_id,
        "user",
        "Explain it simply."
    )


    history = get_history(
        conversation_id
    )


    print("\n========== MEMORY TEST ==========\n")


    for message in history:
        print(
            message["role"],
            ":",
            message["content"]
        )


    assert len(history) == 3


    assert history[0]["content"] == (
        "What is machine learning?"
    )


    assert history[-1]["content"] == (
        "Explain it simply."
    )


    print("\n✅ Memory test passed")


if __name__ == "__main__":

    test_conversation_memory()