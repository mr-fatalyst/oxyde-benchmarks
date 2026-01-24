import statistics
import time
from dataclasses import dataclass
from typing import Callable, Awaitable, Any, Optional

import psutil


@dataclass
class BenchResult:
    """Results from a benchmark run."""

    ops_per_sec: float  # Main metric
    mean_ms: float  # Average time in milliseconds
    median_ms: float  # Median time in milliseconds
    stddev_ms: float  # Standard deviation in milliseconds
    min_ms: float  # Minimum time in milliseconds
    max_ms: float  # Maximum time in milliseconds
    p95_ms: float  # 95th percentile in milliseconds
    p99_ms: float  # 99th percentile in milliseconds
    iterations: int  # Number of iterations measured
    # Resource usage
    memory_delta_mb: float  # Memory change during test (MB)
    memory_peak_mb: float  # Peak memory usage (MB)
    cpu_user_sec: float  # User CPU time (seconds)
    cpu_system_sec: float  # System CPU time (seconds)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "ops_per_sec": round(self.ops_per_sec, 2),
            "mean_ms": round(self.mean_ms, 4),
            "median_ms": round(self.median_ms, 4),
            "stddev_ms": round(self.stddev_ms, 4),
            "min_ms": round(self.min_ms, 4),
            "max_ms": round(self.max_ms, 4),
            "p95_ms": round(self.p95_ms, 4),
            "p99_ms": round(self.p99_ms, 4),
            "iterations": self.iterations,
            "memory_delta_mb": round(self.memory_delta_mb, 2),
            "memory_peak_mb": round(self.memory_peak_mb, 2),
            "cpu_user_sec": round(self.cpu_user_sec, 4),
            "cpu_system_sec": round(self.cpu_system_sec, 4),
        }


async def measure(
    func: Callable[[], Awaitable[Any]],
    iterations: int = 1000,
    warmup: int = 100,
    setup: Optional[Callable[[], Awaitable[None]]] = None,
    teardown: Optional[Callable[[], Awaitable[None]]] = None,
) -> BenchResult:
    """Measure performance of an async function.

    Args:
        func: Async function to benchmark
        iterations: Number of iterations to measure
        warmup: Number of warmup iterations (excluded from results)
        setup: Optional async function to run BEFORE each iteration (not timed).
               Use for mutating tests that need fresh state.
        teardown: Optional async function to run AFTER each iteration (not timed).
                  Use for cleanup after mutating operations.

    Returns:
        BenchResult with performance statistics
    """
    process = psutil.Process()

    # Warmup phase - exclude from measurements
    for _ in range(warmup):
        if setup:
            await setup()
        await func()
        if teardown:
            await teardown()

    # Capture resource usage before measurement
    mem_before = process.memory_info().rss
    cpu_before = process.cpu_times()
    peak_memory = mem_before

    # Measurement phase
    times_ns: list[int] = []
    for i in range(iterations):
        # Run setup if provided (not timed)
        if setup:
            await setup()

        # Time only the actual function
        start = time.perf_counter_ns()
        await func()
        elapsed = time.perf_counter_ns() - start
        times_ns.append(elapsed)

        # Run teardown if provided (not timed)
        if teardown:
            await teardown()

        # Track peak memory (sampled, not every iteration for performance)
        if (i + 1) % 10 == 0:
            current_mem = process.memory_info().rss
            if current_mem > peak_memory:
                peak_memory = current_mem

    # Capture resource usage after measurement
    mem_after = process.memory_info().rss
    cpu_after = process.cpu_times()

    # Calculate resource deltas
    memory_delta_mb = (mem_after - mem_before) / (1024 * 1024)
    memory_peak_mb = peak_memory / (1024 * 1024)
    cpu_user_sec = cpu_after.user - cpu_before.user
    cpu_system_sec = cpu_after.system - cpu_before.system

    # Convert to milliseconds and sort for percentile calculations
    times_ms = [t / 1_000_000 for t in times_ns]
    times_ms.sort()

    # Calculate statistics
    mean_ms = statistics.mean(times_ms)
    median_ms = statistics.median(times_ms)
    stddev_ms = statistics.stdev(times_ms) if len(times_ms) > 1 else 0.0
    min_ms = min(times_ms)
    max_ms = max(times_ms)

    # Percentiles
    p95_index = int(len(times_ms) * 0.95)
    p99_index = int(len(times_ms) * 0.99)
    p95_ms = times_ms[p95_index]
    p99_ms = times_ms[p99_index]

    # Operations per second
    ops_per_sec = 1000 / mean_ms if mean_ms > 0 else 0.0

    return BenchResult(
        ops_per_sec=ops_per_sec,
        mean_ms=mean_ms,
        median_ms=median_ms,
        stddev_ms=stddev_ms,
        min_ms=min_ms,
        max_ms=max_ms,
        p95_ms=p95_ms,
        p99_ms=p99_ms,
        iterations=iterations,
        memory_delta_mb=memory_delta_mb,
        memory_peak_mb=memory_peak_mb,
        cpu_user_sec=cpu_user_sec,
        cpu_system_sec=cpu_system_sec,
    )
