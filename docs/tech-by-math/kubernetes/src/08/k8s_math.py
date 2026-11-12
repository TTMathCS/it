# The resource scores of the Kubernetes 1.34 scheduler and the HPA replica rule, written in Python from
# pkg/scheduler/framework/plugins/noderesources/{least,most,balanced}_allocated.go (integer arithmetic as in Go)
# and pkg/controller/podautoscaler/replica_calculator.go. Default weights: cpu 1, memory 1; MaxNodeScore 100.
import math

MAX = 100


def least_requested(requested, capacity):
    return 0 if capacity == 0 or requested > capacity else (capacity - requested) * MAX // capacity


def most_requested(requested, capacity):
    return 0 if capacity == 0 else min(requested, capacity) * MAX // capacity


def weighted(score_fn, req, alloc, weights=(1, 1)):
    s = sum(score_fn(r, a) * w for r, a, w in zip(req, alloc, weights))
    return s // sum(weights)


def balanced(req, alloc):
    fr = [min(r / a, 1.0) for r, a in zip(req, alloc)]
    std = abs(fr[0] - fr[1]) / 2 if len(fr) == 2 else 0.0
    return int((1 - std) * MAX)


def fits(used, pod, alloc):
    return all(u + p <= a for u, p, a in zip(used, pod, alloc))


def hpa(current_replicas, ratio, tolerance=0.1):
    """ratio = current metric / target. Inside [1 - tol, 1 + tol]: no change; else ceil(ratio x replicas)."""
    if 1 - tolerance <= ratio <= 1 + tolerance:
        return current_replicas
    return math.ceil(ratio * current_replicas)
