"""
run_report.py — Pipeline Run Report Generator

Reads the pipeline run log (run-log.jsonl) and per-agent conversation logs
(*_log.jsonl files in the agent_conversation_logs directory), then produces
a self-contained single-page HTML report with:
  - Run Log section: timestamped entries from each agent
  - Token Usage section: per-agent token counts, cost, and an interactive
    Chart.js timeline

Usage:
    python run_report.py [--run-log <path>] [--conv-log-dir <path>] [--output-dir <path>]

Output:
    <output-dir>/run-report_YYYY-MM-DD_HH-MM-SS.html
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# 1. CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an HTML pipeline run report from agent logs.",
    )
    parser.add_argument(
        "--run-log",
        default=str(Path(__file__).parent / "workspace" / ".sentinels" / "run-log.jsonl"),
        metavar="PATH",
        help="Path to the run-log.jsonl file (default: workspace/.sentinels/run-log.jsonl).",
    )
    parser.add_argument(
        "--conv-log-dir",
        default=str(Path(__file__).parent / "workspace" / ".sentinels" / "agent_conversation_logs"),
        metavar="PATH",
        help="Path to directory containing *_log.jsonl conversation log files "
             "(default: workspace/.sentinels/agent_conversation_logs).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).parent / "workspace"),
        metavar="PATH",
        help="Directory to write the HTML report into (default: workspace/).",
    )
    parser.add_argument(
        "--git-log",
        default=str(Path(__file__).parent / "workspace" / ".sentinels" / "git_log.jsonl"),
        metavar="PATH",
        help="Path to the git_log.jsonl file (default: workspace/.sentinels/git_log.jsonl).",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# 2. Run Log Loader
# ---------------------------------------------------------------------------

def load_run_log(run_log_path: Path) -> list[dict]:
    """Load entries from run-log.jsonl. Returns an empty list if file is absent."""
    if not run_log_path.exists():
        return []
    entries = []
    with open(run_log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                print(
                    f"Warning: skipping unparseable run-log line: {line}",
                    file=sys.stderr,
                )
    return entries


# ---------------------------------------------------------------------------
# 3. Git Log Loader
# ---------------------------------------------------------------------------

def load_git_log(git_log_path: Path) -> list[dict]:
    """Load entries from git_log.jsonl. Returns an empty list if file is absent."""
    if not git_log_path.exists():
        return []
    entries = []
    with open(git_log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                print(
                    f"Warning: skipping unparseable git-log line: {line}",
                    file=sys.stderr,
                )
    return entries


# ---------------------------------------------------------------------------
# 5. Conversation Log Loaders
# ---------------------------------------------------------------------------

def load_conversation_entries(conv_log_dir: Path) -> list[dict]:
    """Load every raw entry from *_log.jsonl files, sorted chronologically.

    Used to render the Conversation History section.  Returns an empty list
    when the directory does not exist.
    """
    if not conv_log_dir.exists():
        return []
    entries = []
    for jsonl_file in sorted(conv_log_dir.glob("*_log.jsonl")):
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    print(
                        f"Warning: skipping unparseable line in {jsonl_file.name}: {line.rstrip()}",
                        file=sys.stderr,
                    )
    entries.sort(key=lambda e: e.get("ts", ""))
    return entries


def load_conversation_records(conv_log_dir: Path) -> list[dict]:
    """Walk conv_log_dir and return token usage records derived from conversation logs.

    Reads *_log.jsonl files written by conversation_logger.py.  Only
    ``assistant`` and ``result`` role entries carry token data:

    - ``assistant`` entries contribute per-message token counts; cost_usd is 0.
    - ``result`` entries contribute the session-total cost_usd; token counts
      are zeroed to avoid double-counting with the per-message assistant entries.

    Returns an empty list (rather than exiting) so the report can still be
    generated even when no conversation logs exist yet.
    """
    if not conv_log_dir.exists():
        return []
    records = []
    for jsonl_file in sorted(conv_log_dir.glob("*_log.jsonl")):
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    print(
                        f"Warning: skipping unparseable line in {jsonl_file.name}: {line.rstrip()}",
                        file=sys.stderr,
                    )
                    continue

                role = entry.get("role")
                if role == "assistant":
                    records.append({
                        "ts": entry["ts"],
                        "agent": entry["agent"],
                        "input_tokens": entry.get("input_tokens", 0),
                        "output_tokens": entry.get("output_tokens", 0),
                        "cache_read_tokens": entry.get("cache_read_tokens", 0),
                        "cache_write_tokens": entry.get("cache_write_tokens", 0),
                        "cost_usd": 0.0,
                    })
                elif role == "result":
                    records.append({
                        "ts": entry["ts"],
                        "agent": entry["agent"],
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cache_read_tokens": 0,
                        "cache_write_tokens": 0,
                        "cost_usd": entry.get("cost_usd", 0.0),
                    })
    return records


# ---------------------------------------------------------------------------
# 4. Token Aggregator
# ---------------------------------------------------------------------------

def aggregate(records: list[dict]) -> dict:
    """Aggregate token records into minute buckets and per-agent totals."""
    def _zero() -> dict:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.0,
        }

    bucket_map: dict = defaultdict(lambda: defaultdict(_zero))
    agent_map: dict = defaultdict(_zero)
    numeric_keys = (
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_write_tokens",
        "cost_usd",
    )

    for rec in records:
        ts: str = rec["ts"]
        agent: str = rec["agent"]
        minute = ts[:16] + ":00Z"
        bucket = bucket_map[minute][agent]
        totals = agent_map[agent]
        for key in numeric_keys:
            bucket[key] += rec.get(key, 0)
            totals[key] += rec.get(key, 0)

    buckets = []
    for minute in sorted(bucket_map.keys()):
        for agent in sorted(bucket_map[minute].keys()):
            entry = {"minute": minute, "agent": agent}
            entry.update(bucket_map[minute][agent])
            buckets.append(entry)

    agent_totals = {agent: dict(totals) for agent, totals in sorted(agent_map.items())}

    grand_total = _zero()
    for totals in agent_map.values():
        for key in numeric_keys:
            grand_total[key] += totals[key]

    return {
        "buckets": buckets,
        "agent_totals": agent_totals,
        "grand_total": grand_total,
    }


# ---------------------------------------------------------------------------
# 5. Chart.js bundle fetcher
# ---------------------------------------------------------------------------

CHARTJS_CDN_URL = "https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js"


def fetch_chartjs(cache_dir: Path) -> str:
    """Return the Chart.js UMD bundle, using a local cache to avoid re-downloading."""
    cache_path = cache_dir / "chart.umd.min.js"
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path.read_text(encoding="utf-8")
    cache_dir.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(CHARTJS_CDN_URL) as response:
        content = response.read().decode("utf-8")
    cache_path.write_text(content, encoding="utf-8")
    return content


# ---------------------------------------------------------------------------
# 6. HTML Builder
# ---------------------------------------------------------------------------

_MAX_CONTENT_CHARS = 500


def _esc(text: str) -> str:
    """Minimal HTML escaping for safe inline insertion."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _truncate(text: str, limit: int = _MAX_CONTENT_CHARS) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _render_content_html(entry: dict) -> str:
    """Return an HTML fragment summarising the content of one conversation entry."""
    role = entry.get("role", "")
    content = entry.get("content", "")

    if role == "system":
        return f"<em>subtype: {_esc(str(entry.get('subtype', '')))}</em>"

    if role == "result":
        stop = _esc(str(entry.get("stop_reason", "")))
        turns = entry.get("num_turns", "")
        cost = entry.get("cost_usd", 0.0)
        return f"<em>stop={stop} &nbsp; turns={turns} &nbsp; cost=${cost:.6f}</em>"

    if role == "assistant":
        parts: list[str] = []
        if isinstance(content, list):
            for block in content:
                btype = block.get("type", "")
                if btype == "text":
                    parts.append(_esc(_truncate(block.get("text", ""))))
                elif btype == "tool_use":
                    inp_str = _truncate(json.dumps(block.get("input", {}), ensure_ascii=False), 200)
                    parts.append(f"<code>[tool:{_esc(block.get('name', ''))}] {_esc(inp_str)}</code>")
                elif btype == "tool_result":
                    status = "error" if block.get("is_error") else "ok"
                    res = _truncate(str(block.get("content", "")), 200)
                    parts.append(f"<code>[result:{status}] {_esc(res)}</code>")
                elif btype == "thinking":
                    parts.append(f"<em>[thinking] {_esc(_truncate(block.get('thinking', ''), 200))}</em>")
        elif isinstance(content, str):
            parts.append(_esc(_truncate(content)))
        return "<br>".join(parts) if parts else "<em>(empty)</em>"

    if role == "user":
        if isinstance(content, list):
            parts = []
            for block in content:
                if block.get("type") == "tool_result":
                    status = "error" if block.get("is_error") else "ok"
                    res = _truncate(str(block.get("content", "")), 200)
                    parts.append(f"<code>[result:{status}] {_esc(res)}</code>")
            return "<br>".join(parts) if parts else "<em>(empty)</em>"
        return _esc(_truncate(str(content)))

    if role == "tool":
        tool_name = _esc(entry.get("tool_name", ""))
        args_str = _truncate(json.dumps(entry.get("arguments", {}), ensure_ascii=False), 200)
        result = _truncate(str(content))
        return (
            f"<code>[call: {tool_name}]</code> {_esc(args_str)}"
            f"<br><code>[output]</code> {_esc(result)}"
        )

    # Ollama assistant messages or any other role — best-effort
    if isinstance(content, str):
        rendered = _esc(_truncate(content))
    else:
        rendered = _esc(_truncate(json.dumps(content, ensure_ascii=False)))
    tool_calls = entry.get("tool_calls")
    if tool_calls:
        tc_parts = []
        for tc in tool_calls:
            args_str = _truncate(json.dumps(tc.get("arguments", {}), ensure_ascii=False), 200)
            tc_parts.append(f"<code>[tool:{_esc(tc.get('name', ''))}] {_esc(args_str)}</code>")
        rendered = (rendered + "<br>" if rendered else "") + "<br>".join(tc_parts)
    return rendered or "<em>(empty)</em>"


