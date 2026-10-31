
"""Spaced repetition (SM-2 algorithm)."""
 
 
def update(ease: float, interval: int, reps: int, quality: int):
    """quality: 1=Again, 3=Hard, 4=Good, 5=Easy. Returns (ease, interval_days, reps)."""
    if quality < 3:
        reps, interval = 0, 0  # show again today
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = max(1, round(interval * ease))
        reps += 1
    ease = max(1.3, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    return ease, interval, reps