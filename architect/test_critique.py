"""Offline tests for design.critique (step 5): python test_critique.py   (no Minecraft, no network, no API spend).

A mocked client stands in for Anthropic: it records the call and hands back a canned response. Covers the parsing, the
no-change path (flaws empty -> the spec comes back exactly as given), the big-program guard (a critic that shrinks a
machine hall gets overruled), the refusal error, the plain-stream fallback and what the request carries (screenshots,
brief, report, rubric, model, structured-output schema).
"""
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).parent))
import shapes  # noqa: E402,F401  imported first on purpose (design imports massing)
import design  # noqa: E402
from test_design import spec, vol, feature  # noqa: E402

PNG = "iVBORw0KGgo="  # not a real picture: the mock never looks


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name, extra)
    if not cond:
        check.failed += 1


check.failed = 0


class Stream:
    def __init__(self, resp, boom=None):
        self.resp, self.boom = resp, boom

    def __enter__(self):
        if self.boom:
            raise self.boom
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.resp


class Client:
    """beta.messages.stream and messages.stream record their kwargs; the beta one can be made to fail."""

    def __init__(self, payload=None, stop="end_turn", beta_error=None, usage=None):
        text = json.dumps(payload)
        self.resp = NS(content=[NS(type="thinking", thinking="..."), NS(type="text", text=text)], stop_reason=stop,
                       usage=usage or NS(input_tokens=10000, output_tokens=2000, cache_creation_input_tokens=0,
                                         cache_read_input_tokens=0),
                       model="claude-sonnet-5-5")
        self.calls = []
        self.beta_error = beta_error
        self.beta = NS(messages=NS(stream=self._beta))
        self.messages = NS(stream=self._plain)

    def _beta(self, **kw):
        self.calls.append(("beta", kw))
        self.resp.model = kw["model"]  # the API reports the model that answered
        return Stream(self.resp, self.beta_error)

    def _plain(self, **kw):
        self.calls.append(("plain", kw))
        self.resp.model = kw["model"]
        return Stream(self.resp)


REPORT = {"kit": "station_white", "fixes": ["core: w 9 -> 15"], "notes": ["gear on labs s: no blank wall, skipped"],
          "doorways": 4, "blocks": 12345, "concept": "x", "volumes": [{"id": "core", "shape": "round"}]}
BRIEF = "a white research station with a ring lab around a core tower"


def base_spec():
    core = vol(id="core", shape="round", r=9, w=0, d=0, floor_hs=[8, 6, 6], program=["hall", "lab", "lab"])
    hall = vol(id="hall", w=21, d=17, floor_hs=[9], program=["machine_hall"],
               place={"mode": "attach", "to": "core", "side": "e", "gap": 0})
    return spec([core, hall], features=[feature("gear", "hall", side="s", size=4)])


def test_no_change():
    s = base_spec()
    before = json.dumps(s, sort_keys=True)
    client = Client({"flaws": [], "spec": s})
    new, flaws, cost = design.critique(client, BRIEF, s, REPORT, [("se view", PNG), ("nw view", PNG)])
    check("no change: the spec comes back unchanged", new == s and json.dumps(s, sort_keys=True) == before)
    check("no change: no flaws", flaws == [], flaws)
    # 10k in * $2/M + 2k out * $10/M = 0.04
    check("no change: cost from usage (Sonnet prices)", abs(cost - 0.04) < 1e-9, cost)
    # even a drifting spec with no flaws is ignored: the critic must name a flaw to change anything
    drift = copy.deepcopy(s)
    drift["volumes"][0]["r"] = 12
    new, flaws, _ = design.critique(Client({"flaws": [], "spec": drift}), BRIEF, s, REPORT, [])
    check("no change: a changed spec without flaws is ignored", new == s and new is s)


