#!/usr/bin/env python3
"""Golden tests for both build-IR frontends → the shared Bazel backend.

Proves the IR + emit_bazel are frontend-agnostic: a meson `introspect` fixture
and a mozbuild emitter-object fixture each produce their golden BUILD through the
same backend. No meson/bazel/mozilla tree needed — exercises the translation.

    python3 test_roundtrip.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import emit_bazel  # noqa: E402
import meson_frontend  # noqa: E402
import mozbuild_frontend  # noqa: E402


def _check(label, got, golden_path, spot_checks):
    golden = open(golden_path).read()
    if got != golden:
        sys.stderr.write("[{}] MISMATCH vs golden:\n{}\n".format(label, got))
        return False
    for msg, ok in spot_checks:
        if not ok(got):
            sys.stderr.write("[{}] spot-check failed: {}\n".format(label, msg))
            return False
    print("PASS {}".format(label))
    return True


def _within(text, target, needle):
    """needle appears inside the `target` block of `text`."""
    blk = text.split('name = "{}"'.format(target), 1)[-1].split("\n)", 1)[0]
    return needle in blk


def main():
    td = os.path.join(HERE, "testdata")
    ok = True

    # meson: target grouping + link-line dep + codegen flag mapping.
    targets = json.load(open(os.path.join(td, "demo.intro-targets.json")))
    got = emit_bazel.emit(meson_frontend.convert(targets, "/SRC", "demo"))
    ok &= _check("meson", got, os.path.join(td, "demo.golden.BUILD"), [
        ("link dep app->:core", lambda t: _within(t, "app", '":core"')),
        ("codegen cmd mapped", lambda t: 'cmd = "echo \\"#define DEMO_VERSION 1\\" > $@"' in t),
        ("build dir dropped from includes", lambda t: "demo-build" not in t),
    ])

    # mozbuild: per-context grouping + USE_LIBS deps + codegen consume-edge.
    objects = json.load(open(os.path.join(td, "firefox_like.objects.json")))
    got = emit_bazel.emit(mozbuild_frontend.convert(objects, "firefox"))
    ok &= _check("mozbuild", got, os.path.join(td, "firefox_like.golden.BUILD"), [
        ("USE_LIBS dep dombindings->:xpcom", lambda t: _within(t, "dombindings", '":xpcom"')),
        ("USE_LIBS dep firefox->:dombindings", lambda t: _within(t, "firefox", '":dombindings"')),
        ("generated cpp deduped in lib srcs",
         lambda t: _within(t, "dombindings", '"dom/bindings/FooBinding.cpp"')
         and t.split('name = "dombindings"', 1)[-1].split("\n)", 1)[0].count("FooBinding.cpp") == 1),
        ("generated header folded into srcs", lambda t: _within(t, "dombindings", '"dom/bindings/FooBinding.h"')),
    ])

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
