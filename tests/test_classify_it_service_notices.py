"""Tests for historical IT-service notice classification."""

from __future__ import annotations

import unittest

import pandas as pd

from one_off_scripts.classify_it_service_notices import classify_notices


class ClassifyNoticesTest(unittest.TestCase):
    def test_multi_label_tags_and_core_priority(self) -> None:
        notices = pd.DataFrame(
            {
                "key": ["core-ai", "adjacent-ai", "excluded-ai", "not-it"],
                "project_name": [
                    "AIシステム開発",
                    "AI活用調査",
                    "AI研修運営",
                    "庁舎清掃",
                ],
                "organization_name": ["A", "B", "C", "D"],
                "lg_code": ["13", "13", "13", "13"],
                "prefecture_name": ["東京都", "東京都", "東京都", "東京都"],
                "city_code": [None, None, None, None],
                "city_name": [None, None, None, None],
                "cft_issue_date": [
                    "2025-01-01T00:00:00+09:00",
                    "2025-01-02T00:00:00+09:00",
                    "2025-01-03T00:00:00+09:00",
                    "2025-01-04T00:00:00+09:00",
                ],
                "cft_issue_year": [2025, 2025, 2025, 2025],
                "category": ["役務", "役務", "役務", "役務"],
                "procedure_type": [None, None, None, None],
                "external_document_uri": [None, None, None, None],
            }
        )
        taxonomy = {
            "version": "test",
            "patterns": {
                "system_development": r"システム.*開発",
                "artificial_intelligence": r"AI",
            },
            "core_it_delivery_subgroups": ["system_development"],
            "adjacent_subgroups": ["artificial_intelligence"],
            "exclusion_patterns": {
                "artificial_intelligence": r"AI.*研修",
            },
        }

        result = classify_notices(notices, taxonomy).set_index("key")

        self.assertTrue(result.loc["core-ai", "it_related"])
        self.assertTrue(result.loc["core-ai", "core_it_delivery"])
        self.assertFalse(result.loc["core-ai", "digital_or_ai_adjacent"])
        self.assertEqual(result.loc["core-ai", "subgroup_count"], 2)
        self.assertEqual(
            result.loc["core-ai", "matched_subgroups"],
            "system_development|artificial_intelligence",
        )

        self.assertFalse(result.loc["adjacent-ai", "core_it_delivery"])
        self.assertTrue(result.loc["adjacent-ai", "digital_or_ai_adjacent"])
        self.assertFalse(result.loc["excluded-ai", "it_related"])
        self.assertFalse(result.loc["not-it", "it_related"])


if __name__ == "__main__":
    unittest.main()
