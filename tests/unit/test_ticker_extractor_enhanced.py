"""
Enhanced ticker extraction tests with blacklist and whitelist filtering.

Tests cover:
- Blacklist filtering (common English words)
- Whitelist validation (known tickers only)
- Stock context detection
- Edge cases and performance
"""

import pytest
from backend.utils.ticker_extractor import (
    extract_tickers,
    has_stock_context,
    BLACKLIST_WORDS,
    KNOWN_TICKERS
)


class TestBlacklistFiltering:
    """Test that common English words are filtered out"""
    
    def test_single_letter_blacklist(self):
        """Single letters I and A should be filtered"""
        assert extract_tickers('I HAVE A LOT OF MONEY') == []
    
    def test_common_articles_filtered(self):
        """Common articles (THE, FOR, AND) should be filtered"""
        result = extract_tickers('THE FOR AND OR BUT NOT')
        assert result == []
    
    def test_common_prepositions_filtered(self):
        """Prepositions (AT, BY, IN, ON, TO) should be filtered"""
        result = extract_tickers('AT BY IN ON TO UP')
        assert result == []
    
    def test_common_verbs_filtered(self):
        """Verbs (GET, MAKE, GO, COME) should be filtered"""
        result = extract_tickers('GET MAKE GO COME TAKE PUT')
        assert result == []
    
    def test_trading_jargon_filtered(self):
        """Trading terms not in whitelist should be filtered"""
        result = extract_tickers('BUY SELL LONG SHORT BULL BEAR HODL YOLO')
        assert result == []
    
    def test_financial_terms_filtered(self):
        """Currency codes (USD, EUR) and financial terms filtered"""
        result = extract_tickers('USD EUR GBP ETF IPO EPS PE')
        assert result == []
    
    def test_mixed_blacklist_and_valid(self):
        """Text with both blacklist words and valid tickers"""
        result = extract_tickers('BUY AAPL AND TSLA NOW')
        assert set(result) == {'AAPL', 'TSLA'}
    
    def test_blacklist_case_insensitive(self):
        """Blacklist filtering should be case-insensitive"""
        result = extract_tickers('the for and apple STOCK')
        assert extract_tickers('THE FOR AND APPLE STOCK') == result


class TestWhitelistValidation:
    """Test that only known tickers are accepted"""
    
    def test_valid_ticker_extraction(self):
        """Known tickers should be extracted"""
        result = extract_tickers('$AAPL $TSLA $GOOGL')
        assert set(result) == {'AAPL', 'TSLA', 'GOOGL'}
    
    def test_cashtag_format(self):
        """Cashtag format ($AAPL) should be recognized"""
        result = extract_tickers('I like $AAPL and $MSFT')
        assert set(result) == {'AAPL', 'MSFT'}
    
    def test_all_caps_format(self):
        """All caps format (AAPL) without $ should work"""
        result = extract_tickers('AAPL and MSFT are tech stocks')
        assert set(result) == {'AAPL', 'MSFT'}
    
    def test_unknown_ticker_rejected(self):
        """Unknown tickers should be rejected"""
        result = extract_tickers('$XYZZY $INVALIDTICKER $FAKE')
        assert result == []
    
    def test_mixed_known_and_unknown(self):
        """Mix of known and unknown tickers"""
        result = extract_tickers('$AAPL is better than $XYZZY')
        assert result == ['AAPL']
    
    def test_faang_tickers(self):
        """FAANG stocks should be recognized"""
        result = extract_tickers('$AAPL $MSFT $GOOGL $AMZN $META $NVDA')
        assert set(result) == {'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA'}
    
    def test_meme_stocks(self):
        """Meme stocks should be recognized"""
        result = extract_tickers('GME and AMC to the moon!')
        assert set(result) == {'GME', 'AMC'}
    
    def test_etf_tickers(self):
        """ETF tickers should be recognized"""
        result = extract_tickers('SPY QQQ IWM are great ETFs')
        assert set(result) == {'SPY', 'QQQ', 'IWM'}
    
    def test_sorted_output(self):
        """Output should be sorted alphabetically"""
        result = extract_tickers('$TSLA $AAPL $MSFT')
        assert result == ['AAPL', 'MSFT', 'TSLA']  # Sorted order
    
    def test_deduplication(self):
        """Duplicate tickers should be deduplicated"""
        result = extract_tickers('AAPL and $AAPL and AAPL')
        assert result == ['AAPL']


