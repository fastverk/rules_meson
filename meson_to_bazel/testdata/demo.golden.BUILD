load("@rules_cc//cc:defs.bzl", "cc_binary", "cc_library")

genrule(
    name = "gen_version",
    outs = [
        "version.h",
    ],
    cmd = "echo \"#define DEMO_VERSION 1\" > $@",
)

cc_library(
    name = "core",
    srcs = [
        "core.c",
    ],
    includes = [
        ".",
        "inc",
    ],
    defines = [
        "CORE_BUILD",
    ],
    copts = [
        "-Wall",
        "-O0",
        "-g",
    ],
)

cc_binary(
    name = "app",
    srcs = [
        "main.c",
    ],
    includes = [
        ".",
        "inc",
    ],
    copts = [
        "-Wall",
        "-O0",
        "-g",
    ],
    deps = [
        ":core",
    ],
)
