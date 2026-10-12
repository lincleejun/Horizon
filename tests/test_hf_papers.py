from datetime import datetime, timezone

import asyncio

import httpx

from src.models import HFPapersConfig
from src.scrapers.hf_papers import HFPapersScraper


def _row(paper_id, listed_at, upvotes):
    return {
        "numComments": 2,
        "paper": {
            "id": paper_id,
            "title": f"Paper {paper_id}",
            "summary": "Abstract.",
            "upvotes": upvotes,
            "submittedOnDailyAt": listed_at,
            "publishedAt": "2026-01-01T00:00:00.000Z",
            "authors": [{"name": "A"}],
        },
    }


def test_filters_by_listing_date_and_upvotes_and_sorts():
    asyncio.run(_run())


async def _run():
    rows = [
        _row("1", "2026-10-09T10:00:00.000Z", 6),
        _row("2", "2026-10-09T10:00:00.000Z", 50),
        _row("3", "2026-10-09T10:00:00.000Z", 1),  # too few upvotes
        _row("4", "2026-10-01T10:00:00.000Z", 99),  # outside window
    ]
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=rows))
    async with httpx.AsyncClient(transport=transport) as client:
        scraper = HFPapersScraper(HFPapersConfig(enabled=True, min_upvotes=5, profile="papers"), client)
        items = await scraper.fetch(datetime(2026, 10, 9, tzinfo=timezone.utc))

    assert [item.metadata["arxiv_id"] for item in items] == ["2", "1"]
    assert str(items[0].url) == "https://huggingface.co/papers/2"
    assert items[0].profile == "papers"
