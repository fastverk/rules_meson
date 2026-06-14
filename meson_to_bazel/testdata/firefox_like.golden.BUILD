load("@rules_cc//cc:defs.bzl", "cc_binary", "cc_library")

genrule(
    name = "FooBinding",
    outs = [
        "dom/bindings/FooBinding.cpp",
        "dom/bindings/FooBinding.h",
    ],
    srcs = [
        "dom/bindings/Foo.webidl",
    ],
    cmd = "python Codegen.py codegen $(OUTS) $(SRCS)",
)

cc_library(
    name = "xpcom",
    srcs = [
        "xpcom/base/nsCOMPtr.cpp",
    ],
)

cc_library(
    name = "dombindings",
    srcs = [
        "dom/bindings/FooBinding.cpp",
        "dom/bindings/BindingUtils.cpp",
        "dom/bindings/FooBinding.h",
    ],
    includes = [
        "dom/bindings",
    ],
    defines = [
        "MOZILLA_INTERNAL_API",
    ],
    deps = [
        ":xpcom",
    ],
)

cc_binary(
    name = "firefox",
    srcs = [
        "browser/app/nsBrowserApp.cpp",
    ],
    deps = [
        ":dombindings",
    ],
)
