"""
Tests for RAG v5.7.0 improvements.

PR1: Advanced chunking as default
PR2: Two-phase filtering
PR3: Retrieval metrics
PR4: Freshness scoring
PR5: Authority and spam detection
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

# PR2: Two-Phase Filtering Tests
class TestTwoPhaseFilter:
    """Test suite for two-phase filtering."""

    def test_platform_normalization(self):
        """iOS should match ios, mobile, and all."""
        from resync.knowledge.retrieval.filter_strategy import TwoPhaseFilter

        filter = TwoPhaseFilter()

        normalized = filter.normalize_filter_value("platform", "ios")
        assert normalized == ["ios", "mobile", "all"]

        normalized = filter.normalize_filter_value("platform", "android")
        assert normalized == ["android", "mobile", "all"]

        normalized = filter.normalize_filter_value("platform", "web")
        assert normalized == ["web", "all"]

    def test_environment_normalization(self):
        """Production should normalize to prod."""
        from resync.knowledge.retrieval.filter_strategy import TwoPhaseFilter

        filter = TwoPhaseFilter()

        normalized = filter.normalize_filter_value("environment", "production")
        assert "prod" in normalized
        assert "production" in normalized
        assert "all" in normalized

    def test_hard_filter_applies_strict_matching(self):
        """Hard filters should use strict AND logic."""
        from resync.knowledge.retrieval.filter_strategy import TwoPhaseFilter, FilterConfig

        config = FilterConfig()
        filter = TwoPhaseFilter(config)

        docs = [
            {"metadata": {"platform": "ios", "doc_type": "manual"}},
            {"metadata": {"platform": "android", "doc_type": "manual"}},
            {"metadata": {"platform": "ios", "doc_type": "blog"}},
        ]

        result = filter.apply_hard_filter(docs, {"platform": "ios", "doc_type": "manual"})

        assert len(result.documents) == 1
        assert result.documents[0]["metadata"]["platform"] == "ios"
        assert result.documents[0]["metadata"]["doc_type"] == "manual"

    def test_fallback_removes_least_important_filters_first(self):
        """Fallback should remove tags before platform."""
        from resync.knowledge.retrieval.filter_strategy import TwoPhaseFilter, FilterConfig

        config = FilterConfig(
            min_results=2,
            fallback_remove_filters=["tags", "doc_type", "platform"],
        )
        filter = TwoPhaseFilter(config)

        docs = [
            {"metadata": {"platform": "ios", "tags": ["urgent"], "doc_type": "manual"}},
            {"metadata": {"platform": "ios", "tags": ["normal"], "doc_type": "manual"}},
            {"metadata": {"platform": "android", "tags": ["urgent"], "doc_type": "blog"}},
        ]

        # Only 1 doc matches all filters
        hard_filters = {"platform": "ios", "tags": "urgent", "doc_type": "manual"}
        initial_result = filter.apply_hard_filter(docs, hard_filters)
        assert len(initial_result.documents) == 1

        # Fallback should remove tags first
        fallback_result = filter.apply_fallback(docs, hard_filters)
        assert fallback_result.fallback_triggered
        assert "tags" in (fallback_result.fallback_reason or "")

    def test_create_filter_config_separates_soft_hard(self):
        """create_filter_config should put hierarchical filters in soft."""
        from resync.knowledge.retrieval.filter_strategy import create_filter_config

        config = create_filter_config(
            platform="ios",
            environment="prod",
            doc_type="manual",
            tags=["important"],
        )

        # Platform and environment are soft (hierarchical)
        assert "platform" in config.soft_filters
        assert "environment" in config.soft_filters

        # Doc type and tags are hard (strict)
        assert "doc_type" in config.hard_filters
        assert "tags" in config.hard_filters


# PR3: Retrieval Metrics Tests
class TestRetrievalMetrics:
    """Test suite for retrieval metrics calculation."""

    def test_recall_at_k_calculation(self):
        """Recall@k should correctly calculate proportion retrieved."""
        from resync.knowledge.retrieval.metrics import recall_at_k

        relevant = {"doc1", "doc2", "doc3"}
        retrieved = ["doc1", "doc4", "doc2", "doc5", "doc6"]

        # At k=3, we have doc1 and doc2 from relevant set
        assert recall_at_k(relevant, retrieved, 3) == 2 / 3

        # At k=5, still only doc1 and doc2
        assert recall_at_k(relevant, retrieved, 5) == 2 / 3

        # At k=1, only doc1
        assert recall_at_k(relevant, retrieved, 1) == 1 / 3

    def test_reciprocal_rank_calculation(self):
        """MRR should return 1/position of first relevant."""
        from resync.knowledge.retrieval.metrics import reciprocal_rank

        relevant = {"doc2", "doc3"}
        retrieved = ["doc1", "doc2", "doc3", "doc4"]

        # First relevant (doc2) is at position 2
        assert reciprocal_rank(relevant, retrieved) == 0.5

        # First relevant at position 1
        assert reciprocal_rank({"doc1"}, retrieved) == 1.0

        # No relevant docs found
        assert reciprocal_rank({"doc5"}, retrieved) == 0.0

    def test_ndcg_at_k_binary_relevance(self):
        """nDCG with binary relevance should work correctly."""
        from resync.knowledge.retrieval.metrics import ndcg_at_k_binary

        relevant = {"doc1", "doc2"}
        
        # Perfect ranking
        perfect = ["doc1", "doc2", "doc3", "doc4"]
        assert ndcg_at_k_binary(relevant, perfect, 4) == 1.0

        # Imperfect ranking
        imperfect = ["doc3", "doc1", "doc4", "doc2"]
        score = ndcg_at_k_binary(relevant, imperfect, 4)
        assert 0 < score < 1

    def test_regression_gate_detects_regression(self):
        """RegressionGate should detect metric regression."""
        from resync.knowledge.retrieval.metrics import (
            RetrievalMetrics,
            RegressionGate,
            RegressionThresholds,
        )

        baseline = RetrievalMetrics(
            recall_at_5=0.85,
            mrr=0.75,
            ndcg_at_10=0.80,
            p95_latency_ms=100.0,
        )

        # Small regression - should pass
        small_regression = RetrievalMetrics(
            recall_at_5=0.84,  # -1.2%
            mrr=0.74,  # -1.3%
            ndcg_at_10=0.79,  # -1.25%
            p95_latency_ms=105.0,  # +5%
        )

        gate = RegressionGate(baseline)
        passed, failures = gate.check(small_regression)
        assert passed

        # Large regression - should fail
        large_regression = RetrievalMetrics(
            recall_at_5=0.75,  # -11.8%
            mrr=0.65,  # -13.3%
            ndcg_at_10=0.70,  # -12.5%
            p95_latency_ms=150.0,  # +50%
        )

        passed, failures = gate.check(large_regression)
        assert not passed
        assert len(failures) > 0


# PR4: Freshness Scoring Tests
class TestFreshnessScorer:
    """Test suite for freshness scoring."""

    def test_age_decay_at_half_life(self):
        """Score should be ~0.5 at half-life."""
        from resync.knowledge.retrieval.freshness import FreshnessConfig, FreshnessScorer

        config = FreshnessConfig(half_life_days=180, recent_boost_factor=1.0)
        scorer = FreshnessScorer(config)

        now = datetime.now(timezone.utc)
        half_life_ago = now - timedelta(days=180)

        score = scorer.calculate_age_score(half_life_ago, now)
        assert 0.45 < score < 0.55  # Approximately 0.5

    def test_recent_document_gets_boost(self):
        """Documents within recent_boost_days should get boosted."""
        from resync.knowledge.retrieval.freshness import FreshnessConfig, FreshnessScorer

        config = FreshnessConfig(recent_boost_days=30, recent_boost_factor=1.2)
        scorer = FreshnessScorer(config)

        now = datetime.now(timezone.utc)
        recent = now - timedelta(days=7)
        old = now - timedelta(days=60)

        recent_score = scorer.calculate_age_score(recent, now)
        old_score = scorer.calculate_age_score(old, now)

        # Recent should be boosted relative to its base decay
        assert recent_score > old_score

    def test_deprecated_document_penalty(self):
        """Deprecated documents should receive penalty."""
        from resync.knowledge.retrieval.freshness import FreshnessConfig, FreshnessScorer

        config = FreshnessConfig(deprecated_penalty=0.3)
        scorer = FreshnessScorer(config)

        doc_active = {"metadata": {"is_deprecated": False, "last_updated": datetime.now(timezone.utc).isoformat()}}
        doc_deprecated = {"metadata": {"is_deprecated": True, "last_updated": datetime.now(timezone.utc).isoformat()}}

        score_active = scorer.calculate_combined_score(doc_active)
        score_deprecated = scorer.calculate_combined_score(doc_deprecated)

        assert score_deprecated < score_active
        assert score_deprecated == pytest.approx(score_active * 0.3, rel=0.1)

    def test_version_preference(self):
        """Older versions should be penalized."""
        from resync.knowledge.retrieval.freshness import FreshnessScorer

        scorer = FreshnessScorer()

        latest_versions = {"doc1": 5}

        doc_latest = {"document_id": "doc1#c001", "metadata": {"doc_version": 5}}
        doc_old = {"document_id": "doc1#c002", "metadata": {"doc_version": 2}}

        score_latest = scorer.calculate_combined_score(doc_latest, latest_versions)
        score_old = scorer.calculate_combined_score(doc_old, latest_versions)

        assert score_old < score_latest

    def test_query_deserves_freshness(self):
        """Queries with freshness keywords should trigger QDF."""
        from resync.knowledge.retrieval.freshness import FreshnessScorer

        scorer = FreshnessScorer()

        assert scorer.query_deserves_freshness("what are the latest updates")
        assert scorer.query_deserves_freshness("show me recent changes")
        assert not scorer.query_deserves_freshness("how to configure backup")


# PR5: Authority and Spam Detection Tests
class TestAuthorityScorer:
    """Test suite for authority scoring."""

    def test_doc_type_scoring(self):
        """Policy docs should score higher than blog posts."""
        from resync.knowledge.retrieval.authority import AuthorityScorer

        scorer = AuthorityScorer()

        policy_score = scorer.score_doc_type("policy")
        manual_score = scorer.score_doc_type("manual")
        blog_score = scorer.score_doc_type("blog")
        forum_score = scorer.score_doc_type("forum")

        assert policy_score > manual_score > blog_score > forum_score

    def test_source_tier_scoring(self):
        """Verified sources should score higher than community."""
        from resync.knowledge.retrieval.authority import AuthorityScorer

        scorer = AuthorityScorer()

        verified = scorer.score_source("verified")
        official = scorer.score_source("official")
        community = scorer.score_source("community")
        generated = scorer.score_source("generated")

        assert verified > official > community > generated

    def test_combined_authority_score(self):
        """Combined score should weight all factors."""
        from resync.knowledge.retrieval.authority import AuthorityScorer

        scorer = AuthorityScorer()

        high_authority = {
            "metadata": {
                "doc_type": "policy",
                "source_tier": "verified",
                "authority_tier": 1,
            }
        }

        low_authority = {
            "metadata": {
                "doc_type": "forum",
                "source_tier": "community",
                "authority_tier": 5,
            }
        }

        assert scorer.calculate_authority_score(high_authority) > scorer.calculate_authority_score(low_authority)


class TestSemanticSpamDetector:
    """Test suite for spam detection."""

    def test_short_content_flagged(self):
        """Very short content should increase spam score."""
        from resync.knowledge.retrieval.authority import SemanticSpamDetector

        detector = SemanticSpamDetector()

        short_doc = {"content": "Buy now!", "metadata": {}}
        normal_doc = {
            "content": "This is a normal document with sufficient content to be considered legitimate.",
            "metadata": {"doc_type": "manual", "source_file": "test.md", "last_updated": "2024-01-01"},
        }

        short_score = detector.calculate_spam_score(short_doc)
        normal_score = detector.calculate_spam_score(normal_doc)

        assert short_score > normal_score

    def test_missing_metadata_increases_score(self):
        """Missing metadata should increase spam likelihood."""
        from resync.knowledge.retrieval.authority import SemanticSpamDetector

        detector = SemanticSpamDetector()

        complete_metadata = {
            "content": "Normal content with enough text.",
            "metadata": {
                "doc_type": "manual",
                "source_file": "test.md",
                "last_updated": "2024-01-01",
            },
        }

        missing_metadata = {
            "content": "Normal content with enough text.",
            "metadata": {},
        }

        complete_score = detector.calculate_spam_score(complete_metadata)
        missing_score = detector.calculate_spam_score(missing_metadata)

        assert missing_score > complete_score

    def test_suspicious_patterns_detected(self):
        """Known spam patterns should be detected."""
        from resync.knowledge.retrieval.authority import SemanticSpamDetector

        detector = SemanticSpamDetector()

        spam_doc = {
            "content": "Click here now! Limited time offer! Buy now and get 100% free!",
            "metadata": {},
        }

        clean_doc = {
            "content": "This document describes the configuration process for the backup system.",
            "metadata": {"doc_type": "manual"},
        }

        assert detector.calculate_spam_score(spam_doc) > detector.calculate_spam_score(clean_doc)

    def test_filter_spam_removes_suspicious(self):
        """filter_spam should remove documents above threshold."""
        from resync.knowledge.retrieval.authority import SemanticSpamDetector, SpamDetectionConfig

        config = SpamDetectionConfig(threshold=0.3)
        detector = SemanticSpamDetector(config)

        docs = [
            {"content": "Buy now! Click here! Free money!", "metadata": {}},
            {
                "content": "This is a legitimate technical document about system administration.",
                "metadata": {"doc_type": "manual", "source_file": "admin.md", "last_updated": "2024-01-01"},
            },
        ]

        filtered = detector.filter_spam(docs, log_filtered=False)

        # Should filter out the spam doc
        assert len(filtered) <= len(docs)


class TestMultiSignalRerank:
    """Test suite for multi-signal reranking."""

    def test_multi_signal_combines_scores(self):
        """Multi-signal rerank should combine all signals."""
        from resync.knowledge.retrieval.authority import apply_multi_signal_rerank, MultiSignalConfig

        docs = [
            {
                "document_id": "doc1",
                "content": "High authority, fresh document about system configuration.",
                "score": 0.9,
                "metadata": {
                    "doc_type": "policy",
                    "authority_tier": 1,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                    "is_deprecated": False,
                },
            },
            {
                "document_id": "doc2",
                "content": "Low authority, old forum post.",
                "score": 0.95,  # Higher relevance but lower authority
                "metadata": {
                    "doc_type": "forum",
                    "authority_tier": 5,
                    "last_updated": (datetime.now(timezone.utc) - timedelta(days=365)).isoformat(),
                    "is_deprecated": False,
                },
            },
        ]

        config = MultiSignalConfig(
            relevance_weight=0.4,
            freshness_weight=0.3,
            authority_weight=0.3,
        )

        ranked = apply_multi_signal_rerank(docs, config=config)

        # All docs should have signal breakdown
        for doc in ranked:
            assert "_signal_breakdown" in doc
            assert "relevance" in doc["_signal_breakdown"]
            assert "freshness" in doc["_signal_breakdown"]
            assert "authority" in doc["_signal_breakdown"]


class TestInferDocType:
    """Test suite for doc_type inference."""

    def test_infer_doc_type_from_filename(self):
        """Should infer doc type from source filename."""
        from resync.knowledge.retrieval.authority import infer_doc_type

        assert infer_doc_type("security_policy.md") == "policy"
        assert infer_doc_type("user_manual.pdf") == "manual"
        assert infer_doc_type("api_reference.html") == "api_doc"
        assert infer_doc_type("kb_article_001.md") == "knowledge_base"
        assert infer_doc_type("blog_post_2024.md") == "blog"
        assert infer_doc_type("forum_discussion.html") == "forum"
        assert infer_doc_type("random_file.txt") == "unknown"


# Integration test
class TestRAGIntegration:
    """Integration tests for full RAG pipeline with v5.7.0 features."""

    def test_full_pipeline_metadata_flow(self):
        """Metadata should flow correctly through the pipeline."""
        from resync.knowledge.ingestion.advanced_chunking import ChunkMetadata, ChunkType

        metadata = ChunkMetadata(
            source_file="admin_manual.md",
            document_title="Administration Manual",
            chunk_index=0,
            section_path="Chapter 1 > Configuration",
            chunk_type=ChunkType.TEXT,
            doc_type="manual",
            source_tier="official",
            authority_tier=2,
            last_updated="2024-12-15T00:00:00Z",
            is_deprecated=False,
            platform="all",
            environment="prod",
        )

        metadata_dict = metadata.to_dict()

        # All v5.7.0 fields should be present
        assert metadata_dict["doc_type"] == "manual"
        assert metadata_dict["source_tier"] == "official"
        assert metadata_dict["authority_tier"] == 2
        assert metadata_dict["last_updated"] == "2024-12-15T00:00:00Z"
        assert metadata_dict["is_deprecated"] is False
        assert metadata_dict["platform"] == "all"
        assert metadata_dict["environment"] == "prod"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