def test_changed():
    s = base_spec()
    fixed = copy.deepcopy(s)
    fixed["volumes"][0]["roof"] = "dome"
    fixed["features"][0]["on"] = "core"
    flaws_in = [{"what": "gear skipped, no blank wall", "fix": "moved the gear to the windowless core wall"},
                {"what": "core roof reads flat", "fix": "dome roof"}]
    new, flaws, cost = design.critique(Client({"flaws": flaws_in, "spec": fixed}), BRIEF, s, REPORT, [("se view", PNG)])
    check("changed: the corrected spec is returned", new == fixed and new["volumes"][0]["roof"] == "dome")
    check("changed: flaws parsed as what/fix pairs", flaws == flaws_in, flaws)
    check("changed: the input spec was not mutated", s["volumes"][0]["roof"] == "flat")
    # the composer accepts what the critic returns
    ghosts, rep = design.compose(new)
    check("changed: the result composes", rep["blocks"] > 1000, rep["blocks"])


def test_big_guard():
    s = base_spec()
    shrunk = copy.deepcopy(s)
    hall = shrunk["volumes"][1]
    hall["floor_hs"] = [6]
    hall["w"], hall["d"] = 15, 11
    shrunk["volumes"][0]["floor_hs"] = [8, 6]  # a normal volume may be changed
    shrunk["volumes"][0]["program"] = ["hall", "lab"]
    new, flaws, _ = design.critique(Client({"flaws": [{"what": "hall too tall", "fix": "shrank it"}], "spec": shrunk}),
                                    BRIEF, s, REPORT, [])
    h = new["volumes"][1]
    check("guard: the machine hall keeps its floor height", h["floor_hs"] == [9], h["floor_hs"])
    check("guard: the machine hall keeps its footprint", (h["w"], h["d"]) == (21, 17), (h["w"], h["d"]))
    check("guard: the guard says what it undid", sum(1 for f in flaws if f["what"].startswith("(guard)")) >= 2,
          [f["what"] for f in flaws])
    check("guard: a non-big volume's change goes through", new["volumes"][0]["floor_hs"] == [8, 6])
    # enlarging a big volume is fine
    bigger = copy.deepcopy(s)
    bigger["volumes"][1]["floor_hs"] = [12]
    bigger["volumes"][1]["w"] = 27
    new, flaws, _ = design.critique(Client({"flaws": [{"what": "a", "fix": "b"}], "spec": bigger}), BRIEF, s, REPORT, [])
    check("guard: enlarging a machine hall is allowed", new["volumes"][1]["floor_hs"] == [12] and new["volumes"][1]["w"] == 27
          and not any(f["what"].startswith("(guard)") for f in flaws), flaws)
    # dropping a big floor is undone too
    two = base_spec()
    two["volumes"][1]["floor_hs"] = [9, 9]
    two["volumes"][1]["program"] = ["machine_hall", "expansion"]
    cut = copy.deepcopy(two)
    cut["volumes"][1]["floor_hs"] = [9]
    cut["volumes"][1]["program"] = ["machine_hall"]
    new, flaws, _ = design.critique(Client({"flaws": [{"what": "a", "fix": "b"}], "spec": cut}), BRIEF, two, REPORT, [])
    check("guard: a dropped big floor is restored", new["volumes"][1]["floor_hs"] == [9, 9]
          and new["volumes"][1]["program"] == ["machine_hall", "expansion"], new["volumes"][1])


