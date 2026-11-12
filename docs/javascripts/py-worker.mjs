// Runs Python (Pyodide 314.0.7, MPL-2.0, self-hosted in assets/pyodide/) in a Web Worker, so a slow or endless
// program can be stopped without freezing the page. Used by javascripts/py-play.js. No packages are ever loaded.
import { loadPyodide } from "../assets/pyodide/pyodide.mjs";

const ready = loadPyodide({
  indexURL: new URL("../assets/pyodide/", import.meta.url).href,
  packages: [],
});

const HARNESS = `
import sys, io, time, traceback

def _akadian_run(code, tests):
    out = io.StringIO()
    old = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = out
    ns = {"__name__": "__main__"}
    res = {"error": None, "tests": [], "ms": 0}
    t0 = time.perf_counter()
    try:
        exec(compile(code, "solution.py", "exec"), ns)
        for call, want in tests:
            row = {"call": call, "want": want}
            try:
                got = eval(call, ns)
                exp = eval(want, {})
                ok = got == exp
                if not ok and isinstance(got, float) and isinstance(exp, (int, float)):
                    ok = abs(got - exp) < 1e-6
                row["ok"] = bool(ok)
                row["got"] = repr(got)
            except Exception:
                row["ok"] = False
                row["got"] = "error: " + traceback.format_exc(limit=-1).strip().splitlines()[-1]
            res["tests"].append(row)
    except Exception:
        tb = traceback.format_exc().splitlines()
        tb = [l for l in tb if "_akadian_run" not in l and "<exec>" not in l]
        res["error"] = "\\n".join(tb[-6:])
    finally:
        sys.stdout, sys.stderr = old
    res["ms"] = round((time.perf_counter() - t0) * 1000)
    res["out"] = out.getvalue()[-20000:]
    return res
`;

ready.then((py) => py.runPython(HARNESS));

self.onmessage = async (e) => {
  const { id, code, tests } = e.data;
  try {
    const py = await ready;
    const run = py.globals.get("_akadian_run");
    const r = run(code, py.toPy(tests));
    const res = r.toJs({ dict_converter: Object.fromEntries });
    r.destroy();
    run.destroy();
    self.postMessage({ id, res });
  } catch (err) {
    self.postMessage({ id, res: { error: String(err && err.message || err), tests: [], out: "" } });
  }
};
