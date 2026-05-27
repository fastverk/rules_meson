# rules_meson — internal notes

**Status:** private / local-only. Do not push to GitHub, do not register
in any bazel-registry, do not reference publicly.

## What this is

General-purpose meson → Bazel tooling, factored out of rules_postgres so
the meson machinery can be developed independently of any one consumer.
Same shape as rules_rdf (general layer) → rules_jena (concrete impl).

## v0 (M0) scope

Just the foundation:

- **`meson_tools` module extension** — http_archives meson 1.7.1 source
  + http_files prebuilt ninja 1.12.1 (darwin universal2 for now). Both
  sha256-pinned.
- **`meson_configure` build rule** — runs `meson setup` hermetically,
  emits compile_commands.json + a log file. Path-relativization happens
  inside `meson_runner.py` so output is portable across sandboxes.
- **Hello-world example** — `examples/hello/` proves the toolchain
  works against a 2-line meson project before we point it at anything
  complicated.

## Future scope (deferred — see project_postgres_bazel_native memory)

- **M1**: extend `meson_configure` to also emit `meson_introspect.json`
  + capture generated headers as a TreeArtifact.
- **M2**: `meson_to_bazel` rule. Introspection-driven generator that
  emits cc_library / genrule per meson target. Validate against
  `examples/hello`, then `custom_target`, then `configure_file`
  examples BEFORE pointing at Postgres.
- **M3**: hermetic `bison_target` + `flex_target` rules mirroring
  meson's macros. Required for projects whose build uses code
  generation (Postgres' SQL parser being the canonical hard case).

## How rules_postgres consumes this

rules_postgres declares a local_path_override to rules_meson and uses
`meson_configure` directly. Its `pg_meson_configure` is a thin macro
wrapping `meson_configure` with PG-specific option defaults
(ssl=none, uuid=none, libcurl excluded for PG17) and the Postgres
overlay-header pre-removal list (pg_config.h etc.).

The `pre_remove` attr on `meson_configure` is the generic mechanism;
PG just happens to be its first consumer. Other meson projects with
similar source-tree-cleanup needs can use it too.

## Dev setup

- Bazel 9.1.0 (see `.bazelversion`).
- rules_meson is consumed via `local_path_override` from rules_postgres
  and rules_lang. Clone all three alongside each other.
- No system meson / ninja dep — everything fetched hermetically.

## Migrated assets (from rules_postgres, 2026-05-22)

| File | Old location | New location |
|---|---|---|
| meson_tools.bzl | rules_postgres/postgres/meson_tools.bzl | rules_meson/meson/meson_tools.bzl |
| meson_runner.py | rules_postgres/postgres/private/meson_runner.py | rules_meson/meson/private/meson_runner.py |
| meson_configure (rule) | rules_postgres/postgres/meson.bzl | rules_meson/meson/meson_configure.bzl |
| pg_meson_configure (macro) | (was the rule) | rules_postgres/postgres/meson.bzl (now a wrapper macro) |