class TestStockContext:
    """Test has_stock_context function for contextual awareness"""
    
    def test_stock_keyword_present(self):
        """Should return True when stock keyword is near ticker"""
        assert has_stock_context('I like AAPL stock', 'AAPL') is True
    
    def test_buy_keyword(self):
        """Should detect 'buy' keyword"""
        assert has_stock_context('Buy AAPL tomorrow', 'AAPL') is True
    
    def test_sell_keyword(self):
        """Should detect 'sell' keyword"""
        assert has_stock_context('Sell AAPL at 130', 'AAPL') is True
    
    def test_price_keyword(self):
        """Should detect 'price' keyword"""
        assert has_stock_context('AAPL price target 150', 'AAPL') is True
    
    def test_dividend_keyword(self):
        """Should detect 'dividend' keyword"""
        assert has_stock_context('AAPL dividend yield 0.5%', 'AAPL') is True
    
    def test_no_stock_context(self):
        """Should return False when no stock keywords nearby"""
        assert has_stock_context('AAPL is a common acronym', 'AAPL') is False
    
    def test_ticker_not_found(self):
        """Should return False when ticker not in text"""
        assert has_stock_context('Buy MSFT stock', 'AAPL') is False
    
    def test_context_window(self):
        """Should respect context_window parameter"""
        text = 'AAPL' + ' ' * 100 + 'stock'
        # With small window, should not find stock keyword
        assert has_stock_context(text, 'AAPL', context_window=10) is False
        # With large window, should find it
        assert has_stock_context(text, 'AAPL', context_window=150) is True
    
    def test_bullish_context(self):
        """Should detect bullish keywords"""
        assert has_stock_context('Very bullish on AAPL', 'AAPL') is True
    
    def test_bearish_context(self):
        """Should detect bearish keywords"""
        assert has_stock_context('Getting bearish on AAPL', 'AAPL') is True
    
    def test_tradingview_emoji_context(self):
        """Should detect trading emoji context"""
        assert has_stock_context('AAPL 📈', 'AAPL') is True
        assert has_stock_context('AAPL 📉', 'AAPL') is True
    
    def test_shorthand_context(self):
        """Should detect DD (due diligence) and other trading shorthand"""
        assert has_stock_context('Doing DD on AAPL', 'AAPL') is True


class TestEdgeCases:
    """Test edge cases and special scenarios"""
    
    def test_empty_string(self):
        """Empty string should return empty list"""
        assert extract_tickers('') == []
    
    def test_only_whitespace(self):
        """Whitespace-only string should return empty list"""
        assert extract_tickers('   \n\t  ') == []
    
    def test_mixed_case_with_cashtag(self):
        """Mixed case should be normalized up"""
        result = extract_tickers('$aapl $TsLa $MsFt')
        assert set(result) == {'AAPL', 'TSLA', 'MSFT'}
    
    def test_ticker_at_start(self):
        """Ticker at start of string"""
        result = extract_tickers('AAPL hit new high')
        assert result == ['AAPL']
    
    def test_ticker_at_end(self):
        """Ticker at end of string"""
        result = extract_tickers('I bought AAPL')
        assert result == ['AAPL']
    
    def test_multiple_consecutive_tickers(self):
        """Multiple tickers without separator"""
        result = extract_tickers('$AAPL$MSFT$GOOGL')
        assert set(result) == {'AAPL', 'MSFT', 'GOOGL'}
    
    def test_ticker_with_numbers(self):
        """Ticker-like strings with numbers should fail"""
        result = extract_tickers('$AAP2 $TSL4 $GOOG9')
        assert result == []  # Not in whitelist
    
    def test_very_long_all_caps_word(self):
        """Very long all-caps word (>5 letters) should not match pattern"""
        result = extract_tickers('INCREDIBLE WONDERFUL SPECTACULAR')
        assert result == []
    
    def test_two_letter_word_not_in_whitelist(self):
        """2-letter words not in whitelist should be filtered"""
        result = extract_tickers('IT IS AT UP OF')
        assert result == []
    
    def test_two_letter_ticker_in_whitelist(self):
        """2-letter tickers in whitelist like GME->NO, BB->YES should work"""
        result = extract_tickers('BB is a great stock')
        assert result == ['BB']
    
    def test_special_characters_ignored(self):
        """Special characters should be ignored"""
        result = extract_tickers('$AAPL! @MSFT# $GOOGL%')
        assert set(result) == {'AAPL', 'MSFT', 'GOOGL'}
    
    def test_punctuation_handling(self):
        """Punctuation should not break extraction"""
        result = extract_tickers('AAPL, MSFT, GOOGL.')
        assert set(result) == {'AAPL', 'MSFT', 'GOOGL'}


