#!/usr/bin/env python3
"""Golden test: meson introspect fixture -> build-IR -> BUILD.bazel.

Runs the frontend + backend on a checked-in real `meson introspect --targets`
fixture (testdata/demo.intro-targets.json, captured from a lib+exe+codegen
project) and asserts the emitted BUILD matches the golden. No meson/bazel needed
to run this — it exercises the translation, not the build.

    python3 test_roundtrip.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import emit_bazel  # noqa: E402
import meson_frontend  # noqa: E402


def main():
    targets = json.load(open(os.path.join(HERE, "testdata/demo.intro-targets.json")))
    graph = meson_frontend.convert(targets, "/SRC", "demo")
    got = emit_bazel.emit(graph)
    golden = open(os.path.join(HERE, "testdata/demo.golden.BUILD")).read()
    if got != golden:
        sys.stderr.write("MISMATCH between emitted BUILD and golden:\n")
        sys.stderr.write(got)
        return 1

    # Spot-check the three things compile_commands.json cannot express.
    assert 'cmd = "echo \\"#define DEMO_VERSION 1\\" > $@"' in got, "codegen cmd not mapped"
    assert 'deps = [\n        ":core",\n    ],' in got, "link dep app->core not recovered"
    assert "demo-build" not in got, "meson build dir leaked into includes"
    print("PASS: meson -> build-IR -> Bazel golden; deps + codegen + flag handling correct")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
