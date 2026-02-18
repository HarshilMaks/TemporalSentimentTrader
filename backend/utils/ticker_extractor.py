import re

# BLACKLIST: Common English words that often appear in ALL CAPS but are NOT tickers
BLACKLIST_WORDS = {
    # Single letters
    'I', 'A',
    
    # Common articles & prepositions
    'THE', 'FOR', 'AND', 'OR', 'BUT', 'NOT', 'IS', 'ARE', 'WAS', 'WERE', 'BE', 'BEING',
    'HAVE', 'HAS', 'HAD', 'DO', 'DOES', 'DID', 'WILL', 'WOULD', 'COULD', 'SHOULD',
    'MAY', 'MIGHT', 'MUST', 'CAN', 'AT', 'BY', 'IN', 'ON', 'TO', 'UP', 'OUT', 'OF',
    'OVER', 'UNDER', 'WITH', 'FROM', 'AS', 'ABOUT', 'INTO', 'THROUGH', 'DURING',
    
    # Common verbs
    'GET', 'MAKE', 'GO', 'COME', 'TAKE', 'PUT', 'SET', 'KEEP', 'HOLD', 'FIND',
    'GIVE', 'TELL', 'WORK', 'CALL', 'NEED', 'WANT', 'LOOK', 'SEEM', 'FEEL', 'TRY',
    'SELL', 'BUY', 'MARKET', 'STOCK',
    
    # Common adjectives & adverbs
    'GOOD', 'BAD', 'BEST', 'WORST', 'NEW', 'OLD', 'BIG', 'SMALL', 'HIGH', 'LOW',
    'LONG', 'SHORT', 'FAST', 'SLOW', 'EASY', 'HARD', 'FIRST', 'LAST', 'OTHER',
    'SAME', 'DIFFERENT', 'ONLY', 'VERY', 'MORE', 'MOST', 'LESS', 'LEAST', 'ALL', 'SOME',
    
    # Common nouns
    'TIME', 'YEAR', 'DAY', 'WEEK', 'MONTH', 'HOUR', 'MINUTE', 'SECOND', 'MOMENT',
    'PLACE', 'WAY', 'THING', 'PEOPLE', 'MAN', 'WOMAN', 'CHILD', 'PERSON', 'LIFE',
    'MONEY', 'PRICE', 'COST', 'VALUE', 'CASH', 'GAIN', 'LOSS', 'PROFIT', 'RISK',
    'MARKET', 'TRADE', 'DEAL', 'BUSINESS', 'COMPANY', 'FIRM', 'BANK', 'FUND',
    'RATE', 'RETURN', 'YIELD', 'GROWTH', 'TREND', 'DATA', 'INFO', 'NEWS',
    
    # Trading/Financial jargon that's not a ticker
    'BUY', 'SELL', 'LONG', 'SHORT', 'BULL', 'BEAR', 'CALL', 'PUT', 'MOON', 'HOLD',
    'HODL', 'YOLO', 'LOL', 'TO', 'THE', 'A', 'AN', 'AND', 'OR', 'IS', 'IT',
    'THIS', 'THAT', 'THESE', 'THOSE', 'WHAT', 'WHICH', 'WHERE', 'WHEN', 'WHY', 'HOW',
    
    # Common financial terms that could be confused as tickers
    'USD', 'EUR', 'GBP', 'JPY', 'CHF', 'AUD', 'CAD', 'NZD', 'INR', 'CNY',
    'ETF', 'IPO', 'EPS', 'PE', 'ROE', 'ROI', 'IRR', 'ACB',
    
    # Internet slang & emoji replacements
    'MOON', 'PUMP', 'DUMP', 'DIP', 'RIP', 'HODL', 'DIAMOND', 'HANDS',
    'ROCKET', 'FIRE', 'TO', 'THE', 'DO', 'YOUR', 'OWN', 'DD', 'YOLO', 'NOW',
}

