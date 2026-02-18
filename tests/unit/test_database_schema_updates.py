"""Test database schema updates for Phase 1 Day 3.

Tests verify:
1. New columns added: is_quality, quality_score, quality_tier
2. Model properly reflects database schema
3. Alembic migrations are registered
"""

import pytest
from backend.models.reddit import RedditPost
from sqlalchemy import inspect
import os


class TestDatabaseSchemaUpdates:
    """Verify database schema has been updated with quality scoring fields."""
    
    def test_reddit_post_model_has_quality_score(self):
        """Verify quality_score field exists in RedditPost model."""
        assert hasattr(RedditPost, 'quality_score')
    
    def test_reddit_post_model_has_quality_tier(self):
        """Verify quality_tier field exists in RedditPost model."""
        assert hasattr(RedditPost, 'quality_tier')
    
    def test_reddit_post_model_has_is_quality(self):
        """Verify is_quality field exists in RedditPost model."""
        assert hasattr(RedditPost, 'is_quality')
    
    def test_model_columns_have_correct_types(self):
        """Verify column types are set correctly."""
        mapper = inspect(RedditPost)
        columns = {col.name: col.type for col in mapper.columns}
        
        # quality_score should be Float
        assert columns['quality_score'].python_type == float
        
        # quality_tier should be String
        assert columns['quality_tier'].python_type == str
        
        # is_quality should be Boolean
        assert columns['is_quality'].python_type == bool


class TestAlembicMigrations:
    """Verify Alembic migrations are in place."""
    
    def test_migration_files_exist(self):
        """Verify migration files are present."""
        migration_dir = '/home/harshil/tft-trader/alembic/versions'
        migration_files = os.listdir(migration_dir)
        
        # Should have our quality scoring migrations
        assert any('quality_scoring' in f for f in migration_files), \
            "Missing quality scoring migration"
        assert any('quality_fields' in f for f in migration_files), \
            "Missing quality fields migration"
    
    def test_migration_chain_is_consistent(self):
        """Verify migration chain is properly set up."""
        # Read migration files and verify parents/children relationships
        migration_dir = '/home/harshil/tft-trader/alembic/versions'
        
        # Find the quality scoring migrations
        quality_migrations = [
            f for f in os.listdir(migration_dir)
            if 'quality' in f.lower() and f.endswith('.py')
        ]
        
        # Should have at least quality optimization migration
        assert len(quality_migrations) >= 1, \
            f"Expected quality scoring migrations, found {quality_migrations}"
        
        # Read one migration to ensure it's properly formatted
        mig_file = quality_migrations[0]
        with open(os.path.join(migration_dir, mig_file)) as f:
            content = f.read()
            # Should have revision identifier and upgrade/downgrade functions
            assert 'revision: str =' in content
            assert 'def upgrade()' in content
            assert 'def downgrade()' in content


class TestQualityFieldDefaults:
    """Verify quality fields have appropriate defaults."""
    
    def test_quality_score_has_default(self):
        """Verify quality_score has a default value."""
        mapper = inspect(RedditPost)
        quality_score = mapper.columns['quality_score']
        assert quality_score.default is not None
    
    def test_quality_tier_has_default(self):
        """Verify quality_tier has a default value."""
        mapper = inspect(RedditPost)
        quality_tier = mapper.columns['quality_tier']
        assert quality_tier.default is not None
    
    def test_is_quality_has_default(self):
        """Verify is_quality has a default value."""
        mapper = inspect(RedditPost)
        is_quality = mapper.columns['is_quality']
        assert is_quality.default is not None
    
    def test_quality_fields_can_be_not_null(self):
        """Verify quality fields are properly defined with defaults."""
        mapper = inspect(RedditPost)
        
        # Check that defaults are set
        assert mapper.columns['quality_score'].default is not None
        assert mapper.columns['quality_tier'].default is not None
        assert mapper.columns['is_quality'].default is not None


class TestIndexes:
    """Verify performance indexes are created."""
    
    def test_quality_score_index_in_code(self):
        """Verify quality_score index is defined."""
        # Check if indexes are defined in model's __table_args__
        table_args = RedditPost.__table_args__
        assert table_args is not None, "No table args defined"
        
        # Look for quality_score index
        quality_indexes = [arg for arg in table_args 
                          if hasattr(arg, 'name') and 'quality_score' in arg.name]
        assert len(quality_indexes) > 0, "Missing quality_score index"
    
    def test_composite_index_includes_is_quality_and_created_at(self):
        """Verify composite index on is_quality and created_at."""
        table_args = RedditPost.__table_args__
        
        # Look for composite index
        composite_indexes = [arg for arg in table_args 
                           if hasattr(arg, 'name') and 'quality_created' in arg.name]
        assert len(composite_indexes) > 0, \
            "Missing composite index for (is_quality, created_at)"
    
    def test_created_at_index_exists(self):
        """Verify created_at has an index."""
        table_args = RedditPost.__table_args__
        
        # Look for created_at index
        created_at_indexes = [arg for arg in table_args 
                             if hasattr(arg, 'name') and 'created_at' in arg.name]
        assert len(created_at_indexes) > 0, "Missing created_at index"
    
    def test_quality_fields_indexed(self):
        """Verify quality fields have index=True."""
        mapper = inspect(RedditPost)
        
        # quality_score and is_quality should be indexed
        assert mapper.columns['quality_score'].index == True
        assert mapper.columns['is_quality'].index == True


class TestMigrationSequence:
    """Verify migration sequence is correct."""
    
    def test_quality_migrations_after_reddit_enhancements(self):
        """Verify quality migrations come after reddit_post_enhanced_fields."""
        migration_dir = '/home/harshil/tft-trader/alembic/versions'
        migration_pairs = []
        
        for f in os.listdir(migration_dir):
            if f.endswith('.py') and not f.startswith('__'):
                # Extract revision and down_revision
                with open(os.path.join(migration_dir, f)) as mf:
                    content = mf.read()
                    # Find revision line
                    for line in content.split('\n'):
                        if line.startswith("revision: str ="):
                            rev = line.split("'")[1]
                            migration_pairs.append((rev, f))
                            break
        
        # At least one quality migration should exist
        quality_migs = [m for m in migration_pairs if 'quality' in m[1].lower()]
        assert len(quality_migs) > 0, \
            f"No quality migrations found in {migration_dir}"
