import json
import platform
import socket
from datetime import datetime
from pathlib import Path
from typing import Any


def get_machine_info() -> dict:
    """Gather system information.

    Returns:
        Dictionary with machine details
    """
    import os

    info = {
        "hostname": socket.gethostname(),
        "cpu": platform.processor() or "Unknown",
        "cores": os.cpu_count() or 0,
        "os": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
    }

    # Try to get detailed CPU info on Linux
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    info["cpu"] = line.split(":")[1].strip()
                    break
    except (FileNotFoundError, PermissionError):
        pass

    # Check if running in Docker/container with cgroup limits
    in_container = os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv")

    # Try to get RAM info
    ram_total = None
    ram_available = None

    # First try cgroup v2 memory limit (Docker/container)
    if in_container:
        try:
            with open("/sys/fs/cgroup/memory.max") as f:
                val = f.read().strip()
                if val != "max":
                    ram_total = int(val)
        except (FileNotFoundError, PermissionError, ValueError):
            pass

        # Try cgroup v1 if v2 not available
        if ram_total is None:
            try:
                with open("/sys/fs/cgroup/memory/memory.limit_in_bytes") as f:
                    val = int(f.read().strip())
                    # Check if it's not the "unlimited" value
                    if val < 9223372036854771712:
                        ram_total = val
            except (FileNotFoundError, PermissionError, ValueError):
                pass

    # Fallback to psutil or /proc/meminfo for host memory
    if ram_total is None:
        try:
            import psutil

            mem = psutil.virtual_memory()
            ram_total = mem.total
            ram_available = mem.available
        except ImportError:
            try:
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            ram_total = int(line.split()[1]) * 1024  # KB to bytes
                        elif line.startswith("MemAvailable:"):
                            ram_available = int(line.split()[1]) * 1024
            except (FileNotFoundError, PermissionError):
                pass

    if ram_total:
        info["ram_total_gb"] = round(ram_total / (1024**3), 1)
    if ram_available:
        info["ram_available_gb"] = round(ram_available / (1024**3), 1)

    # Check for CPU limits in cgroups
    if in_container:
        cpu_limit = None
        # Try cgroup v2
        try:
            with open("/sys/fs/cgroup/cpu.max") as f:
                val = f.read().strip()
                if val != "max":
                    parts = val.split()
                    if len(parts) == 2 and parts[0] != "max":
                        quota = int(parts[0])
                        period = int(parts[1])
                        cpu_limit = quota / period
        except (FileNotFoundError, PermissionError, ValueError):
            pass

        # Try cgroup v1
        if cpu_limit is None:
            try:
                with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us") as f:
                    quota = int(f.read().strip())
                if quota > 0:
                    with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us") as f:
                        period = int(f.read().strip())
                    cpu_limit = quota / period
            except (FileNotFoundError, PermissionError, ValueError):
                pass

        if cpu_limit:
            info["cpu_limit"] = round(cpu_limit, 1)
            info["cores"] = round(cpu_limit, 1)  # Override with container limit

    if in_container:
        info["container"] = True

    return info


def save_env_info(
    output_dir: Path,
    db_type: str,
    db_version: str,
    config: dict,
    packages: dict[str, str],
) -> None:
    """Save environment information to JSON file.

    Args:
        output_dir: Directory to save results
        db_type: Database type (postgres/sqlite)
        db_version: Database version string
        config: Configuration used for benchmarks
        packages: Dictionary of package names to versions
    """
    env_info = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "machine": get_machine_info(),
        "python": platform.python_version(),
        "database": {
            "type": db_type,
            "version": db_version,
        },
        "packages": packages,
        "config": config,
    }

    env_file = output_dir / "env.json"
    with open(env_file, "w") as f:
        json.dump(env_info, f, indent=2)


def save_results(
    output_dir: Path,
    db_type: str,
    results: dict[str, dict[str, Any]],
) -> None:
    """Save benchmark results to JSON file.

    Args:
        output_dir: Directory to save results
        db_type: Database type (postgres/sqlite)
        results: Nested dict: {orm_name: {test_name: BenchResult}}
    """
    results_file = output_dir / f"{db_type}.json"

    # Convert BenchResult objects to dicts
    serialized = {}
    for orm_name, tests in results.items():
        serialized[orm_name] = {}
        for test_name, result in tests.items():
            if hasattr(result, "to_dict"):
                serialized[orm_name][test_name] = result.to_dict()
            else:
                serialized[orm_name][test_name] = result

    # Calculate summary statistics
    summary = calculate_summary(serialized, db_type)

    output_data = {
        "results": serialized,
        "summary": summary,
    }

    with open(results_file, "w") as f:
        json.dump(output_data, f, indent=2)


