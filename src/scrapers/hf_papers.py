"""Hugging Face Daily Papers scraper."""

import logging
from datetime import datetime, timezone
from typing import List

import httpx

from ..models import ContentItem, HFPapersConfig, SourceType
from .base import BaseScraper

logger = logging.getLogger(__name__)

API_URL = "https://huggingface.co/api/daily_papers"


class HFPapersScraper(BaseScraper):
    """Fetch community-curated papers from the Hugging Face Daily Papers API."""

    def __init__(self, config: HFPapersConfig, http_client: httpx.AsyncClient):
        super().__init__({}, http_client)
        self.cfg = config

    async def fetch(self, since: datetime) -> List[ContentItem]:
        response = await self.client.get(API_URL, params={"limit": 100})
        response.raise_for_status()

        today = datetime.now(timezone.utc).date()
        items = []
        for row in response.json():
            paper = row.get("paper") or {}
            paper_id = paper.get("id")
            # Papers are often submitted days after their arXiv date, so the
            # window applies to the daily-listing date, not publishedAt. Listings
            # are stamped 00:00 UTC, so compare whole days and skip today's
            # still-open listing: its upvotes are immature and it is picked up
            # by tomorrow's run.
            listed_at = paper.get("submittedOnDailyAt")
            if not paper_id or not listed_at:
                continue
            published_at = datetime.fromisoformat(listed_at.replace("Z", "+00:00"))
            upvotes = paper.get("upvotes") or 0
            if not since.date() <= published_at.date() < today:
                continue
            if upvotes < self.cfg.min_upvotes:
                continue

            authors = [a.get("name") for a in paper.get("authors") or [] if a.get("name")]
            lines = [paper.get("summary") or row.get("summary") or ""]
            if paper.get("githubRepo"):
                lines.append(f"Code: {paper['githubRepo']} ({paper.get('githubStars') or 0} stars)")
            if paper.get("projectPage"):
                lines.append(f"Project page: {paper['projectPage']}")
            lines.append(f"arXiv: https://arxiv.org/abs/{paper_id}")

            items.append(
                ContentItem(
                    id=self._generate_id(SourceType.HF_PAPERS.value, "paper", paper_id),
                    source_type=SourceType.HF_PAPERS,
                    title=paper.get("title") or row.get("title") or paper_id,
                    url=f"https://huggingface.co/papers/{paper_id}",
                    content="\n\n".join(line for line in lines if line),
                    author=", ".join(authors[:5]) or None,
                    published_at=published_at,
                    profile=self.cfg.profile,
                    metadata={
                        "upvotes": upvotes,
                        "comments": row.get("numComments") or 0,
                        "arxiv_id": paper_id,
                        "category": self.cfg.category,
                    },
                )
            )

        items.sort(key=lambda item: item.metadata["upvotes"], reverse=True)
        return items[: self.cfg.max_items]