def _build_conversation_history_html(entries: list[dict]) -> str:
    """Build one collapsible <details> block per agent, collapsed by default."""
    if not entries:
        return "  <p><em>No conversation log entries recorded.</em></p>\n"

    # Group entries by agent, preserving the global chronological order within each group.
    agent_entries: dict[str, list[dict]] = defaultdict(list)
    for entry in entries:
        agent_entries[entry.get("agent", "unknown")].append(entry)

    html_parts: list[str] = []
    for agent in sorted(agent_entries.keys()):
        agent_list = agent_entries[agent]
        count = len(agent_list)
        rows: list[str] = []
        for entry in agent_list:
            ts = _esc(entry.get("ts", ""))
            context = _esc(entry.get("context", ""))
            role = entry.get("role", "")
            in_tok = entry.get("input_tokens", 0)
            out_tok = entry.get("output_tokens", 0)
            tok_str = f"in={in_tok:,} out={out_tok:,}" if (in_tok or out_tok) else ""
            rows.append(
                f"      <tr>"
                f'<td class="ts-col">{ts}</td>'
                f'<td class="ctx-col">{context}</td>'
                f'<td class="role-col role-{_esc(role)}"><code>{_esc(role)}</code></td>'
                f'<td class="content-col">{_render_content_html(entry)}</td>'
                f'<td class="tok-col">{tok_str}</td>'
                f"</tr>"
            )
        table = (
            "    <table>\n"
            "      <thead>\n"
            "        <tr>"
            "<th>Timestamp</th>"
            "<th>Context</th>"
            "<th>Role</th>"
            "<th>Content</th>"
            "<th>Tokens</th>"
            "</tr>\n"
            "      </thead>\n"
            "      <tbody>\n"
            + "\n".join(rows) + "\n"
            "      </tbody>\n"
            "    </table>\n"
        )
        html_parts.append(
            f"  <details>\n"
            f"    <summary>"
            f"<strong>{_esc(agent)}</strong>"
            f' <span class="entry-count">({count} entries)</span>'
            f"</summary>\n"
            + table
            + "  </details>\n"
        )

    return "\n".join(html_parts) + "\n"


