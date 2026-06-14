#!/usr/bin/env python3
"""The mozbuild BuildBackend that feeds the build-IR mozbuild frontend.

This is the production glue: run inside a configured mozilla-central via
`./mach build-backend -b BuildIR`, it walks the TreeMetadataEmitter object
stream and dumps the JSON `mozbuild_frontend.py` consumes — the mozbuild
analogue of meson's `introspect --targets`.

Validated against the real Mozilla object model (gecko-dev
python/mozbuild/mozbuild/frontend/data.py + emitter.py):

  * a target's context dir is `obj.relsrcdir` (ContextDerived)
  * library name is `obj.basename` (BaseLibrary); program name is `obj.program`
    (BaseProgram)
  * dependencies are `obj.linked_libraries` — *resolved* Library objects on the
    Linkable, keyed by `.basename` — NOT the raw USE_LIBS strings
  * Sources/UnifiedSources carry `.files`; GeneratedFile carries
    `.script/.method/.inputs/.outputs`; Defines carries `.defines`;
    LocalInclude carries `.path`

`record()` dispatches on the class *name* so it runs against real emitter
objects (inside mach) and against shaped test doubles (here) without importing
mozbuild — the BuildIRBackend subclass below is the only part that needs it.
"""
import json
import os
import re

_LIB_TYPES = {
    "StaticLibrary", "SharedLibrary", "Library", "RustLibrary",
    "SandboxedWasmLibrary", "HostLibrary", "HostSharedLibrary",
}
_PROG_TYPES = {"Program", "SimpleProgram", "HostProgram", "HostSimpleProgram"}
_SOURCES_TYPES = {"Sources", "UnifiedSources", "HostSources", "WasmSources"}


def _str_list(xs):
    return [str(x) for x in (xs or [])]


def _gen_name(outputs):
    """GeneratedFile has no name; synthesize a stable one from its first output."""
    stem = os.path.splitext(os.path.basename(str(outputs[0])))[0] if outputs else "generated"
    return re.sub(r"[^0-9A-Za-z_]", "_", stem)


def record(obj):
    """A single TreeMetadataEmitter object -> a dump record (or None to skip)."""
    kind = type(obj).__name__
    ctx = getattr(obj, "relsrcdir", "") or ""

    if kind == "GeneratedFile":
        return {
            "type": "GeneratedFile", "context": ctx,
            "name": _gen_name(obj.outputs),
            "script": str(obj.script) if obj.script else "",
            "method": obj.method or "",
            "inputs": _str_list(obj.inputs),
            "outputs": _str_list(obj.outputs),
        }
    if kind in _SOURCES_TYPES:
        return {"type": "UnifiedSources" if kind == "UnifiedSources" else "Sources",
                "context": ctx, "files": _str_list(obj.files)}
    if kind in ("Defines", "HostDefines", "WasmDefines"):
        return {"type": "Defines", "context": ctx, "defines": dict(obj.defines)}
    if kind == "LocalInclude":
        return {"type": "LocalInclude", "context": ctx, "path": str(obj.path)}
    if kind in _LIB_TYPES:
        return {"type": kind, "context": ctx, "name": obj.basename,
                "use_libs": [l.basename for l in getattr(obj, "linked_libraries", [])]}
    if kind in _PROG_TYPES:
        return {"type": kind, "context": ctx, "name": obj.program,
                "use_libs": [l.basename for l in getattr(obj, "linked_libraries", [])]}
    return None


def dump(objs, out):
    """Serialize an emitter object stream to the frontend's JSON."""
    json.dump([r for r in (record(o) for o in objs) if r], out, indent=2)


# --- the actual mach backend (only imports mozbuild when run inside mach) ----
try:
    from mozbuild.backend.base import BuildBackend  # noqa: E402

    class BuildIRBackend(BuildBackend):
        """`./mach build-backend -b BuildIR` -> build_ir.objects.json in the objdir."""

        def _init(self):
            self._records = []

        def consume_object(self, obj):
            rec = record(obj)
            if rec is not None:
                self._records.append(rec)
            return True

        def consume_finished(self):
            path = os.path.join(self.environment.topobjdir, "build_ir.objects.json")
            with open(path, "w") as fh:
                json.dump(self._records, fh, indent=2)
except ImportError:
    BuildIRBackend = None  # not running inside mach; record()/dump() still usable
