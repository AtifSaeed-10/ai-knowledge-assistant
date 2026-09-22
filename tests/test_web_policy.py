"""Domain policy: authentic sites in, blocklist out."""

from __future__ import annotations

import unittest

from web_fallback.policy import (
    TIER_BLOCK,
    TIER_T1,
    TIER_T2,
    TIER_UNKNOWN,
    get_domain_policy,
    reset_domain_policy_cache,
    select_hits,
)
from web_fallback.types import WebHit


def _hit(url: str, title: str = "Title", snippet: str = "A useful snippet.") -> WebHit:
    return WebHit(
        title=title,
        url=url,
        snippet=snippet,
        domain="",
        provider="tavily",
        preview=False,
    )


class TestDomainPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reset_domain_policy_cache()
        cls.policy = get_domain_policy()

    def test_official_and_reference_hosts(self):
        self.assertEqual(self.policy.classify("theifab.com"), TIER_T1)
        self.assertEqual(self.policy.classify("www.fifa.com"), TIER_T1)
        self.assertEqual(self.policy.classify("cdc.gov"), TIER_T1)
        self.assertEqual(self.policy.classify("en.wikipedia.org"), TIER_T2)
        self.assertEqual(self.policy.classify("ox.ac.uk"), TIER_T2)
        self.assertEqual(self.policy.classify("espn.com"), TIER_T2)
        self.assertEqual(self.policy.classify("forbes.com"), TIER_T2)
        self.assertEqual(self.policy.classify("coindesk.com"), TIER_T2)
        self.assertEqual(self.policy.classify("coinmarketcap.com"), TIER_T2)
        self.assertEqual(self.policy.classify("skysports.com"), TIER_T2)

    def test_gov_suffix_does_not_match_lookalikes(self):
        self.assertEqual(self.policy.classify("nasa.gov"), TIER_T1)
        self.assertEqual(self.policy.classify("government.com"), TIER_UNKNOWN)

    def test_blocklist(self):
        self.assertEqual(self.policy.classify("quora.com"), TIER_BLOCK)
        self.assertEqual(self.policy.classify("www.pinterest.com"), TIER_BLOCK)
        self.assertEqual(self.policy.classify("old.reddit.com"), TIER_BLOCK)

    def test_select_drops_blocked_and_ranks_official_first(self):
        hits = [
            _hit("https://www.quora.com/what-is-offside", title="Quora"),
            _hit("https://en.wikipedia.org/wiki/Offside_(association_football)", title="Wiki"),
            _hit("https://www.theifab.com/laws/offside", title="IFAB"),
        ]
        selected = select_hits(hits, allow_t3=False, limit=5, policy=self.policy)
        urls = [item.url for item in selected]
        self.assertEqual(selected[0].tier, TIER_T1)
        self.assertIn("https://www.theifab.com/laws/offside", urls)
        self.assertIn(
            "https://en.wikipedia.org/wiki/Offside_(association_football)",
            urls,
        )
        self.assertTrue(all("quora" not in item.url for item in selected))

    def test_tier3_only_when_trusted_pool_is_thin(self):
        blog = _hit("https://random-tactics.example.net/offside", title="Blog")
        trusted_only = select_hits([blog], allow_t3=False, limit=5, policy=self.policy)
        self.assertEqual(trusted_only, [])
        broadened = select_hits([blog], allow_t3=True, limit=5, policy=self.policy)
        self.assertEqual(len(broadened), 1)
        self.assertEqual(broadened[0].tier, TIER_UNKNOWN)

    def test_non_english_wikipedia_is_dropped_when_english_exists(self):
        hits = [
            _hit(
                "https://ja.wikipedia.org/wiki/GPT-6_Astra",
                title="GPT-6 Astra",
                snippet="GPT-6 AstraはOpenAIが開発した大規模言語モデルである。",
            ),
            _hit(
                "https://en.wikipedia.org/wiki/GPT-6_Astra",
                title="GPT-6 Astra",
                snippet="GPT-6 Astra is a large language model developed by OpenAI.",
            ),
            _hit(
                "https://ja.wikipedia.org/wiki/GPT-6_Astra",
                title="GPT-6 Astra duplicate",
                snippet="別の日本語ページ。",
            ),
        ]
        selected = select_hits(hits, allow_t3=False, limit=5, policy=self.policy)
        urls = [item.url for item in selected]
        self.assertEqual(urls, ["https://en.wikipedia.org/wiki/GPT-6_Astra"])

    def test_wikipedia_talk_and_category_pages_are_dropped(self):
        hits = [
            _hit(
                "https://en.wikipedia.org/wiki/Category_talk:2010–11_NBA_season",
                title="Category talk:2010–11 NBA season",
            ),
            _hit(
                "https://en.wikipedia.org/wiki/Category:Prime_ministers_of_Pakistan",
                title="Category:Prime ministers of Pakistan",
            ),
            _hit(
                "https://en.wikipedia.org/wiki/List_of_prime_ministers_of_Pakistan",
                title="List of prime ministers of Pakistan",
                snippet="Shehbaz Sharif is the incumbent prime minister of Pakistan.",
            ),
        ]
        selected = select_hits(
            hits,
            allow_t3=False,
            limit=5,
            policy=self.policy,
            question="who are pakistan last 5 prime ministers",
        )
        urls = [item.url for item in selected]
        self.assertEqual(
            urls,
            ["https://en.wikipedia.org/wiki/List_of_prime_ministers_of_Pakistan"],
        )

    def test_irrelevant_name_match_is_dropped_when_question_tokens_are_missing(self):
        hits = [
            _hit(
                "https://en.wikipedia.org/wiki/Chris_Winnes",
                title="Chris Winnes",
                snippet="Christopher Robert Winnes is an American retired ice hockey winger.",
            ),
            _hit(
                "https://en.wikipedia.org/wiki/List_of_NBA_champions",
                title="List of NBA champions",
                snippet="NBA champions from 2010 through 2026, including the Dallas Mavericks in 2011.",
            ),
        ]
        selected = select_hits(
            hits,
            allow_t3=False,
            limit=5,
            policy=self.policy,
            question="NBA winners from 2010-2026 ranking",
        )
        urls = [item.url for item in selected]
        self.assertEqual(urls, ["https://en.wikipedia.org/wiki/List_of_NBA_champions"])
        self.assertTrue(all("Winnes" not in item.title for item in selected))

    def test_blocked_never_survives_broaden(self):
        hits = [_hit("https://www.quora.com/offside", title="Quora")]
        self.assertEqual(select_hits(hits, allow_t3=True, limit=5, policy=self.policy), [])

    def test_recency_drops_name_only_pages_that_omit_the_asked_fact(self):
        hits = [
            _hit(
                "https://www.cnbc.com/elon-musk-g20-ai",
                title="Elon Musk at G20: AI will increase the global economy",
                snippet="Elon Musk speaks at the G20 meeting about his predictions for AI.",
            ),
            _hit(
                "https://www.forbes.com/profile/elon-musk/",
                title="Elon Musk net worth",
                snippet="Elon Musk's net worth is $428 billion as of September 2026.",
            ),
        ]
        selected = select_hits(
            hits,
            allow_t3=False,
            limit=5,
            policy=self.policy,
            question="what is the net worth of elon musk latest",
            today_year=2026,
        )
        urls = [item.url for item in selected]
        self.assertEqual(urls, ["https://www.forbes.com/profile/elon-musk/"])

    def test_recency_prefers_current_year_over_stale_official_pages(self):
        hits = [
            _hit(
                "https://www.uefa.com/uefachampionsleague/news/newsid=2014",
                title="Return to Ajax | UEFA Champions League 2014/15",
                snippet="An archive interview from the 2014/15 season.",
            ),
            _hit(
                "https://www.uefa.com/uefachampionsleague/news/round-up-2023",
                title="Champions League round-up: score five | 2023/24",
                snippet="Opening-night winners in the 2023/24 Champions League.",
            ),
            _hit(
                "https://www.espn.com/soccer/report/2026-match",
                title="Match report 21 September 2026",
                snippet="The last match finished with a score of 2-1 on 21 September 2026.",
            ),
        ]
        selected = select_hits(
            hits,
            allow_t3=False,
            limit=5,
            policy=self.policy,
            question="what is the score of the last match",
            today_year=2026,
        )
        urls = [item.url for item in selected]
        self.assertEqual(urls[0], "https://www.espn.com/soccer/report/2026-match")
        self.assertTrue(all("2014" not in item.url for item in selected))
        self.assertTrue(all("2023" not in item.url for item in selected))

    def test_recency_with_only_stale_pages_returns_nothing(self):
        hits = [
            _hit(
                "https://www.uefa.com/uefachampionsleague/news/newsid=2018",
                title="Barcelona-Roma - UEFA Champions League - 2018",
                snippet="A 2018 Champions League match report.",
            ),
        ]
        selected = select_hits(
            hits,
            allow_t3=False,
            limit=5,
            policy=self.policy,
            question="what is the score of the last match",
            today_year=2026,
        )
        self.assertEqual(selected, [])

    def test_historical_questions_keep_older_dated_pages(self):
        hits = [
            _hit(
                "https://www.uefa.com/uefachampionsleague/history/2018",
                title="Barcelona-Roma - UEFA Champions League - 2018",
                snippet="Match report from the 2018 Champions League tie.",
            ),
        ]
        selected = select_hits(
            hits,
            allow_t3=False,
            limit=5,
            policy=self.policy,
            question="what was the score of the 2018 champions league tie",
            today_year=2026,
        )
        self.assertEqual(len(selected), 1)


if __name__ == "__main__":
    unittest.main()
