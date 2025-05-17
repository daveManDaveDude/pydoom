# Ensure that the project root is on the Python path for imports
import sys
import os

# Insert project root (one level up from tests directory)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))