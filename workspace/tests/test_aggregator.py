"""Tests for the aggregator component."""

from token_report import aggregate


class TestAggregator:
    """Tests for the aggregator component."""

    def test_minute_bucketing(self):
        """Test minute bucketing with sum aggregation.

        Given four records for the same agent where two share the same minute,
        verify:
        - Exactly three bucket rows (two single records + one combined)
        - Correct summed values in the shared-minute row
        """
        records = [
            {
                "ts": "2026-03-30T12:00:15Z",
                "agent": "test",
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_tokens": 200,
                "cache_write_tokens": 0,
                "cost_usd": 0.001,
            },
            {
                "ts": "2026-03-30T12:00:45Z",  # Same minute
                "agent": "test",
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_tokens": 200,
                "cache_write_tokens": 0,
                "cost_usd": 0.001,
            },
            {
                "ts": "2026-03-30T12:01:15Z",  # Different minute
                "agent": "test",
                "input_tokens": 50,
                "output_tokens": 25,
                "cache_read_tokens": 100,
                "cache_write_tokens": 0,
                "cost_usd": 0.0005,
            },
            {
                "ts": "2026-03-30T12:02:15Z",  # Different minute
                "agent": "test",
                "input_tokens": 75,
                "output_tokens": 37,
                "cache_read_tokens": 150,
                "cache_write_tokens": 10,
                "cost_usd": 0.00075,
            },
        ]

        result = aggregate(records)
        buckets = result["buckets"]

        # Assert exactly three buckets
        assert len(buckets) == 3, (
            f"Expected 3 buckets, got {len(buckets)}"
        )

        # Check the first bucket (combined minute)
        first_bucket = buckets[0]
        assert first_bucket["minute"] == "2026-03-30T12:00:00Z"
        assert first_bucket["agent"] == "test"
        assert first_bucket["input_tokens"] == 200  # 100 + 100
        assert first_bucket["output_tokens"] == 100  # 50 + 50
        assert first_bucket["cache_read_tokens"] == 400  # 200 + 200
        assert first_bucket["cache_write_tokens"] == 0  # 0 + 0
        assert first_bucket["cost_usd"] == 0.002  # 0.001 + 0.001

    def test_multi_agent_totals(self):
        """Test aggregation with multiple agents.

        Given records from two agents, verify:
        - agent_totals contains one entry per agent with correct sums
        - grand_total sums across both agents
        """
        records = [
            {
                "ts": "2026-03-30T12:00:15Z",
                "agent": "agent_a",
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_tokens": 200,
                "cache_write_tokens": 0,
                "cost_usd": 0.001,
            },
            {
                "ts": "2026-03-30T12:01:15Z",
                "agent": "agent_a",
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_tokens": 200,
                "cache_write_tokens": 0,
                "cost_usd": 0.001,
            },
            {
                "ts": "2026-03-30T12:00:15Z",
                "agent": "agent_b",
                "input_tokens": 50,
                "output_tokens": 25,
                "cache_read_tokens": 100,
                "cache_write_tokens": 10,
                "cost_usd": 0.0005,
            },
            {
                "ts": "2026-03-30T12:01:15Z",
                "agent": "agent_b",
                "input_tokens": 50,
                "output_tokens": 25,
                "cache_read_tokens": 100,
                "cache_write_tokens": 10,
                "cost_usd": 0.0005,
            },
        ]

        result = aggregate(records)
        agent_totals = result["agent_totals"]
        grand_total = result["grand_total"]

        # Assert one entry per agent
        assert len(agent_totals) == 2, (
            f"Expected 2 agent totals, got {len(agent_totals)}"
        )

        # Check agent_a totals
        agent_a_total = next(
            (a for a in agent_totals if a["agent"] == "agent_a"), None
        )
        assert agent_a_total is not None
        assert agent_a_total["input_tokens"] == 200
        assert agent_a_total["output_tokens"] == 100
        assert agent_a_total["cache_read_tokens"] == 400
        assert agent_a_total["cache_write_tokens"] == 0
        assert agent_a_total["cost_usd"] == 0.002

        # Check agent_b totals
        agent_b_total = next(
            (a for a in agent_totals if a["agent"] == "agent_b"), None
        )
        assert agent_b_total is not None
        assert agent_b_total["input_tokens"] == 100
        assert agent_b_total["output_tokens"] == 50
        assert agent_b_total["cache_read_tokens"] == 200
        assert agent_b_total["cache_write_tokens"] == 20
        assert agent_b_total["cost_usd"] == 0.001

        # Check grand total
        assert grand_total["agent"] == "Total"
        assert grand_total["input_tokens"] == 300  # 200 + 100
        assert grand_total["output_tokens"] == 150  # 100 + 50
        assert grand_total["cache_read_tokens"] == 600  # 400 + 200
        assert grand_total["cache_write_tokens"] == 20  # 0 + 20
        assert grand_total["cost_usd"] == 0.003  # 0.002 + 0.001

    def test_empty_input(self):
        """Test aggregation with empty input.

        Verify:
        - Returns structure with empty lists
        - grand_total has all fields set to zero
        """
        result = aggregate([])

        # Assert empty buckets
        assert result["buckets"] == [], (
            f"Expected empty buckets, got {result['buckets']}"
        )

        # Assert empty agent_totals
        assert result["agent_totals"] == [], (
            f"Expected empty agent_totals, got {result['agent_totals']}"
        )

        # Assert grand_total with zeros
        grand_total = result["grand_total"]
        assert grand_total["agent"] == "Total"
        assert grand_total["input_tokens"] == 0
        assert grand_total["output_tokens"] == 0
        assert grand_total["cache_read_tokens"] == 0
        assert grand_total["cache_write_tokens"] == 0
        assert grand_total["cost_usd"] == 0.0

    def test_bucket_sorting(self):
        """Test that buckets are sorted by minute then by agent."""
        records = [
            {
                "ts": "2026-03-30T12:02:15Z",
                "agent": "zebra",
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_read_tokens": 20,
                "cache_write_tokens": 0,
                "cost_usd": 0.0001,
            },
            {
                "ts": "2026-03-30T12:01:15Z",
                "agent": "alpha",
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_read_tokens": 20,
                "cache_write_tokens": 0,
                "cost_usd": 0.0001,
            },
            {
                "ts": "2026-03-30T12:01:20Z",
                "agent": "beta",
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_read_tokens": 20,
                "cache_write_tokens": 0,
                "cost_usd": 0.0001,
            },
            {
                "ts": "2026-03-30T12:02:20Z",
                "agent": "alpha",
                "input_tokens": 10,
                "output_tokens": 5,
                "cache_read_tokens": 20,
                "cache_write_tokens": 0,
                "cost_usd": 0.0001,
            },
        ]

        result = aggregate(records)
        buckets = result["buckets"]

        # Assert buckets are sorted by (minute, agent)
        expected_order = [
            ("2026-03-30T12:01:00Z", "alpha"),
            ("2026-03-30T12:01:00Z", "beta"),
            ("2026-03-30T12:02:00Z", "alpha"),
            ("2026-03-30T12:02:00Z", "zebra"),
        ]

        actual_order = [(b["minute"], b["agent"]) for b in buckets]
        assert actual_order == expected_order, (
            f"Expected order {expected_order}, got {actual_order}"
        )
