"""PHOENIX-EVAL Static Visualization Generator.

Reads exported benchmark CSV metrics from results/exports/ and generates:
1. Markdown / ASCII charts under results/charts/visualizations.md
2. Self-contained static HTML + SVG charts under results/charts/visualizations.html

Covers the 7 prioritized benchmark research visualizations:
- Chart 1: Overall Model Performance (Raw Score vs Effective Score vs Safety Failure Rate)
- Chart 2: Multidimensional Capability Radar / Profile (D1-D6)
- Chart 3: Safety Failure Rate by Enterprise Architecture Domain
- Chart 4: Difficulty Tier Degradation Curve (Introductory -> Intermediate -> Advanced)
- Chart 5: Task Family Vulnerability Distribution (T01-T10)
- Chart 6: Counterfactual Paired Sensitivity Outcomes
- Chart 7: Metamorphic Invariant Preservation Rate (MR1-MR6)
"""

import csv
from pathlib import Path
from typing import Any

from phoenix_eval.core.paths import get_paths


def load_csv(csv_path: Path) -> list[dict[str, Any]]:
    """Safely load CSV rows into dictionaries."""
    if not csv_path.is_file():
        return []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def ascii_bar(val: float, max_val: float = 100.0, width: int = 25) -> str:
    """Generate an ASCII bar representation."""
    if max_val <= 0:
        return ""
    ratio = min(max(val / max_val, 0.0), 1.0)
    filled = int(round(ratio * width))
    bar = "█" * filled + "░" * (width - filled)
    return bar