def test_request():
    s = base_spec()
    client = Client({"flaws": [], "spec": s})
    design.critique(client, BRIEF, s, REPORT, [("se view (isometric)", PNG), ("street view", PNG)])
    kind, kw = client.calls[0]
    check("request: the beta call with server-side fallbacks is tried first",
          kind == "beta" and kw.get("fallbacks") == "default" and "server-side-fallback-2026-07-01" in kw["betas"], kind)
    check("request: model is the critic model", kw["model"] == design.CRITIC_MODEL == "claude-sonnet-5-5", kw["model"])
    check("request: adaptive thinking", kw["thinking"] == {"type": "adaptive"}, kw["thinking"])
    fmt = kw["output_config"]["format"]
    check("request: structured output is the flaws + spec schema",
          fmt["type"] == "json_schema" and set(fmt["schema"]["properties"]) == {"flaws", "spec"}
          and fmt["schema"]["additionalProperties"] is False and fmt["schema"]["required"] == ["flaws", "spec"], fmt["schema"]["required"])
    check("request: the spec half of the schema is design.SCHEMA", fmt["schema"]["properties"]["spec"] == design.SCHEMA)
    check("request: the rubric (theme, silhouette, skipped features) and the hard rule are in the system prompt",
          all(w in kw["system"] for w in ("Theme and colour fidelity", "landmark", "SKIPPED", "never shrink floor heights"))
          and "Machine halls and expansion floors are 9-13 high" in kw["system"])
    content = kw["messages"][0]["content"]
    imgs = [b for b in content if b["type"] == "image"]
    text = "\n".join(b["text"] for b in content if b["type"] == "text")
    check("request: both screenshots are attached as images", len(imgs) == 2 and imgs[0]["source"]["data"] == PNG, len(imgs))
    check("request: brief, spec and report are in the text",
          BRIEF in text and '"machine_hall"' in text and "no blank wall, skipped" in text and "se view (isometric)" in text)
    check("request: the report is trimmed to what the critic needs", "concept" not in text.split("Composer report:")[1].split("Screenshots")[0])
    # an endpoint without the beta falls back to the plain stream
    client = Client({"flaws": [], "spec": s}, beta_error=RuntimeError("unknown beta header"))
    new, flaws, cost = design.critique(client, BRIEF, s, REPORT, [])
    check("fallback: a rejected beta retries with the plain stream", [c[0] for c in client.calls] == ["beta", "plain"]
          and "fallbacks" not in client.calls[1][1] and "betas" not in client.calls[1][1], [c[0] for c in client.calls])
    check("fallback: ...and still returns the result", new == s and cost > 0)
    client = Client({"flaws": [], "spec": s}, beta_error=RuntimeError("connection reset by peer"))
    try:
        design.critique(client, BRIEF, s, REPORT, [])
        ok = False
    except RuntimeError:
        ok = True
    check("fallback: an unrelated error is not swallowed", ok)


def test_refusal():
    s = base_spec()
    try:
        design.critique(Client({"flaws": [], "spec": s}, stop="refusal"), BRIEF, s, REPORT, [])
        ok = False
    except RuntimeError as e:
        ok = "refused" in str(e)
    check("refusal: raises so the caller keeps the current build", ok)
    # no volumes back: ignored, original kept
    new, flaws, _ = design.critique(Client({"flaws": [{"what": "x", "fix": "y"}], "spec": {**s, "volumes": []}}), BRIEF, s, REPORT, [])
    check("empty spec back: the original is kept", new == s and len(flaws) == 1)


def test_env_model():
    import importlib
    import os
    os.environ["ARCHITECT_CRITIC_MODEL"] = "claude-haiku-5-5"
    try:
        m = importlib.reload(design)
        check("env: ARCHITECT_CRITIC_MODEL picks the critic model", m.CRITIC_MODEL == "claude-haiku-5-5", m.CRITIC_MODEL)
        s = base_spec()
        c = Client({"flaws": [], "spec": s}, usage=NS(input_tokens=1_000_000, output_tokens=0))
        _, _, cost = m.critique(c, BRIEF, s, REPORT, [])
        check("env: a Haiku critic is priced as Haiku", c.calls[0][1]["model"] == "claude-haiku-5-5" and abs(cost - 0.10) < 1e-9, cost)
    finally:
        os.environ.pop("ARCHITECT_CRITIC_MODEL")
        importlib.reload(design)


def main():
    test_no_change()
    test_changed()
    test_big_guard()
    test_request()
    test_refusal()
    test_env_model()
    print()
    print("FAILED" if check.failed else "ALL OK", check.failed)
    return 1 if check.failed else 0


if __name__ == "__main__":
    sys.exit(main())
