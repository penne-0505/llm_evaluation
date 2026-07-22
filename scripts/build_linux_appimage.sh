#!/usr/bin/env bash
set -euo pipefail

readonly APPIMAGETOOL_VERSION="1.9.1"
readonly APPIMAGETOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"
readonly APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-x86_64.AppImage"
readonly APPIMAGE_RUNTIME_VERSION="20251108"
readonly APPIMAGE_RUNTIME_SHA256="2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d"
readonly APPIMAGE_RUNTIME_URL="https://github.com/AppImage/type2-runtime/releases/download/${APPIMAGE_RUNTIME_VERSION}/runtime-x86_64"

version="${1:-dev-local}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
work_root="$(mktemp -d "${TMPDIR:-/tmp}/prism-appimage.XXXXXX")"
appdir="$work_root/PrismLLMEval.AppDir"
pyinstaller_dist="$work_root/pyinstaller-dist"
pyinstaller_work="$work_root/pyinstaller-work"
tool_path="$work_root/appimagetool-${APPIMAGETOOL_VERSION}-x86_64.AppImage"
runtime_path="$work_root/runtime-${APPIMAGE_RUNTIME_VERSION}-x86_64"
artifact_basename="prism-llm-eval-${version}-linux-x86_64.AppImage"
artifact_path="$repo_root/dist/$artifact_basename"

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "Linux x86_64 host is required to build this AppImage." >&2
  exit 1
fi

if [[ -e "$artifact_path" || -e "$artifact_path.sha256" ]]; then
  echo "Output already exists: $artifact_path (or its checksum)." >&2
  echo "Use a new version label or move the existing artifact before rebuilding." >&2
  exit 1
fi

cd "$repo_root"

echo "Installing Python dependencies..."
uv sync

echo "Installing frontend dependencies..."
npm ci --prefix frontend

echo "Building frontend..."
npm run build --prefix frontend

echo "Building Linux onedir bundle with PyInstaller..."
uv run --with pyinstaller==6.21.0 pyinstaller \
  packaging/linux/prism-llm-eval.spec \
  --noconfirm \
  --clean \
  --distpath "$pyinstaller_dist" \
  --workpath "$pyinstaller_work"

echo "Assembling AppDir..."
mkdir -p \
  "$appdir/usr/lib" \
  "$appdir/usr/bin" \
  "$appdir/usr/share/applications" \
  "$appdir/usr/share/icons/hicolor/scalable/apps" \
  "$repo_root/dist"
cp -a "$pyinstaller_dist/prism-llm-eval" "$appdir/usr/lib/prism-llm-eval"
cp packaging/linux/AppRun "$appdir/AppRun"
cp packaging/linux/prism-llm-eval.desktop "$appdir/prism-llm-eval.desktop"
cp packaging/linux/prism-llm-eval.desktop "$appdir/usr/share/applications/prism-llm-eval.desktop"
cp packaging/linux/prism-llm-eval.svg "$appdir/prism-llm-eval.svg"
cp packaging/linux/prism-llm-eval.svg "$appdir/usr/share/icons/hicolor/scalable/apps/prism-llm-eval.svg"
chmod +x "$appdir/AppRun"
ln -s ../lib/prism-llm-eval/prism-llm-eval "$appdir/usr/bin/prism-llm-eval"
ln -s prism-llm-eval.svg "$appdir/.DirIcon"

echo "Downloading appimagetool ${APPIMAGETOOL_VERSION}..."
curl --fail --location --silent --show-error "$APPIMAGETOOL_URL" --output "$tool_path"
echo "Downloading AppImage runtime ${APPIMAGE_RUNTIME_VERSION}..."
curl --fail --location --silent --show-error "$APPIMAGE_RUNTIME_URL" --output "$runtime_path"

# intent-invariant: INV-002 (DevOps/linux-appimage-release) — 外部build入力の改変を実行前に検知する。
echo "$APPIMAGETOOL_SHA256  $tool_path" | sha256sum --check --status
echo "$APPIMAGE_RUNTIME_SHA256  $runtime_path" | sha256sum --check --status
chmod +x "$tool_path"

echo "Creating AppImage: $artifact_path"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$tool_path" \
  --no-appstream \
  --runtime-file "$runtime_path" \
  "$appdir" \
  "$artifact_path"
chmod +x "$artifact_path"

(
  cd "$repo_root/dist"
  sha256sum "$artifact_basename" > "$artifact_basename.sha256"
)

echo "AppImage created at $artifact_path"
echo "SHA256 created at $artifact_path.sha256"
echo "Temporary build directory retained at $work_root"