# WHITELIST: Comprehensive list of popular tickers across all categories
KNOWN_TICKERS = {
    # FAANG + Tech Giants
    'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'META', 'NVDA', 'AMD', 'INTC', 'TSLA',
    'NFLX', 'ADBE', 'CRM', 'ORCL', 'CSCO', 'AVGO', 'QCOM', 'TXN', 'MU', 'AMAT',
    'LRCX', 'KLAC', 'SNPS', 'CDNS', 'MCHP', 'MRVL', 'ADI', 'NXPI', 'ASML',
    
    # Meme Stocks
    'GME', 'AMC', 'BB', 'BBBY', 'NOK', 'PLTR', 'WISH', 'CLOV', 'SOFI', 'HOOD',
    'COIN', 'DKNG', 'SPCE', 'OPEN', 'FUBO', 'SKLZ', 'ROOT', 'GOEV',
    
    # Major ETFs
    'SPY', 'QQQ', 'IWM', 'DIA', 'VOO', 'VTI', 'ARKK', 'ARKG', 'ARKF', 'ARKW',
    'XLF', 'XLE', 'XLK', 'XLV', 'XLI', 'XLP', 'XLY', 'XLB', 'XLU', 'XLRE',
    'SMH', 'SOXX', 'VGT', 'GLD', 'SLV', 'USO', 'TLT', 'HYG', 'SQQQ', 'TQQQ',
    
    # Finance & Banking
    'JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'BLK', 'SCHW', 'AXP', 'USB',
    'PNC', 'TFC', 'COF', 'BK', 'STT', 'V', 'MA', 'PYPL', 'SQ', 'FIS',
    
    # EV & Auto
    'F', 'GM', 'TM', 'HMC', 'RIVN', 'LCID', 'NIO', 'XPEV', 'LI', 'PLUG',
    
    # Energy & Oil
    'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'PXD', 'OXY', 'HAL', 'MPC', 'PSX',
    
    # Healthcare & Pharma
    'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'DHR', 'MRK', 'LLY', 'BMY',
    'AMGN', 'GILD', 'CVS', 'CI', 'ISRG', 'MDT', 'SYK', 'BSX', 'ZTS', 'REGN',
    'MRNA', 'BNTX', 'VRTX', 'BIIB', 'ILMN',
    
    # Retail & Consumer
    'WMT', 'COST', 'TGT', 'HD', 'LOW', 'NKE', 'SBUX', 'MCD', 'CMG', 'DPZ',
    'YUM', 'BKNG', 'MAR', 'HLT', 'DIS', 'CMCSA', 'T', 'VZ', 'TMUS',
    
    # Consumer Goods
    'PG', 'KO', 'PEP', 'PM', 'MO', 'CL', 'EL', 'MDLZ', 'MNST', 'KHC',
    'GIS', 'K', 'HSY', 'CLX', 'CHD',
    
    # Industrial & Aerospace
    'BA', 'CAT', 'DE', 'GE', 'HON', 'UPS', 'FDX', 'RTX', 'LMT', 'NOC',
    'GD', 'LHX', 'TXT', 'ETN', 'EMR', 'ROK', 'PH', 'ITW',
    
    # Chinese Stocks
    'BABA', 'JD', 'PDD', 'BIDU', 'TME', 'BILI', 'IQ', 'NTES', 'WB', 'DIDI',
    
    # SPACs & Recent IPOs
    'RBLX', 'ABNB', 'DASH', 'SNOW', 'PLTR', 'U', 'CPNG', 'GRAB', 'RIVN',
    
    # Semiconductors
    'TSM', 'AVGO', 'QCOM', 'TXN', 'INTC', 'MU', 'AMAT', 'LRCX', 'KLAC',
    
    # Communication & Social
    'SNAP', 'PINS', 'TWTR', 'SPOT', 'MTCH', 'ZM', 'DOCU', 'TEAM', 'WDAY',
    
    # Cloud & Software
    'CRM', 'ADBE', 'NOW', 'PANW', 'CRWD', 'ZS', 'DDOG', 'NET', 'OKTA', 'SPLK',
    'TWLO', 'SNOW', 'MRVL', 'FTNT', 'ABNB', 'UBER', 'LYFT',
    
    # Real Estate
    'AMT', 'PLD', 'CCI', 'EQIX', 'PSA', 'SPG', 'O', 'WELL', 'DLR', 'AVB',
    
    # Crypto-Related
    'MSTR', 'COIN', 'SQ', 'RIOT', 'MARA', 'CLSK', 'HUT', 'BITF',
    
    # Leveraged ETFs
    'UPRO', 'SPXL', 'TQQQ', 'SQQQ', 'SPXS', 'UDOW', 'SDOW', 'TNA', 'TZA',
    'UVXY', 'VXX', 'VIXY',
}


