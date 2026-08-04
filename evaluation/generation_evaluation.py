from rag import ask_question
from evaluation_data import evaluation_data


def run_generation_evaluation():

    passed = 0
    failed = 0


    print("=" * 70)
    print("GENERATION EVALUATION")
    print("=" * 70)


    for index, item in enumerate(evaluation_data, start=1):

        question = item["question"]

        expected_keywords = item["expected_keywords"]


        print("\n")
        print("=" * 70)
        print(f"QUESTION {index}")
        print(question)
        print("=" * 70)


        answer = ask_question(question)


        print("\nANSWER:")
        print(answer)


        keyword_found = any(
            keyword.lower() in answer.lower()
            for keyword in expected_keywords
        )


        if keyword_found:
            passed += 1
            print("\n✅ PASS")

        else:
            failed += 1
            print("\n❌ FAIL")


    total = len(evaluation_data)


    print("\n")
    print("=" * 70)
    print("FINAL GENERATION SUMMARY")
    print("=" * 70)

    print(f"Total Questions : {total}")
    print(f"Passed          : {passed}")
    print(f"Failed          : {failed}")

    print(
        f"Accuracy        : {(passed/total)*100:.2f}%"
    )


if __name__ == "__main__":
    run_generation_evaluation()