"""Tests for the local Capella bridge adapter."""

import json
import stat
from pathlib import Path

import pytest

from engineering_gateway.infrastructure.capella_adapter import (
    CapellaAdapterError,
    CapellaBridgeConfig,
    LocalCapellaAdapter,
)

# Preserve the existing test module while only changing the stale protocol message
# expectation below.

# ...
