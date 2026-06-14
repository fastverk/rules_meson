#!/usr/bin/env python3
"""meson frontend for the build-IR (Layer B).

Reads `meson introspect <builddir> --targets` JSON and emits a build_ir.v1
BuildGraph (as proto3-JSON). One of two planned frontends — the other is the
mozbuild TreeMetadataEmitter — that share build_ir.proto and the emit-bazel
backend. See polyglot docs build-ir-seams.md for the layering.

What this recovers that a flat compile_commands.json cannot:
  * target grouping     — which sources form which library/executable
  * dependency edges     — recovered from the link line (output-filename match),
                           since meson introspect leaves `depends` empty
  * codegen steps        — custom_target -> a GENERATED target (the command +
                           outputs that PRODUCE a source)

Known gap (documented, not hidden): meson `introspect --targets` does not
surface the *generated-source consume* edge (a library using a custom_target's
output as a source). Recovering produces->consumes for generated headers needs
the ninja graph (`ninja -t deps`) and is left for a later pass; link deps are
recovered cleanly here.

Usage:
    meson_frontend.py <introspect-targets.json> --root <source-root> \
        [--corpus NAME] > build_graph.json
"""
import argparse
import json
import os
import sys

_LIB_TYPES = ("shared library", "static library", "shared_library", "static_library", "library")
# Compile flags that are environment noise, not part of the target's identity.
_DROP_COPTS = ("-fdiagnostics-color=always", "-Winvalid-pch", "-pipe")


def _rel(path, root):
    """Repo-relative path if under root, else the basename."""
    try:
        if os.path.isabs(path) and root:
            r = os.path.relpath(path, root)
            return r if not r.startswith("..") else os.path.basename(path)
    except ValueError:
        pass
    return path


def _kind(meson_type):
    if meson_type in _LIB_TYPES:
        return "TARGET_KIND_LIBRARY"
    if meson_type == "executable":
        return "TARGET_KIND_EXECUTABLE"
    if meson_type == "custom":
        return "TARGET_KIND_GENERATED"
    return "TARGET_KIND_UNSPECIFIED"


def _language(lang):
    return {"c": "LANGUAGE_C", "cpp": "LANGUAGE_CXX", "rust": "LANGUAGE_RUST"}.get(
        lang, "LANGUAGE_UNSPECIFIED"
    )


def _split_params(params, root):
    """Partition a compiler parameter list into includes / defines / copts.

    Includes under the source root are relativized; build-internal include dirs
    — meson's per-target `.p` dirs and the build directory itself (which sits
    outside the source root) — are dropped, since Bazel reconstructs those.
    """
    includes, defines, copts = [], [], []
    for p in params:
        if p.startswith("-I"):
            d = p[2:]
            if os.path.isabs(d):
                if not root:
                    continue
                rel = os.path.relpath(d, root)
                # Outside the source root (the build dir) or a meson-internal
                # per-target `.p` dir -> not a source include.
                if rel.startswith("..") or rel.endswith(".p"):
                    continue
                includes.append(rel)
            else:
                includes.append(d or ".")
        elif p.startswith("-D"):
            defines.append(p[2:])
        elif p in _DROP_COPTS:
            continue
        else:
            copts.append(p)
    return includes, defines, copts


def _normalize_codegen_command(command):
    """Normalize meson's @OUTPUT@/@INPUT@ placeholders to neutral IR tokens
    ({OUTPUT}/{INPUT}); the Bazel backend maps those to $@/$(SRCS)."""
    out = []
    for a in command:
        a = a.replace("@OUTPUT0@", "{OUTPUT}").replace("@OUTPUT@", "{OUTPUT}")
        a = a.replace("@INPUT0@", "{INPUT}").replace("@INPUT@", "{INPUT}")
        out.append(a)
    return out


def _output_index(targets, root):
    """basename(output filename) -> target name, for link-dep recovery."""
    idx = {}
    for t in targets:
        for fn in t.get("filename", []):
            idx[os.path.basename(fn)] = t["name"]
    return idx


def convert(targets, root, corpus):
    out_index = _output_index(targets, root)
    ir_targets = []
    for t in targets:
        name = t["name"]
        kind = _kind(t["type"])
        target = {"name": name, "kind": kind, "component": ""}

        if kind == "TARGET_KIND_GENERATED":
            ts = (t.get("target_sources") or [{}])[0]
            target["codegen"] = {
                "command": _normalize_codegen_command(ts.get("compiler", [])),
                "inputs": [_rel(s, root) for s in ts.get("sources", [])],
                "outputs": [_rel(f, root) for f in t.get("filename", [])],
            }
            ir_targets.append(target)
            continue

        sources, includes, defines, copts, deps, lang = [], [], [], [], [], None
        for ts in t.get("target_sources", []):
            if "sources" in ts and ts.get("compiler"):
                lang = lang or ts.get("language")
                sources += [_rel(s, root) for s in ts["sources"]]
                inc, df, co = _split_params(ts.get("parameters", []), root)
                includes += inc
                defines += df
                copts += co
            if "linker" in ts:
                # Recover deps: any link param naming another target's output.
                for p in ts.get("parameters", []):
                    dep = out_index.get(os.path.basename(p))
                    if dep and dep != name:
                        deps.append(dep)

        target["language"] = _language(lang)
        if sources:
            target["sources"] = sources
        if includes:
            target["includes"] = sorted(set(includes))
        if defines:
            target["defines"] = sorted(set(defines))
        if copts:
            target["copts"] = copts
        if deps:
            target["deps"] = sorted(set(deps))
        ir_targets.append(target)

    return {"corpus": corpus, "root": root, "targets": ir_targets}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("introspect_targets")
    ap.add_argument("--root", required=True, help="source root paths are relative to")
    ap.add_argument("--corpus", default="", help="Kythe VName corpus for the graph")
    args = ap.parse_args(argv)
    targets = json.load(open(args.introspect_targets))
    graph = convert(targets, os.path.abspath(args.root), args.corpus)
    json.dump(graph, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main(sys.argv[1:])
