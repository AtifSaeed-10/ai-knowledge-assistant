from llm_service import generate_response
from config import MEMORY_WINDOW

def rewrite_query(question, history):
    """
    Converts follow-up questions into standalone questions.
    """

    if not history:
        return question


    recent_history = history[-MEMORY_WINDOW:]


    conversation = "\n".join(
        [
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in recent_history
        ]
    )


    prompt = f"""
You are a query rewriting system.

Your job:
Rewrite the current user question into a standalone question.

Rules:
- Identify the MAIN TOPIC from the user's previous question.
- Words like "it", "this", "that", "explain it", "simplify it" refer to the main topic, not individual words from the answer.
- Rewrite the question using the main topic.
- Do not answer the question.
- Only return the rewritten question.
- Keep it short.


Conversation History:

{conversation}


Current Question:

{question}


Standalone Question:
(Return only the rewritten question, nothing else)
""".strip()


    rewritten_question = generate_response(prompt)


    return rewritten_question.strip()