# meson_to_bazel — the build-IR slice

The first concrete slice of the build-translation stack described in polyglot's
`docs/src/build-ir-seams.md`. It realizes **Layer B** (the build-target IR) with
a meson frontend and a Bazel backend:

```
meson introspect --targets   ──frontend──▶   build_ir.v1.BuildGraph   ──backend──▶   BUILD.bazel
   (meson_frontend.py)                       (build_ir.proto)                        (emit_bazel.py)
```

- **`build_ir.proto`** — the shared, frontend-agnostic schema. The thing that
  moves into a shared `build-ir` module (next to a `translator-core` harness
  shared with `rules_ci_ir`) once the **mozbuild** frontend lands. This is the
  consolidation point: moz.build becomes a *second frontend* into this IR, not a
  parallel build IR.
- **`meson_frontend.py`** — `meson introspect --targets` JSON → `BuildGraph`.
- **`emit_bazel.py`** — `BuildGraph` → `cc_library` / `cc_binary` / `genrule`.
  Frontend-agnostic, so meson and moz.build emit identical Bazel from one IR.

## Why this exists (vs. just using compile_commands.json)

A flat `compile_commands.json` (which `meson_configure` already captures, and
which is one structuring step from a Kythe `CompilationUnit`) is **per-TU and
lossy**. This slice recovers the structure it drops — demonstrated on the
checked-in fixture (a `library` + `executable` + `custom_target`):

- **target grouping** — `core.c` → `cc_library(core)`, `main.c` → `cc_binary(app)`;
- **dependency edges** — `app → :core`, recovered from the **link line**
  (meson's `introspect` leaves `depends` empty);
- **codegen** — the `custom_target` → a `genrule` (with meson's `@OUTPUT@`
  mapped to `$@` and the `sh -c` form unwrapped).

`build_ir.proto`'s `corpus` + `Target.name` are the **Kythe `VName` basis**: each
target down-projects to Layer-A `CompilationUnit`s, which is how polyglot's
`Lir → Entry` symbol graph can later **validate the decomposition** (§5 of the
seams doc).

## Run

```sh
python3 test_roundtrip.py        # golden test, no meson/bazel needed

# against a live meson build dir:
meson introspect <builddir> --targets > targets.json
python3 meson_frontend.py targets.json --root <srcroot> --corpus myproj > graph.json
python3 emit_bazel.py graph.json > BUILD.bazel
```

## Known gaps (next passes)

- **Generated-source consume edge.** `introspect --targets` does not surface a
  library *consuming* a `custom_target` output as a source (only the codegen
  step itself). Recovering produces→consumes for generated headers needs the
  ninja graph (`ninja -t deps`). Link deps are recovered cleanly today.
- **Rust / linker libs / system deps / generated-include dirs** — not yet mapped.
- **`translator-core` + Kythe `CompilationUnit` emit** — the IR is in place; the
  harness extraction and the Layer-A down-projection are the next steps.
- **mozbuild frontend** — the second frontend (`TreeMetadataEmitter` →
  `BuildGraph`), which is what the Firefox decomposition consumes.
