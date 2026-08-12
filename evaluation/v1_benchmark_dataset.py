"""
DocuSage RAG V1 Baseline Benchmark Dataset

Grounded in documents currently present in the Chroma index:
  - MACHINE LEARNING.pdf
  - football_rules.pdf

PDFs on disk but NOT indexed (used for unanswerable cases):
  - laws-of-cricket.pdf
  - ww2.pdf

Do not modify this dataset between V1 and V2 runs if you want
apples-to-apples comparison. Add new questions in a separate file instead.
"""

# Categories:
#   factual        - direct fact lookup
#   semantic       - paraphrased / conceptual
#   exact_term     - names, numbers, exact phrases
#   multi_chunk    - needs combining info (often multi-page)
#   comparison     - compare/contrast concepts
#   conversational - requires history / rewrite
#   unanswerable   - should refuse / insufficient evidence

V1_BENCHMARK = [

    # ------------------------------------------------------------------
    # MACHINE LEARNING — factual
    # ------------------------------------------------------------------
    {
        "id": "ml_f01",
        "category": "factual",
        "difficulty": "easy",
        "question": "Who coined the term Machine Learning and in what year?",
        "expected_answer": "Arthur Samuel coined the term Machine Learning in 1959 while at IBM.",
        "expected_keywords": ["Arthur Samuel", "1959"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [6],
        "answerable": True,
    },
    {
        "id": "ml_f02",
        "category": "factual",
        "difficulty": "easy",
        "question": "What is Arthur Samuel's definition of machine learning?",
        "expected_answer": "The field of study that gives computers the ability to learn without being explicitly programmed.",
        "expected_keywords": ["learn without being explicitly programmed"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [6],
        "answerable": True,
    },
    {
        "id": "ml_f03",
        "category": "factual",
        "difficulty": "easy",
        "question": "According to Tom Mitchell's definition, when is a computer program said to learn?",
        "expected_answer": "A program learns from experience E with respect to tasks T and performance P if performance at T, measured by P, improves with E.",
        "expected_keywords": ["experience E", "tasks T", "performance measure P"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [6],
        "answerable": True,
    },
    {
        "id": "ml_f04",
        "category": "factual",
        "difficulty": "easy",
        "question": "What are the three main types of learning mentioned in the introduction?",
        "expected_answer": "Supervised, Unsupervised, and Reinforcement learning.",
        "expected_keywords": ["Supervised", "Unsupervised", "Reinforcement"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [2],
        "answerable": True,
    },
    {
        "id": "ml_f05",
        "category": "factual",
        "difficulty": "easy",
        "question": "What does ID3 stand for in decision trees?",
        "expected_answer": "Iterative Dichotomiser 3.",
        "expected_keywords": ["Iterative Dichotomiser"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [30, 31],
        "answerable": True,
    },
    {
        "id": "ml_f06",
        "category": "factual",
        "difficulty": "medium",
        "question": "What are the four commonly used distance metrics in geometric models?",
        "expected_answer": "Euclidean, Minkowski, Manhattan, and Mahalanobis.",
        "expected_keywords": ["Euclidean", "Minkowski", "Manhattan", "Mahalanobis"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [11],
        "answerable": True,
    },
    {
        "id": "ml_f07",
        "category": "factual",
        "difficulty": "easy",
        "question": "What is a Classification and Regression Tree (CART)?",
        "expected_answer": "A predictive algorithm that predicts a target variable's values based on other values; it is a decision tree.",
        "expected_keywords": ["predictive algorithm", "decision tree"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [36],
        "answerable": True,
    },

    # ------------------------------------------------------------------
    # MACHINE LEARNING — semantic / paraphrased
    # ------------------------------------------------------------------
    {
        "id": "ml_s01",
        "category": "semantic",
        "difficulty": "medium",
        "question": "How would you explain machine learning in simple terms based on the lecture notes?",
        "expected_answer": "Programming computers to optimize a performance criterion using example data or past experience.",
        "expected_keywords": ["optimize", "example data"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [6],
        "answerable": True,
    },
    {
        "id": "ml_s02",
        "category": "semantic",
        "difficulty": "medium",
        "question": "When a decision tree memorizes noise and produces inaccurate results, what problem is that?",
        "expected_answer": "Overfitting.",
        "expected_keywords": ["Overfitting", "noise"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [36],
        "answerable": True,
    },
    {
        "id": "ml_s03",
        "category": "semantic",
        "difficulty": "medium",
        "question": "What kind of learning problem is predicting continuous sales from advertising spend?",
        "expected_answer": "Regression, a supervised learning technique for continuous output.",
        "expected_keywords": ["Regression", "supervised", "continuous"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [37],
        "answerable": True,
    },
    {
        "id": "ml_s04",
        "category": "semantic",
        "difficulty": "medium",
        "question": "In geometric models, how can similarity between points be represented without drawing a separating line?",
        "expected_answer": "Using distance-based models where nearby points are treated as similar.",
        "expected_keywords": ["distance", "similar"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [10],
        "answerable": True,
    },
    {
        "id": "ml_s05",
        "category": "semantic",
        "difficulty": "medium",
        "question": "What is the purpose of Shannon entropy in building decision trees?",
        "expected_answer": "Entropy measures uncertainty or randomness in data and helps assess predictability of events.",
        "expected_keywords": ["entropy", "uncertainty", "randomness"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [30],
        "answerable": True,
    },

    # ------------------------------------------------------------------
    # MACHINE LEARNING — exact terminology / numbers
    # ------------------------------------------------------------------
    {
        "id": "ml_e01",
        "category": "exact_term",
        "difficulty": "easy",
        "question": "In the Enjoy Sport concept learning example, how many attributes describe each day?",
        "expected_answer": "Six attributes.",
        "expected_keywords": ["six attributes", "six"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [9],
        "answerable": True,
    },
    {
        "id": "ml_e02",
        "category": "exact_term",
        "difficulty": "easy",
        "question": "Name the six attributes used in the Enjoy Sport learning task.",
        "expected_answer": "Sky, AirTemp, Humidity, Wind, Water, and Forecast.",
        "expected_keywords": ["Sky", "AirTemp", "Humidity", "Wind", "Water", "Forecast"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [9],
        "answerable": True,
    },
    {
        "id": "ml_e03",
        "category": "exact_term",
        "difficulty": "medium",
        "question": "In the ID3 weather example table, how many Yes and No outcomes are there in total?",
        "expected_answer": "9 Yes and 5 No, for a total of 14.",
        "expected_keywords": ["9", "5", "14"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [31],
        "answerable": True,
    },
    {
        "id": "ml_e04",
        "category": "exact_term",
        "difficulty": "medium",
        "question": "What typical small value is given as an example for the perceptron learning rate?",
        "expected_answer": "0.1",
        "expected_keywords": ["0.1"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [52],
        "answerable": True,
    },
    {
        "id": "ml_e05",
        "category": "exact_term",
        "difficulty": "easy",
        "question": "Who wrote the textbook Introduction to Machine Learning published by MIT Press in the text books list?",
        "expected_answer": "Ethem Alpaydin.",
        "expected_keywords": ["Ethem Alpaydin"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [3],
        "answerable": True,
    },

    # ------------------------------------------------------------------
    # MACHINE LEARNING — multi-chunk / multi-page
    # ------------------------------------------------------------------
    {
        "id": "ml_m01",
        "category": "multi_chunk",
        "difficulty": "hard",
        "question": "What topics are covered under Unit II on Supervised and Unsupervised Learning?",
        "expected_answer": "Decision trees, regression, neural networks, SVMs, KNN, and clustering methods like K-means and K-Mode.",
        "expected_keywords": ["Decision Trees", "Neural Networks", "Support Vector", "clustering"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [2, 4],
        "answerable": True,
    },
    {
        "id": "ml_m02",
        "category": "multi_chunk",
        "difficulty": "hard",
        "question": "For the checkers learning problem, what are task T, performance measure P, and training experience E?",
        "expected_answer": "T: play checkers; P: percent of games won; E: opportunity to play against itself.",
        "expected_keywords": ["Play Checkers", "games won", "play against itself"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [13, 16],
        "answerable": True,
    },
    {
        "id": "ml_m03",
        "category": "multi_chunk",
        "difficulty": "hard",
        "question": "What limitations of classification and regression trees are described?",
        "expected_answer": "Overfitting, high variance, and low bias for very complex trees.",
        "expected_keywords": ["Overfitting", "High variance", "Low bias"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [36],
        "answerable": True,
    },

    # ------------------------------------------------------------------
    # MACHINE LEARNING — comparison
    # ------------------------------------------------------------------
    {
        "id": "ml_c01",
        "category": "comparison",
        "difficulty": "hard",
        "question": "What is the difference between grouping models and grading models?",
        "expected_answer": "Grouping models break the instance space into segments with a simple method in each; grading models form one global model over the instance space.",
        "expected_keywords": ["Grouping", "Grading", "segments"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [12],
        "answerable": True,
    },
    {
        "id": "ml_c02",
        "category": "comparison",
        "difficulty": "medium",
        "question": "How do classification trees differ from regression trees?",
        "expected_answer": "Classification trees have categorical outcomes; regression trees have continuous outcomes.",
        "expected_keywords": ["Categorical", "Continuous"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [30],
        "answerable": True,
    },
    {
        "id": "ml_c03",
        "category": "comparison",
        "difficulty": "medium",
        "question": "What is the difference between a centroid and a medoid?",
        "expected_answer": "A centroid is a centre of mass / mean position; a medoid is the most centrally located actual data point.",
        "expected_keywords": ["centroid", "medoid"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [11],
        "answerable": True,
    },
    {
        "id": "ml_c04",
        "category": "comparison",
        "difficulty": "medium",
        "question": "What is the difference between Linear SVM and Non-linear SVM?",
        "expected_answer": "Linear SVM is for data separable by a straight line; Non-linear SVM is for data that cannot be separated by a straight line.",
        "expected_keywords": ["Linear SVM", "Non-linear", "straight line"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [55],
        "answerable": True,
    },

    # ------------------------------------------------------------------
    # FOOTBALL RULES — factual / exact
    # ------------------------------------------------------------------
    {
        "id": "fb_f01",
        "category": "factual",
        "difficulty": "easy",
        "question": "What is advantage in football?",
        "expected_answer": "When an offence occurs and the non-offending team has useful possession, the referee allows play to continue because it benefits them.",
        "expected_keywords": ["advantage", "non-offending", "possession"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [4],
        "answerable": True,
    },
    {
        "id": "fb_f02",
        "category": "factual",
        "difficulty": "easy",
        "question": "How does the referee signal advantage?",
        "expected_answer": "By extending one or both arms forward at shoulder height.",
        "expected_keywords": ["arms", "shoulder"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [4],
        "answerable": True,
    },
    {
        "id": "fb_f03",
        "category": "factual",
        "difficulty": "easy",
        "question": "When is the ball out of play?",
        "expected_answer": "When it completely crosses the touchline or goal line, touches an official with certain consequences, or the referee stops play.",
        "expected_keywords": ["crosses", "touchline", "goal line"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [8],
        "answerable": True,
    },
    {
        "id": "fb_f04",
        "category": "factual",
        "difficulty": "easy",
        "question": "When is a corner kick awarded?",
        "expected_answer": "When the whole ball goes out over the goal line (not in the goal) and was last touched by a defending team player.",
        "expected_keywords": ["goal line", "defending"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [14],
        "answerable": True,
    },
    {
        "id": "fb_e01",
        "category": "exact_term",
        "difficulty": "easy",
        "question": "How high must corner flags be?",
        "expected_answer": "At least 1.5 m (5 ft) high and must not be pointed or dangerous.",
        "expected_keywords": ["1.5", "5 ft"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [13],
        "answerable": True,
    },
    {
        "id": "fb_e02",
        "category": "exact_term",
        "difficulty": "easy",
        "question": "How far must opponents stay from the corner arc at a corner kick?",
        "expected_answer": "At least 9.15 m (10 yds).",
        "expected_keywords": ["9.15", "10 yds"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [13, 14],
        "answerable": True,
    },
    {
        "id": "fb_e03",
        "category": "exact_term",
        "difficulty": "easy",
        "question": "What is the standard length of each half of a football game?",
        "expected_answer": "45 minutes.",
        "expected_keywords": ["45"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [11],
        "answerable": True,
    },

    # ------------------------------------------------------------------
    # FOOTBALL — semantic / multi / comparison
    # ------------------------------------------------------------------
    {
        "id": "fb_s01",
        "category": "semantic",
        "difficulty": "medium",
        "question": "Why was the Football Rules booklet created instead of only using the official Laws of the Game?",
        "expected_answer": "The official Laws are detailed and technical; Football Rules is a simpler reduced version for easier understanding.",
        "expected_keywords": ["simpler", "Laws of the Game"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [2],
        "answerable": True,
    },
    {
        "id": "fb_s02",
        "category": "semantic",
        "difficulty": "medium",
        "question": "What should happen if the ball bursts while it is in play?",
        "expected_answer": "The referee drops the ball for one player of the team that last touched it (defending goalkeeper if in the penalty area).",
        "expected_keywords": ["drops the ball", "last touched"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [7],
        "answerable": True,
    },
    {
        "id": "fb_m01",
        "category": "multi_chunk",
        "difficulty": "hard",
        "question": "What disciplinary actions correspond to careless, reckless, and serious foul play?",
        "expected_answer": "Careless: no card; Reckless: yellow card; Excessive force/serious foul play: red card.",
        "expected_keywords": ["Careless", "Reckless", "Yellow", "Red"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [22],
        "answerable": True,
    },
    {
        "id": "fb_c01",
        "category": "comparison",
        "difficulty": "medium",
        "question": "What is the difference between SPA and DOGSO fouls?",
        "expected_answer": "SPA stops a promising attack (yellow); DOGSO denies a goal or obvious goal-scoring opportunity (red).",
        "expected_keywords": ["promising attack", "goal-scoring", "DOGSO"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [22],
        "answerable": True,
    },
    {
        "id": "fb_f05",
        "category": "factual",
        "difficulty": "easy",
        "question": "Do team captains have special privileges to argue with the referee?",
        "expected_answer": "No. Captains have no special privileges to protest or argue with match officials.",
        "expected_keywords": ["no special privileges"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [9],
        "answerable": True,
    },
    {
        "id": "fb_f06",
        "category": "factual",
        "difficulty": "medium",
        "question": "What happens if an advantage is played and the player who should have received a red card then gets involved in the game?",
        "expected_answer": "The referee stops play, sends off the player, and awards an indirect free kick to the opponents.",
        "expected_keywords": ["sends off", "indirect free kick"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [5],
        "answerable": True,
    },

    # ------------------------------------------------------------------
    # Conversational (requires history / query rewrite)
    # ------------------------------------------------------------------
    {
        "id": "cv_01",
        "category": "conversational",
        "difficulty": "hard",
        "question": "When was it coined?",
        "history": [
            {"role": "user", "content": "Who coined the term Machine Learning?"},
            {"role": "assistant", "content": "Arthur Samuel coined the term Machine Learning while working at IBM."},
        ],
        "expected_answer": "1959.",
        "expected_keywords": ["1959"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [6],
        "answerable": True,
    },
    {
        "id": "cv_02",
        "category": "conversational",
        "difficulty": "hard",
        "question": "How does the referee signal it?",
        "history": [
            {"role": "user", "content": "What is advantage in football?"},
            {
                "role": "assistant",
                "content": "Advantage is when the referee allows play to continue after an offence because the non-offending team has useful possession.",
            },
        ],
        "expected_answer": "By extending one or both arms forward at shoulder height.",
        "expected_keywords": ["arms", "shoulder"],
        "expected_document": "football_rules.pdf",
        "expected_pages": [4],
        "answerable": True,
    },
    {
        "id": "cv_03",
        "category": "conversational",
        "difficulty": "hard",
        "question": "What are its main limitations?",
        "history": [
            {"role": "user", "content": "What is a Classification and Regression Tree?"},
            {
                "role": "assistant",
                "content": "A CART is a predictive decision-tree algorithm used to predict a target variable from other values.",
            },
        ],
        "expected_answer": "Overfitting, high variance, and low bias for complex trees.",
        "expected_keywords": ["Overfitting", "variance"],
        "expected_document": "MACHINE LEARNING.pdf",
        "expected_pages": [36],
        "answerable": True,
    },

    # ------------------------------------------------------------------
    # Unanswerable — should refuse / insufficient evidence
    # ------------------------------------------------------------------
    {
        "id": "ua_01",
        "category": "unanswerable",
        "difficulty": "medium",
        "question": "What is the LBW rule in cricket?",
        "expected_answer": "Insufficient evidence / not in the provided documents.",
        "expected_keywords": [],
        "expected_document": None,
        "expected_pages": [],
        "answerable": False,
        "notes": "laws-of-cricket.pdf exists on disk but is not indexed in V1 Chroma.",
    },
    {
        "id": "ua_02",
        "category": "unanswerable",
        "difficulty": "medium",
        "question": "When did World War II end in Europe?",
        "expected_answer": "Insufficient evidence / not in the provided documents.",
        "expected_keywords": [],
        "expected_document": None,
        "expected_pages": [],
        "answerable": False,
        "notes": "ww2.pdf exists on disk but is not indexed in V1 Chroma.",
    },
    {
        "id": "ua_03",
        "category": "unanswerable",
        "difficulty": "easy",
        "question": "What is the capital of Japan?",
        "expected_answer": "Insufficient evidence / not in the provided documents.",
        "expected_keywords": [],
        "expected_document": None,
        "expected_pages": [],
        "answerable": False,
    },
    {
        "id": "ua_04",
        "category": "unanswerable",
        "difficulty": "medium",
        "question": "According to the documents, what is the stock price of NVIDIA today?",
        "expected_answer": "Insufficient evidence / not in the provided documents.",
        "expected_keywords": [],
        "expected_document": None,
        "expected_pages": [],
        "answerable": False,
    },
    {
        "id": "ua_05",
        "category": "unanswerable",
        "difficulty": "hard",
        "question": "How many substitutions are allowed in the 2026 FIFA World Cup final specifically?",
        "expected_answer": "Insufficient evidence — competition-specific 2026 details are not in the simplified rules booklet.",
        "expected_keywords": [],
        "expected_document": None,
        "expected_pages": [],
        "answerable": False,
        "notes": "Football rules discuss substitutions generally but not 2026 World Cup finals specifics.",
    },
]


def dataset_stats():
    from collections import Counter

    cats = Counter(item["category"] for item in V1_BENCHMARK)
    return {
        "total": len(V1_BENCHMARK),
        "by_category": dict(cats),
        "answerable": sum(1 for i in V1_BENCHMARK if i.get("answerable", True)),
        "unanswerable": sum(1 for i in V1_BENCHMARK if not i.get("answerable", True)),
    }


if __name__ == "__main__":
    print(dataset_stats())
