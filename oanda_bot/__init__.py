"""
oanda_bot package initializer.

This file is intentionally lightweight: no submodule imports to avoid side effects
and speed up `import oanda_bot`. Import subpackages directly when needed.
"""

__version__ = "0.1.0"

# Only expose version at package level; submodules should be imported explicitly
__all__ = ["__version__"]
