import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace

from src.ai.analyzer import ContentAnalyzer
from src.models import ContentItem
from src.processing.profiles import ProfileRegistry


class FakeClient:
    config = SimpleNamespace(analysis_batch_size=10, analysis_concurrency=2, throttle_sec=0)

    def __init__(self):
        self.calls = []

    async def complete(self, system, user, temperature=None, max_tokens=None):
        self.calls.append(user)
        if "### Item" in user:  # batch call: score item 0 only, omit item 1
            return json.dumps({"results": [{"index": 0, "score": 8, "reason": "r", "summary": "s", "tags": []}]})
        return json.dumps({"score": 3, "reason": "single", "summary": "s", "tags": []})


def _item(n):
    return ContentItem(
        id=f"rss:x:{n}", source_type="rss", title=f"T{n}", url=f"https://example.com/{n}",
        content="body", published_at=datetime.now(timezone.utc), profile="tech-news",
    )


def test_batch_scores_in_one_call_and_falls_back_for_omitted_items():
    client = FakeClient()
    analyzer = ContentAnalyzer(client, ProfileRegistry.load(Path("profiles").resolve(), "tech-news"))
    items = asyncio.run(analyzer.analyze_batch([_item(0), _item(1)]))

    assert [i.processing.analysis.score for i in items] == [8, 3]
    assert len(client.calls) == 2  # one batch call + one single-item fallback
