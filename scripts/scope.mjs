// 段階的導入向けの共有スコープ解決: 既定では「導入以降に追加された docs」だけを
// 検証対象へ絞るための母集合を一箇所で決める。env 未設定なら null を返し、
// 全走査の従来挙動を保つ（後方互換）。

const DEFAULT_DIFF_FILTER = "A";
const DIFF_FILTER_RE = /^[ACDMRTUXB]+$/;
const COMPATIBILITY_BASELINE_HEADER = "path\tblob_sha1";
const SHA1_RE = /^[0-9a-f]{40}$/;

const normalizePath = (path) => {
  const segments = [];
  for (const segment of path.replaceAll("\\", "/").split("/")) {
    if (segment === "" || segment === ".") continue;
    if (segment === "..") segments.pop();
    else segments.push(segment);
  }
  return segments.join("/");
};

// env 読み取りは権限が無くても安全側（未設定扱い = 全走査）に倒す。
const readEnv = (key) => {
  try {
    return Deno.env.get(key);
  } catch {
    return undefined;
  }
};

const fromPathList = (raw) =>
  raw
    .split(/[\n:]+/)
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map(normalizePath);

const diffFilter = () => {
  const raw = readEnv("DD_SCOPE_DIFF_FILTER")?.trim();
  if (raw === undefined || raw === "") return DEFAULT_DIFF_FILTER;
  if (!DIFF_FILTER_RE.test(raw)) {
    throw new Error(
      `scope: DD_SCOPE_DIFF_FILTER must contain only git diff-filter letters (${raw})`,
    );
  }
  return raw;
};

const fromGitDiff = async (base) => {
  const filter = diffFilter();
  let output;
  try {
    const command = new Deno.Command("git", {
      args: [
        "diff",
        "--name-only",
        `--diff-filter=${filter}`,
        `${base}...HEAD`,
      ],
      stdout: "piped",
      stderr: "piped",
    });
    output = await command.output();
  } catch (err) {
    throw new Error(
      `scope: DD_SCOPE_BASE is set but "git" could not run (need --allow-run=git): ${err.message}`,
    );
  }
  if (!output.success) {
    const stderr = new TextDecoder().decode(output.stderr).trim();
    throw new Error(
      `scope: git diff against base "${base}" failed (exit ${output.code}): ${stderr}`,
    );
  }
  return new TextDecoder()
    .decode(output.stdout)
    .split(/\r?\n/)
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map(normalizePath);
};

const runGit = async (args, errorContext) => {
  let output;
  try {
    output = await new Deno.Command("git", {
      args,
      stdout: "piped",
      stderr: "piped",
    }).output();
  } catch (err) {
    throw new Error(`scope: ${errorContext}: ${err.message}`);
  }
  if (!output.success) {
    const stderr = new TextDecoder().decode(output.stderr).trim();
    throw new Error(
      `scope: ${errorContext}: ${stderr || `exit ${output.code}`}`,
    );
  }
  return new TextDecoder().decode(output.stdout).trim();
};

const compatibilityBaselinePath = () =>
  readEnv("DD_SCOPE_COMPATIBILITY_BASELINE")?.trim();

const readCompatibilityBaseline = async (path) => {
  let source;
  try {
    source = await Deno.readTextFile(path);
  } catch (err) {
    throw new Error(
      `scope: cannot read compatibility baseline "${path}": ${err.message}`,
    );
  }

  const lines = source.replace(/^\uFEFF/, "").split(/\r?\n/);
  if (lines.shift() !== COMPATIBILITY_BASELINE_HEADER) {
    throw new Error(
      `scope: compatibility baseline "${path}" must start with "${COMPATIBILITY_BASELINE_HEADER}"`,
    );
  }

  const entries = new Map();
  for (const [index, raw] of lines.entries()) {
    if (raw === "" || raw.startsWith("#")) continue;
    const columns = raw.split("\t");
    if (columns.length !== 2 || columns.some((column) => column === "")) {
      throw new Error(
        `scope: malformed compatibility baseline row ${index + 2} in "${path}"`,
      );
    }
    const [entryPath, blob] = columns;
    const normalized = normalizePath(entryPath);
    if (
      entryPath !== normalized ||
      entryPath.startsWith("/") ||
      !entryPath.endsWith(".md") ||
      !SHA1_RE.test(blob) ||
      entries.has(entryPath)
    ) {
      throw new Error(
        `scope: invalid compatibility baseline row ${index + 2} in "${path}"`,
      );
    }
    await runGit(
      ["ls-files", "--error-unmatch", "--", entryPath],
      `compatibility baseline path "${entryPath}" is unknown; add it to git, or remove its baseline row only after confirming its retirement`,
    );
    await runGit(
      ["cat-file", "-e", `${blob}^{blob}`],
      `compatibility baseline blob "${blob}" is unknown`,
    );
    entries.set(entryPath, blob);
  }
  if (entries.size === 0) {
    throw new Error(`scope: compatibility baseline "${path}" has no entries`);
  }
  return entries;
};

const matchesCompatibilityBaseline = async (path, blob) => {
  try {
    await Deno.stat(path);
  } catch (err) {
    if (err instanceof Deno.errors.NotFound) return false;
    throw err;
  }
  const currentBlob = await runGit(
    ["hash-object", "--", path],
    `cannot hash compatibility baseline path "${path}"`,
  );
  return currentBlob === blob;
};

const excludeExactCompatibilityBaselines = async (paths, manifestPath) => {
  const entries = await readCompatibilityBaseline(manifestPath);
  const scope = new Set(paths);
  for (const [path, blob] of entries) {
    if (scope.has(path) && await matchesCompatibilityBaseline(path, blob)) {
      scope.delete(path);
    }
  }
  return scope;
};

// 検証対象の母集合を返す。
// - DD_SCOPE_PATHS: 改行 / コロン区切りの明示パスリスト（テスト・CI 自前計算向け）。
// - DD_SCOPE_BASE: git ref。既定では `<ref>...HEAD` で追加されたファイルのみ。
// - DD_SCOPE_DIFF_FILTER: DD_SCOPE_BASE 使用時の git diff-filter。既定は A。
// - DD_SCOPE_COMPATIBILITY_BASELINE: git scope 内で、記録 blob と完全一致する
//   legacy Markdown を一時的に除外する TSV。内容変更・rename・delete は除外されない。
// - いずれも未設定: null（= 全走査）。
// 優先順位は DD_SCOPE_PATHS > DD_SCOPE_BASE > null。
export const loadScope = async () => {
  const paths = readEnv("DD_SCOPE_PATHS");
  if (paths !== undefined && paths.trim() !== "") {
    return new Set(fromPathList(paths));
  }
  const base = readEnv("DD_SCOPE_BASE");
  if (base !== undefined && base.trim() !== "") {
    const scope = await fromGitDiff(base.trim());
    const manifestPath = compatibilityBaselinePath();
    return manifestPath
      ? await excludeExactCompatibilityBaselines(scope, manifestPath)
      : new Set(scope);
  }
  return null;
};

// scope が null（= 全走査）のときは全ファイルが対象。
export const makeInScope = (scope) => (path) =>
  scope === null || scope.has(normalizePath(path));

export { normalizePath };
