# Tech by Math, Networks tutorial 8: what limits one TCP connection. The window / RTT limit, the
# bandwidth-delay product, and a simulation of additive-increase / multiplicative-decrease with a loss
# every 1/p packets, compared with the Mathis formula. A model in Python, not a real TCP stack.
import math

print("Part 1. A connection can have at most one window in flight per round trip: rate <= window / RTT")
for win_kib, rtt_ms in ((64, 1), (64, 20), (64, 100), (1024, 100), (16384, 100)):
    rate = win_kib * 1024 * 8 / (rtt_ms / 1000) / 1e6
    print(f"   window {win_kib:>6} KiB, RTT {rtt_ms:>3} ms: at most {rate:>9,.1f} Mbit/s")
bdp = 1e9 * 0.080 / 8
print(f"   to fill 1 Gbit/s at RTT 80 ms the window must be >= bandwidth x delay = {bdp:,.0f} bytes = {bdp / 2**20:.1f} MiB")

print("\nPart 2. AIMD sawtooth: +1 segment per round trip, halve on a loss; one loss every 1/p segments")
MSS, RTT = 1460, 0.1
for p in (1e-2, 1e-3, 1e-4, 1e-5):
    cwnd, sent, since_loss, rounds = 10.0, 0.0, 0.0, 0
    total_rounds, total_sent = 0, 0.0
    while total_rounds < 200_000:
        sent_now = cwnd
        since_loss += sent_now
        total_sent += sent_now
        total_rounds += 1
        if since_loss >= 1 / p:
            cwnd = max(1.0, cwnd / 2)
            since_loss = 0.0
        else:
            cwnd += 1
    sim = total_sent / total_rounds * MSS * 8 / RTT / 1e6
    mathis = MSS * 8 / RTT * math.sqrt(3 / (2 * p)) / 1e6
    print(f"   loss rate {p:.0e}: simulated {sim:7.2f} Mbit/s, Mathis (MSS/RTT) x sqrt(3/(2p)) = {mathis:7.2f} Mbit/s")
