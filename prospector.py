#!/usr/bin/env python3
"""
Prospector — correo frío B2B, escrito uno a uno.

    python prospector.py buscar "Providencia"
    python prospector.py analizar
    python prospector.py lista
"""

import sys

from prospector.cli import main

if __name__ == "__main__":
    sys.exit(main())
