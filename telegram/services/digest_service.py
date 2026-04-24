import asyncio
from typing import List
from html import escape

from parser.fetcher import ArxivFetcher


class DigestService:
    def __init__(self, fetcher: ArxivFetcher):
        self.fetcher = fetcher


    def build_query(self, topic: str) -> str:
        if not topic:
            raise ValueError
        return f'(ti:"{topic}" OR abs:"{topic}")'
    

    async def fetch_for_topic(self, topic: str, limit: int = 5):
        query = self.build_query(topic)
        if not query:
            raise ValueError
        return await asyncio.to_thread(self.fetcher.fetch, query, limit)


    def _to_hashtag(self, topic: str) -> str:
        normalized = topic.strip().lower().replace(" ", "_").replace("-", "_")
        normalized = "".join(ch for ch in normalized if ch.isalnum() or ch == "_")
        return f"#{normalized}"

    
    def _format_paper(self, topic: str, paper) -> str:
        title = escape(paper.title)
        summary = escape(paper.summary)
        link = escape(paper.pdf_url)
        hashtag = escape(self._to_hashtag(topic))

        return (
            f"<b>{title}</b>\n"
            f"<blockquote>{summary}</blockquote>\n"
            f"Ссылка: {link}\n"
            f"{hashtag}"
        )


    def build_messages_per_paper(self, topic: str, papers) -> List[str]:
        messages: List[str] = []
        for paper in papers:
            messages.append(self._format_paper(topic, paper))
        return messages


    async def build_digest_messages(self, topics: List[str], per_topic_limit: int = 5) -> List[str]:
        all_messages: List[str] = []
        for topic in topics:
            papers = await self.fetch_for_topic(topic, limit=per_topic_limit)
            topic_messages = self.build_messages_per_paper(topic, papers)
            all_messages.extend(topic_messages)
        return all_messages
    



      