def extract_tickers(text: str) -> list[str]:
    """
    Extract stock tickers from text using regex patterns and whitelisting.
    
    Handles:
    - Cashtags: $AAPL
    - All caps words: TSLA (2-5 letters)
    
    Filters:
    - BLACKLIST: Excludes common English words (THE, FOR, AND, etc.)
    - WHITELIST: Only returns known tickers from KNOWN_TICKERS set
    - De-duplicates results
    - Case-insensitive matching
    
    Example:
    >>> extract_tickers('$AAPL and $TSLA are great stocks')
    ['AAPL', 'TSLA']
    
    >>> extract_tickers('THIS IS A TEST FOR BAD EXTRACTION')
    []  # All blocked by blacklist
    
    >> extract_tickers('Buy $GOOG at the market tomorrow')
    ['GOOG']  # THE and MARKET filtered by blacklist
    """
    # Pattern 1: Cashtags like $AAPL
    # Pattern 2: All caps words (2-5 letters) not preceded/followed by letters
    pattern = r'\$([A-Z]{1,5})\b|(?<!\w)([A-Z]{2,5})(?!\w)'
    
    matches = re.findall(pattern, text.upper())
    
    tickers = set()
    for match in matches:
        ticker = match[0] or match[1]  # match[0] for $AAPL, match[1] for AAPL
        
        # Reject if in blacklist (common English words)
        if ticker in BLACKLIST_WORDS:
            continue
        
        # Accept only if in whitelist (known tickers)
        if ticker in KNOWN_TICKERS:
            tickers.add(ticker)
    
    return sorted(list(tickers))  # Return sorted for consistency


def has_stock_context(text: str, ticker: str, context_window: int = 50) -> bool:
    """
    Check if a ticker appears in stock-related context.
    
    Looks for stock keywords (buy, sell, trade, price, earnings, etc.) 
    within context_window characters of the ticker.
    
    Args:
        text: Full text to search
        ticker: Ticker symbol to check context for
        context_window: Number of characters to look around ticker (default: 50)
    
    Returns:
        True if ticker has stock-related context, False otherwise
    
    Example:
    >>> has_stock_context('I love AAPL stock', 'AAPL')
    True
    
    >>> has_stock_context('AAPL is a common acronym', 'AAPL')
    False
    """
    # Stock-related keywords that should appear near ticker
    stock_keywords = {
        'stock', 'buy', 'sell', 'trade', 'price', 'earnings', 'dividend',
        'shares', 'share', 'trading', 'bullish', 'bearish', 'call', 'put',
        'option', 'options', 'short', 'long', 'position', 'upside', 'downside',
        '📈', '📉', '$', 'ticker', 'symbol', 'company', 'corporation', 'inc',
        'corp', 'ltd', 'financial', 'investor', 'investment', 'profit', 'earnings',
        'revenue', 'margin', 'pe', 'ratio', 'analysis', 'forecast', 'pump', 'dump',
        'moon', 'diamond', 'hands', 'rocket', 'ipo', 'etf', 'portfolio', 'dd'
    }
    
    # Find ticker position in text
    ticker_upper = ticker.upper()
    text_upper = text.upper()
    
    try:
        ticker_pos = text_upper.find(ticker_upper)
        if ticker_pos == -1:
            return False
        
        # Get context around ticker
        start = max(0, ticker_pos - context_window)
        end = min(len(text), ticker_pos + len(ticker_upper) + context_window)
        context = text_upper[start:end]
        
        # Check if any stock keyword appears in context
        for keyword in stock_keywords:
            if keyword.upper() in context:
                return True
        
        return False
    except Exception:
        return False
