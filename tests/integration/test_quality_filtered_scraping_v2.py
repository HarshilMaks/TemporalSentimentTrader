"""Integration tests for quality-filtered Reddit scraping pipeline.

Tests verify:
1. Quality scoring integration
2. Skip reason tracking
3. Configurable min_quality threshold
4. Stats comprehensiveness
5. Database persistence with quality fields
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from backend.services.reddit_service import RedditService
from backend.services.quality_scorer import QualityScorer


class MockRedditScraper:
    """Mock Reddit scraper for testing."""
    
    def scrape_posts(self, subreddit, limit, post_type, time_filter):
        """Return mock Reddit posts."""
        return [
            {
                'post_id': f'{subreddit}_high_quality_1',
                'subreddit': subreddit,
                'title': 'AAPL stock to moon 🚀 earnings incoming',
                'body': 'Just bought 1000 shares of $AAPL. This is going to pump hard.',
                'author': 'test_user_1',
                'score': 500,
                'num_comments': 150,
                'upvote_ratio': 0.95,
                'is_self': True,
                'link_flair_text': 'Discussion',
                'created_at': datetime.now(timezone.utc),
                'url': 'https://reddit.com/r/test/post1'
            },
            {
                'post_id': f'{subreddit}_low_quality_2',
                'subreddit': subreddit,
                'title': 'wtf',
                'body': '',  # Empty body = low quality
                'author': 'test_user_2',
                'score': 2,
                'num_comments': 0,
                'upvote_ratio': 0.5,
                'is_self': True,
                'link_flair_text': None,
                'created_at': datetime.now(timezone.utc),
                'url': 'https://reddit.com/r/test/post2'
            },
            {
                'post_id': f'{subreddit}_no_ticker_3',
                'subreddit': subreddit,
                'title': 'General market discussion',
                'body': 'The markets are doing well today.',
                'author': 'test_user_3',
                'score': 100,
                'num_comments': 50,
                'upvote_ratio': 0.85,
                'is_self': True,
                'link_flair_text': None,
                'created_at': datetime.now(timezone.utc),
                'url': 'https://reddit.com/r/test/post3'
            },
            {
                'post_id': f'{subreddit}_good_quality_4',
                'subreddit': subreddit,
                'title': '$TSLA analysis for tomorrow',
                'body': 'Technical analysis showing bullish breakout on TSLA. Price target 250.',
                'author': 'test_user_4',
                'score': 350,
                'num_comments': 120,
                'upvote_ratio': 0.92,
                'is_self': True,
                'link_flair_text': 'DD',
                'created_at': datetime.now(timezone.utc),
                'url': 'https://reddit.com/r/test/post4'
            },
            {
                'post_id': f'{subreddit}_high_quality_5',
                'subreddit': subreddit,
                'title': 'MSFT earnings beat expectations',
                'body': 'Strong earnings report. Bought MSFT calls for next quarter.',
                'author': 'test_user_5',
                'score': 450,
                'num_comments': 180,
                'upvote_ratio': 0.96,
                'is_self': True,
                'link_flair_text': 'Discussion',
                'created_at': datetime.now(timezone.utc),
                'url': 'https://reddit.com/r/test/post5'
            },
        ]


class TestQualityFilteredScraping:
    """Test quality-filtered Reddit scraping integration."""
    
    @pytest.mark.asyncio
    async def test_scrape_with_quality_filtering(self):
        """Test that high-quality posts are saved and low-quality posts are skipped."""
        service = RedditService(scraper=MockRedditScraper())
        
        # Mock the database session
        mock_db = AsyncMock()
        mock_db.add = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.execute = AsyncMock()
        
        stats = await service.scrape_and_save(
            mock_db, subreddits=['wallstreetbets'], limit=5, min_quality=50
        )
        
        # With min_quality=50: 3 high-quality posts saved, 2 low-quality posts skipped
        assert stats['saved'] == 3
        assert stats['skipped'] == 2
        assert stats['total_fetched'] == 5
        
        # Verify one post was skipped due to low quality
        assert stats['skip_reasons']['low_quality'] == 1
        # Verify one post was skipped due to no tickers
        assert stats['skip_reasons']['no_tickers'] == 1
    
    @pytest.mark.asyncio
    async def test_skip_reasons_tracking(self):
        """Test that skip reasons are properly tracked."""
        service = RedditService(scraper=MockRedditScraper())
        
        mock_db = AsyncMock()
        mock_db.add = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.execute = AsyncMock()
        
        stats = await service.scrape_and_save(
            mock_db, subreddits=['wallstreetbets'], limit=5
        )
        
        # Verify skip reasons structure
        assert 'skip_reasons' in stats
        assert 'no_tickers' in stats['skip_reasons']
        assert 'duplicate' in stats['skip_reasons']
        assert 'low_quality' in stats['skip_reasons']
        assert 'other' in stats['skip_reasons']
        
        # Total skips should equal sum of skip reasons
        total_skip_reasons = sum(stats['skip_reasons'].values())
        assert total_skip_reasons == stats['skipped']
    
    @pytest.mark.asyncio
    async def test_configurable_min_quality_threshold(self):
        """Test that min_quality threshold is configurable."""
        # Scrape with strict threshold (70)
        service_strict = RedditService(scraper=MockRedditScraper(), min_quality=70)
        mock_db = AsyncMock()
        mock_db.add = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.execute = AsyncMock()
        
        stats_strict = await service_strict.scrape_and_save(
            mock_db, subreddits=['wallstreetbets'], limit=5
        )
        
        # Scrape with lenient threshold (30)
        service_lenient = RedditService(scraper=MockRedditScraper(), min_quality=30)
        mock_db2 = AsyncMock()
        mock_db2.add = AsyncMock()
        mock_db2.flush = AsyncMock()
        mock_db2.execute = AsyncMock()
        
        stats_lenient = await service_lenient.scrape_and_save(
            mock_db2, subreddits=['wallstreetbets'], limit=5
        )
        
        # Lenient should save more posts than strict
        assert stats_lenient['saved'] > stats_strict['saved']
        assert stats_strict['quality_threshold'] == 70
        assert stats_lenient['quality_threshold'] == 30
    
    @pytest.mark.asyncio
    async def test_quality_fields_populated(self):
        """Test that quality fields are properly calculated."""
        service = RedditService(scraper=MockRedditScraper())
        
        mock_db = AsyncMock()
        saved_posts = []
        
        # Capture added posts
        async def capture_add(post):
            saved_posts.append(post)
        
        mock_db.add = capture_add
        mock_db.flush = AsyncMock()
        mock_db.execute = AsyncMock()
        
        await service.scrape_and_save(
            mock_db, subreddits=['wallstreetbets'], limit=5, min_quality=50
        )
        
        # Verify saved posts have quality fields
        assert len(saved_posts) > 0
        for post in saved_posts:
            assert hasattr(post, 'quality_score')
            assert post.quality_score is not None
            assert 0 <= post.quality_score <= 100
            assert post.quality_tier in ['poor', 'fair', 'good', 'excellent']
            assert isinstance(post.is_quality, bool)
    
    @pytest.mark.asyncio
    async def test_acceptance_rate_calculation(self):
        """Test that acceptance rate is calculated correctly."""
        service = RedditService(scraper=MockRedditScraper())
        
        mock_db = AsyncMock()
        mock_db.add = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.execute = AsyncMock()
        
        stats = await service.scrape_and_save(
            mock_db, subreddits=['wallstreetbets'], limit=5
        )
        
        # Verify acceptance_rate is present and correct
        assert 'acceptance_rate' in stats
        expected_rate = (stats['saved'] / stats['total_fetched']) * 100
        assert abs(stats['acceptance_rate'] - expected_rate) < 0.01
    
    @pytest.mark.asyncio
    async def test_per_subreddit_stats(self):
        """Test that per-subreddit statistics are properly tracked."""
        service = RedditService(scraper=MockRedditScraper())
        
        mock_db = AsyncMock()
        mock_db.add = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.execute = AsyncMock()
        
        stats = await service.scrape_and_save(
            mock_db, subreddits=['wallstreetbets'], limit=5
        )
        
        # Verify per-subreddit breakdown
        assert 'by_subreddit' in stats
        assert 'wallstreetbets' in stats['by_subreddit']
        
        sub_stats = stats['by_subreddit']['wallstreetbets']
        assert 'saved' in sub_stats
        assert 'skipped' in sub_stats
        assert 'failed' in sub_stats
        assert 'fetched' in sub_stats
        assert 'skip_reasons' in sub_stats
        
        # Verify aggregation matches
        assert sub_stats['saved'] == stats['saved']
        assert sub_stats['skipped'] == stats['skipped']
    
    @pytest.mark.asyncio
    async def test_duplicate_post_detection(self):
        """Test that duplicate posts are properly detected and skipped."""
        service = RedditService(scraper=MockRedditScraper())
        
        mock_db = AsyncMock()
        saved_post_ids = set()
        
        async def capture_add(post):
            saved_post_ids.add(post.post_id)
        
        mock_db.add = capture_add
        mock_db.flush = AsyncMock()
        mock_db.execute = AsyncMock()
        
        # First scrape
        stats1 = await service.scrape_and_save(
            mock_db, subreddits=['wallstreetbets'], limit=5, min_quality=0  # Accept all
        )
        
        first_saved = len(saved_post_ids)
        
        # Second scrape with same posts
        stats2 = await service.scrape_and_save(
            mock_db, subreddits=['wallstreetbets'], limit=5, min_quality=0
        )
        
        # All posts in second scrape should be duplicates
        assert stats2['skipped'] == stats2['total_fetched']
        assert stats2['skip_reasons']['duplicate'] == stats2['skipped']
        
        # No new posts added in second scrape
        assert len(saved_post_ids) == first_saved
    
    @pytest.mark.asyncio
    async def test_comprehensive_metrics_returned(self):
        """Test that all expected metrics are present in returned dict."""
        service = RedditService(scraper=MockRedditScraper())
        
        mock_db = AsyncMock()
        mock_db.add = AsyncMock()
        mock_db.flush = AsyncMock()
        mock_db.execute = AsyncMock()
        
        stats = await service.scrape_and_save(
            mock_db, subreddits=['wallstreetbets'], limit=5
        )
        
        # Verify all expected fields are present
        expected_fields = [
            'saved', 'skipped', 'failed', 'total_fetched',
            'quality_threshold', 'skip_reasons', 'acceptance_rate',
            'by_subreddit'
        ]
        
        for field in expected_fields:
            assert field in stats, f"Missing expected field: {field}"
        
        # Verify types
        assert isinstance(stats['saved'], int)
        assert isinstance(stats['skipped'], int)
        assert isinstance(stats['failed'], int)
        assert isinstance(stats['total_fetched'], int)
        assert isinstance(stats['quality_threshold'], int)
        assert isinstance(stats['skip_reasons'], dict)
        assert isinstance(stats['acceptance_rate'], (int, float))
        assert isinstance(stats['by_subreddit'], dict)
