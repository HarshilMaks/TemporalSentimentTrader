"""
Quality Scorer Service for Reddit Posts

This module provides enterprise-grade quality scoring for Reddit posts before
they enter the ML pipeline. Implements multi-dimensional scoring:
- Engagement scoring (upvotes + comment normalization)
- Content quality (length penalties, text analysis)
- Upvote ratio validation (brigading detection)
- Spam detection (emoji, caps, keywords)

Quality tiers:
- Poor: 0-30 (filtered out)
- Fair: 30-50 (marginal, use cautiously)
- Good: 50-70 (suitable for training)
- Excellent: 70+ (high confidence signals)
"""

import re
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class QualityScore:
    """Score breakdown for a single post"""
    overall_score: float  # 0-100
    engagement_score: float  # 0-100
    content_score: float  # 0-100
    upvote_ratio_score: float  # 0-100
    spam_score: float  # 0-100 (lower is better)
    is_quality: bool  # True if overall_score >= min_threshold
    quality_tier: str  # "poor", "fair", "good", "excellent"
    reasons: List[str]  # Raw/marginal reasons
    flags: List[str]  # Issues detected


class QualityScorer:
    """
    Enterprise-grade quality scoring for Reddit posts.
    
    Combines multiple dimensions to determine post quality for ML training.
    Prevents garbage-in-garbage-out by filtering low-signal posts early.
    """
    
    # Score thresholds (configurable)
    MIN_QUALITY_THRESHOLD = 30  # Absolute minimum
    GOOD_QUALITY_THRESHOLD = 50  # Safe for training
    EXCELLENT_QUALITY_THRESHOLD = 70  # High confidence
    
    # Engagement thresholds
    MIN_UPVOTES = 5  # Absolute minimum engagement
    MIN_COMMENT_COUNT = 2  # At least some discussion
    
    # Content constraints
    MIN_CONTENT_LENGTH = 50  # Characters
    MAX_CONTENT_LENGTH = 50000  # Posts longer than this are suspicious
    
    # Upvote ratio
    BRIGADING_THRESHOLD = 0.4  # Flag if ratio < 40%
    SUSPICIOUS_HIGH_RATIO = 0.99  # Flag if ratio > 99% (artificial engagement)
    
    # Spam indicators
    MAX_EMOJI_RATIO = 0.1  # 10% emoji = spam
    MAX_CAPS_RATIO = 0.3  # 30% CAPS = spam
    SPAM_KEYWORDS = {
        'buy bags', 'pump it', 'diamond hands', 'moon', 'rocket',
        'lamborghini', 'hodl', 'gme', 'amc', 'penny stock',
        'get rich quick', 'guaranteed', 'can\'t lose', 'sure thing',
        'click here', 'limited time', 'act now', 'exclusive',
        'crypto pump', 'nft', 'coin', 'token', 'doge'
    }
    
    # Sentiment/engagement multipliers
    COMMENT_WEIGHT = 0.3  # Comments worth 30% vs upvotes
    
    def __init__(self, min_quality: int = 30):
        """
        Initialize quality scorer.
        
        Args:
            min_quality: Minimum score threshold for quality posts (0-100)
        """
        self.min_quality = min_quality
    
    def score_post(
        self,
        title: str,
        body: str,
        upvotes: int,
        downvotes: int,
        comment_count: int,
        upvote_ratio: float,
        created_at: Optional[datetime] = None
    ) -> QualityScore:
        """
        Calculate comprehensive quality score for a Reddit post.
        
        Args:
            title: Post title
            body: Post body/content
            upvotes: Number of upvotes
            downvotes: Number of downvotes
            comment_count: Number of comments
            upvote_ratio: Ratio of upvotes to total (0-1)
            created_at: Post creation time (for age penalty)
        
        Returns:
            QualityScore with detailed breakdown and flags
        """
        flags = []
        reasons = []
        
        # Calculate individual scores
        engagement_score = self._score_engagement(
            upvotes, downvotes, comment_count, flags
        )
        content_score = self._score_content(
            title, body, flags, reasons
        )
        upvote_ratio_score = self._score_upvote_ratio(
            upvote_ratio, flags
        )
        spam_score = self._score_spam(title, body, flags)
        
        # Weighted overall score (0-100)
        overall_score = (
            engagement_score * 0.35 +  # Engagement is most important
            content_score * 0.30 +      # Content quality matters
            upvote_ratio_score * 0.20 +  # Ratio flags manipulation
            (100 - spam_score) * 0.15  # Spam detection (inverted)
        )
        
        # Determine quality tier
        if overall_score >= self.EXCELLENT_QUALITY_THRESHOLD:
            quality_tier = "excellent"
        elif overall_score >= self.GOOD_QUALITY_THRESHOLD:
            quality_tier = "good"
        elif overall_score >= self.MIN_QUALITY_THRESHOLD:
            quality_tier = "fair"
        else:
            quality_tier = "poor"
        
        # Final quality determination
        is_quality = overall_score >= self.min_quality
        
        return QualityScore(
            overall_score=round(overall_score, 2),
            engagement_score=round(engagement_score, 2),
            content_score=round(content_score, 2),
            upvote_ratio_score=round(upvote_ratio_score, 2),
            spam_score=round(spam_score, 2),
            is_quality=is_quality,
            quality_tier=quality_tier,
            reasons=reasons,
            flags=flags
        )
    
    def _score_engagement(
        self,
        upvotes: int,
        downvotes: int,
        comment_count: int,
        flags: List[str]
    ) -> float:
        """
        Score engagement: normalized upvotes + comments.
        
        Higher engagement = more community interest.
        """
        # Minimum engagement checks
        if upvotes < self.MIN_UPVOTES:
            flags.append(f"Low upvotes: {upvotes} < {self.MIN_UPVOTES}")
            return 0.0
        
        if comment_count < self.MIN_COMMENT_COUNT:
            flags.append(f"Low comments: {comment_count} < {self.MIN_COMMENT_COUNT}")
            return 20.0  # Partial credit for upvotes alone
        
        # Engagement scoring with diminishing returns
        # Logarithmic scale: 10 upvotes = 30 points, 100 = 60 points
        upvote_score = min(100, math.log10(upvotes + 1) * 30)
        
        # Comment score: factor in discussion depth
        # 5 comments = 20 points, 50 = 60 points
        comment_score = min(100, math.log10(comment_count + 1) * 20)
        
        # Combined score with weighting
        engagement_score = (upvote_score * 0.7) + (comment_score * self.COMMENT_WEIGHT)
        
        # Bonus for balanced engagement (upvotes + comments both strong)
        if upvotes >= 20 and comment_count >= 5:
            engagement_score = min(100, engagement_score * 1.1)
        
        return engagement_score
    
    def _score_content(
        self,
        title: str,
        body: str,
        flags: List[str],
        reasons: List[str]
    ) -> float:
        """
        Score content quality: length, relevance, completeness.
        """
        full_content = f"{title} {body}".strip()
        content_length = len(full_content)
        
        # Minimum content length check
        if content_length < self.MIN_CONTENT_LENGTH:
            flags.append(f"Content too short: {content_length} < {self.MIN_CONTENT_LENGTH}")
            return 0.0
        
        # Maximum content length (suspicious)
        if content_length > self.MAX_CONTENT_LENGTH:
            flags.append(f"Content too long: {content_length} > {self.MAX_CONTENT_LENGTH}")
            return 30.0  # Very suspicious
        
        # Content score based on length
        # 50 chars = 20, 500 = 80, 5000 = 100
        length_score = min(
            100,
            20 + (math.log10(content_length) - 1.7) * 25
        )
        
        # Bonus for substantive content (paragraph breaks, multiple sentences)
        sentences = len(re.split(r'[.!?]+', body))
        paragraphs = len(body.split('\n\n'))
        
        if sentences >= 3:
            length_score = min(100, length_score * 1.1)
        
        if paragraphs >= 2:
            length_score = min(100, length_score * 1.05)
        
        # Detect low-effort content
        if body.lower().count('discuss') < 1 and len(body.split()) < 20:
            reasons.append("Low-effort content (minimal discussion)")
        
        return length_score
    
    def _score_upvote_ratio(
        self,
        upvote_ratio: float,
        flags: List[str]
    ) -> float:
        """
        Score upvote ratio: detect brigading and artificial engagement.
        
        Healthy: 0.5-0.95 (50-95% upvoted)
        Suspicious: <0.4 or >0.99
        """
        # Validate ratio range
        if not (0 <= upvote_ratio <= 1):
            return 50.0  # Unknown ratio
        
        # Detect brigading (too many downvotes)
        if upvote_ratio < self.BRIGADING_THRESHOLD:
            flags.append(f"Possible brigading: ratio {upvote_ratio:.0%} < {self.BRIGADING_THRESHOLD:.0%}")
            return 20.0  # Low score for brigaded posts
        
        # Detect artificial engagement (too few downvotes)
        if upvote_ratio > self.SUSPICIOUS_HIGH_RATIO:
            flags.append(f"Suspicious high ratio: {upvote_ratio:.0%} > {self.SUSPICIOUS_HIGH_RATIO:.0%}")
            return 40.0  # Suspicious
        
        # Score based on distance from healthy zone (0.5-0.95)
        healthy_min = 0.5
        healthy_max = 0.95
        
        if healthy_min <= upvote_ratio <= healthy_max:
            # Closer to 0.7 (70% upvote) is ideal
            ideal_ratio = 0.7
            distance = abs(upvote_ratio - ideal_ratio)
            ratio_score = 100 - (distance * 100)  # Max 100 at ideal
        else:
            # Outside healthy range
            ratio_score = 50 + (min(abs(upvote_ratio - healthy_min), abs(upvote_ratio - healthy_max)) * 50)
        
        return ratio_score
    
    def _score_spam(
        self,
        title: str,
        body: str,
        flags: List[str]
    ) -> float:
        """
        Score spam probability: emoji, caps, keywords.
        
        Returns inverse score (0-100, where 100 = high spam).
        """
        # Keep original case for caps detection
        full_text_original = f"{title} {body}"
        # Lowercase for keyword matching
        full_text = full_text_original.lower()
        spam_indicators = 0.0
        
        # 1. Emoji detection
        emoji_count = len(re.findall(r'[🚀💎🤑💰💸🌙⭐🔥💯👍👎]', full_text))
        text_length = len(full_text)
        emoji_ratio = emoji_count / max(1, text_length)
        
        if emoji_ratio > self.MAX_EMOJI_RATIO:
            flags.append(f"Spam emoji ratio: {emoji_ratio:.1%} > {self.MAX_EMOJI_RATIO:.1%}")
            spam_indicators += 40
        elif emoji_count > 3:
            spam_indicators += 20
        
        # 2. All-caps detection (on original text to preserve case)
        caps_count = sum(1 for c in full_text_original if c.isupper())
        caps_ratio = caps_count / max(1, text_length)
        
        if caps_ratio > self.MAX_CAPS_RATIO:
            flags.append(f"Spam caps ratio: {caps_ratio:.1%} > {self.MAX_CAPS_RATIO:.1%}")
            spam_indicators += 30
        
        # 3. Spam keyword detection (on lowercased text)
        for keyword in self.SPAM_KEYWORDS:
            if keyword in full_text:
                flags.append(f"Spam keyword detected: '{keyword}'")
                spam_indicators += 15
        
        # 4. Suspicious URLs
        url_count = len(re.findall(r'http[s]?://', full_text))
        if url_count > 3:
            flags.append(f"High URL count: {url_count}")
            spam_indicators += 20
        elif url_count > 1:
            spam_indicators += 10
        
        # 5. Repetitive patterns (likely copy-paste spam)
        # Check for repeated phrases
        words = full_text.split()
        if len(words) > 20:
            word_freq = {}
            for word in words:
                if len(word) > 3:  # Ignore short words
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            max_freq_ratio = max(word_freq.values(), default=0) / len(words)
            if max_freq_ratio > 0.15:  # 15% of text is one word
                flags.append(f"High word repetition: {max_freq_ratio:.0%}")
                spam_indicators += 25
        
        # Cap spam score at 100
        spam_score = min(100, spam_indicators)
        
        return spam_score


