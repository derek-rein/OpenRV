#!/usr/bin/env python3
"""Move non-Mach-O files out of nested-code locations before codesign.

codesign treats every regular file under Contents/MacOS, Contents/PlugIns and
Contents/Frameworks as nested code. A plain data file there (timeline.mu, a .py
plugin, a GLSL node, a .rvpkg) makes the seal fail with "code object is not
signed at all / In subcomponent: ...".

Apple's guidance (TN2206 / "Placing content in a bundle") is to keep only code
in those directories. For each bundle (the app and any nested .app/.bundle/
.plugin/.xpc that has a Contents dir) this moves every non-Mach-O regular file
to Contents/Resources/<same relative path> and leaves a relative symlink in its
place. RV finds plugins through -[NSBundle builtInPlugInsPath] and scans
PlugIns/<Type> directories (QDir / opendir follow symlinks), so lookups keep
working. Mirroring the relative layout also keeps realpath(__file__)-relative
lookups between data files working (e.g. otio_reader -> ../SupportFiles).

Exceptions, signed in place instead (codesign stores the signature in xattrs):
  * executable scripts (shebang + exec bit) in Contents/MacOS, because RV runs
    them by path next to the executable and they may use their own dirname
    (crashpad_handler_macos.sh);
  * files whose Resources destination already exists.

Files inside nested .framework bundles are left alone; frameworks have their own
Versions/X/Resources layout and are sealed as a unit.

Prints the in-place list NUL-separated on stdout. Log lines go to stderr.
"""
import os
import stat
import sys

CODE_DIRS = ("MacOS", "PlugIns", "Frameworks")
BUNDLE_EXTS = (".app", ".framework", ".bundle", ".plugin", ".xpc", ".appex", ".dSYM")
MACHO_MAGIC = {
    b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca",
}


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def is_macho(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) in MACHO_MAGIC
    except OSError:
        return False


def is_exec_script(path):
    st = os.lstat(path)
    if not st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
        return False
    with open(path, "rb") as f:
        return f.read(2) == b"#!"


def bundles(app):
    """The app plus nested bundles (with a Contents dir), deepest first."""
    found = [app]
    for root, dirs, _ in os.walk(app):
        for d in dirs:
            p = os.path.join(root, d)
            if d.endswith(BUNDLE_EXTS) and not d.endswith((".framework", ".dSYM")) \
                    and os.path.isdir(os.path.join(p, "Contents")):
                found.append(p)
    found.sort(key=lambda p: p.count(os.sep), reverse=True)
    return found


def process(bundle, in_place):
    contents = os.path.join(bundle, "Contents")
    resources = os.path.join(contents, "Resources")
    moved = 0
    for code_dir in CODE_DIRS:
        top = os.path.join(contents, code_dir)
        if not os.path.isdir(top) or os.path.islink(top):
            continue
        for root, dirs, files in os.walk(top):
            # Do not descend into nested bundles; they are handled on their own
            # (frameworks are left as-is).
            dirs[:] = [d for d in dirs if not d.endswith(BUNDLE_EXTS)
                       and not os.path.islink(os.path.join(root, d))]
            for name in files:
                path = os.path.join(root, name)
                if os.path.islink(path) or not os.path.isfile(path):
                    continue
                if is_macho(path):
                    continue
                rel = os.path.relpath(path, contents)
                if code_dir == "MacOS" and is_exec_script(path):
                    log(f"sign-in-place (script) {rel}")
                    in_place.append(path)
                    continue
                dest = os.path.join(resources, rel)
                if os.path.lexists(dest):
                    log(f"sign-in-place (destination exists) {rel}")
                    in_place.append(path)
                    continue
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                os.rename(path, dest)
                os.symlink(os.path.relpath(dest, os.path.dirname(path)), path)
                moved += 1
                log(f"relocated {rel} -> Resources/{rel}")
    log(f"{bundle}: relocated {moved} non-Mach-O file(s)")


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: relocate_nonmacho.py RV.app")
    app = os.path.abspath(sys.argv[1])
    in_place = []
    for b in bundles(app):
        process(b, in_place)
    sys.stdout.buffer.write(b"".join(os.fsencode(p) + b"\0" for p in in_place))


if __name__ == "__main__":
    main()
