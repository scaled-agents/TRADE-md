"""Allow `python -m trade_md` as an alias for the CLI."""
import sys

from trade_md.cli import main

sys.exit(main())
