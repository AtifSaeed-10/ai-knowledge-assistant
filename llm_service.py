from config import (
    PRIMARY_LLM,
    FALLBACK_LLM,
)

from ollama_service import (
    generate_ollama_response,
    generate_ollama_stream
)

from groq_service import (
    generate_groq_response,
    generate_groq_stream
)


providers = {
    "ollama": generate_ollama_response,
    "groq": generate_groq_response,
}


stream_providers = {
    "ollama": generate_ollama_stream,
    "groq": generate_groq_stream,
}



def generate_response(prompt: str) -> str:

    try:

        print("\n" + "=" * 50)
        print(f"Using provider: {PRIMARY_LLM}")
        print("=" * 50)


        response = providers[PRIMARY_LLM](prompt)


        print("Response generated successfully.")


        return response


    except Exception as e:

        print("\nPRIMARY PROVIDER FAILED")
        print(e)

        print("Trying fallback provider...")
        print(FALLBACK_LLM)



    try:

        response = providers[FALLBACK_LLM](prompt)

        return response


    except Exception as e:

        print("\nFALLBACK PROVIDER FAILED")
        print(e)


        return (
            "Sorry, I couldn't generate a response at the moment."
        )





def generate_response_stream(prompt: str):

    try:

        print("\n" + "=" * 50)
        print(f"Streaming provider: {PRIMARY_LLM}")
        print("=" * 50)


        stream = stream_providers[PRIMARY_LLM](prompt)


        for chunk in stream:

            yield chunk



    except Exception as e:


        print("\nPRIMARY STREAM FAILED")
        print(e)

        print("Trying fallback stream...")



        try:

            stream = stream_providers[FALLBACK_LLM](prompt)


            for chunk in stream:

                yield chunk



        except Exception as e:

            print("\nFALLBACK STREAM FAILED")
            print(e)

            yield (
                "Sorry, I couldn't generate a response."
            )