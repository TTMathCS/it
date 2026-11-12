# Retry with back-off (NiFi 1.16 and later): a FlowFile sent to a relationship
# marked "retry" is put back, up to Number of Retry Attempts (default 10) times,
# and waits min(max back-off, 2^r x base) before retry r + 1, where r is the
# number of retries so far (StandardProcessSession.calculateBackoffTime).
# Defaults: penalty 30 sec, yield 1 sec, max back-off 10 mins (ProcessorNode).
from nifi_math import backoff_ms

for name, base in [("penalize the FlowFile (base = penalty duration, 30 s)", 30_000),
                   ("yield the processor (base = yield duration, 1 s)", 1_000)]:
    print(name)
    total = 0
    for r in range(10):                 # retried while r < 10
        w = backoff_ms(r, 600_000, base)
        total += w
        print(f"   retry {r + 1:>2}: wait min(600 s, 2^{r} x {base // 1000} s) = {w / 1000:>5.0f} s   total {total / 1000:>6,.0f} s")
    print(f"   all 10 retries: {total / 1000:,.0f} s = {total / 60_000:.1f} min, then the FlowFile goes to the relationship itself")
    print()
