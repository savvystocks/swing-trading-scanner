"""7-pattern confluence detectors for the flow-first scanner.

Each detector returns a dict with:
  fires: bool
  side: 'CALL' | 'PUT' | None
  score: int (points contributed to confluence total)
  label: str (human-readable signal description)
  details: dict (raw signal data for debugging/email rendering)
"""
