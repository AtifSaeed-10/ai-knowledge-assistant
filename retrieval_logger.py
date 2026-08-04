from datetime import datetime
import os


LOG_FILE = "logs/retrieval.log"


def log_retrieval(
    question,
    chunks,
    distances,
    ids,
    metadata
):

    os.makedirs(
        "logs",
        exist_ok=True
    )


    with open(
        LOG_FILE,
        "a",
        encoding="utf-8"
    ) as file:


        file.write("\n")
        file.write("=" * 70)
        file.write("\n")


        file.write(
            f"TIME: {datetime.now()}\n\n"
        )


        file.write(
            f"QUESTION:\n{question}\n\n"
        )


        for i in range(len(chunks)):

            file.write(
                f"RESULT {i+1}\n"
            )

            file.write(
                f"ID: {ids[i]}\n"
            )

            file.write(
                f"DISTANCE: {distances[i]:.4f}\n"
            )

            file.write(
                f"METADATA: {metadata[i]}\n"
            )

            file.write(
                "TEXT:\n"
            )

            file.write(
                chunks[i][:300]
            )

            file.write("\n\n")