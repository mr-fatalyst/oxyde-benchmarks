#!/usr/bin/env python3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from config import (
    BenchConfig,
    AVAILABLE_ORMS,
    ALL_TESTS,
    MUTATING_TESTS,
    READ_ONLY_TESTS,
    default_config,
)
from common.base import Benchmark
from common.db import parse_db_url
from common.report import (
    save_env_info,
    save_results,
    save_markdown_report,
    print_terminal_report,
)

app = typer.Typer()
console = Console()


def get_benchmark_class(orm_name: str) -> type[Benchmark] | None:
    """Load benchmark class for given ORM.

    Args:
        orm_name: Name of ORM (e.g., "oxyde", "asyncpg")

    Returns:
        Benchmark class or None if not available
    """
    try:
        if orm_name == "oxyde":
            from oxyde_bench.bench import OxydeBenchmark

            return OxydeBenchmark
        elif orm_name == "oxyde-raw":
            from oxyde_raw_bench.bench import OxydeRawBenchmark

            return OxydeRawBenchmark
        elif orm_name == "asyncpg":
            from asyncpg_bench.bench import AsyncpgBenchmark

            return AsyncpgBenchmark
        elif orm_name == "django":
            from django_bench.bench import DjangoBenchmark

            return DjangoBenchmark
        elif orm_name == "sqlalchemy":
            from sqlalchemy_bench.bench import SQLAlchemyBenchmark

            return SQLAlchemyBenchmark
        elif orm_name == "tortoise":
            from tortoise_bench.bench import TortoiseBenchmark

            return TortoiseBenchmark
        elif orm_name == "piccolo":
            from piccolo_bench.bench import PiccoloBenchmark

            return PiccoloBenchmark
        elif orm_name == "peewee":
            from peewee_bench.bench import PeeweeBenchmark

            return PeeweeBenchmark
        elif orm_name == "sqlmodel":
            from sqlmodel_bench.bench import SQLModelBenchmark

            return SQLModelBenchmark
        else:
            return None
    except ImportError as e:
        console.print(f"[yellow]Warning: Could not import {orm_name}: {e}[/yellow]")
        return None


def run_isolated_benchmark(
    orm_name: str,
    db_url: str,
    config: BenchConfig,
    tests_to_run: list[str],
    show_logs: bool = False,
) -> tuple[str, dict[str, dict]] | None:
    """Run benchmark for a single ORM in isolated subprocess.

    This provides accurate memory measurements since each ORM runs in
    a fresh Python process without other ORMs loaded.

    Args:
        orm_name: Name of ORM to benchmark
        db_url: Database connection URL
        config: Benchmark configuration
        tests_to_run: List of test names to run

    Returns:
        Tuple of (actual_name, results_dict) or None on failure
    """
    import subprocess
    import json

    console.print(f"\n[bold blue]Running {orm_name} benchmarks...[/bold blue]")

    # Prepare config for subprocess
    config_dict = {
        "iterations": config.iterations,
        "warmup": config.warmup,
        "users_count": config.users_count,
        "posts_per_user": config.posts_per_user,
        "tests": tests_to_run,
    }

    try:
        # Run subprocess
        result = subprocess.run(
            [
                sys.executable,
                "run_single_orm.py",
                orm_name,
                db_url,
                json.dumps(config_dict),
            ],
            stdout=subprocess.PIPE,
            stderr=None if show_logs else subprocess.PIPE,  # None = show in console
            text=True,
            timeout=1800,  # 30 minute timeout
        )

        if result.returncode != 0:
            console.print(f"[red]Subprocess failed for {orm_name}:[/red]")
            console.print(result.stderr)
            return None

        # Parse output
        try:
            output = json.loads(result.stdout)
            actual_name = output.get("orm_name", orm_name)
            results = output.get("results", {})

            # Print results
            for test_name, test_result in results.items():
                if "error" in test_result:
                    console.print(
                        f"  ✗ {test_name}: [red]Error: {test_result['error']}[/red]"
                    )
                else:
                    ops = test_result.get("ops_per_sec", 0)
                    console.print(f"  ✓ {test_name}: [green]{ops:,.0f} ops/sec[/green]")

            return actual_name, results

        except json.JSONDecodeError:
            console.print(f"[red]Failed to parse output from {orm_name}:[/red]")
            console.print(result.stdout[:500])
            return None

    except subprocess.TimeoutExpired:
        console.print(f"[red]Timeout running {orm_name}[/red]")
        return None
    except Exception as e:
        console.print(f"[red]Error running {orm_name}: {e}[/red]")
        return None


