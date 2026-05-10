"""Stepped review algorithm.

Mastery levels and their next-review delays after a 'good' answer:
  0 (new)        →  +0d  (still queued today)
  1              →  +1d
  2              →  +3d
  3              →  +7d
  4              →  +21d
  5 (mastered)   →  +60d

Result mapping:
  again  → mastery max(0, m-1), next +0d (today)
  hard   → mastery unchanged,  next +1d
  good   → mastery min(5, m+1), per table above
  easy   → mastery min(5, m+2), then per table
"""

from datetime import datetime, timedelta

DELAY_DAYS = {0: 0, 1: 1, 2: 3, 3: 7, 4: 21, 5: 60}


def apply_review(current_mastery: int, result: str) -> tuple[int, datetime]:
    m = current_mastery
    if result == "again":
        m = max(0, m - 1)
    elif result == "hard":
        pass
    elif result == "good":
        m = min(5, m + 1)
    elif result == "easy":
        m = min(5, m + 2)
    else:
        raise ValueError(f"unknown result: {result}")

    days = DELAY_DAYS.get(m, 0)
    next_at = datetime.utcnow() + timedelta(days=days)
    return m, next_at
