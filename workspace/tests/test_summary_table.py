"""Tests for the summary table renderer component."""

from token_report import render_summary_table


class TestSummaryTable:
    """Tests for the render_summary_table function."""

    def test_correct_values(self):
        """Test summary table with correct token counts and cost formatting.

        Given two agent-total dicts and a grand-total dict with known values,
        verify the returned HTML contains the correctly formatted token counts
        (with commas) and costs (6 dp) for each row.
        """
        agent_totals = [
            {
                "agent": "agent_a",
                "input_tokens": 1000000,
                "output_tokens": 500000,
                "cache_read_tokens": 200000,
                "cache_write_tokens": 50000,
                "cost_usd": 0.123456,
            },
            {
                "agent": "agent_b",
                "input_tokens": 2000000,
                "output_tokens": 1000000,
                "cache_read_tokens": 400000,
                "cache_write_tokens": 100000,
                "cost_usd": 0.246789,
            },
        ]

        grand_total = {
            "agent": "Total",
            "input_tokens": 3000000,
            "output_tokens": 1500000,
            "cache_read_tokens": 600000,
            "cache_write_tokens": 150000,
            "cost_usd": 0.370245,
        }

        html = render_summary_table(agent_totals, grand_total)

        # Verify HTML structure
        assert "<table>" in html
        assert "</table>" in html

        # Verify agent_a values with thousands separators
        assert "agent_a" in html
        assert "1,000,000" in html  # input_tokens for agent_a
        assert "500,000" in html  # output_tokens for agent_a
        assert "200,000" in html  # cache_read_tokens for agent_a
        assert "50,000" in html  # cache_write_tokens for agent_a
        assert "0.123456" in html  # cost_usd for agent_a

        # Verify agent_b values with thousands separators
        assert "agent_b" in html
        assert "2,000,000" in html  # input_tokens for agent_b
        assert "1,000,000" in html  # output_tokens for agent_b
        assert "400,000" in html  # cache_read_tokens for agent_b
        assert "100,000" in html  # cache_write_tokens for agent_b
        assert "0.246789" in html  # cost_usd for agent_b

        # Verify total row with correctly summed values
        assert "Total" in html
        assert "3,000,000" in html  # total input_tokens
        assert "1,500,000" in html  # total output_tokens
        assert "600,000" in html  # total cache_read_tokens
        assert "150,000" in html  # total cache_write_tokens
        assert "0.370245" in html  # total cost_usd

    def test_grand_total_row(self):
        """Test that grand total row is present and correctly formatted.

        Verify the HTML contains the text "Total" and the correctly summed
        values in the final row.
        """
        agent_totals = [
            {
                "agent": "agent_x",
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_tokens": 25,
                "cache_write_tokens": 10,
                "cost_usd": 0.001234,
            },
        ]

        grand_total = {
            "agent": "Total",
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 25,
            "cache_write_tokens": 10,
            "cost_usd": 0.001234,
        }

        html = render_summary_table(agent_totals, grand_total)

        # Verify total row exists
        assert "Total" in html
        assert "class='total-row'" in html

        # Verify total row contains correct values
        assert "100" in html
        assert "50" in html
        assert "25" in html
        assert "10" in html
        assert "0.001234" in html

    def test_empty_agent_list(self):
        """Test summary table with empty agent list.

        Verify that render_summary_table with empty agent list returns
        a valid HTML table containing only the header and grand-total row
        without raising an exception.
        """
        agent_totals = []

        grand_total = {
            "agent": "Total",
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.0,
        }

        html = render_summary_table(agent_totals, grand_total)

        # Verify HTML structure
        assert "<table>" in html
        assert "</table>" in html

        # Verify header is present
        assert "Agent" in html
        assert "Input Tokens" in html
        assert "Output Tokens" in html
        assert "Cache Read Tokens" in html
        assert "Cache Write Tokens" in html
        assert "Total Cost (USD)" in html

        # Verify total row is present
        assert "Total" in html
        assert "0" in html
        assert "0.000000" in html

    def test_header_structure(self):
        """Test that table has correct header row with all required columns."""
        agent_totals = []
        grand_total = {
            "agent": "Total",
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.0,
        }

        html = render_summary_table(agent_totals, grand_total)

        # Verify header columns
        assert "<th>Agent</th>" in html
        assert "<th style='text-align: right;'>Input Tokens</th>" in html
        assert "<th style='text-align: right;'>Output Tokens</th>" in html
        assert (
            "<th style='text-align: right;'>Cache Read Tokens</th>" in html
        )
        assert (
            "<th style='text-align: right;'>Cache Write Tokens</th>" in html
        )
        assert (
            "<th style='text-align: right;'>Total Cost (USD)</th>" in html
        )

    def test_multiple_agents_order(self):
        """Test that agent rows appear in the same order as input list."""
        agent_totals = [
            {
                "agent": "zebra",
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_tokens": 25,
                "cache_write_tokens": 10,
                "cost_usd": 0.001,
            },
            {
                "agent": "alpha",
                "input_tokens": 200,
                "output_tokens": 100,
                "cache_read_tokens": 50,
                "cache_write_tokens": 20,
                "cost_usd": 0.002,
            },
            {
                "agent": "beta",
                "input_tokens": 300,
                "output_tokens": 150,
                "cache_read_tokens": 75,
                "cache_write_tokens": 30,
                "cost_usd": 0.003,
            },
        ]

        grand_total = {
            "agent": "Total",
            "input_tokens": 600,
            "output_tokens": 300,
            "cache_read_tokens": 150,
            "cache_write_tokens": 60,
            "cost_usd": 0.006,
        }

        html = render_summary_table(agent_totals, grand_total)

        # Find positions of agent names in HTML
        zebra_pos = html.find("zebra")
        alpha_pos = html.find("alpha")
        beta_pos = html.find("beta")
        total_pos = html.find("class='total-row'")

        # Verify order: zebra, alpha, beta, then total row
        assert zebra_pos < alpha_pos < beta_pos < total_pos, (
            f"Agents not in expected order. "
            f"zebra={zebra_pos}, alpha={alpha_pos}, "
            f"beta={beta_pos}, total={total_pos}"
        )

    def test_cost_precision(self):
        """Test that costs are formatted to exactly 6 decimal places."""
        agent_totals = [
            {
                "agent": "test_agent",
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_tokens": 25,
                "cache_write_tokens": 10,
                "cost_usd": 0.1,  # Should be formatted as 0.100000
            },
        ]

        grand_total = {
            "agent": "Total",
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_tokens": 25,
            "cache_write_tokens": 10,
            "cost_usd": 0.1,
        }

        html = render_summary_table(agent_totals, grand_total)

        # Verify 6 decimal places
        assert "0.100000" in html

    def test_thousands_separators(self):
        """Test that integer token counts have thousands separators."""
        agent_totals = [
            {
                "agent": "test_agent",
                "input_tokens": 1234567,
                "output_tokens": 9876543,
                "cache_read_tokens": 111111,
                "cache_write_tokens": 222222,
                "cost_usd": 0.123456,
            },
        ]

        grand_total = {
            "agent": "Total",
            "input_tokens": 1234567,
            "output_tokens": 9876543,
            "cache_read_tokens": 111111,
            "cache_write_tokens": 222222,
            "cost_usd": 0.123456,
        }

        html = render_summary_table(agent_totals, grand_total)

        # Verify thousands separators in all token counts
        assert "1,234,567" in html  # input_tokens
        assert "9,876,543" in html  # output_tokens
        assert "111,111" in html  # cache_read_tokens
        assert "222,222" in html  # cache_write_tokens
