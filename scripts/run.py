"""Entry point wrapper — invokes the sop_automation CLI."""
import sys
from sop_automation.cli import main

if __name__ == "__main__":
    sys.exit(main())
