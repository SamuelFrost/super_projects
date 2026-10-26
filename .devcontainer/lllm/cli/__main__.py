import asyncio
import sys

from lllm.cli.cli_config import _write_to_stdout, main

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _write_to_stdout("\n")
        print("lllm: interrupted", file=sys.stderr)
        raise SystemExit(130) from None
