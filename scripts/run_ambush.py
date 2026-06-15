import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.catalyst.ambush_generator import run

if __name__ == "__main__":
    run(
        preview="--preview" in sys.argv,
        force="--force" in sys.argv,
        alert="--alert" in sys.argv,
    )
