def is_valid_response(answer: str):

    if not answer:
        return False


    bad_patterns = [
        "I don't know",
        "I cannot answer",
        "you didn't provide",
        "please provide more details"
    ]


    answer_lower = answer.lower()


    for pattern in bad_patterns:

        if pattern.lower() in answer_lower:
            return False


    return True