"""
Database utilities for quality scoring and migrations.

Provides helper functions for:
- Populating is_quality field based on quality_score
- Bulk updating quality tiers
- Performance testing and indexing
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Tuple


async def populate_is_quality_field(
    session: AsyncSession,
    quality_threshold: float = 50.0
) -> Dict[str, int]:
    """
    Populate is_quality field based on quality_score.
    
    Sets is_quality=True for posts with quality_score >= threshold,
    False otherwise.
    
    Args:
        session: AsyncSession for database operations
        quality_threshold: Minimum quality_score to mark as quality (default: 50)
    
    Returns:
        Dict with update counts: {
            'updated': number of rows updated,
            'low_quality': count marked False,
            'high_quality': count marked True
        }
    
    Example:
        >>> async with get_session() as session:
        ...     result = await populate_is_quality_field(session, threshold=50)
        ...     print(f"Updated {result['updated']} rows")
    """
    # Update rows where quality_score >= threshold to is_quality = True
    high_quality_result = await session.execute(
        text(f"""
            UPDATE reddit_posts 
            SET is_quality = TRUE 
            WHERE quality_score >= :threshold AND is_quality = FALSE
        """),
        {"threshold": quality_threshold}
    )
    high_quality_count = high_quality_result.rowcount
    
    # Update rows where quality_score < threshold to is_quality = False
    low_quality_result = await session.execute(
        text(f"""
            UPDATE reddit_posts 
            SET is_quality = FALSE 
            WHERE quality_score < :threshold AND is_quality = TRUE
        """),
        {"threshold": quality_threshold}
    )
    low_quality_count = low_quality_result.rowcount
    
    await session.commit()
    
    return {
        'updated': high_quality_count + low_quality_count,
        'high_quality': high_quality_count,
        'low_quality': low_quality_count,
        'threshold': quality_threshold
    }


async def get_quality_index_performance(session: AsyncSession) -> Dict[str, tuple]:
    """
    Retrieve index size and performance statistics.
    
    Returns:
        Dict with index information: {
            'idx_quality_score': (size_mb, row_count),
            'idx_quality_created': (size_mb, row_count),
            'idx_created_at': (size_mb, row_count),
            'table_stats': {'total_rows': int, 'total_size_mb': float}
        }
    """
    # Get index sizes and row counts
    result = await session.execute(
        text("""
            SELECT 
                indexname,
                ROUND(pg_relation_size(indexrelid) / 1024.0 / 1024.0, 2) as size_mb,
                (SELECT COUNT(*) FROM reddit_posts) as row_count
            FROM pg_indexes 
            JOIN pg_class ON pg_class.relname = indexname 
            WHERE tablename = 'reddit_posts' 
            AND indexname LIKE 'idx_%'
            ORDER BY pg_relation_size(indexrelid) DESC
        """)
    )
    
    index_stats = {}
    for row in result:
        index_name, size_mb, row_count = row
        index_stats[index_name] = (size_mb, row_count)
    
    # Get table statistics
    table_stats_result = await session.execute(
        text("""
            SELECT 
                COUNT(*) as total_rows,
                ROUND(pg_total_relation_size('reddit_posts') / 1024.0 / 1024.0, 2) as total_size_mb
            FROM reddit_posts
        """)
    )
    
    table_row = table_stats_result.first()
    table_stats = {
        'total_rows': table_row[0] if table_row else 0,
        'total_size_mb': table_row[1] if table_row else 0.0
    }
    
    return {
        **index_stats,
        'table_stats': table_stats
    }


async def benchmark_quality_queries(session: AsyncSession) -> Dict[str, float]:
    """
    Benchmark common quality filtering queries.
    
    Measures query execution time for:
    1. High-quality posts: WHERE is_quality = true
    2. Quality range: WHERE quality_score > 60 ORDER BY created_at DESC LIMIT 100
    3. Recent high-quality: WHERE is_quality = true AND created_at > now() - interval '7 days'
    
    Returns:
        Dict with benchmark results (query_name -> execution_time_ms)
    
    Example:
        >>> async with get_session() as session:
        ...     benchmarks = await benchmark_quality_queries(session)
        ...     for query, time_ms in benchmarks.items():
        ...         print(f"{query}: {time_ms}ms")
    """
    import time
    
    benchmarks = {}
    
    # Benchmark 1: Simple is_quality filter
    queries = {
        'simple_is_quality_filter': """
            SELECT id, post_id, title, quality_score 
            FROM reddit_posts 
            WHERE is_quality = true 
            LIMIT 100
        """,
        'quality_range_with_ordering': """
            SELECT id, post_id, title, quality_score, created_at 
            FROM reddit_posts 
            WHERE quality_score > 60 
            ORDER BY created_at DESC 
            LIMIT 100
        """,
        'recent_high_quality': """
            SELECT id, post_id, title, quality_score 
            FROM reddit_posts 
            WHERE is_quality = true 
            AND created_at > now() - interval '7 days' 
            ORDER BY created_at DESC 
            LIMIT 100
        """,
        'quality_distribution': """
            SELECT 
                quality_tier,
                COUNT(*) as count,
                AVG(quality_score) as avg_score
            FROM reddit_posts 
            GROUP BY quality_tier
        """,
        'composite_index_test': """
            SELECT id, post_id, quality_score 
            FROM reddit_posts 
            WHERE is_quality = true 
            AND created_at > now() - interval '24 hours'
            ORDER BY created_at DESC 
            LIMIT 50
        """
    }
    
    for query_name, query in queries.items():
        try:
            start = time.time()
            result = await session.execute(text(query))
            _ = result.fetchall()  # Force execution
            elapsed = (time.time() - start) * 1000  # Convert to milliseconds
            benchmarks[query_name] = round(elapsed, 2)
        except Exception as e:
            benchmarks[query_name] = {'error': str(e)}
    
    return benchmarks


async def analyze_quality_distribution(session: AsyncSession) -> Dict:
    """
    Analyze quality score distribution across all posts.
    
    Returns:
        Dict with distribution statistics: {
            'total_posts': int,
            'quality_tiers': {
                'poor': {'count': int, 'percentage': float},
                'fair': {...},
                'good': {...},
                'excellent': {...}
            },
            'score_statistics': {
                'min': float,
                'max': float,
                'mean': float,
                'median': float,
                'stdev': float
            }
        }
    """
    # Quality tier distribution
    tier_result = await session.execute(
        text("""
            SELECT 
                quality_tier,
                COUNT(*) as count,
                ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM reddit_posts), 2) as percentage,
                ROUND(AVG(quality_score), 2) as avg_score,
                MIN(quality_score) as min_score,
                MAX(quality_score) as max_score
            FROM reddit_posts
            GROUP BY quality_tier
            ORDER BY CASE 
                WHEN quality_tier = 'poor' THEN 1
                WHEN quality_tier = 'fair' THEN 2
                WHEN quality_tier = 'good' THEN 3
                WHEN quality_tier = 'excellent' THEN 4
                ELSE 5
            END
        """)
    )
    
    quality_tiers = {}
    for row in tier_result:
        tier_name, count, percentage, avg_score, min_score, max_score = row
        quality_tiers[tier_name] = {
            'count': count,
            'percentage': percentage,
            'avg_score': float(avg_score) if avg_score else 0,
            'min_score': float(min_score) if min_score else 0,
            'max_score': float(max_score) if max_score else 0
        }
    
    # Overall statistics
    stats_result = await session.execute(
        text("""
            SELECT 
                COUNT(*) as total,
                MIN(quality_score) as min,
                MAX(quality_score) as max,
                ROUND(AVG(quality_score)::numeric, 2) as mean,
                ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY quality_score)::numeric, 2) as median,
                ROUND(STDDEV(quality_score)::numeric, 2) as stdev
            FROM reddit_posts
            WHERE quality_score IS NOT NULL
        """)
    )
    
    stats_row = stats_result.first()
    score_statistics = {
        'total_posts': stats_row[0],
        'min': float(stats_row[1]) if stats_row[1] else 0,
        'max': float(stats_row[2]) if stats_row[2] else 0,
        'mean': float(stats_row[3]) if stats_row[3] else 0,
        'median': float(stats_row[4]) if stats_row[4] else 0,
        'stdev': float(stats_row[5]) if stats_row[5] else 0
    }
    
    return {
        'total_posts': score_statistics['total_posts'],
        'quality_tiers': quality_tiers,
        'score_statistics': score_statistics
    }
