"""Why safetensors, not pickle: a deterministic, stdlib-only demonstration that a
pickle file executes arbitrary code the moment it is loaded, while a safetensors
file is inert data. This is the core of the AI supply-chain argument in Section
16.5. The payload here is harmless (it appends a marker to a list) but uses the
exact __reduce__ mechanism a real model-file exploit uses. Runs in CI, no deps.
"""

from __future__ import annotations

import pickle

_MARKER: list[str] = []


class _Payload:
    """A class whose __reduce__ runs code at unpickling time. PyTorch .bin/.pt
    files are pickles, so loading an untrusted one runs whatever the author put
    here. A real exploit would call os.system; this one just leaves a marker.
    """

    def __reduce__(self):
        return (_mark, ("code ran at load time",))


def _mark(message: str) -> str:
    _MARKER.append(message)
    return message


def demonstrate() -> bool:
    """Pickle a payload, load it, and confirm code executed on load. Returns True
    when the marker was set by the load, which is the unsafe behavior.
    """
    _MARKER.clear()
    blob = pickle.dumps(_Payload())
    pickle.loads(blob)            # this line alone runs _Payload.__reduce__
    return _MARKER == ["code ran at load time"]


def main() -> None:
    ran = demonstrate()
    print(f"pickle executed code on load : {ran}  (this is why .bin/.pt is unsafe)")
    print("safetensors load             : raw bytes + JSON header, no opcodes to run")
    print("controls: prefer safetensors, scan with modelscan, sign with model-signing,")
    print("          and emit a CycloneDX 1.7 AI-BOM (all validation-only here)")
    assert ran, "the pickle payload should have executed on load"


if __name__ == "__main__":
    main()
