import finnhub
import os 
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import httpx
import asyncio
from dotenv import load_dotenv

load_dotenv()

FIN_KEY = os.getenv("FINN_HUB")
if not FIN_KEY:
    raise ValueError("FINN_HUB environment variable not set")

fin_client = finnhub.Client(api_key=FIN_KEY)

async def get_stock_data(ticker):
    """
    Asynchronously gathers a comprehensive set of stock data from Finnhub.
    """
    stock_data = {}
    try:
        # Get company profile
        stock_data['company_profile'] = await asyncio.to_thread(fin_client.company_profile2, symbol=ticker)
    
        # Get recommendation trends
        stock_data['recommendation_trends'] = await asyncio.to_thread(fin_client.recommendation_trends, ticker)
   
        # Get earnings surprises
        stock_data['earnings_surprises'] = await asyncio.to_thread(fin_client.company_earnings, ticker, limit=5)
  
        # Get insider sentiment
        now = datetime.now(timezone.utc)
        three_months_ago = now - timedelta(days=90)

        stock_data['insider_sentiment'] = await asyncio.to_thread(
            fin_client.stock_insider_sentiment,
            ticker,
            _from=three_months_ago.date().isoformat(),  # convert to date
            to=now.date().isoformat()
        )
    except Exception as e:
        print("Error in getting general stock data: ", e)

    return stock_data or {}

ALPACA_KEY = os.environ["ALPACA_KEY"]
ALPACA_SECRET = os.environ["ALPACA_SECRET"]

async def fetch_ticker_news(
    ticker: str,
    limit: int = 50, # max
    sort: str = "desc", # or 'asc'
    published_from: str = None,
    include_content: bool = True, 
    exclude_contentless: bool = True
) -> Dict[str, Any]:
    """
    Fetches ticker-specific news via Alpaca's News API.
    Returns parsed JSON with metadata and content.
    """
    url = "https://data.alpaca.markets/v1beta1/news"

    params = {
        "symbols": ticker,
        "limit": limit,
        "sort": sort,
        "include_content": include_content,
        "exclude_contentless": exclude_contentless
    }

    if published_from:
        params["start"] = published_from  

    headers = {
        "APCA-API-KEY-ID": ALPACA_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET,
        "Accept": "application/json"
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            response = response.json()
            return response.get("news", [])
    except Exception as e:
        print(e)
        return []

