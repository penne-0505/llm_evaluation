// 段階的導入向けの共有スコープ解決: 既定では「導入以降に追加された docs」だけを
// 検証対象へ絞るための母集合を一箇所で決める。env 未設定なら null を返し、
// 全走査の従来挙動を保つ（後方互換）。

const DEFAULT_DIFF_FILTER = "A";
const DIFF_FILTER_RE = /^[ACDMRTUXB]+$/;
const COMPATIBILITY_BASELINE_HEADER = "path\tblob_sha1";
const SHA1_RE = /^[0-9a-f]{40}$/;

export type DocScope = Set<string> | null;
export type InScopePredicate = (path: string) => boolean;

const errorMessage = (err: unknown): string =>
  err instanceof Error ? err.message : String(err);

const normalizePath = (path: string): string => {
  const segments: string[] = [];
  for (const segment of path.replaceAll("\\", "/").split("/")) {
    if (segment === "" || segment === ".") continue;
    if (segment === "..") segments.pop();
    else segments.push(segment);
  }
  return segments.join("/");
};

// env 読み取りは権限が無くても安全側（未設定扱い = 全走査）に倒す。
const readEnv = (key: string): string | undefined => {
  try {
    return Deno.env.get(key);
  } catch {
    return undefined;
  }
};

const fromPathList = (raw: string): string[] =>
  raw
    .split(/[\n:]+/)
    .map((entry) => entry.trim())
    .filter(Boolean)
    .map(normalizePath);

const diffFilter = (): string => {
  const raw = readEnv("DD_SCOPE_DIFF_FILTER")?.trim();
  if (raw === undefined || raw === "") return DEFAULT_DIFF_FILTER;
  if (!DIFF_FILTER_RE.test(raw)) {
    throw new Error(
      `scope: DD_SCOPE_DIFF_FILTER must contain only git diff-filter letters (${raw})`,
    );
  }
  return raw;
};

// Deno blocks --allow-run=<binary> when the current process has
// LD_LIBRARY_PATH / LD_PRELOAD. Passing a sanitized `env` alone is not enough;
// clearEnv must replace the child environment entirely.
const gitCommandOptions = (
  args: string[],
): Deno.CommandOptions => {
  const env = { ...Deno.env.toObject() };
  delete env.LD_LIBRARY_PATH;
  delete env.LD_PRELOAD;
  return {
    args,
    stdout: "piped",
    stderr: "piped",
    clearEnv: true,
    env,
  };
};

const fromGitDiff = async (base: string): Promise<string[]> => {
  const filter = diffFilter();
  let output: Deno.CommandOutput;
  try {
    const command = new Deno.Command(
      "git",
      gitCommandOptions([
        "diff",
        "--name-only",
        `--diff-filter=${filter}`,
        `${base}...HEAD`,
      ]),
    );
    output = await command.output();
  } catch (err) {
    throw new Error(
      `scope: DD_SCOPE_BASE is set but "git" could not run (need --allow-run=git): ${
        errorMessage(err)
      }`,
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

const runGit = async (
  args: string[],
  errorContext: string,
): Promise<string> => {
  let output: Deno.CommandOutput;
  try {
    output = await new Deno.Command("git", gitCommandOptions(args)).output();
  } catch (err) {
    throw new Error(`scope: ${errorContext}: ${errorMessage(err)}`);
  }
  if (!output.success) {
    const stderr = new TextDecoder().decode(output.stderr).trim();
    throw new Error(
      `scope: ${errorContext}: ${stderr || `exit ${output.code}`}`,
    );
  }
  return new TextDecoder().decode(output.stdout).trim();
};

const compatibilityBaselinePath = (): string | undefined =>
  readEnv("DD_SCOPE_COMPATIBILITY_BASELINE")?.trim();

const readCompatibilityBaseline = async (
  path: string,
): Promise<Map<string, string>> => {
  let source: string;
  try {
    source = await Deno.readTextFile(path);
  } catch (err) {
    throw new Error(
      `scope: cannot read compatibility baseline "${path}": ${
        errorMessage(err)
      }`,
    );
  }

  const lines = source.replace(/^\uFEFF/, "").split(/\r?\n/);
  if (lines.shift() !== COMPATIBILITY_BASELINE_HEADER) {
    throw new Error(
      `scope: compatibility baseline "${path}" must start with "${COMPATIBILITY_BASELINE_HEADER}"`,
    );
  }

  const entries = new Map<string, string>();
  for (const [index, raw] of lines.entries()) {
    if (raw === "" || raw.startsWith("#")) continue;
    const columns = raw.split("\t");
    if (columns.length !== 2 || columns.some((column) => column === "")) {
      throw new Error(
        `scope: malformed compatibility baseline row ${index + 2} in "${path}"`,
      );
    }
    const [entryPath, blob] = columns as [string, string];
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

const matchesCompatibilityBaseline = async (
  path: string,
  blob: string,
): Promise<boolean> => {
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

const excludeExactCompatibilityBaselines = async (
  paths: string[],
  manifestPath: string,
): Promise<Set<string>> => {
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
export const loadScope = async (): Promise<DocScope> => {
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
export const makeInScope = (scope: DocScope): InScopePredicate => (path) =>
  scope === null || scope.has(normalizePath(path));

export { normalizePath };