def get_driver_name(db_type: str) -> str:
    """Get the raw driver name for a database type.

    Args:
        db_type: Database type (postgres/sqlite/mysql)

    Returns:
        Driver name (asyncpg/aiosqlite/aiomysql)
    """
    if db_type == "postgres":
        return "asyncpg"
    elif db_type == "mysql":
        return "aiomysql"
    else:
        return "aiosqlite"


def calculate_summary(
    results: dict[str, dict[str, dict]], db_type: str = "postgres"
) -> dict:
    """Calculate summary statistics and rankings.

    Args:
        results: Nested dict of benchmark results
        db_type: Database type (postgres/sqlite/mysql)

    Returns:
        Summary with rankings and scores
    """
    # Raw drivers (not ORMs) - shown for reference but not ranked
    # Use appropriate driver based on database type
    DRIVER = get_driver_name(db_type)
    DRIVERS = {DRIVER}

    # Calculate average ops/sec for each ORM
    orm_scores: dict[str, list[float]] = {}

    for orm_name, tests in results.items():
        scores = []
        for test_result in tests.values():
            if isinstance(test_result, dict) and "ops_per_sec" in test_result:
                scores.append(test_result["ops_per_sec"])
        if scores:
            orm_scores[orm_name] = scores

    # Calculate mean score for each ORM
    orm_means = {
        orm: sum(scores) / len(scores) if scores else 0
        for orm, scores in orm_scores.items()
    }

    # Separate drivers from ORMs
    driver_means = {k: v for k, v in orm_means.items() if k in DRIVERS}
    orm_only_means = {k: v for k, v in orm_means.items() if k not in DRIVERS}

    # Find baseline from drivers (for reference column)
    baseline_score = (
        max(driver_means.values())
        if driver_means
        else (max(orm_means.values()) if orm_means else 1.0)
    )
    baseline_name = max(driver_means, key=driver_means.get) if driver_means else None

    # Calculate relative scores (as fraction of baseline) for ORMs only
    relative_scores = {
        orm: score / baseline_score if baseline_score > 0 else 0
        for orm, score in orm_only_means.items()
    }

    # Rank ORMs (excluding drivers)
    ranked = sorted(
        relative_scores.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    return {
        "overall": [
            {"rank": i + 1, "orm": orm, "score": round(score, 3)}
            for i, (orm, score) in enumerate(ranked)
        ],
        "absolute_scores": {orm: round(score, 2) for orm, score in orm_means.items()},
        "baseline": {
            "name": baseline_name,
            "score": round(baseline_score, 2) if baseline_score else 0,
        },
        "drivers": list(driver_means.keys()),
    }


def generate_markdown_report(results_dir: Path, db_type: str) -> str:
    """Generate markdown report from results.

    Args:
        results_dir: Directory containing results files
        db_type: Database type (postgres/sqlite)

    Returns:
        Markdown formatted report as string
    """
    # Load results
    results_file = results_dir / f"{db_type}.json"
    env_file = results_dir / "env.json"

    with open(results_file) as f:
        data = json.load(f)

    with open(env_file) as f:
        env = json.load(f)

    results = data["results"]
    summary = data["summary"]

    # Get config from env
    config = env.get("config", {})

    # Start building markdown
    machine = env.get("machine", {})
    ram_info = ""
    if machine.get("ram_total_gb"):
        ram_info = f", {machine['ram_total_gb']} GB RAM"

    lines = [
        "# ORM Benchmark Results",
        "",
        f"**Date:** {env['timestamp']}",
        f"**Database:** {env['database']['type']} {env['database']['version']}",
        f"**Python:** {env['python']}",
        f"**Machine:** {machine.get('os', 'Unknown')}, {machine.get('cpu', 'Unknown')}, {machine.get('cores', 'N/A')} cores{ram_info}",
        "",
        "## Benchmark Conditions",
        "",
        "| Parameter | Value |",
        "|-----------|-------|",
        f"| Iterations | {config.get('iterations', 'N/A')} |",
        f"| Warmup iterations | {config.get('warmup', 'N/A')} |",
        f"| Users in DB | {config.get('users_count', 'N/A')} |",
        f"| Posts per user | {config.get('posts_per_user', 'N/A')} |",
        f"| Total posts | {config.get('users_count', 0) * config.get('posts_per_user', 0)} |",
        "",
        "Each test resets the database and prepares fresh data before running.",
        "",
        "## Summary",
        "",
        "| Rank | ORM | Relative Score | Avg ops/sec |",
        "|------|-----|----------------|-------------|",
    ]

    # Add summary table
    for entry in summary["overall"]:
        orm = entry["orm"]
        score = entry["score"]
        avg_ops = summary["absolute_scores"].get(orm, 0)
        lines.append(f"| {entry['rank']} | **{orm}** | {score:.3f} | {avg_ops:,.0f} |")

    lines.extend(["", "## Detailed Results", ""])

    # Group tests by category
    categories = {
        "CRUD Operations": [
            "insert_single",
            "insert_bulk_100",
            "select_pk",
            "select_filter",
            "update_single",
            "update_bulk",
            "delete_single",
        ],
        "Queries": [
            "filter_simple",
            "filter_complex",
            "filter_in",
            "order_limit",
            "aggregate_count",
            "aggregate_mixed",
        ],
        "Relations": [
            "join_simple",
            "join_filter",
            "prefetch_related",
            "nested_prefetch",
        ],
        "Concurrent": [
            "concurrent_10",
            "concurrent_50",
            "concurrent_100",
        ],
    }

    for category_name, test_names in categories.items():
        lines.extend([f"### {category_name}", ""])

        # Build table header
        orm_names = sorted(results.keys())
        header = "| Test | " + " | ".join(orm_names) + " |"
        separator = "|------|" + "|".join(["------"] * len(orm_names)) + "|"

        lines.extend([header, separator])

        # Add rows
        for test_name in test_names:
            row_cells = [test_name]
            for orm_name in orm_names:
                test_result = results[orm_name].get(test_name, {})
                if test_result and "ops_per_sec" in test_result:
                    ops = test_result["ops_per_sec"]
                    row_cells.append(f"{ops:,.0f}")
                else:
                    row_cells.append("N/A")

            lines.append("| " + " | ".join(row_cells) + " |")

        lines.append("")

    # Add Resource Usage section
    lines.extend(["## Resource Usage", ""])

    # Memory table
    lines.extend(["### Peak Memory (MB)", ""])
    orm_names = sorted(results.keys())
    header = "| Test | " + " | ".join(orm_names) + " |"
    separator = "|------|" + "|".join(["------"] * len(orm_names)) + "|"
    lines.extend([header, separator])

    all_tests = []
    for cat_tests in categories.values():
        all_tests.extend(cat_tests)

    for test_name in all_tests:
        row_cells = [test_name]
        for orm_name in orm_names:
            test_result = results[orm_name].get(test_name, {})
            if test_result and "memory_peak_mb" in test_result:
                mem = test_result["memory_peak_mb"]
                row_cells.append(f"{mem:.1f}")
            else:
                row_cells.append("N/A")
        lines.append("| " + " | ".join(row_cells) + " |")
    lines.append("")

    # CPU table
    lines.extend(["### CPU Time (seconds)", ""])
    header = "| Test | " + " | ".join(orm_names) + " |"
    separator = "|------|" + "|".join(["------"] * len(orm_names)) + "|"
    lines.extend([header, separator])

    for test_name in all_tests:
        row_cells = [test_name]
        for orm_name in orm_names:
            test_result = results[orm_name].get(test_name, {})
            if test_result and "cpu_user_sec" in test_result:
                cpu = test_result["cpu_user_sec"] + test_result.get("cpu_system_sec", 0)
                row_cells.append(f"{cpu:.2f}")
            else:
                row_cells.append("N/A")
        lines.append("| " + " | ".join(row_cells) + " |")
    lines.append("")

    # Latency section
    lines.extend(["## Latency", ""])

    # Mean latency table
    lines.extend(["### Mean Latency (ms)", ""])
    header = "| Test | " + " | ".join(orm_names) + " |"
    separator = "|------|" + "|".join(["------"] * len(orm_names)) + "|"
    lines.extend([header, separator])

    for test_name in all_tests:
        row_cells = [test_name]
        for orm_name in orm_names:
            test_result = results[orm_name].get(test_name, {})
            if test_result and "mean_ms" in test_result:
                lat = test_result["mean_ms"]
                row_cells.append(f"{lat:.3f}")
            else:
                row_cells.append("N/A")
        lines.append("| " + " | ".join(row_cells) + " |")
    lines.append("")

    # P95 latency table
    lines.extend(["### P95 Latency (ms)", ""])
    header = "| Test | " + " | ".join(orm_names) + " |"
    separator = "|------|" + "|".join(["------"] * len(orm_names)) + "|"
    lines.extend([header, separator])

    for test_name in all_tests:
        row_cells = [test_name]
        for orm_name in orm_names:
            test_result = results[orm_name].get(test_name, {})
            if test_result and "p95_ms" in test_result:
                lat = test_result["p95_ms"]
                row_cells.append(f"{lat:.3f}")
            else:
                row_cells.append("N/A")
        lines.append("| " + " | ".join(row_cells) + " |")
    lines.append("")

    # P99 latency table
    lines.extend(["### P99 Latency (ms)", ""])
    header = "| Test | " + " | ".join(orm_names) + " |"
    separator = "|------|" + "|".join(["------"] * len(orm_names)) + "|"
    lines.extend([header, separator])

    for test_name in all_tests:
        row_cells = [test_name]
        for orm_name in orm_names:
            test_result = results[orm_name].get(test_name, {})
            if test_result and "p99_ms" in test_result:
                lat = test_result["p99_ms"]
                row_cells.append(f"{lat:.3f}")
            else:
                row_cells.append("N/A")
        lines.append("| " + " | ".join(row_cells) + " |")
    lines.append("")

    return "\n".join(lines)


def save_markdown_report(results_dir: Path, db_type: str) -> None:
    """Generate and save markdown report.

    Args:
        results_dir: Directory containing results files
        db_type: Database type (postgres/sqlite)
    """
    report = generate_markdown_report(results_dir, db_type)
    report_file = results_dir / f"{db_type}_report.md"

    with open(report_file, "w") as f:
        f.write(report)


def print_terminal_report(
    results: dict[str, dict[str, Any]],
    db_type: str,
    config: dict | None = None,
    env_info: dict | None = None,
) -> None:
    """Print formatted results to terminal using rich tables.

    Args:
        results: Nested dict: {orm_name: {test_name: result_dict}}
        db_type: Database type (postgres/sqlite/mysql)
        config: Optional config dict with iterations, warmup, users_count, etc.
        env_info: Optional environment info dict with machine details
    """
    from rich.console import Console
    from rich.table import Table

    console = Console()

    # Convert BenchResult objects to dicts if needed
    serialized = {}
    for orm_name, tests in results.items():
        serialized[orm_name] = {}
        for test_name, result in tests.items():
            if hasattr(result, "to_dict"):
                serialized[orm_name][test_name] = result.to_dict()
            else:
                serialized[orm_name][test_name] = result

    # Print Environment Info
    console.print("\n[bold cyan]═══ Environment ═══[/bold cyan]\n")

    env_table = Table(show_header=False, box=None)
    env_table.add_column("Parameter", style="bold")
    env_table.add_column("Value", style="green")

    machine = env_info.get("machine", {}) if env_info else get_machine_info()
    import os

    # Show container info if running in Docker
    if machine.get("container"):
        env_table.add_row("Environment", "Docker Container")

    env_table.add_row(
        "OS", machine.get("os", platform.system() + " " + platform.release())
    )
    env_table.add_row("CPU", machine.get("cpu", platform.processor() or "Unknown"))

    cores = machine.get("cores", os.cpu_count() or "N/A")
    if machine.get("cpu_limit"):
        env_table.add_row("CPU Limit", f"{machine['cpu_limit']} cores")
    else:
        env_table.add_row("CPU Cores", str(cores))

    if machine.get("ram_total_gb"):
        label = "RAM Limit" if machine.get("container") else "RAM Total"
        env_table.add_row(label, f"{machine['ram_total_gb']} GB")
    if machine.get("ram_available_gb"):
        env_table.add_row("RAM Available", f"{machine['ram_available_gb']} GB")
    env_table.add_row("Python", machine.get("python", platform.python_version()))

    console.print(env_table)

    # Print Benchmark Conditions
    if config:
        console.print("\n[bold cyan]═══ Benchmark Configuration ═══[/bold cyan]\n")

        cond_table = Table(show_header=False, box=None)
        cond_table.add_column("Parameter", style="bold")
        cond_table.add_column("Value", style="green")

        cond_table.add_row("Database", db_type)
        cond_table.add_row("Driver (baseline)", get_driver_name(db_type))
        cond_table.add_row("Iterations", str(config.get("iterations", "N/A")))
        cond_table.add_row("Warmup", str(config.get("warmup", "N/A")))
        cond_table.add_row("Users in DB", str(config.get("users_count", "N/A")))
        cond_table.add_row("Posts per user", str(config.get("posts_per_user", "N/A")))

        users = config.get("users_count", 0)
        posts = config.get("posts_per_user", 0)
        cond_table.add_row("Total posts", str(users * posts))

        # Docker resource limits if available
        if config.get("memory_limit"):
            cond_table.add_row("Memory Limit", config.get("memory_limit"))
        if config.get("cpu_limit"):
            cond_table.add_row("CPU Limit", str(config.get("cpu_limit")))

        console.print(cond_table)

    # Calculate summary
    summary = calculate_summary(serialized, db_type)

    # Print Summary Table
    console.print("\n[bold cyan]═══ Summary ═══[/bold cyan]\n")

    summary_table = Table(title="ORM Rankings")
    summary_table.add_column("Rank", style="bold", justify="center")
    summary_table.add_column("ORM", style="cyan")
    summary_table.add_column("Relative Score", justify="right")
    summary_table.add_column("Avg ops/sec", justify="right", style="green")

    for entry in summary["overall"]:
        orm = entry["orm"]
        score = entry["score"]
        avg_ops = summary["absolute_scores"].get(orm, 0)
        summary_table.add_row(
            str(entry["rank"]),
            orm,
            f"{score:.3f}",
            f"{avg_ops:,.0f}",
        )

    # Add driver baseline info
    if summary.get("baseline", {}).get("name"):
        baseline = summary["baseline"]
        summary_table.add_row(
            "-",
            f"{baseline['name']} (baseline)",
            "1.000",
            f"{baseline['score']:,.0f}",
            style="dim",
        )

    console.print(summary_table)

    # Test categories
    categories = {
        "CRUD Operations": [
            "insert_single",
            "insert_bulk_100",
            "select_pk",
            "select_filter",
            "update_single",
            "update_bulk",
            "delete_single",
        ],
        "Queries": [
            "filter_simple",
            "filter_complex",
            "filter_in",
            "order_limit",
            "aggregate_count",
            "aggregate_mixed",
        ],
        "Relations": [
            "join_simple",
            "join_filter",
            "prefetch_related",
            "nested_prefetch",
        ],
        "Concurrent": [
            "concurrent_10",
            "concurrent_50",
            "concurrent_100",
        ],
    }

    orm_names = sorted(serialized.keys())

    # Print detailed tables for each category
    for category_name, test_names in categories.items():
        # Check if any tests in this category have results
        has_results = any(
            test_name in serialized.get(orm, {})
            for test_name in test_names
            for orm in orm_names
        )
        if not has_results:
            continue

        console.print(f"\n[bold cyan]═══ {category_name} (ops/sec) ═══[/bold cyan]\n")

        table = Table()
        table.add_column("Test", style="bold")
        for orm_name in orm_names:
            table.add_column(orm_name, justify="right")

        for test_name in test_names:
            row = [test_name]
            for orm_name in orm_names:
                test_result = serialized[orm_name].get(test_name, {})
                if test_result and "ops_per_sec" in test_result:
                    ops = test_result["ops_per_sec"]
                    row.append(f"[green]{ops:,.0f}[/green]")
                elif test_result and "error" in test_result:
                    row.append("[red]Error[/red]")
                else:
                    row.append("[dim]N/A[/dim]")
            table.add_row(*row)

        console.print(table)

    # Print Resource Usage Section
    console.print("\n[bold cyan]═══ Resource Usage ═══[/bold cyan]")

    # Collect all test names
    all_tests = []
    for cat_tests in categories.values():
        all_tests.extend(cat_tests)

    # Memory Table
    console.print("\n[bold]Peak Memory (MB)[/bold]\n")
    mem_table = Table()
    mem_table.add_column("Test", style="bold")
    for orm_name in orm_names:
        mem_table.add_column(orm_name, justify="right")

    for test_name in all_tests:
        has_data = any(
            serialized.get(orm, {}).get(test_name, {}).get("memory_peak_mb")
            for orm in orm_names
        )
        if not has_data:
            continue
        row = [test_name]
        for orm_name in orm_names:
            test_result = serialized[orm_name].get(test_name, {})
            if test_result and "memory_peak_mb" in test_result:
                mem = test_result["memory_peak_mb"]
                row.append(f"{mem:.1f}")
            else:
                row.append("[dim]N/A[/dim]")
        mem_table.add_row(*row)

    console.print(mem_table)

    # CPU Table
    console.print("\n[bold]CPU Time (seconds)[/bold]\n")
    cpu_table = Table()
    cpu_table.add_column("Test", style="bold")
    for orm_name in orm_names:
        cpu_table.add_column(orm_name, justify="right")

    for test_name in all_tests:
        has_data = any(
            serialized.get(orm, {}).get(test_name, {}).get("cpu_user_sec")
            for orm in orm_names
        )
        if not has_data:
            continue
        row = [test_name]
        for orm_name in orm_names:
            test_result = serialized[orm_name].get(test_name, {})
            if test_result and "cpu_user_sec" in test_result:
                cpu = test_result["cpu_user_sec"] + test_result.get("cpu_system_sec", 0)
                row.append(f"{cpu:.2f}")
            else:
                row.append("[dim]N/A[/dim]")
        cpu_table.add_row(*row)

    console.print(cpu_table)

    # Latency Section
    console.print("\n[bold cyan]═══ Latency ═══[/bold cyan]")

    # Mean Latency Table
    console.print("\n[bold]Mean Latency (ms)[/bold]\n")
    lat_table = Table()
    lat_table.add_column("Test", style="bold")
    for orm_name in orm_names:
        lat_table.add_column(orm_name, justify="right")

    for test_name in all_tests:
        has_data = any(
            serialized.get(orm, {}).get(test_name, {}).get("mean_ms")
            for orm in orm_names
        )
        if not has_data:
            continue
        row = [test_name]
        for orm_name in orm_names:
            test_result = serialized[orm_name].get(test_name, {})
            if test_result and "mean_ms" in test_result:
                lat = test_result["mean_ms"]
                row.append(f"{lat:.3f}")
            else:
                row.append("[dim]N/A[/dim]")
        lat_table.add_row(*row)

    console.print(lat_table)

    # P95 Latency Table
    console.print("\n[bold]P95 Latency (ms)[/bold]\n")
    p95_table = Table()
    p95_table.add_column("Test", style="bold")
    for orm_name in orm_names:
        p95_table.add_column(orm_name, justify="right")

    for test_name in all_tests:
        has_data = any(
            serialized.get(orm, {}).get(test_name, {}).get("p95_ms")
            for orm in orm_names
        )
        if not has_data:
            continue
        row = [test_name]
        for orm_name in orm_names:
            test_result = serialized[orm_name].get(test_name, {})
            if test_result and "p95_ms" in test_result:
                lat = test_result["p95_ms"]
                row.append(f"{lat:.3f}")
            else:
                row.append("[dim]N/A[/dim]")
        p95_table.add_row(*row)

    console.print(p95_table)

    # P99 Latency Table
    console.print("\n[bold]P99 Latency (ms)[/bold]\n")
    p99_table = Table()
    p99_table.add_column("Test", style="bold")
    for orm_name in orm_names:
        p99_table.add_column(orm_name, justify="right")

    for test_name in all_tests:
        has_data = any(
            serialized.get(orm, {}).get(test_name, {}).get("p99_ms")
            for orm in orm_names
        )
        if not has_data:
            continue
        row = [test_name]
        for orm_name in orm_names:
            test_result = serialized[orm_name].get(test_name, {})
            if test_result and "p99_ms" in test_result:
                lat = test_result["p99_ms"]
                row.append(f"{lat:.3f}")
            else:
                row.append("[dim]N/A[/dim]")
        p99_table.add_row(*row)

    console.print(p99_table)
