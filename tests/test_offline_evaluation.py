import unittest
from pathlib import Path

from evaluation.run_offline import evaluate, load_dataset


class OfflineEvaluationTests(unittest.TestCase):
    def test_reference_dataset_has_perfect_deterministic_baseline(self):
        result = evaluate(load_dataset(Path("evaluation/dataset.v1.json")))

        self.assertEqual(result["case_count"], 5)
        self.assertEqual(result["recall_at_k"], 1.0)
        self.assertEqual(result["mrr"], 0.75)
        self.assertEqual(result["citation_correctness"], 1.0)
        self.assertEqual(result["refusal_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