def _build_run_log_html(entries: list[dict]) -> str:
    if not entries:
        return "  <p><em>No run log entries recorded.</em></p>\n"

    rows = []
    for entry in entries:
        ts = entry.get("timestamp", "")
        agent = entry.get("agent_name", "")
        msg = entry.get("message", "")
        rows.append(
            f"    <tr>"
            f"<td>{ts}</td>"
            f"<td>{agent}</td>"
            f"<td>{msg}</td>"
            f"</tr>"
        )

    return (
        "  <table>\n"
        "    <thead>\n"
        "      <tr><th>Timestamp</th><th>Agent</th><th>Message</th></tr>\n"
        "    </thead>\n"
        "    <tbody>\n"
        + "\n".join(rows) + "\n"
        "    </tbody>\n"
        "  </table>\n"
    )


def _build_git_log_html(entries: list[dict]) -> str:
    if not entries:
        return "  <p><em>No git commits recorded during this run.</em></p>\n"

    rows = []
    for entry in entries:
        ts = entry.get("timestamp", "")
        committer = entry.get("committer", "")
        message = entry.get("message", "")
        rows.append(
            f"    <tr>"
            f"<td>{ts}</td>"
            f"<td>{committer}</td>"
            f"<td>{message}</td>"
            f"</tr>"
        )

    return (
        "  <table>\n"
        "    <thead>\n"
        "      <tr><th>Timestamp</th><th>Committer</th><th>Message</th></tr>\n"
        "    </thead>\n"
        "    <tbody>\n"
        + "\n".join(rows) + "\n"
        "    </tbody>\n"
        "  </table>\n"
    )


