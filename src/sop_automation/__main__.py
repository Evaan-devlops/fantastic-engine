"""Allow `python -m sop_automation` to invoke the CLI."""
import sys

from sop_automation.cli import main

if __name__ == "__main__":
    sys.exit(main())
