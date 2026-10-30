import asyncio
import sys

from lllm.experimental_warnings import (
    HIDE_EXPERIMENTAL_WARNINGS_FLAG,
    hide_experimental_warnings,
)

if HIDE_EXPERIMENTAL_WARNINGS_FLAG in sys.argv:
    hide_experimental_warnings()

from lllm.cli.cli_config import write_to_stdout, main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        write_to_stdout("\n")
        print("lllm: interrupted", file=sys.stderr)
        raise SystemExit(130) from None