def _build_token_html(agg: dict) -> str:
    if not agg["agent_totals"]:
        return "  <p><em>No token usage data recorded.</em></p>\n"

    rows = []
    for agent, totals in sorted(agg["agent_totals"].items()):
        rows.append(
            f"    <tr>"
            f"<td>{agent}</td>"
            f"<td>{totals['input_tokens']:,}</td>"
            f"<td>{totals['output_tokens']:,}</td>"
            f"<td>{totals['cache_read_tokens']:,}</td>"
            f"<td>{totals['cache_write_tokens']:,}</td>"
            f"<td>{totals['cost_usd']:.6f}</td>"
            f"</tr>"
        )
    tbody = "\n".join(rows)

    gt = agg["grand_total"]
    tfoot_row = (
        f"    <tr>"
        f"<td><strong>Grand Total</strong></td>"
        f"<td>{gt['input_tokens']:,}</td>"
        f"<td>{gt['output_tokens']:,}</td>"
        f"<td>{gt['cache_read_tokens']:,}</td>"
        f"<td>{gt['cache_write_tokens']:,}</td>"
        f"<td>{gt['cost_usd']:.6f}</td>"
        f"</tr>"
    )

    return (
        "  <table>\n"
        "    <thead>\n"
        "      <tr>\n"
        "        <th>Agent</th>\n"
        "        <th>Input Tokens</th>\n"
        "        <th>Output Tokens</th>\n"
        "        <th>Cache Read</th>\n"
        "        <th>Cache Write</th>\n"
        "        <th>Total Cost (USD)</th>\n"
        "      </tr>\n"
        "    </thead>\n"
        "    <tbody>\n"
        + tbody + "\n"
        "    </tbody>\n"
        "    <tfoot>\n"
        + tfoot_row + "\n"
        "    </tfoot>\n"
        "  </table>\n"
    )


