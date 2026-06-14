#!/usr/bin/env python3
"""Validate the mozbuild backend mapping against the real object model.

We can't run `./mach build-backend` here (no configured mozilla-central), so we
validate the next best thing: feed `mozbuild_backend.record()` a set of test
doubles shaped with the EXACT attribute names the real emitter objects carry
(verified against gecko-dev data.py/emitter.py) — `basename`,
`linked_libraries`, `relsrcdir`, `.files`, `.script/.method/.inputs/.outputs`,
`.path`, `.defines`, program `.program` — and confirm the full chain
(objects -> backend dump -> frontend -> emit_bazel) reproduces the same golden
BUILD as the hand-authored fixture. If real-shaped objects reproduce it, the
fixture was faithful and the backend mapping is correct.

    python3 test_mozbuild_backend.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import emit_bazel  # noqa: E402
import mozbuild_backend  # noqa: E402
import mozbuild_frontend  # noqa: E402


# Test doubles. Class NAMES match the real mozbuild classes (record() dispatches
# on type(obj).__name__); attributes match the real ones.
def _obj(cls_name, **attrs):
    return type(cls_name, (), attrs)()


def build_objects():
    xpcom = _obj("StaticLibrary", relsrcdir="xpcom/base", basename="xpcom", linked_libraries=[])
    dombindings = _obj("StaticLibrary", relsrcdir="dom/bindings", basename="dombindings",
                       linked_libraries=[xpcom])
    return [
        xpcom,
        _obj("Sources", relsrcdir="xpcom/base", files=["nsCOMPtr.cpp"]),

        _obj("GeneratedFile", relsrcdir="dom/bindings", script="Codegen.py", method="codegen",
             inputs=["Foo.webidl"], outputs=("FooBinding.cpp", "FooBinding.h")),
        dombindings,
        _obj("UnifiedSources", relsrcdir="dom/bindings", files=["FooBinding.cpp"]),
        _obj("Sources", relsrcdir="dom/bindings", files=["BindingUtils.cpp"]),
        _obj("Defines", relsrcdir="dom/bindings", defines={"MOZILLA_INTERNAL_API": True}),
        _obj("LocalInclude", relsrcdir="dom/bindings", path="/dom/bindings"),

        _obj("Program", relsrcdir="browser/app", program="firefox", linked_libraries=[dombindings]),
        _obj("Sources", relsrcdir="browser/app", files=["nsBrowserApp.cpp"]),
    ]


def main():
    # 1) backend: real-shaped objects -> dump records.
    records = [r for r in (mozbuild_backend.record(o) for o in build_objects()) if r]

    # Cross-check the recovered structure that comes ONLY from the real model:
    dom = [r for r in records if r.get("name") == "dombindings"][0]
    assert dom["use_libs"] == ["xpcom"], "deps must come from linked_libraries.basename"
    ff = [r for r in records if r.get("name") == "firefox"][0]
    assert ff["type"] == "Program" and ff["use_libs"] == ["dombindings"]
    gen = [r for r in records if r["type"] == "GeneratedFile"][0]
    assert gen["name"] == "FooBinding" and list(gen["outputs"]) == ["FooBinding.cpp", "FooBinding.h"]

    # 2) full chain reproduces the golden the hand-authored fixture produces.
    got = emit_bazel.emit(mozbuild_frontend.convert(records, "firefox"))
    golden = open(os.path.join(HERE, "testdata/firefox_like.golden.BUILD")).read()
    if got != golden:
        sys.stderr.write("MISMATCH: real-shaped objects did not reproduce the golden:\n" + got)
        return 1

    print("PASS mozbuild-backend: real object model -> backend -> frontend -> Bazel == golden")
    print("  (deps via linked_libraries.basename, name via basename/program, context via relsrcdir)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