class QualityScorerConfig:
    """Configuration for quality scorer (production settings)"""
    
    # Thresholds for filtering
    MIN_QUALITY_SCORE = 30  # Posts below this are dropped
    GOOD_QUALITY_SCORE = 50  # Posts at or above used for training
    EXCELLENT_QUALITY_SCORE = 70  # High-confidence training data
    
    # Engagement requirements
    MIN_UPVOTES = 5
    MIN_COMMENTS = 2
    
    # Content requirements
    MIN_CONTENT_LENGTH = 50  # chars
    
    # Upvote ratio
    BRIGADING_THRESHOLD = 0.4
    
    @classmethod
    def for_training(cls) -> QualityScorer:
        """Create scorer configured for training data"""
        return QualityScorer(min_quality=cls.GOOD_QUALITY_SCORE)
    
    @classmethod
    def for_analysis(cls) -> QualityScorer:
        """Create scorer configured for post-hoc analysis"""
        return QualityScorer(min_quality=cls.MIN_QUALITY_SCORE)


# Example usage and testing
if __name__ == "__main__":
    # Demo posts
    scorer = QualityScorer(min_quality=50)
    
    # High-quality post example
    good_post = scorer.score_post(
        title="Analysis of Tesla Q4 earnings and sentiment correlation",
        body="""Interesting analysis from today's earnings call. 
        
        Key findings:
        1. Revenue beat expectations by 12%
        2. Margin expansion despite supply chain challenges
        3. Guidance forward-looking
        
        Reddit sentiment has been overwhelmingly positive in r/stocks and r/investing.
        This could signal strong buy momentum in coming weeks.""",
        upvotes=150,
        downvotes=20,
        comment_count=42,
        upvote_ratio=0.88
    )
    print(f"Good Post: {good_post.quality_tier} ({good_post.overall_score})")
    print(f"  Flags: {good_post.flags}\n")
    
    # Spam post example
    spam_post = scorer.score_post(
        title="🚀🚀 MOON SOON 🚀🚀 BUY NOW!!!",
        body="BUY BUY BUY!!! GUARANTEED MONEY!!! LAMBORGHINI TIME!!! 💎💰🤑",
        upvotes=8,
        downvotes=50,
        comment_count=2,
        upvote_ratio=0.14
    )
    print(f"Spam Post: {spam_post.quality_tier} ({spam_post.overall_score})")
    print(f"  Flags: {spam_post.flags}")