class TestPerformance:
    """Performance and efficiency tests"""
    
    def test_extraction_speed_long_text(self):
        """Extraction should be fast even on long text"""
        long_text = ' '.join(['word'] * 10000 + ['$AAPL', '$MSFT'])
        result = extract_tickers(long_text)
        assert set(result) == {'AAPL', 'MSFT'}
    
    def test_many_tickers(self):
        """Should handle many tickers efficiently"""
        # Use a smaller, known subset to avoid ticker count variations
        test_tickers = {'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'NFLX'}
        tickers = ' '.join(['$' + t for t in test_tickers])
        result = extract_tickers(tickers)
        assert len(result) == len(test_tickers)
        assert set(result) == test_tickers
    
    def test_repeated_tickers(self):
        """Many repetitions of same ticker"""
        text = '$AAPL ' * 1000
        result = extract_tickers(text)
        assert result == ['AAPL']


class TestBlacklistContent:
    """Verify blacklist contains expected words"""
    
    def test_blacklist_not_empty(self):
        """Blacklist should not be empty"""
        assert len(BLACKLIST_WORDS) > 0
    
    def test_common_words_in_blacklist(self):
        """Common words should be in blacklist"""
        assert 'THE' in BLACKLIST_WORDS
        assert 'AND' in BLACKLIST_WORDS
        assert 'FOR' in BLACKLIST_WORDS
        assert 'I' in BLACKLIST_WORDS
    
    def test_trading_slang_in_blacklist(self):
        """Trading slang should be in blacklist"""
        assert 'HODL' in BLACKLIST_WORDS
        assert 'YOLO' in BLACKLIST_WORDS
        assert 'MOON' in BLACKLIST_WORDS


class TestWhitelistContent:
    """Verify whitelist contains expected tickers"""
    
    def test_whitelist_not_empty(self):
        """Whitelist should not be empty"""
        assert len(KNOWN_TICKERS) > 0
    
    def test_major_tickers_in_whitelist(self):
        """Major tickers should be in whitelist"""
        major = {'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NVDA'}
        assert major.issubset(KNOWN_TICKERS)
    
    def test_etf_in_whitelist(self):
        """Popular ETFs should be in whitelist"""
        etfs = {'SPY', 'QQQ', 'IWM', 'VTI', 'VOO'}
        assert etfs.issubset(KNOWN_TICKERS)
    
    def test_meme_stocks_in_whitelist(self):
        """Meme stocks should be in whitelist"""
        meme = {'GME', 'AMC'}
        assert meme.issubset(KNOWN_TICKERS)


class TestRegressions:
    """Regression tests for known issues"""
    
    def test_dd_not_extracted(self):
        """DD (due diligence) should not be extracted as ticker"""
        result = extract_tickers('Doing DD on $AAPL')
        assert result == ['AAPL']
    
    def test_call_not_extracted(self):
        """CALL (options/preposition) should not extracted separately"""
        result = extract_tickers('I got a call about AAPL')
        assert result == ['AAPL']
    
    def test_put_not_extracted(self):
        """PUT (options/verb) should not be extracted separately"""
        result = extract_tickers('Put your money in AAPL')
        assert result == ['AAPL']
    
    def test_all_reddit_walstreetbets_examples(self):
        """Real r/wallstreetbets style text"""
        text = """
        $AAPL to the moon! 🚀
        $GME hold the line diamond hands
        Bullish on $TSLA
        Buy the dip $MSFT
        FDA approval for $PFE coming soon
        """
        result = extract_tickers(text)
        # Should extract all known tickers, not meme/slang
        assert 'AAPL' in result
        assert 'GME' in result
        assert 'TSLA' in result
        assert 'MSFT' in result
        assert 'PFE' in result
        # Common slang should NOT appear
        assert all(w not in result for w in ['MOON', 'HOLD', 'DIP'])