@app.command()
def run(
    db: str = typer.Option(
        "sqlite",
        "--db",
        help="Database to use (postgres or sqlite)",
    ),
    db_url: Optional[str] = typer.Option(
        None,
        "--db-url",
        help="Custom database URL (overrides --db)",
    ),
    orms: Optional[str] = typer.Option(
        None,
        "--orms",
        help="Comma-separated list of ORMs to test (default: all)",
    ),
    tests: Optional[str] = typer.Option(
        None,
        "--tests",
        help="Comma-separated list of tests to run (default: all)",
    ),
    category: Optional[str] = typer.Option(
        None,
        "--category",
        help="Test category: crud, queries, relations, concurrent, mutating, readonly",
    ),
    iterations: int = typer.Option(
        default_config.iterations,
        "--iterations",
        help="Number of iterations per test",
    ),
    warmup: int = typer.Option(
        default_config.warmup,
        "--warmup",
        help="Number of warmup iterations",
    ),
    output: str = typer.Option(
        "results",
        "--output",
        help="Output directory for results",
    ),
    logs: bool = typer.Option(
        False,
        "--logs",
        help="Show subprocess stderr in real-time for debugging",
    ),
):
    """Run ORM benchmarks."""
    from config import TEST_CATEGORIES

    # Parse configuration
    config = BenchConfig(
        iterations=iterations,
        warmup=warmup,
        output_dir=output,
    )

    # Determine which ORMs to test
    if orms:
        orms_to_test = [o.strip() for o in orms.split(",")]
    else:
        orms_to_test = AVAILABLE_ORMS

    # Determine which tests to run
    if tests:
        tests_to_run = [t.strip() for t in tests.split(",")]
    elif category:
        if category == "mutating":
            tests_to_run = MUTATING_TESTS
        elif category == "readonly":
            tests_to_run = READ_ONLY_TESTS
        elif category in TEST_CATEGORIES:
            tests_to_run = TEST_CATEGORIES[category]
        else:
            console.print(f"[red]Unknown category: {category}[/red]")
            console.print(
                f"Available: {', '.join(TEST_CATEGORIES.keys())}, mutating, readonly"
            )
            sys.exit(1)
    else:
        tests_to_run = ALL_TESTS

    # Determine database(s) to test
    if db_url:
        db_configs = [("postgres" if "postgres" in db_url else "sqlite", db_url)]
    elif db.lower() == "all":
        # Run all databases sequentially
        db_configs = [
            ("postgres", parse_db_url("postgres")),
            ("mysql", parse_db_url("mysql")),
            ("sqlite", parse_db_url("sqlite")),
        ]
    else:
        db_type = db.lower()
        db_configs = [(db_type, parse_db_url(db_type))]

    # Run benchmarks for each database
    for db_type, final_db_url in db_configs:
        console.print(f"\n[bold]{'=' * 60}[/bold]")
        console.print(f"[bold]ORM Benchmark Runner - {db_type.upper()}[/bold]")
        console.print(f"[bold]{'=' * 60}[/bold]")
        console.print(f"Database: {db_type}")
        console.print(f"URL: {final_db_url}")
        console.print(f"Iterations: {config.iterations} (warmup: {config.warmup})")
        console.print(f"ORMs: {', '.join(orms_to_test)}")
        console.print(f"Tests: {len(tests_to_run)} tests")

        # Create output directory
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = Path(config.output_dir) / f"{timestamp}_{db_type}"
        output_dir.mkdir(parents=True, exist_ok=True)

        console.print(f"Output: {output_dir}")

        # Run benchmarks - each ORM in isolated subprocess for accurate measurement
        all_results = {}

        for orm_name in orms_to_test:
            result = run_isolated_benchmark(
                orm_name,
                final_db_url,
                config,
                tests_to_run,
                show_logs=logs,
            )
            if result:
                actual_name, results = result
                if results:
                    all_results[actual_name] = results

        # Save results for this database
        if all_results:
            console.print("\n[bold]Saving results...[/bold]")

            # Get package versions
            try:
                import importlib.metadata

                packages = {}
                for orm in orms_to_test:
                    try:
                        pkg_name = orm
                        if orm == "sqlalchemy":
                            pkg_name = "sqlalchemy"
                        elif orm == "tortoise":
                            pkg_name = "tortoise-orm"
                        packages[orm] = importlib.metadata.version(pkg_name)
                    except Exception:
                        pass
            except Exception:
                packages = {}

            # Save environment info
            save_env_info(
                output_dir,
                db_type,
                "unknown",
                {
                    "iterations": config.iterations,
                    "warmup": config.warmup,
                    "users_count": config.users_count,
                    "posts_per_user": config.posts_per_user,
                },
                packages,
            )

            # Save results
            save_results(output_dir, db_type, all_results)

            # Generate markdown report
            save_markdown_report(output_dir, db_type)

            console.print(f"\n[green]✓ Results saved to {output_dir}[/green]")

            # Display terminal report
            print_terminal_report(
                all_results,
                db_type,
                config={
                    "iterations": config.iterations,
                    "warmup": config.warmup,
                    "users_count": config.users_count,
                    "posts_per_user": config.posts_per_user,
                },
            )

        else:
            console.print("\n[yellow]No results to save[/yellow]")


if __name__ == "__main__":
    app()
