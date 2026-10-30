#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPDIR="$ROOT/.build/AppDir"
DIST="$ROOT/dist"
OWNER="${GITHUB_REPOSITORY_OWNER:-${GITHUB_REPOSITORY%%/*}}"
REPO="${GITHUB_REPOSITORY#*/}"
TAG="${GITHUB_REF_NAME:-latest}"
ASSET="Monitor-Tesouro-x86_64.AppImage"

# Fixados pelos SHA-256 dos assets oficiais verificados em 2026-10-29.
APPIMAGETOOL_SHA256="793fca0ce4bcc309dc65d3f66669f58e3755643e4dadbe03932e7b436128494f"
RUNTIME_SHA256="617aa77314d57c8b8e4fae9c3f0b35af7b30d5529cb69e98f64f92510ed98a46"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
RUNTIME_URL="https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64"

for command in python3 curl sha256sum ldd rsvg-convert; do
    command -v "$command" >/dev/null || { echo "Dependência ausente: $command" >&2; exit 1; }
done
[[ "$(uname -m)" == "x86_64" ]] || { echo "Este build gera AppImage x86_64." >&2; exit 1; }

PYTHON="$(readlink -f "$(command -v python3)")"
PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PYTHON_STDLIB="/usr/lib/python$PYTHON_VERSION"
[[ -x "$PYTHON" && -d "$PYTHON_STDLIB/lib-dynload" ]] || { echo "Python de sistema não encontrado em $PYTHON_STDLIB." >&2; exit 1; }
python3 -c 'import _ssl, _tkinter, tkinter, tomllib' || { echo "Instale Python, Tkinter e os módulos SSL/TOML do sistema." >&2; exit 1; }

rm -rf "$APPDIR" "$DIST"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib" "$APPDIR/usr/src" "$DIST"
install -Dm755 "$ROOT/packaging/AppDir/AppRun" "$APPDIR/AppRun"
VERSION="${TAG#v}"
sed "s/@VERSION@/$VERSION/g" "$ROOT/packaging/AppDir/monitor-tesouro.desktop" > "$APPDIR/monitor-tesouro.desktop"
rsvg-convert --width 256 --height 256 "$ROOT/packaging/AppDir/monitor-tesouro.svg" \
    -o "$APPDIR/monitor-tesouro.png"
install -Dm644 "$APPDIR/monitor-tesouro.png" "$APPDIR/.DirIcon"
cp -a "$ROOT/src/monitor_tesouro" "$APPDIR/usr/src/monitor_tesouro"
cp -a "$PYTHON_STDLIB" "$APPDIR/usr/lib/"
install -Dm755 "$PYTHON" "$APPDIR/usr/bin/python3"

# Bundle only non-core shared libraries required by Python SSL/Tk and their closure.
libdir="$APPDIR/usr/lib/x86_64-linux-gnu"
mkdir -p "$libdir"
SSL_MODULE="$(find "$APPDIR/usr/lib/python$PYTHON_VERSION/lib-dynload" -maxdepth 1 -name '_ssl*.so' -print -quit)"
TK_MODULE="$(find "$APPDIR/usr/lib/python$PYTHON_VERSION/lib-dynload" -maxdepth 1 -name '_tkinter*.so' -print -quit)"
[[ -n "$SSL_MODULE" && -n "$TK_MODULE" ]] || { echo "Módulos _ssl/_tkinter ausentes no runtime incluído." >&2; exit 1; }
queue=("$APPDIR/usr/bin/python3" "$SSL_MODULE" "$TK_MODULE")
while ((${#queue[@]})); do
    object="${queue[0]}"
    queue=("${queue[@]:1}")
    while read -r dependency; do
        [[ -n "$dependency" && -e "$dependency" ]] || continue
        name="$(basename "$dependency")"
        case "$name" in
            libc.so.*|libm.so.*|libpthread.so.*|libdl.so.*|librt.so.*|ld-linux*.so.*) continue ;;
        esac
        target="$libdir/$name"
        if [[ ! -e "$target" ]]; then
            install -Dm755 "$dependency" "$target"
            queue+=("$target")
        fi
    done < <(ldd "$object" 2>/dev/null | awk '$2 == "=>" && $3 ~ /^\// {print $3} $1 ~ /^\// {print $1}')
done

mkdir -p "$APPDIR/usr/share/tcltk" "$APPDIR/usr/lib/tcltk"
cp -a /usr/share/tcltk/. "$APPDIR/usr/share/tcltk/"
if [[ -d /usr/lib/tcltk ]]; then cp -a /usr/lib/tcltk/. "$APPDIR/usr/lib/tcltk/"; fi
install -Dm644 "$ROOT/LICENSE" "$APPDIR/usr/share/licenses/monitor-tesouro/LICENSE"
install -Dm644 "$ROOT/config.exemplo.toml" "$APPDIR/usr/share/monitor-tesouro/config.exemplo.toml"

appimagetool="$DIST/appimagetool-x86_64.AppImage"
runtime="$DIST/runtime-x86_64"
curl --fail --location --silent --show-error "$APPIMAGETOOL_URL" -o "$appimagetool"
curl --fail --location --silent --show-error "$RUNTIME_URL" -o "$runtime"
echo "$APPIMAGETOOL_SHA256  $appimagetool" | sha256sum --check --status || { echo "SHA-256 de appimagetool não confere." >&2; exit 1; }
echo "$RUNTIME_SHA256  $runtime" | sha256sum --check --status || { echo "SHA-256 do runtime AppImage não confere." >&2; exit 1; }
chmod +x "$appimagetool"

UPDATE_INFO="gh-releases-zsync|$OWNER|$REPO|latest|$ASSET.zsync"
FILE_URL="https://github.com/$OWNER/$REPO/releases/download/$TAG/$ASSET"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$appimagetool" \
    --runtime-file "$runtime" \
    --no-appstream \
    --file-url "$FILE_URL" \
    --updateinformation "$UPDATE_INFO" \
    "$APPDIR" "$DIST/$ASSET"

cat > "$DIST/Monitor-Tesouro-sem-fuse.sh" <<'LAUNCHER'
#!/bin/sh
set -eu
APPIMAGE_EXTRACT_AND_RUN=1
export APPIMAGE_EXTRACT_AND_RUN
APPIMAGE_FILE="$(dirname -- "$0")/Monitor-Tesouro-x86_64.AppImage"
exec "$APPIMAGE_FILE" "$@"
LAUNCHER
chmod +x "$DIST/Monitor-Tesouro-sem-fuse.sh"
rm -f "$appimagetool" "$runtime"
echo "Build concluído:"
ls -lh "$DIST/$ASSET" "$DIST/$ASSET.zsync" "$DIST/Monitor-Tesouro-sem-fuse.sh"
