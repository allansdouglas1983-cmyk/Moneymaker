import concurrent.futures
import json
import sys
import time

sys.path.insert(0, "audit")
from extract_metadata import extract_market_metadata  # noqa: E402


def main() -> None:
    with open("audit/market_level_files.txt") as fh:
        paths = [line.strip() for line in fh if line.strip()]

    t0 = time.time()
    done = 0
    with open("audit/full_corpus_metadata.jsonl", "w") as out:
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
            for result in pool.map(extract_market_metadata, paths, chunksize=32):
                out.write(json.dumps(result) + "\n")
                done += 1
                if done % 2000 == 0:
                    elapsed = time.time() - t0
                    print(f"{done}/{len(paths)} done in {elapsed:.1f}s", file=sys.stderr)
    print(f"TOTAL: {done} files in {time.time() - t0:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
