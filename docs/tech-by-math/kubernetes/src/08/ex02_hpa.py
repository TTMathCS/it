# Tech by Math, Kubernetes tutorial 8: the Horizontal Pod Autoscaler's rule (k8s_math.hpa, from
# replica_calculator.go; default tolerance 0.1), worked cases and a day of traffic. A model; no cluster ran.
import math
from k8s_math import hpa

print("Worked cases (target CPU utilisation 60% of the pods' requests):")
for reps, util in ((4, 90), (10, 65), (10, 50), (3, 200), (6, 54)):
    r = util / 60
    print(f"   {reps:>2} pods at {util:>3}%: ratio {util}/60 = {r:.3f} -> {hpa(reps, r)} pods")

print("\nA day of traffic: demand in cores (each pod requests 1 core, target 60%, so a pod 'should' carry 0.6 core).")
print("The HPA looks again and again; utilisation is a whole percent, int(100 x used millicores / requested),")
print("as in metrics/utilization.go. (That pods cannot use more than they are given is ignored here.)")
demand = [3 + 9 * max(0.0, math.sin(math.pi * (h - 6) / 14)) for h in range(24)]   # cores, peak at 13:00
reps, rows = 5, []
for h, d in enumerate(demand):
    steps = 0
    while True:
        util = int(round(d * 1000) * 100 // (reps * 1000))      # whole percent of the requested CPU
        new = hpa(reps, util / 60)
        steps += 1
        if new == reps or steps > 20:
            break
        reps = new
    rows.append((h, d, reps, int(round(d * 1000) * 100 // (reps * 1000))))
for h, d, r, u in rows:
    ideal = -(-round(d * 1000) // 600)                       # ceil(demand / 0.6), in whole millicores
    print(f"   {h:02d}:00 demand {d:5.2f} cores -> {r:>2} pods (utilisation {u:>3}%; ceil(demand / 0.6) = {ideal:>2})")
