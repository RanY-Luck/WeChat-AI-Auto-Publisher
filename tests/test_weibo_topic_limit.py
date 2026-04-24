from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WeiboTopicLimitTests(unittest.TestCase):
    def test_scheduler_reads_configurable_hot_topic_candidate_limit(self):
        script_text = (ROOT / "scheduler_app.py").read_text(encoding="utf-8")
        config_example_text = (ROOT / "config" / "config.py.example").read_text(encoding="utf-8")

        self.assertIn('hot_topic_candidate_limit', config_example_text)
        self.assertIn('topic_candidate_limit = _safe_int(', script_text)
        self.assertIn('publish_config.get("hot_topic_candidate_limit")', script_text)
        self.assertIn('topic_candidates = [item for item in topic_candidates if item][:topic_candidate_limit]', script_text)


if __name__ == "__main__":
    unittest.main()
