from ..models import Embedding
from sqlalchemy import select
import numpy as np
from .embed import get_embedding

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors, normalized 0..1."""
    a_norm = a / np.linalg.norm(a)
    b_norm = b / np.linalg.norm(b)
    return float(np.dot(a_norm, b_norm))  # 1 = identical, 0 = orthogonal

def get_similar(text: str, db, max_results: int = 20, threshold: float = 0.2):
    """
    Return embeddings from the database similar to the given text.
    Threshold: 0..1, minimum similarity (0.2 means >= 80% similar).
    """
    # Synchronous version of embedding
    vector = get_embedding(text)  # should return a list or numpy array

    # Step 1: order by cosine distance in SQL for index use
    stmt = (
        select(Embedding)
        .order_by(Embedding.embedding.cosine_distance(vector))  # pgvector index
        .limit(max_results)
    )

    candidates = db.scalars(stmt).all()  # synchronous fetch

    results = []
    min_similarity = 1.0 - threshold  # convert distance threshold to similarity

    for r in candidates:
        sim = cosine_similarity(np.array(r.embedding), np.array(vector))
        print(r.article.content[r.start_ind:r.end_ind], sim)
        if sim < min_similarity:
            break  # stop iterating, further items will be less similar
        results.append(r)

    return results



async def get_similare_articles(text:str, db, max_results:int = 20, threshold: float = .2):
    snippets =  get_similar(text, db, max_results, threshold)
    article_ids = {s.article_id : s for s in snippets}
    res = ""

    for _, e in article_ids.items():
        res += f"Headline: {e.article.headline},\n URL: {e.article.url},\n Date: {e.article.created}\n Text: {e.article.content}\n"

    return res

async def get_similar_snippets(text:str, db, max_results:int = 20, threshold: float = .2):
    snippets =  get_similar(text, db, max_results, threshold)

    res = ""

    for e in snippets:
        res += f"Headline: {e.article.headline},\n URL: {e.article.url},\n Date: {e.article.created}\nSnippet: {e.article.content[e.start_ind:e.end_ind]}\n"

    return res