def generate_markdown_visualizations(exports_dir: Path, output_file: Path) -> str:
    """Generate Markdown and ASCII charts from CSV exports."""
    overall = load_csv(exports_dir / "overall_metrics.csv")
    dimensions = load_csv(exports_dir / "dimension_metrics.csv")
    domains = load_csv(exports_dir / "domain_metrics.csv")
    difficulties = load_csv(exports_dir / "difficulty_metrics.csv")
    families = load_csv(exports_dir / "task_family_metrics.csv")
    paired = load_csv(exports_dir / "paired_case_sensitivity.csv")
    metamorphic = load_csv(exports_dir / "metamorphic_results.csv")

    lines: list[str] = [
        "# PHOENIX-EVAL Benchmark Visualizations & Comparative Analytics",
        "",
        "> [!NOTE]",
        "> **SIMULATED BASELINE EXPERIMENTS:**",
        "> All charts below reflect offline mock provider fixtures (`mock-valid-migration`, `mock-unsafe-migration`, `mock-malformed-response`) evaluated during benchmark pipeline calibration and verification. Zero commercial frontier models were evaluated in this campaign.",
        "",
        "---",
        "",
        "## Chart 1: Overall Performance & Safety Failure Discrepancy",
        "",
        "Shows the stark divergence between raw score (rubric fulfillment) and effective score after safety-gate enforcement.",
        "",
        "| Model Identifier | Raw Score (0-100) | Effective Score (0-100) | Safety Failure % | Visual Comparison (Eff vs Raw) |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]

    for m in overall:
        raw = float(m.get("mean_raw_score", 0.0))
        eff = float(m.get("mean_effective_score", 0.0))
        fail = float(m.get("safety_failure_rate", 0.0)) * 100.0
        bar = f"`{ascii_bar(eff, 100.0, 15)}` ({eff:.1f}%)"
        lines.append(
            f"| **{m.get('model_identifier')}** | {raw:.1f} | {eff:.1f} | {fail:.1f}% | {bar} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## Chart 2: Multidimensional Capability Profile (D1–D6)",
            "",
            "Evaluates performance across the 6 deterministic grading dimensions:",
            "- **D1**: Decision Validity",
            "- **D2**: Dependency Ordering",
            "- **D3**: Evidence Grounding",
            "- **D4**: Blocker Identification",
            "- **D5**: Fallback & Uncertainty Handling",
            "- **D6**: Constraint Adherence",
            "",
            "| Dimension | Model | Mean Score | Max | Normalized | Visual Progress |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )

    for d in dimensions:
        dim_name = d.get("dimension_name", "")
        model = d.get("model_identifier", "")
        score = float(d.get("mean_score", 0.0))
        max_s = float(d.get("max_score", 1.0))
        norm = float(d.get("mean_normalized_score", 0.0)) * 100
        lines.append(
            f"| {dim_name} | `{model}` | {score:.2f} | {max_s:.1f} | {norm:.1f}% | `{ascii_bar(norm, 100.0, 12)}` |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## Chart 3: Safety Failure Rate by Enterprise Architecture Domain",
            "",
            "Evaluates whether specific domain environments (Banking, Telecom, Government, Identity, ERP) induce higher vulnerability rates.",
            "",
            "| Enterprise Domain | Model | Samples | Safety Failure Rate | Visual Risk Bar |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )

    for dom in domains:
        dname = dom.get("domain_name", "")
        model = dom.get("model_identifier", "")
        cnt = dom.get("sample_count", "0")
        fail = float(dom.get("safety_failure_rate", 0.0)) * 100.0
        lines.append(
            f"| **{dname.upper()}** | `{model}` | {cnt} | {fail:.1f}% | `{ascii_bar(fail, 100.0, 12)}` |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## Chart 4: Difficulty Tier Degradation Curve",
            "",
            "Tracks degradation in effective score as graph complexity and constraint density increase.",
            "",
            "| Difficulty Tier | Model | Samples | Mean Raw | Mean Effective | Safety Fail % |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )

    for diff in difficulties:
        tier = diff.get("difficulty_level", "")
        model = diff.get("model_identifier", "")
        cnt = diff.get("sample_count", "0")
        raw = float(diff.get("mean_raw_score", 0.0))
        eff = float(diff.get("mean_effective_score", 0.0))
        fail = float(diff.get("safety_failure_rate", 0.0)) * 100.0
        lines.append(f"| {tier} | `{model}` | {cnt} | {raw:.1f} | {eff:.1f} | {fail:.1f}% |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## Chart 5: Task Family Vulnerability Distribution (T01–T10)",
            "",
            "Detailed performance per task family, identifying systemic migration blindspots.",
            "",
            "| Family ID | Family Name | Model | Evaluated | Eff Score | Critical Violations |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )

    for fam in families:
        fid = fam.get("family_id", "")
        fname = fam.get("family_name", "")
        model = fam.get("model_identifier", "")
        eval_c = fam.get("evaluated_count", "0")
        eff = float(fam.get("mean_effective_score", 0.0))
        vios = fam.get("critical_violations_count", "0")
        lines.append(f"| `{fid}` | {fname} | `{model}` | {eval_c} | {eff:.1f} | {vios} |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## Chart 6: Counterfactual Paired Sensitivity Outcomes",
            "",
            "Analyzes whether models correctly flip decisions when a single blocker or vulnerability is injected.",
            "",
            "| Pair ID | Model | Decision A | Decision B | Classification | Sensitivity Status |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
    )

    for p in paired:
        pid = p.get("pair_id", "")
        model = p.get("model_identifier", "")
        dec_a = p.get("decision_a", "")
        dec_b = p.get("decision_b", "")
        cls_val = p.get("classification", "")
        status = "PASSED" if "CORRECT" in cls_val.upper() else "FAILED"
        lines.append(f"| `{pid}` | `{model}` | {dec_a} | {dec_b} | `{cls_val}` | **{status}** |")

    lines.extend(
        [
            "",
            "---",
            "",
            "## Chart 7: Metamorphic Invariant Preservation Rate (MR1–MR6)",
            "",
            "Verifies metamorphic relations (Label Permutation, Component Order, Constraint Insertion, Epistemic Removal, Redundant Blocker, Rollback Inversion).",
            "",
            "| Relation | Model | Test ID | Outcome | Details |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
    )

    for m in metamorphic[:20]:  # Cap sample display
        rel = m.get("relation_type", "")
        model = m.get("model_identifier", "")
        tid = m.get("test_id", "")
        outcome = m.get("outcome", "")
        detail = m.get("details", "")[:60]
        lines.append(f"| `{rel}` | `{model}` | `{tid}` | **{outcome}** | {detail}... |")

    content = "\n".join(lines) + "\n"
    output_file.write_text(content, encoding="utf-8")
    return content


def generate_html_visualizations(exports_dir: Path, output_file: Path) -> None:
    """Generate clean self-contained HTML page with SVG visualizations."""
    overall = load_csv(exports_dir / "overall_metrics.csv")
    domains = load_csv(exports_dir / "domain_metrics.csv")
    difficulties = load_csv(exports_dir / "difficulty_metrics.csv")

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>PHOENIX-EVAL Benchmark Visualizations</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 2rem; }
  h1, h2, h3 { color: #38bdf8; }
  .container { max-width: 1100px; margin: 0 auto; }
  .card { background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 2rem; border: 1px solid #334155; }
  table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
  th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #334155; }
  th { background: #0f172a; color: #94a3b8; font-weight: 600; }
  .bar-container { background: #334155; border-radius: 4px; height: 20px; width: 100%; overflow: hidden; }
  .bar-fill { background: #38bdf8; height: 100%; }
  .bar-fill.danger { background: #ef4444; }
  .badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: bold; }
  .badge-safe { background: #10b981; color: #ffffff; }
  .badge-danger { background: #ef4444; color: #ffffff; }
</style>
</head>
<body>
<div class="container">
  <h1>PHOENIX-EVAL — Benchmark Analytics & Visualizations</h1>
  <p style="color: #94a3b8;">Deterministic Cryptographic Migration Intelligence Evaluation</p>

  <div style="background: #1e3a5f; border-left: 4px solid #38bdf8; padding: 1rem; margin-bottom: 2rem; border-radius: 4px;">
    <strong>SIMULATED BASELINE EXPERIMENTS:</strong> All charts below reflect offline mock provider fixtures (<code>mock-valid-migration</code>, <code>mock-unsafe-migration</code>, <code>mock-malformed-response</code>) evaluated during benchmark pipeline calibration and verification. Zero commercial frontier models were evaluated in this campaign.
  </div>

  <div class="card">
    <h2>1. Overall Model Comparison (Effective Score vs Safety Failure Rate)</h2>
    <table>
      <thead>
        <tr>
          <th>Model Identifier</th>
          <th>Raw Score</th>
          <th>Effective Score</th>
          <th>Safety Failure Rate</th>
          <th>Safety Gate Status</th>
        </tr>
      </thead>
      <tbody>
"""
    for m in overall:
        raw = float(m.get("mean_raw_score", 0.0))
        eff = float(m.get("mean_effective_score", 0.0))
        fail = float(m.get("safety_failure_rate", 0.0)) * 100.0
        status_badge = (
            '<span class="badge badge-safe">RESILIENT</span>'
            if fail < 20.0
            else '<span class="badge badge-danger">CRITICAL VETO</span>'
        )
        html += f"""        <tr>
          <td><strong>{m.get("model_identifier")}</strong></td>
          <td>{raw:.1f}</td>
          <td>
            <div style="display:flex; align-items:center; gap: 8px;">
              <span>{eff:.1f}</span>
              <div class="bar-container" style="width: 150px;">
                <div class="bar-fill" style="width: {eff}%;"></div>
              </div>
            </div>
          </td>
          <td>
            <div style="display:flex; align-items:center; gap: 8px;">
              <span>{fail:.1f}%</span>
              <div class="bar-container" style="width: 100px;">
                <div class="bar-fill danger" style="width: {fail}%;"></div>
              </div>
            </div>
          </td>
          <td>{status_badge}</td>
        </tr>
"""
    html += """      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>2. Enterprise Architecture Domain Vulnerabilities</h2>
    <table>
      <thead>
        <tr>
          <th>Domain</th>
          <th>Model</th>
          <th>Evaluated Tasks</th>
          <th>Safety Failure Rate</th>
        </tr>
      </thead>
      <tbody>
"""
    for dom in domains:
        dname = dom.get("domain_name", "").upper()
        model = dom.get("model_identifier", "")
        cnt = dom.get("sample_count", "0")
        fail = float(dom.get("safety_failure_rate", 0.0)) * 100.0
        html += f"""        <tr>
          <td><strong>{dname}</strong></td>
          <td><code>{model}</code></td>
          <td>{cnt}</td>
          <td>{fail:.1f}%</td>
        </tr>
"""
    html += """      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>3. Difficulty Tier Performance Degradation</h2>
    <table>
      <thead>
        <tr>
          <th>Difficulty Level</th>
          <th>Model</th>
          <th>Effective Score</th>
          <th>Safety Failure Rate</th>
        </tr>
      </thead>
      <tbody>
"""
    for diff in difficulties:
        tier = diff.get("difficulty_level", "")
        model = diff.get("model_identifier", "")
        eff = float(diff.get("mean_effective_score", 0.0))
        fail = float(diff.get("safety_failure_rate", 0.0)) * 100.0
        html += f"""        <tr>
          <td><strong>{tier}</strong></td>
          <td><code>{model}</code></td>
          <td>{eff:.1f}</td>
          <td>{fail:.1f}%</td>
        </tr>
"""
    html += """      </tbody>
    </table>
  </div>
</div>
</body>
</html>
"""
    output_file.write_text(html, encoding="utf-8")


def main() -> None:
    """Generate all static visualizations."""
    paths = get_paths()
    exports_dir = paths.exports_dir
    charts_dir = paths.results_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    md_path = charts_dir / "visualizations.md"
    html_path = charts_dir / "visualizations.html"

    print("Generating static visualizations from CSV exports...")
    generate_markdown_visualizations(exports_dir, md_path)
    generate_html_visualizations(exports_dir, html_path)
    print(f"Generated Markdown charts: {md_path}")
    print(f"Generated HTML visualizations: {html_path}")


if __name__ == "__main__":
    main()
