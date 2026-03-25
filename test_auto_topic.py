import sys
import os
import asyncio
from pydantic import BaseModel
from typing import Optional
from server import _generate_auto_topic

# Simulate basic testing
print(_generate_auto_topic("default"))