def _build_chart_js(agg: dict) -> str:
    all_minutes = sorted({b["minute"] for b in agg["buckets"]})
    all_agents = sorted(agg["agent_totals"].keys())
    bucket_lookup = {(b["minute"], b["agent"]): b for b in agg["buckets"]}

    token_series = []
    for agent in all_agents:
        for token_type in ["input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"]:
            data = [
                bucket_lookup.get((minute, agent), {}).get(token_type, 0)
                for minute in all_minutes
            ]
            token_series.append({"label": f"{agent} \u00b7 {token_type}", "data": data})

    cost_series = []
    for agent in all_agents:
        data = [
            bucket_lookup.get((minute, agent), {}).get("cost_usd", 0)
            for minute in all_minutes
        ]
        cost_series.append({"label": f"{agent} \u00b7 cost_usd", "data": data})

    raw_data_json = json.dumps({
        "labels": all_minutes,
        "token_series": token_series,
        "cost_series": cost_series,
    })

    return """\
const RAW_DATA = """ + raw_data_json + """;

(function () {
  var ctx = document.getElementById('tokenChart').getContext('2d');
  window.chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: RAW_DATA.labels,
      datasets: RAW_DATA.token_series.map(function(s) {
        return { label: s.label, data: s.data, fill: false, tension: 0.1 };
      })
    },
    options: {
      plugins: { title: { display: true, text: 'Token Usage Over Time' } },
      scales: { y: { title: { display: true, text: 'Tokens' } } }
    }
  });

  var currentView = 'tokens';

  function renderChart(labels, datasets) {
    window.chart.data.labels = labels;
    window.chart.data.datasets = datasets.map(function(s) {
      return { label: s.label, data: s.data, fill: false, tension: 0.1 };
    });
    window.chart.update();
  }

  function getFilteredIndices() {
    var fromVal = document.getElementById('fromPicker').value;
    var toVal = document.getElementById('toPicker').value;
    var indices = [];
    RAW_DATA.labels.forEach(function(label, idx) {
      var labelSlice = label.slice(0, 16);
      if (fromVal && labelSlice < fromVal) { return; }
      if (toVal && labelSlice > toVal) { return; }
      indices.push(idx);
    });
    return indices;
  }

  function applyFilter() {
    var indices = getFilteredIndices();
    var filteredLabels = indices.map(function(i) { return RAW_DATA.labels[i]; });
    var series = currentView === 'tokens' ? RAW_DATA.token_series : RAW_DATA.cost_series;
    var filteredDatasets = series.map(function(s) {
      return { label: s.label, data: indices.map(function(i) { return s.data[i]; }) };
    });
    renderChart(filteredLabels, filteredDatasets);
  }

  document.getElementById('toggleBtn').addEventListener('click', function() {
    if (currentView === 'tokens') {
      currentView = 'cost';
      this.textContent = 'Switch to Token Counts';
      window.chart.options.plugins.title.text = 'Token Cost Over Time';
      window.chart.options.scales.y.title.text = 'Cost (USD)';
    } else {
      currentView = 'tokens';
      this.textContent = 'Switch to Cost USD';
      window.chart.options.plugins.title.text = 'Token Usage Over Time';
      window.chart.options.scales.y.title.text = 'Tokens';
    }
    applyFilter();
  });

  document.getElementById('fromPicker').addEventListener('change', applyFilter);
  document.getElementById('toPicker').addEventListener('change', applyFilter);
  document.getElementById('resetBtn').addEventListener('click', function() {
    document.getElementById('fromPicker').value = '';
    document.getElementById('toPicker').value = '';
    applyFilter();
  });
})();
"""


