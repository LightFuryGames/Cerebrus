"""
Wrapper for modular memreport tool.
Delegates to cerebrus.tools.memreport.main
"""

import sys
from pathlib import Path

# Add project root to path to allow absolute imports
root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from cerebrus.tools.memreport import main

if __name__ == "__main__":
    main()
