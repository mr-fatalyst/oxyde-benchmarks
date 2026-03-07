#!/usr/bin/env python3
import asyncio
import json
import sys
import random

# Parse arguments
if len(sys.argv) < 4:
    print("Usage: run_single_orm.py <orm_name> <db_url> <config_json>", file=sys.stderr)
    sys.exit(1)

orm_name = sys.argv[1]
db_url = sys.argv[2]
config = json.loads(sys.argv[3])


def get_benchmark_class(orm_name: str):
    """Load benchmark class for given ORM."""
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
    return None


async def run_test(
    bench, test_name: str, iterations: int, warmup: int, pre_generated_ids: list[int]
) -> dict:
    """Run a single benchmark test."""
    from common.timer import measure

    # Index for iterating through pre_generated_ids
    current_idx = [0]

    def next_id() -> int:
        idx = current_idx[0] % len(pre_generated_ids)
        current_idx[0] += 1
        return pre_generated_ids[idx]

    async def get_test_func():
        if test_name == "insert_single":
            return await bench.insert_single()
        elif test_name == "insert_bulk_100":
            return await bench.insert_bulk(100)
        elif test_name == "select_pk":
            return await bench.select_pk(next_id())
        elif test_name == "select_filter":
            return await bench.select_filter()
        elif test_name == "update_single":
            return await bench.update_single(next_id())
        elif test_name == "update_bulk":
            return await bench.update_bulk()
        elif test_name == "delete_single":
            return await bench.delete_single(next_id())
        elif test_name == "filter_simple":
            return await bench.filter_simple()
        elif test_name == "filter_complex":
            return await bench.filter_complex()
        elif test_name == "filter_in":
            return await bench.filter_in(pre_generated_ids[:100])
        elif test_name == "order_limit":
            return await bench.order_limit()
        elif test_name == "aggregate_count":
            return await bench.aggregate_count()
        elif test_name == "aggregate_mixed":
            return await bench.aggregate_mixed()
        elif test_name == "join_simple":
            return await bench.join_simple()
        elif test_name == "join_filter":
            return await bench.join_filter()
        elif test_name == "prefetch_related":
            return await bench.prefetch_related()
        elif test_name == "nested_prefetch":
            return await bench.nested_prefetch()
        elif test_name == "concurrent_10":
            return await bench.concurrent_select(10)
        elif test_name == "concurrent_25":
            return await bench.concurrent_select(25)
        elif test_name == "concurrent_50":
            return await bench.concurrent_select(50)
        elif test_name == "concurrent_75":
            return await bench.concurrent_select(75)
        elif test_name == "concurrent_100":
            return await bench.concurrent_select(100)
        elif test_name == "concurrent_150":
            return await bench.concurrent_select(150)
        elif test_name == "concurrent_200":
            return await bench.concurrent_select(200)
        else:
            raise ValueError(f"Unknown test: {test_name}")

    result = await measure(
        get_test_func,
        iterations=iterations,
        warmup=warmup,
    )

    return result.to_dict()


async def main():
    from common.schema import setup_schema, prepare_data, kill_all_connections

    iterations = config.get("iterations", 100)
    warmup = config.get("warmup", 10)
    users_count = config.get("users_count", 1000)
    posts_per_user = config.get("posts_per_user", 5)
    tests_to_run = config.get("tests", [])

    # Get benchmark class
    BenchClass = get_benchmark_class(orm_name)
    if not BenchClass:
        print(json.dumps({"error": f"Unknown ORM: {orm_name}"}))
        return

    bench = BenchClass()
    results = {}

    try:
        for test_name in tests_to_run:
            try:
                print(
                    f"[DEBUG] === Starting test: {test_name} ===",
                    file=sys.stderr,
                    flush=True,
                )

                # Reset database before each test
                print("[DEBUG] setup_schema...", file=sys.stderr, flush=True)
                await setup_schema(db_url)
                print("[DEBUG] prepare_data...", file=sys.stderr, flush=True)
                await prepare_data(
                    db_url, users=users_count, posts_per_user=posts_per_user
                )

                # Setup ORM
                print("[DEBUG] bench.setup...", file=sys.stderr, flush=True)
                await bench.setup(db_url)

                # Pre-generate IDs
                pre_generated_ids = list(range(1, users_count + 1))
                random.shuffle(pre_generated_ids)

                # Run test
                print(f"[DEBUG] run_test({test_name})...", file=sys.stderr, flush=True)
                result = await run_test(
                    bench, test_name, iterations, warmup, pre_generated_ids
                )
                results[test_name] = result
                print("[DEBUG] run_test done", file=sys.stderr, flush=True)

                # Teardown between tests
                print("[DEBUG] bench.teardown...", file=sys.stderr, flush=True)
                await bench.teardown()
                print(
                    f"[DEBUG] === Test {test_name} completed ===",
                    file=sys.stderr,
                    flush=True,
                )

            except Exception as e:
                results[test_name] = {"error": str(e)}
                try:
                    await bench.teardown()
                except Exception:
                    pass

        # Final cleanup
        try:
            await kill_all_connections(db_url)
        except Exception:
            pass

    except Exception as e:
        results["_setup_error"] = str(e)

    # Output results as JSON
    output = {
        "orm_name": bench.name if hasattr(bench, "name") else orm_name,
        "results": results,
    }
    print(json.dumps(output))


if __name__ == "__main__":
    asyncio.run(main())
