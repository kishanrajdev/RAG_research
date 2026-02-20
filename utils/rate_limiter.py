import time

class RateLimiter:
    """Simple token-bucket limiter: max_calls per period (seconds)."""
    def __init__(self, max_calls: int, period: float):
        self.max_calls = float(max_calls)
        self.period = float(period)
        self.allowance = float(max_calls)
        self.last_check = time.monotonic()

    def wait(self) -> None:
        while True:
            now = time.monotonic()
            elapsed = now - self.last_check
            self.last_check = now

            # refill tokens
            self.allowance += elapsed * (self.max_calls / self.period)
            if self.allowance > self.max_calls:
                self.allowance = self.max_calls

            # if we have a token, consume one and proceed
            if self.allowance >= 1.0:
                self.allowance -= 1.0
                return

            # otherwise sleep until a token should be available
            sleep_time = (1.0 - self.allowance) * (self.period / self.max_calls)
            time.sleep(sleep_time)