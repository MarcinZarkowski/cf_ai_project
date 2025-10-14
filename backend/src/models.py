from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, ARRAY, Text, Table
from sqlalchemy.orm import relationship, Session, selectinload
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector
import pgvector
import datetime
import html2text
from typing import Optional, List, Dict, Any

from .rag.embed import get_embedding, chunk_text  # these may still be async or sync — adapt accordingly

Base = declarative_base()

def clean_html(html: str) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    h.body_width = 0
    return h.handle(html or "").strip()

N_DIM = 256

ticker_article = Table(
    "ticker_article",
    Base.metadata,
    Column("ticker_id", Integer, ForeignKey("ticker.id"), primary_key=True),
    Column("article_id", Integer, ForeignKey("article.id"), primary_key=True),
)

class Ticker(Base):
    __tablename__ = "ticker"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, unique=True, nullable=False, index=True)

    last_updated = Column(DateTime(timezone=True), nullable=True)
    logo = Column(String, nullable=True)
    country = Column(String, nullable=True)
    company = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    exchange = Column(String, nullable=True)
    ipo = Column(String, nullable=True)
    company_url = Column(String, nullable=True)

    recommendation_trends = Column(ARRAY(JSON), nullable=True)
    earnings_surprises = Column(ARRAY(JSON), nullable=True)
    insider_sentiment = Column(ARRAY(JSON), nullable=True)

    last_updated_news = Column(DateTime(timezone=True), nullable=True)

    articles = relationship(
        "Article",
        secondary=ticker_article,
        back_populates="tickers",
        lazy="selectin"
    )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "last_updated": self.last_updated,
            "logo": self.logo,
            "country": self.country,
            "company": self.company,
            "industry": self.industry,
            "exchange": self.exchange,
            "ipo": self.ipo,
            "company_url": self.company_url,
            "recommendation_trends": self.recommendation_trends,
            "earnings_surprises": self.earnings_surprises,
            "insider_sentiment": self.insider_sentiment,
            "last_updated_news": self.last_updated_news,
            "articles": [
                {
                    "url": article.url,
                    "headline": article.headline,
                    "images": article.images,
                    "mentions": article.symbols,
                    "summary": article.summary
                }
                for article in self.articles
            ]
        }

def update_ticker(ticker_symbol: str, data: dict, obj: Optional[Ticker] = None) -> Ticker:
    if obj is None:
        obj = Ticker(ticker=ticker_symbol)

    profile = data.get("company_profile", {})
    obj.logo = profile.get("logo")
    obj.country = profile.get("country")
    obj.company = profile.get("name")
    obj.industry = profile.get("finnhubIndustry")
    obj.exchange = profile.get("exchange")
    obj.ipo = profile.get("ipo")
    obj.company_url = profile.get("weburl")

    obj.recommendation_trends = data.get("recommendation_trends")
    obj.earnings_surprises = data.get("earnings_surprises")
    obj.insider_sentiment = data.get("insider_sentiment", {}).get("data")

    return obj

def get_or_create_tickers(
    ticker_list: List[str], session: Session, existing_ticker: Optional[Ticker] = None
) -> Dict[str, Ticker]:
    """ Synchronous version: fetch or create Ticker rows. """
    # Fetch existing
    existing = session.query(Ticker).filter(Ticker.ticker.in_(ticker_list)).all()
    ticker_map: Dict[str, Ticker] = {t.ticker: t for t in existing}
    if existing_ticker:
        ticker_map[existing_ticker.ticker] = existing_ticker

    to_create = [t for t in ticker_list if t not in ticker_map]
    new_tickers = [Ticker(ticker=t) for t in to_create]
    session.add_all(new_tickers)
    session.flush()  # assign IDs for new ones
    for t in new_tickers:
        ticker_map[t.ticker] = t

    return ticker_map

class Article(Base):
    __tablename__ = "article"
    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(Integer, unique=True, nullable=False, index=True)
    updating_now = Column(Boolean, default=False, nullable=False)
    symbols = Column(ARRAY(String), nullable=True)

    author = Column(String, nullable=True)
    source = Column(String, nullable=True)
    url = Column(String, nullable=True)
    created = Column(String, nullable=True)

    headline = Column(String, nullable=True)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    images = Column(ARRAY(JSON), nullable=True)

    tickers = relationship(
        "Ticker",
        secondary=ticker_article,
        back_populates="articles",
        lazy="select"
    )

    embeddings = relationship(
        "Embedding",
        back_populates="article",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "external_id": self.external_id,
            "symbols": self.symbols,
            "author": self.author,
            "source": self.source,
            "url": self.url,
            "created": self.created,
            "headline": self.headline,
            "summary": self.summary,
            "content": self.content,
            "images": self.images,
        }

def create_article(data: dict) -> Article:
    article = Article(
        external_id=data.get("id"),
        symbols=data.get("symbols", []),
        author=data.get("author"),
        source=data.get("source"),
        url=data.get("url"),
        created=data.get("created_at"),
        headline=data.get("headline"),
        summary=data.get("summary"),
        content=clean_html(data.get("content", "")),
        images=data.get("images", [])
    )
    return article

def add_articles_batch(
    articles_data: List[dict], session: Session, ticker_obj: Ticker
) -> List[Article]:
    """ Synchronous batch addition of articles + embeddings. """
    all_symbols = set()
    for a in articles_data:
        all_symbols.update(a.get("symbols", []))
    ticker_map = get_or_create_tickers(list(all_symbols), session, existing_ticker=ticker_obj)

    articles_to_add: List[Article] = []
    for a_data in articles_data:
        symbols = a_data.pop("symbols", [])
        article = create_article(a_data)
        for sym in symbols:
            if sym in ticker_map:
                article.tickers.append(ticker_map[sym])
        session.add(article)
        session.flush()

        content = article.content or ""
        chunked = chunk_text(content)
        for i, chunk in enumerate(chunked):
            text_piece = chunk.get("text")
            if not text_piece:
                continue
            # Note: get_embedding might be async in your original; if so, wrap or adapt to sync
            embedding_vec = get_embedding(text_piece)
            if embedding_vec is None:
                continue
            embedding_obj = Embedding(
                embedding=embedding_vec,
                article_id=article.id,
                symbols=symbols,
                order=i,
                start_ind=chunk.get("start", 0),
                end_ind=chunk.get("end", len(text_piece)),
            )
            session.add(embedding_obj)
        articles_to_add.append(article)

    session.flush()
    return articles_to_add

class Embedding(Base):
    __tablename__ = "embedding"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbols = Column(ARRAY(String), nullable=False)
    order = Column(Integer, nullable=False)
    start_ind = Column(Integer, nullable=False)
    end_ind = Column(Integer, nullable=False)
    embedding = Column(Vector(N_DIM), nullable=False)

    article_id = Column(Integer, ForeignKey("article.id", ondelete="CASCADE"), nullable=False)
    article = relationship("Article", back_populates="embeddings", lazy="selectin")
