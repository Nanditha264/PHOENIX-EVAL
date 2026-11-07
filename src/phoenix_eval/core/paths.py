"""Path management and project directory resolution for PHOENIX-EVAL."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ProjectPaths:
    """Immutable collection of standard project directory paths."""

    root: Path
    config_dir: Path
    datasets_dir: Path
    scenarios_dir: Path
    tasks_dir: Path
    ground_truth_dir: Path
    fixtures_dir: Path
    results_dir: Path
    raw_runs_dir: Path
    processed_dir: Path
    reports_dir: Path
    docs_dir: Path
    tests_dir: Path
    generated_dir: Path = Path()
    generated_scenarios_dir: Path = Path()
    generated_tasks_dir: Path = Path()
    generated_ground_truth_dir: Path = Path()
    generated_manifests_dir: Path = Path()
    generated_paired_dir: Path = Path()
    generated_metamorphic_dir: Path = Path()
    # Phase 5 Analysis directories
    analysis_dir: Path = Path()
    ingestion_dir: Path = Path()
    validated_dir: Path = Path()
    failure_intelligence_dir: Path = Path()
    paired_analysis_dir: Path = Path()
    metamorphic_analysis_dir: Path = Path()
    statistics_dir: Path = Path()
    exports_dir: Path = Path()
    # Hidden Holdout Benchmark directories
    holdout_dir: Path = Path()
    holdout_scenarios_dir: Path = Path()
    holdout_tasks_dir: Path = Path()
    holdout_ground_truth_dir: Path = Path()

    def __post_init__(self) -> None:
        """Initialize generated and analysis directories with sensible defaults if omitted."""
        empty = Path()
        gen = (
            self.generated_dir if self.generated_dir != empty else (self.datasets_dir / "generated")
        )
        if self.generated_dir == empty:
            object.__setattr__(self, "generated_dir", gen)
        if self.generated_scenarios_dir == empty:
            object.__setattr__(self, "generated_scenarios_dir", gen / "scenarios")
        if self.generated_tasks_dir == empty:
            object.__setattr__(self, "generated_tasks_dir", gen / "tasks")
        if self.generated_ground_truth_dir == empty:
            object.__setattr__(self, "generated_ground_truth_dir", gen / "ground_truth")
        if self.generated_manifests_dir == empty:
            object.__setattr__(self, "generated_manifests_dir", gen / "manifests")
        if self.generated_paired_dir == empty:
            object.__setattr__(self, "generated_paired_dir", gen / "paired_cases")
        if self.generated_metamorphic_dir == empty:
            object.__setattr__(self, "generated_metamorphic_dir", gen / "metamorphic_cases")

        # Phase 5 Analysis outputs layout
        if self.analysis_dir == empty:
            object.__setattr__(self, "analysis_dir", self.results_dir / "analysis")
        if self.ingestion_dir == empty:
            object.__setattr__(self, "ingestion_dir", self.results_dir / "ingestion")
        if self.validated_dir == empty:
            object.__setattr__(self, "validated_dir", self.results_dir / "validated")
        if self.failure_intelligence_dir == empty:
            object.__setattr__(
                self, "failure_intelligence_dir", self.results_dir / "failure_intelligence"
            )
        if self.paired_analysis_dir == empty:
            object.__setattr__(self, "paired_analysis_dir", self.results_dir / "paired_analysis")
        if self.metamorphic_analysis_dir == empty:
            object.__setattr__(
                self, "metamorphic_analysis_dir", self.results_dir / "metamorphic_analysis"
            )
        if self.statistics_dir == empty:
            object.__setattr__(self, "statistics_dir", self.results_dir / "statistics")
        if self.exports_dir == empty:
            object.__setattr__(self, "exports_dir", self.results_dir / "exports")

        # Hidden Holdout layout
        hld = self.datasets_dir / "holdout"
        if self.holdout_dir == empty:
            object.__setattr__(self, "holdout_dir", hld)
        if self.holdout_scenarios_dir == empty:
            object.__setattr__(self, "holdout_scenarios_dir", hld / "scenarios")
        if self.holdout_tasks_dir == empty:
            object.__setattr__(self, "holdout_tasks_dir", hld / "tasks")
        if self.holdout_ground_truth_dir == empty:
            object.__setattr__(self, "holdout_ground_truth_dir", hld / "ground_truth")

    def ensure_directories(self) -> None:
        """Create all standard output and working directories if they do not exist."""
        paths_to_create = [
            self.results_dir,
            self.raw_runs_dir,
            self.processed_dir,
            self.reports_dir,
            self.datasets_dir,
            self.scenarios_dir,
            self.tasks_dir,
            self.ground_truth_dir,
            self.fixtures_dir,
            self.analysis_dir,
            self.ingestion_dir,
            self.validated_dir,
            self.failure_intelligence_dir,
            self.paired_analysis_dir,
            self.metamorphic_analysis_dir,
            self.statistics_dir,
            self.exports_dir,
            self.holdout_dir,
            self.holdout_scenarios_dir,
            self.holdout_tasks_dir,
            self.holdout_ground_truth_dir,
        ]
        for p in (
            self.generated_dir,
            self.generated_scenarios_dir,
            self.generated_tasks_dir,
            self.generated_ground_truth_dir,
            self.generated_manifests_dir,
            self.generated_paired_dir,
            self.generated_metamorphic_dir,
        ):
            if p is not None:
                paths_to_create.append(p)

        for path in paths_to_create:
            path.mkdir(parents=True, exist_ok=True)


def find_project_root(start_path: Optional[Path] = None) -> Path:
    """Find the root directory of the PHOENIX-EVAL project.

    Searches upwards from `start_path` (defaulting to this file or current working directory)
    until it finds `pyproject.toml` or `.git`.
    """
    if start_path is None:
        # Check current working directory first, fallback to module location
        cwd = Path.cwd().resolve()
        if (cwd / "pyproject.toml").exists():
            return cwd
        start_path = Path(__file__).resolve().parent

    current = start_path.resolve()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent

    # Fallback to current working directory
    return Path.cwd().resolve()


def get_paths(custom_root: Optional[Path] = None) -> ProjectPaths:
    """Construct and return standard project paths."""
    root = (custom_root or find_project_root()).resolve()
    datasets = root / "datasets"
    results = root / "results"
    generated = datasets / "generated"

    return ProjectPaths(
        root=root,
        config_dir=root / "config",
        datasets_dir=datasets,
        scenarios_dir=datasets / "scenarios",
        tasks_dir=datasets / "tasks",
        ground_truth_dir=datasets / "ground_truth",
        fixtures_dir=datasets / "fixtures",
        results_dir=results,
        raw_runs_dir=results / "raw_runs",
        processed_dir=results / "processed",
        reports_dir=results / "reports",
        docs_dir=root / "docs",
        tests_dir=root / "tests",
        generated_dir=generated,
        generated_scenarios_dir=generated / "scenarios",
        generated_tasks_dir=generated / "tasks",
        generated_ground_truth_dir=generated / "ground_truth",
        generated_manifests_dir=generated / "manifests",
        generated_paired_dir=generated / "paired_cases",
        generated_metamorphic_dir=generated / "metamorphic_cases",
    )
