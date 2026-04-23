import arxiv
import json
from typing import List
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class Paper:
    arxiv_id: str
    title: str
    summary: str
    published: datetime
    pdf_url: str
    authors: List[str]


class ArxivFetcher:
    def __init__(self):
        self.client = arxiv.Client()

    def fetch(self, query: str, max_results: int) -> List[arxiv.Result]:
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
        )

        papers: List[Paper] = []
        for paper in self.client.results(search):
            papers.append(Paper(
                arxiv_id=paper.entry_id,
                title=paper.title,
                summary=paper.summary,
                published=paper.published,
                pdf_url=paper.pdf_url,
                authors=[author.name for author in paper.authors],
            ))

        return papers

    def save_to_json(self, papers: List[Paper], path: str):
        payload = []
        for paper in papers:
            item = asdict(paper)
            item["published"] = item["published"].isoformat()  
            payload.append(item)

        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=4)
    

if __name__ == "__main__":
    fetcher = ArxivFetcher()
    papers = fetcher.fetch("LLM architecture", 5)
    fetcher.save_to_json(papers, "/Users/iapanferov/Desktop/arxiv/parser/papers.json")