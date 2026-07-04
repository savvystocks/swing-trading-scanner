"""V12 brain - a strictly isolated analytical layer.

ISOLATION INVARIANT (asserted by test_brain.py::test_isolation):
  - Nothing outside src/brain/ imports from src.brain.
  - Nothing in src/brain/ imports any execution module (sandbox_proactive_lab, poller,
    harvest_db, harvest_labeler, harvest_logger, src.catalyst.*, src.telegram, ...).
The brain reads ONLY the nightly gzipped snapshots from the private harvest-snapshots repo -
never the live harvest.db, never the live trading path. If every part of the brain crashed
forever, live trading and harvesting would be entirely unaffected.
"""