def build_html(
    run_log_entries: list[dict],
    agg: dict,
    chartjs_src: str,
    git_log_entries: list[dict] | None = None,
    conv_entries: list[dict] | None = None,
) -> str:
    run_log_html = _build_run_log_html(run_log_entries)
    git_log_html = _build_git_log_html(git_log_entries or [])
    token_table_html = _build_token_html(agg)
    conv_history_html = _build_conversation_history_html(conv_entries or [])
    has_chart_data = bool(agg["agent_totals"])

    chart_section = ""
    chart_script = ""
    if has_chart_data:
        chart_section = (
            "  <div id=\"chart-container\">\n"
            "    <div id=\"controls\">\n"
            "      <button id=\"toggleBtn\">Switch to Cost USD</button>\n"
            "      <label>From: <input type=\"datetime-local\" id=\"fromPicker\"></label>\n"
            "      <label>To: <input type=\"datetime-local\" id=\"toPicker\"></label>\n"
            "      <button id=\"resetBtn\">Reset</button>\n"
            "    </div>\n"
            "    <canvas id=\"tokenChart\"></canvas>\n"
            "  </div>\n"
        )
        chart_script = (
            f"<script>{chartjs_src}</script>\n"
            f"<script>\n{_build_chart_js(agg)}\n</script>\n"
        )

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <title>Pipeline Run Report</title>\n"
        "  <style>\n"
        "    body { font-family: sans-serif; margin: 2rem; }\n"
        "    h1 { margin-bottom: 0.25rem; }\n"
        "    h2 { margin-top: 2rem; margin-bottom: 1rem; border-bottom: 1px solid #ccc; padding-bottom: 0.25rem; }\n"
        "    table { border-collapse: collapse; width: 100%; }\n"
        "    th, td { padding: 6px 12px; border: 1px solid #ccc; text-align: right; }\n"
        "    th:first-child, td:first-child { text-align: left; }\n"
        "    thead { background-color: #f0f0f0; }\n"
        "    tfoot { font-weight: bold; background-color: #e8e8e8; }\n"
        "    #chart-container { margin-top: 2rem; }\n"
        "    #controls { margin-bottom: 1rem; }\n"
        "    details { margin-bottom: 0.75rem; border: 1px solid #ddd; border-radius: 4px; }\n"
        "    details > summary { cursor: pointer; padding: 0.5rem 0.75rem; background: #f7f7f7;\n"
        "                        border-radius: 4px; user-select: none; list-style: none; }\n"
        "    details > summary::-webkit-details-marker { display: none; }\n"
        "    details > summary::before { content: '▶\\00a0'; font-size: 0.75em; }\n"
        "    details[open] > summary::before { content: '▼\\00a0'; }\n"
        "    details > table { border-radius: 0 0 4px 4px; border-top: none; }\n"
        "    .entry-count { font-weight: normal; color: #666; font-size: 0.9em; }\n"
        "    .ts-col  { white-space: nowrap; font-size: 0.85em; text-align: left; }\n"
        "    .ctx-col { white-space: nowrap; font-size: 0.85em; text-align: left; }\n"
        "    .role-col { white-space: nowrap; text-align: left; }\n"
        "    .content-col { text-align: left; word-break: break-word; max-width: 55vw; }\n"
        "    .tok-col { white-space: nowrap; font-size: 0.85em; }\n"
        "    .role-assistant code { color: #1a5276; }\n"
        "    .role-user     code { color: #145a32; }\n"
        "    .role-system   code { color: #7d6608; }\n"
        "    .role-result   code { color: #6e2f8a; }\n"
        "    .role-tool     code { color: #784212; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <h1>Pipeline Run Report</h1>\n"
        "  <h2>Run Log</h2>\n"
        + run_log_html
        + "  <h2>Git Commits</h2>\n"
        + git_log_html
        + "  <h2>Token Usage</h2>\n"
        + token_table_html
        + chart_section
        + "  <h2>Conversation History</h2>\n"
        + conv_history_html
        + chart_script
        + "</body>\n"
        "</html>\n"
    )


# ---------------------------------------------------------------------------
# 7. Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    run_log_path = Path(args.run_log)
    conv_log_dir = Path(args.conv_log_dir)
    output_dir = Path(args.output_dir)
    git_log_path = Path(args.git_log)

    run_log_entries = load_run_log(run_log_path)
    conv_entries = load_conversation_entries(conv_log_dir)
    token_records = load_conversation_records(conv_log_dir)
    git_log_entries = load_git_log(git_log_path)

    if not run_log_entries and not token_records and not conv_entries:
        print("Error: no run log entries and no conversation log records found.", file=sys.stderr)
        sys.exit(1)

    agg = aggregate(token_records)

    cache_dir = Path(__file__).parent / ".chartjs_cache"
    chartjs_src = fetch_chartjs(cache_dir)

    html = build_html(run_log_entries, agg, chartjs_src, git_log_entries, conv_entries)

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = output_dir / f"run-report_{timestamp}.html"
    output_path.write_text(html, encoding="utf-8")

    print(str(output_path.resolve()))


if __name__ == "__main__":
    main()
