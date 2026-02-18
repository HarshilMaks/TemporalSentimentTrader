"""Integration tests for quality-filtered Reddit scraping pipeline.

Tests verify:
1. Quality scoring integration
2. Skip reason tracking
3. Configurable min_quality threshold
4. Stats comprehensiveness
5. Database persistence with quality fields
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.services.reddit_service import RedditService
from backend.services.quality_scorer import QualityScorer, QualityScore
from backend.models.reddit import RedditPost
from backend.database.config import Base


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


@pytest_asyncio.fixture
async def test_db():
    """Create test database."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    yield async_session
    
    await engine.dispose()


class TestQualityFilteredScraping:
    """Test quality-filtered scraping pipeline."""
    
    @pytest.mark.asyncio
    async def test_scrape_with_quality_filtering(self, test_db):
        """Test that low-quality posts are skipped."""
        async_session = test_db
        
        with patch('backend.services.reddit_service.RedditScraper') as mock_scraper_class:
            mock_scraper = MockRedditScraper()
            mock_scraper_class.return_value = mock_scraper
            
            service = RedditService(min_quality=50)
            
            async with async_session() as session:
                stats = await service.scrape_and_save(
                    session,
                    subreddits=['wallstreetbets'],
                    limit=10
                )
            
            # Should save high-quality posts with tickers
            assert stats['saved'] == 3  # AAPL, TSLA, MSFT (not low-quality or no ticker)
            assert stats['skipped'] == 2  # One low-quality, one no ticker
            assert stats['failed'] == 0
            assert stats['total_fetched'] == 5
    
    @pytest.mark.asyncio
    async def test_skip_reasons_tracking(self, test_db):
        """Test that skip reasons are properly tracked."""
        async_session = test_db
        
        with patch('backend.services.reddit_service.RedditScraper') as mock_scraper_class:
            mock_scraper = MockRedditScraper()
            mock_scraper_class.return_value = mock_scraper
            
            service = RedditService(min_quality=50)
            
            async with async_session() as session:
                stats = await service.scrape_and_save(
                    session,
                    subreddits=['wallstreetbets'],
                    limit=10
                )
            
            # Check skip reasons are tracked
            assert 'skip_reasons' in stats
            assert stats['skip_reasons']['low_quality'] == 1
            assert stats['skip_reasons']['no_tickers'] == 1
            assert stats['skip_reasons']['duplicate'] == 0
    
    @pytest.mark.asyncio
    async def test_configurable_min_quality_threshold(self, test_db):
        """Test that min_quality threshold can be configured."""
        async_session = test_db
        
        with patch('backend.services.reddit_service.RedditScraper') as mock_scraper_class:
            mock_scraper = MockRedditScraper()
            mock_scraper_class.return_value = mock_scraper
            
            # Strict threshold (70+)
            service_strict = RedditService(min_quality=70)
            
            async with async_session() as session:
                stats = await service_strict.scrape_and_save(
                    session,
                    subreddits=['wallstreetbets'],
                    limit=10
                )
            
            # With higher threshold, should save fewer posts
            assert stats['quality_threshold'] == 70
            assert stats['saved'] <= 3  # Should be stricter
    
    @pytest.mark.asyncio
    async def test_quality_fields_persisted_in_db(self, test_db):
        """Test that quality fields are correctly saved to database."""
        async_session = test_db
        
        with patch('backend.services.reddit_service.RedditScraper') as mock_scraper_class:
            mock_scraper = MockRedditScraper()
            mock_scraper_class.return_value = mock_scraper
            
            service = RedditService(min_quality=50)
            
            async with async_session() as session:
                await service.scrape_and_save(
                    session,
                    subreddits=['wallstreetbets'],
                    limit=10
                )
                
                # Verify posts were saved with quality fields
                from sqlalchemy import select
                result = await session.execute(select(RedditPost))
                posts = result.scalars().all()
                
                # Check at least some posts were saved
                assert len(posts) > 0
                
                # All posts should have quality fields
                for post in posts:
                    assert post.quality_score is not None
                    assert post.quality_score >= 0
                    assert post.quality_score <= 100
                    assert post.quality_tier is not None
                    assert post.quality_tier in ['poor', 'fair', 'good', 'excellent']
    
    @pytest.mark.asyncio
    async def test_acceptance_rate_calculation(self, test_db):
        """Test that acceptance rate is calculated correctly."""
        async_session = test_db
        
        with patch('backend.services.reddit_service.RedditScraper') as mock_scraper_class:
            mock_scraper = MockRedditScraper()
            mock_scraper_class.return_value = mock_scraper
            
            service = RedditService(min_quality=50)
            
            async with async_session() as session:
                stats = await service.scrape_and_save(
                    session,
                    subreddits=['wallstreetbets'],
                    limit=10
                )
            
            # Verify acceptance rate
            assert 'acceptance_rate' in stats
            if stats['total_fetched'] > 0:
                expected_rate = (stats['saved'] / stats['total_fetched']) * 100
                assert stats['acceptance_rate'] == expected_rate
    
    @pytest.mark.asyncio
    async def test_per_subreddit_stats(self, test_db):
        """Test that per-subreddit statistics are broken down."""
        async_session = test_db
        
        with patch('backend.services.reddit_service.RedditScraper') as mock_scraper_class:
            mock_scraper = MockRedditScraper()
            mock_scraper_class.return_value = mock_scraper
            
            service = RedditService(min_quality=50)
            
            async with async_session() as session:
                stats = await service.scrape_and_save(
                    session,
                    subreddits=['wallstreetbets', 'stocks'],
                    limit=10
                )
            
            # Check per-subreddit stats
            assert 'by_subreddit' in stats
            assert 'wallstreetbets' in stats['by_subreddit']
            assert 'stocks' in stats['by_subreddit']
            
            for sub_name, sub_stats in stats['by_subreddit'].items():
                assert 'saved' in sub_stats
                assert 'skipped' in sub_stats
                assert 'failed' in sub_stats
                assert 'fetched' in sub_stats
                assert 'skip_reasons' in sub_stats
    
    @pytest.mark.asyncio
    async def test_duplicate_post_detection(self, test_db):
        """Test that duplicate posts are skipped."""
        async_session = test_db
        
        with patch('backend.services.reddit_service.RedditScraper') as mock_scraper_class:
            mock_scraper = MockRedditScraper()
            mock_scraper_class.return_value = mock_scraper
            
            service = RedditService(min_quality=50)
            
            # First scrape
            async with async_session() as session1:
                stats1 = await service.scrape_and_save(
                    session1,
                    subreddits=['wallstreetbets'],
                    limit=10
                )
                first_saved = stats1['saved']
            
            # Second scrape (same posts)
            async with async_session() as session2:
                stats2 = await service.scrape_and_save(
                    session2,
                    subreddits=['wallstreetbets'],
                    limit=10
                )
                second_saved = stats2['saved']
            
            # Second scrape should have duplicates skipped
            assert stats2['skip_reasons']['duplicate'] > 0
    
    @pytest.mark.asyncio
    async def test_comprehensive_metrics_returned(self, test_db):
        """Test that comprehensive metrics are returned."""
        async_session = test_db
        
        with patch('backend.services.reddit_service.RedditScraper') as mock_scraper_class:
            mock_scraper = MockRedditScraper()
            mock_scraper_class.return_value = mock_scraper
            
            service = RedditService(min_quality=50)
            
            async with async_session() as session:
                stats = await service.scrape_and_save(
                    session,
                    subreddits=['wallstreetbets'],
                    limit=10
                )
            
            # Verify all expected metrics are present
            expected_keys = {
                'saved', 'skipped', 'failed', 'total_fetched',
                'quality_threshold', 'skip_reasons', 'acceptance_rate',
                'by_subreddit'
            }
            assert set(stats.keys()) == expected_keys
            
            # Verify skip_reasons has all categories
            expected_skip_reasons = {
                'no_tickers', 'duplicate', 'low_quality', 'other'
            }
            assert set(stats['skip_reasons'].keys()) == expected_skip_reasons
