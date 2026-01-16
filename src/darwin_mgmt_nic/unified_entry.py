"""Unified entry point for darwin-nic package"""

import sys
from pathlib import Path

# Add current directory to path for development
current_dir = Path(__file__).parent
if (current_dir / "darwin-nic").exists():
    sys.path.insert(0, str(current_dir))

# Import the main function from our unified entry point
from darwin_nic import main

if __name__ == '__main__':
    sys.exit(main())