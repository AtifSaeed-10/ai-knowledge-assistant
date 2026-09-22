from rag import retrieve_chunks, collection
from evaluation_data import evaluation_data


def run_evaluation():

    questions = evaluation_data

    total_questions = len(questions)

    passed = 0
    failed = 0

    reciprocal_ranks = []
    all_distances = []


    print("\n")
    print("=" * 70)
    print("RETRIEVAL EVALUATION")
    print("=" * 70)


    for index, item in enumerate(questions, start=1):

        question = item["question"]
        expected_keywords = item["expected_keywords"]


        print("\n")
        print("=" * 70)
        print(f"QUESTION {index}")
        print(question)
        print("=" * 70)


        result = retrieve_chunks(
            question,
            collection
        )


        chunks = result["chunks"]
        distances = result["distances"]


        retrieved_text = "\n".join(chunks)


        # -----------------------------
        # Hit@K + MRR calculation
        # -----------------------------

        found_rank = None


        for rank, chunk in enumerate(chunks, start=1):

            keyword_found = any(
                keyword.lower() in chunk.lower()
                for keyword in expected_keywords
            )

            if keyword_found:
                found_rank = rank
                break


        if found_rank:

            passed += 1

            reciprocal_ranks.append(
                1 / found_rank
            )

            print("\n✅ HIT")

        else:

            failed += 1

            reciprocal_ranks.append(0)

            print("\n❌ MISS")


        # -----------------------------
        # Print retrieved chunks
        # -----------------------------

        for i, (chunk, distance) in enumerate(
            zip(chunks, distances),
            start=1
        ):

            print("\n")
            print(f"Chunk {i}")
            print(f"Distance: {distance:.4f}")
            print("-" * 50)

            print(chunk[:300])


        all_distances.extend(distances)



    # -----------------------------
    # Final Metrics
    # -----------------------------

    accuracy = (passed / total_questions) * 100

    mrr = sum(reciprocal_ranks) / total_questions

    average_distance = (
        sum(all_distances) / len(all_distances)
    )


    print("\n")
    print("=" * 70)
    print("FINAL EVALUATION SUMMARY")
    print("=" * 70)

    print(f"Total Questions : {total_questions}")
    print(f"Passed          : {passed}")
    print(f"Failed          : {failed}")

    print(f"Hit@K Accuracy  : {accuracy:.2f}%")
    print(f"MRR             : {mrr:.4f}")
    print(f"Average Distance: {average_distance:.4f}")

if __name__ == "__main__":
    run_evaluation()