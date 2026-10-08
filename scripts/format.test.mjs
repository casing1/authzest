import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { execFileSync, spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

import { preflight, runFormatter, validateEditorConfig } from "./format.mjs";

const editorConfig = `root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 2
trim_trailing_whitespace = true

[*.py]
indent_size = 4

[Makefile]
indent_style = tab
`;
const prettierIgnore = "dist\nnode_modules\npackage-lock.json\n";

function fixture(
  context,
  { git = false, prefix = "authzest-format-test-" } = {},
) {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), prefix)));
  context.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const write = (relative, content = "") => {
    const absolute = path.join(root, relative);
    fs.mkdirSync(path.dirname(absolute), { recursive: true });
    fs.writeFileSync(absolute, content);
  };
  write(".editorconfig", editorConfig);
  write("scripts/prettier-options.json", "{}\n");
  write("scripts/prettier-markdown.ignore", "");
  write("frontend/.prettierignore", prettierIgnore);
  write("frontend/src/example.ts", "const value = 1;\n");
  // Calls to the formatter are mocked; no fixture module is executed.
  write(
    "frontend/node_modules/prettier/bin/prettier.cjs",
    "// A regular file at the fixed installed CLI path.\n",
  );
  if (git) execFileSync("git", ["init", "--quiet", root]);
  else fs.mkdirSync(path.join(root, ".git"));
  const stage = (...files) =>
    execFileSync("git", ["-C", root, "add", "--", ...files]);
  return { root, write, stage };
}

function mockFormatter(input, result = { status: 0, signal: null }) {
  const calls = [];
  const status = runFormatter({
    ...input,
    spawn: (command, args, options) => {
      calls.push({ command, args, options });
      return result;
    },
  });
  return { status, calls };
}

function ordinaryFormattingFixture(context) {
  const installed = fileURLToPath(
    new URL("../frontend/node_modules/prettier/", import.meta.url),
  );
  if (!fs.existsSync(path.join(installed, "bin/prettier.cjs"))) {
    context.skip(
      "The installed Prettier module is needed for this integration",
    );
    return;
  }
  const input = fixture(context, { git: true });
  fs.cpSync(
    installed,
    path.join(input.root, "frontend/node_modules/prettier"),
    {
      recursive: true,
    },
  );
  const markdown = "# Coverage\n\n-    ordinary item\n";
  const typescript = "function coverage(){\nreturn {value:1}\n}\n";
  input.write("docs/ignored.md", markdown);
  input.write("frontend/src/ignored.ts", typescript);
  // Stage first: these remain tracked files after ambient ignores are added.
  input.stage("docs/ignored.md", "frontend/src/ignored.ts");
  input.write(".gitignore", "docs/ignored.md\nfrontend/src/ignored.ts\n");
  input.write(".prettierignore", "docs/ignored.md\nfrontend/src/ignored.ts\n");
  input.write("frontend/.gitignore", "src/ignored.ts\n");
  input.write("frontend/dist/excluded.ts", typescript);
  input.write("frontend/node_modules/excluded.ts", typescript);
  const lockfile = '{"name":"fixture","lockfileVersion":3}';
  input.write("frontend/package-lock.json", lockfile);
  const run = (mode, operation) => {
    let output = "";
    const status = runFormatter({
      root: input.root,
      mode,
      operation,
      spawn: (command, args, options) => {
        const result = spawnSync(command, args, {
          ...options,
          stdio: "pipe",
          encoding: "utf8",
        });
        output += `${result.stdout ?? ""}${result.stderr ?? ""}`;
        return result;
      },
    });
    return { status, output };
  };
  return { ...input, markdown, typescript, lockfile, run };
}

function assertLaunch(call, root, mode, operation, targets) {
  assert.equal(call.command, process.execPath);
  assert.equal(
    call.args[0],
    path.join(root, "frontend/node_modules/prettier/bin/prettier.cjs"),
  );
  const configIndex = call.args.indexOf("--config");
  assert.notEqual(configIndex, -1);
  assert.equal(
    call.args[configIndex + 1],
    path.join(root, "scripts/prettier-options.json"),
  );
  const ignoreFile = path.join(
    root,
    mode === "frontend"
      ? "frontend/.prettierignore"
      : "scripts/prettier-markdown.ignore",
  );
  const ignoreIndex = call.args.indexOf("--ignore-path");
  assert.notEqual(ignoreIndex, -1);
  assert.equal(call.args[ignoreIndex + 1], ignoreFile);
  assert.equal(call.args.filter((arg) => arg === "--ignore-path").length, 1);
  assert.equal(call.args.filter((arg) => arg === "--editorconfig").length, 1);
  assert.equal(call.args.filter((arg) => arg === operation).length, 1);
  assert.equal(
    call.args.filter((arg) => arg === "--check" || arg === "--write").length,
    1,
  );
  const separator = call.args.indexOf("--");
  assert.notEqual(separator, -1);
  assert.deepEqual(call.args.slice(separator + 1), targets);
  const options = call.args.slice(1, separator);
  const allowed = new Set([
    operation,
    "--editorconfig",
    "--config",
    path.join(root, "scripts/prettier-options.json"),
    "--ignore-path",
    ignoreFile,
  ]);
  assert.ok(options.every((arg) => allowed.has(arg)));
  assert.equal(
    call.options.cwd,
    mode === "frontend" ? path.join(root, "frontend") : root,
  );
  assert.equal(call.options.timeout, 120000);
  assert.equal(call.options.killSignal, "SIGKILL");
  assert.equal(call.options.stdio, "inherit");
  assert.equal(call.options.shell, false);
}

test("EditorConfig permits the repository policy, comments, CRLF, and approved values", () => {
  assert.doesNotThrow(() => validateEditorConfig(editorConfig));
  assert.doesNotThrow(() =>
    validateEditorConfig(
      `# Comment\n; Another comment\n${editorConfig}`.replaceAll("\n", "\r\n"),
    ),
  );
  const values = {
    charset: ["utf-8"],
    end_of_line: ["lf", "crlf", "cr"],
    indent_style: ["space", "tab"],
    indent_size: ["1", "4", "16", "tab"],
    insert_final_newline: ["true", "false"],
    trim_trailing_whitespace: ["true", "false"],
  };
  for (const [key, options] of Object.entries(values)) {
    for (const value of options) {
      assert.doesNotThrow(
        () => validateEditorConfig(`root = true\n[*]\n${key} = ${value}\n`),
        `${key}=${value}`,
      );
    }
  }
});

test("EditorConfig rejects unsupported declarations, duplicates, and malformed INI", () => {
  const invalid = [
    "[*]\nindent_size = 2\n",
    "root = false\n[*]\n",
    "root = true\nroot = true\n[*]\n",
    "root = true\ncharset = utf-8\n[*]\n",
    "root = true\n[*.py]\nindent_size = 4\n",
    "root = true\n[*]\n[*.js]\nindent_size = 2\n",
    "root = true\n[*]\n[{alpha,beta}]\nindent_size = 2\n",
    "root = true\n[*]\n[*]\n",
    "root = true\n[*]\n[*.py]\n[*.py]\n",
    "root = true\n[*]\n[Makefile]\n[Makefile]\n",
    "root = true\n[*]\nindent_size = 2\nindent_size = 4\n",
    "root = true\n[*]\nindent_size = 2\nINDENT_SIZE = 4\n",
    "root = true\n[*]\nunknown_key = true\n",
    "root = true\n[*]\nroot = true\n",
    "root true\n[*]\n",
    "root = true\n[*\n",
    "root = true\n[*] extra\n",
    "root = true\n[]\n[*]\n",
    "root = true\n[*]\nindent_size\n",
    "root = true\n[*]\n= 2\n",
    "root = true\n[*]\nindent_size =\n",
    "root = true\n[*]\nindent_size = 2 = 4\n",
  ];
  for (const text of invalid) assert.throws(() => validateEditorConfig(text));
  for (const [key, value] of [
    ["charset", "latin1"],
    ["end_of_line", "auto"],
    ["indent_style", "mixed"],
    ["indent_size", "0"],
    ["indent_size", "17"],
    ["indent_size", "2.5"],
    ["insert_final_newline", "yes"],
    ["trim_trailing_whitespace", "yes"],
  ]) {
    assert.throws(() =>
      validateEditorConfig(`root = true\n[*]\n${key} = ${value}\n`),
    );
  }
});

test("EditorConfig enforces the byte limit and rejects BOM and control characters", () => {
  const base = "root = true\n[*]\n";
  const boundary = `${base}#${" ".repeat(4096 - Buffer.byteLength(base) - 2)}\n`;
  assert.equal(Buffer.byteLength(boundary), 4096);
  assert.doesNotThrow(() => validateEditorConfig(boundary));
  assert.throws(() => validateEditorConfig(`${boundary} `));
  for (const character of ["\uFEFF", "\0", "\u000B", "\u001B", "\u007F"]) {
    assert.throws(() => validateEditorConfig(`${character}${editorConfig}`));
  }
});

test("frontend preflight returns a fixed target and accepts a regular Git marker file", (context) => {
  const { root } = fixture(context);
  assert.deepEqual(preflight(root, "frontend"), {
    root,
    cwd: path.join(root, "frontend"),
    files: ["."],
  });
  fs.rmdirSync(path.join(root, ".git"));
  fs.writeFileSync(path.join(root, ".git"), "gitdir: fixture-worktree\n");
  assert.deepEqual(preflight(root, "frontend").files, ["."]);
});

test("preflight rejects an absent or linked Git marker and unsupported roots or modes", (context) => {
  const { root, write } = fixture(context);
  assert.throws(() => preflight(root, "other"));
  fs.rmdirSync(path.join(root, ".git"));
  assert.throws(() => preflight(root, "frontend"));
  write("git-marker", "gitdir: fixture\n");
  fs.symlinkSync(path.join(root, "git-marker"), path.join(root, ".git"));
  assert.throws(() => preflight(root, "frontend"));
  const special = fixture(context, { prefix: "authzest-format-[test]-" });
  assert.throws(() => preflight(special.root, "frontend"));
});

test("frontend and checked configuration paths must be real files and directories", (context) => {
  for (const relative of [".editorconfig", "scripts/prettier-options.json"]) {
    for (const kind of ["missing", "directory", "symlink", "hardlink"]) {
      const { root, write } = fixture(context);
      const absolute = path.join(root, relative);
      if (kind === "hardlink")
        fs.linkSync(absolute, path.join(root, "second-link"));
      else {
        fs.unlinkSync(absolute);
        if (kind === "directory") fs.mkdirSync(absolute);
        if (kind === "symlink") {
          write(
            "reference",
            relative === ".editorconfig" ? editorConfig : "{}\n",
          );
          fs.symlinkSync(path.join(root, "reference"), absolute);
        }
      }
      assert.throws(() => preflight(root, "frontend"), `${relative}: ${kind}`);
    }
  }
  const { root } = fixture(context);
  fs.renameSync(path.join(root, "frontend"), path.join(root, "frontend-real"));
  fs.symlinkSync(path.join(root, "frontend-real"), path.join(root, "frontend"));
  assert.throws(() => preflight(root, "frontend"));
  const scripts = fixture(context);
  fs.renameSync(
    path.join(scripts.root, "scripts"),
    path.join(scripts.root, "scripts-real"),
  );
  fs.symlinkSync(
    path.join(scripts.root, "scripts-real"),
    path.join(scripts.root, "scripts"),
  );
  assert.throws(() => preflight(scripts.root, "frontend"));
});

test("preflight rejects invalid UTF-8 and any nonempty or malformed options object", (context) => {
  const invalidUtf8 = fixture(context);
  invalidUtf8.write(
    ".editorconfig",
    Buffer.from([0x72, 0x6f, 0x6f, 0x74, 0xff]),
  );
  assert.throws(() => preflight(invalidUtf8.root, "frontend"));
  for (const value of [
    "",
    "null",
    "[]",
    '"config"',
    '{"tabWidth":4}',
    '{"plugins":["ordinary-plugin"]}',
    "{",
    "{} {}",
  ]) {
    const { root, write } = fixture(context);
    write("scripts/prettier-options.json", value);
    assert.throws(() => preflight(root, "frontend"));
  }
});

test("the frontend ignore file allows only the three approved entries", (context) => {
  const valid = fixture(context);
  valid.write(
    "frontend/.prettierignore",
    "# Build outputs\npackage-lock.json\n\nnode_modules\ndist\n",
  );
  assert.doesNotThrow(() => preflight(valid.root, "frontend"));
  valid.write(
    "frontend/.prettierignore",
    prettierIgnore.replaceAll("\n", "\r\n"),
  );
  assert.doesNotThrow(() => preflight(valid.root, "frontend"));
  for (const contents of [
    "dist\nnode_modules\n",
    `${prettierIgnore}src\n`,
    "dist/\nnode_modules\npackage-lock.json\n",
    `${prettierIgnore}!src/example.ts\n`,
  ]) {
    const { root, write } = fixture(context);
    write("frontend/.prettierignore", contents);
    assert.throws(() => preflight(root, "frontend"));
  }
  const missing = fixture(context);
  fs.unlinkSync(path.join(missing.root, "frontend/.prettierignore"));
  assert.throws(() => preflight(missing.root, "frontend"));
});

test("Markdown requires its empty, non-linked ignore file before launch", (context) => {
  for (const kind of [
    "missing",
    "directory",
    "symlink",
    "hardlink",
    "pattern",
    "newline",
    "space",
  ]) {
    const { root, write } = fixture(context, { git: true });
    const absolute = path.join(root, "scripts/prettier-markdown.ignore");
    if (kind === "hardlink")
      fs.linkSync(absolute, path.join(root, "second-ignore-link"));
    else if (["pattern", "newline", "space"].includes(kind))
      write(
        "scripts/prettier-markdown.ignore",
        { pattern: "README.md\n", newline: "\n", space: " " }[kind],
      );
    else {
      fs.unlinkSync(absolute);
      if (kind === "directory") fs.mkdirSync(absolute);
      if (kind === "symlink") {
        write("empty-ignore", "");
        fs.symlinkSync(path.join(root, "empty-ignore"), absolute);
      }
    }
    assert.throws(() => preflight(root, "markdown"), kind);
    let called = false;
    assert.throws(() =>
      runFormatter({
        root,
        mode: "markdown",
        operation: "--check",
        spawn: () => {
          called = true;
          return { status: 0, signal: null };
        },
      }),
    );
    assert.equal(called, false, kind);
  }
});

test("ignore validation does not normalize excluded-directory patterns before launch", (context) => {
  for (const contents of [
    " dist\nnode_modules\npackage-lock.json\n",
    "\tdist\nnode_modules\npackage-lock.json\n",
    "dist \nnode_modules\npackage-lock.json\n",
    "dist\rnode_modules\rpackage-lock.json\r",
  ]) {
    const { root, write } = fixture(context);
    write("frontend/.prettierignore", contents);
    write("frontend/dist/.editorconfig", "[*]\nindent_size = 4\n");
    let launches = 0;
    assert.throws(() =>
      runFormatter({
        root,
        mode: "frontend",
        operation: "--check",
        spawn: () => {
          launches += 1;
          return { status: 0, signal: null };
        },
      }),
    );
    assert.equal(launches, 0);
  }
});

test("frontend live traversal rejects nested EditorConfig aliases and symlinks", (context) => {
  for (const relative of [
    "frontend/.editorconfig",
    "frontend/src/.editorconfig",
    "frontend/src/.EDITORCONFIG",
    "frontend/src/.EditorConfig",
    "frontend/src/node_modules/.editorconfig",
    "frontend/src/dist/.editorconfig",
  ]) {
    const { root, write } = fixture(context);
    write(relative, "[*]\nindent_size = 4\n");
    assert.throws(() => preflight(root, "frontend"), relative);
  }
  for (const relative of [
    "frontend/src/linked.ts",
    "frontend/src/.editorconfig",
  ]) {
    const { root } = fixture(context);
    fs.symlinkSync(path.join(root, ".editorconfig"), path.join(root, relative));
    assert.throws(() => preflight(root, "frontend"), relative);
  }
  const directory = fixture(context);
  fs.symlinkSync(
    path.join(directory.root, "scripts"),
    path.join(directory.root, "frontend/src/linked-directory"),
  );
  assert.throws(() => preflight(directory.root, "frontend"));
});

test("root EditorConfig aliases are rejected and only root build/vendor directories are skipped", (context) => {
  const alias = fixture(context);
  fs.renameSync(
    path.join(alias.root, ".editorconfig"),
    path.join(alias.root, ".EDITORCONFIG"),
  );
  assert.throws(() => preflight(alias.root, "frontend"));
  const { root, write } = fixture(context);
  write("frontend/dist/.editorconfig", "[*]\nindent_size = 4\n");
  write("frontend/node_modules/.EDITORCONFIG", "[*]\nindent_size = 4\n");
  // These are not discovered because the wrapper supplies its checked options file.
  write("frontend/src/.prettierrc", '{"tabWidth":4}\n');
  write("frontend/src/package.json", '{"prettier":{"tabWidth":4}}\n');
  assert.doesNotThrow(() => preflight(root, "frontend"));
});

test("frontend traversal has bounded depth and entry count", (context) => {
  const deep = fixture(context);
  deep.write(
    `frontend/${Array(35).fill("nested").join("/")}/plain.txt`,
    "plain\n",
  );
  assert.throws(() => preflight(deep.root, "frontend"));
  const wide = fixture(context);
  for (let index = 0; index < 10001; index += 1) {
    wide.write(`frontend/entries/file-${index}.txt`, "");
  }
  assert.throws(() => preflight(wide.root, "frontend"));
});

test("Markdown preflight enumerates only tracked Markdown paths with Git", (context) => {
  const { root, write, stage } = fixture(context, { git: true });
  write("README.md", "# Fixture\n");
  write("docs/a b.md", "# A space in the name\n");
  write("--check.md", "# Ordinary leading hyphens\n");
  write("untracked.md", "# Not tracked\n");
  write("notes.txt", "plain\n");
  stage("README.md", "docs/a b.md", "--check.md", "notes.txt");
  const report = preflight(root, "markdown");
  assert.equal(report.root, root);
  assert.equal(report.cwd, root);
  assert.deepEqual(
    [...report.files].sort(),
    ["--check.md", "README.md", "docs/a b.md"].sort(),
  );
});

test("Markdown preflight rejects missing, directory, and symlink targets", (context) => {
  for (const kind of ["missing", "directory", "symlink"]) {
    const { root, write, stage } = fixture(context, { git: true });
    write("README.md", "# Fixture\n");
    stage("README.md");
    fs.unlinkSync(path.join(root, "README.md"));
    if (kind === "directory") fs.mkdirSync(path.join(root, "README.md"));
    if (kind === "symlink") {
      write("reference.txt", "# Fixture\n");
      fs.symlinkSync(
        path.join(root, "reference.txt"),
        path.join(root, "README.md"),
      );
    }
    assert.throws(() => preflight(root, "markdown"), kind);
  }
});

test("Markdown checks live parent paths and untracked EditorConfig aliases", (context) => {
  for (const name of [".editorconfig", ".EDITORCONFIG", ".EditorConfig"]) {
    const { root, write, stage } = fixture(context, { git: true });
    write("docs/README.md", "# Fixture\n");
    stage("docs/README.md");
    write(`docs/${name}`, "[*]\nindent_size = 4\n");
    assert.throws(() => preflight(root, "markdown"), name);
  }
  const linkedConfig = fixture(context, { git: true });
  linkedConfig.write("docs/README.md", "# Fixture\n");
  linkedConfig.stage("docs/README.md");
  fs.symlinkSync(
    path.join(linkedConfig.root, ".editorconfig"),
    path.join(linkedConfig.root, "docs/.editorconfig"),
  );
  assert.throws(() => preflight(linkedConfig.root, "markdown"));
  const parent = fixture(context, { git: true });
  parent.write("docs/README.md", "# Fixture\n");
  parent.stage("docs/README.md");
  fs.renameSync(
    path.join(parent.root, "docs"),
    path.join(parent.root, "docs-real"),
  );
  fs.symlinkSync(
    path.join(parent.root, "docs-real"),
    path.join(parent.root, "docs"),
  );
  assert.throws(() => preflight(parent.root, "markdown"));
});

test("formatter launch uses fixed options and sanitizes experimental and Node environment variables", (context) => {
  const { root } = fixture(context);
  const env = {
    ...process.env,
    PRETTIER_EXPERIMENTAL_CLI: "1",
    prettier_experimental_cli: "1",
    NODE_OPTIONS: "--trace-warnings",
    node_options: "--trace-warnings",
    NoDe_PaTh: "ordinary/path",
    FORMAT_TEST_KEEP: "yes",
  };
  const original = { ...env };
  for (const operation of ["--check", "--write"]) {
    const result = mockFormatter({ root, mode: "frontend", operation, env });
    assert.equal(result.status, 0);
    assert.equal(result.calls.length, 1);
    assertLaunch(result.calls[0], root, "frontend", operation, ["."]);
    assert.equal(result.calls[0].options.env.FORMAT_TEST_KEEP, "yes");
    assert.ok(
      Object.keys(result.calls[0].options.env).every(
        (key) =>
          !["prettier_experimental_cli", "node_options", "node_path"].includes(
            key.toLowerCase(),
          ),
      ),
    );
  }
  assert.deepEqual(env, original);
});

test("Markdown child arguments are explicit tracked paths after the option separator", (context) => {
  const { root, write, stage } = fixture(context, { git: true });
  write("README.md", "# Fixture\n");
  write("docs/a b.md", "# A space in the name\n");
  write("--check.md", "# Ordinary leading hyphens\n");
  stage("README.md", "docs/a b.md", "--check.md");
  const expected = preflight(root, "markdown").files.map((file) => `./${file}`);
  const result = mockFormatter({
    root,
    mode: "markdown",
    operation: "--check",
  });
  assert.equal(result.status, 0);
  assert.equal(result.calls.length, 1);
  assertLaunch(result.calls[0], root, "markdown", "--check", expected);
});

test("ordinary ignored tracked Markdown still fails check and is formatted", (context) => {
  const input = ordinaryFormattingFixture(context);
  if (!input) return;
  const check = input.run("markdown", "--check");
  assert.equal(check.status, 1, check.output);
  assert.equal(input.run("markdown", "--write").status, 0);
  assert.equal(
    fs.readFileSync(path.join(input.root, "docs/ignored.md"), "utf8"),
    "# Coverage\n\n- ordinary item\n",
  );
  assert.equal(input.run("markdown", "--check").status, 0);
});

test("ordinary ignored tracked frontend TypeScript still fails check and keeps approved exclusions", (context) => {
  const input = ordinaryFormattingFixture(context);
  if (!input) return;
  const check = input.run("frontend", "--check");
  assert.equal(check.status, 1, check.output);
  assert.equal(input.run("frontend", "--write").status, 0);
  assert.equal(
    fs.readFileSync(path.join(input.root, "frontend/src/ignored.ts"), "utf8"),
    "function coverage() {\n  return { value: 1 };\n}\n",
  );
  for (const relative of [
    "frontend/dist/excluded.ts",
    "frontend/node_modules/excluded.ts",
  ]) {
    assert.equal(
      fs.readFileSync(path.join(input.root, relative), "utf8"),
      input.typescript,
    );
  }
  assert.equal(
    fs.readFileSync(
      path.join(input.root, "frontend/package-lock.json"),
      "utf8",
    ),
    input.lockfile,
  );
  assert.equal(
    fs.readFileSync(path.join(input.root, ".editorconfig"), "utf8"),
    editorConfig,
  );
  assert.equal(input.run("frontend", "--check").status, 0);
});

test("invalid caller arguments and configuration fail before formatter launch", (context) => {
  const valid = fixture(context);
  const inputs = [
    { root: valid.root, mode: "frontend", operation: "--version" },
    { root: valid.root, mode: "frontend", operation: "--write --parser babel" },
    { root: valid.root, mode: "frontend", operation: "write" },
    { root: valid.root, mode: "other", operation: "--check" },
  ];
  for (const contents of [
    "root = true\n[*]\nindent_size = 17\n",
    "root = true\n[*]\n[*.js]\nindent_size = 2\n",
  ]) {
    const current = fixture(context);
    current.write(".editorconfig", contents);
    inputs.push({ root: current.root, mode: "frontend", operation: "--check" });
  }
  for (const contents of [
    '{"tabWidth":4}',
    '"ordinary-config"',
    '{"plugins":["ordinary-plugin"]}',
  ]) {
    const current = fixture(context);
    current.write("scripts/prettier-options.json", contents);
    inputs.push({ root: current.root, mode: "frontend", operation: "--check" });
  }
  for (const input of inputs) {
    let called = false;
    assert.throws(() =>
      runFormatter({
        ...input,
        spawn: () => {
          called = true;
          return { status: 0, signal: null };
        },
      }),
    );
    assert.equal(called, false);
  }
});

test("formatter exit status is preserved and process failures are rejected", (context) => {
  const { root } = fixture(context);
  const input = { root, mode: "frontend", operation: "--check" };
  for (const status of [0, 1, 2, 23]) {
    assert.equal(mockFormatter(input, { status, signal: null }).status, status);
  }
  const timeout = Object.assign(new Error("Fixture timeout"), {
    code: "ETIMEDOUT",
  });
  for (const result of [
    { status: null, signal: "SIGKILL", error: timeout },
    { status: null, signal: "SIGTERM" },
    { status: null, signal: null, error: new Error("Fixture launch error") },
    { status: null, signal: null },
  ]) {
    assert.throws(() => mockFormatter(input, result));
  }
  assert.throws(() =>
    runFormatter({
      ...input,
      spawn: () => {
        throw new Error("Fixture spawn error");
      },
    }),
  );
});

test("Markdown with no tracked targets succeeds without launching a formatter", (context) => {
  const { root } = fixture(context, { git: true });
  assert.deepEqual(preflight(root, "markdown").files, []);
  const result = mockFormatter({
    root,
    mode: "markdown",
    operation: "--check",
  });
  assert.equal(result.status, 0);
  assert.deepEqual(result.calls, []);
});

test("ordinary frontend/Markdown formatting matches Prettier and keeps EditorConfig active", (context) => {
  const installed = fileURLToPath(
    new URL("../frontend/node_modules/prettier/", import.meta.url),
  );
  // CI installs the locked formatter before this test; a dependency-free checkout can run unit guards.
  if (!fs.existsSync(path.join(installed, "bin/prettier.cjs"))) {
    context.skip(
      "Install the committed frontend dependencies for ordinary formatter integration",
    );
    return;
  }
  const { root, write, stage } = fixture(context, { git: true });
  fs.cpSync(installed, path.join(root, "frontend/node_modules/prettier"), {
    recursive: true,
  });
  write(
    ".editorconfig",
    editorConfig.replace("indent_size = 2", "indent_size = 4"),
  );
  const source = "function sample(){const first=1;return first;}\n";
  const markdown = "# Sample\n\n- first\n  - nested\n";
  write("frontend/src/example.ts", source);
  write("docs/README.md", markdown);
  stage("docs/README.md");
  // Ambient settings must not override the explicit reviewed options or execute a config module.
  write("frontend/src/.prettierrc.json", '{"tabWidth":2}\n');
  const env = Object.fromEntries(
    Object.entries(process.env).filter(
      ([key]) =>
        !["PRETTIER_EXPERIMENTAL_CLI", "NODE_OPTIONS", "NODE_PATH"].includes(
          key.toUpperCase(),
        ),
    ),
  );
  for (const [relative, input, mode] of [
    ["frontend/src/example.ts", source, "frontend"],
    ["docs/README.md", markdown, "markdown"],
  ]) {
    const baseline = execFileSync(
      process.execPath,
      [
        path.join(installed, "bin/prettier.cjs"),
        "--editorconfig",
        "--config",
        path.join(root, "scripts/prettier-options.json"),
        "--stdin-filepath",
        path.join(root, relative),
      ],
      { cwd: root, input, encoding: "utf8", timeout: 120000, env },
    );
    assert.ok(
      baseline.includes(
        mode === "frontend" ? "    const first" : "    - nested",
      ),
    );
    assert.equal(runFormatter({ root, mode, operation: "--write", env }), 0);
    assert.equal(fs.readFileSync(path.join(root, relative), "utf8"), baseline);
    assert.equal(runFormatter({ root, mode, operation: "--check", env }), 0);
  }
});

test("importing the formatter module has no CLI side effects", (context) => {
  const { root } = fixture(context);
  const modulePath = fileURLToPath(new URL("./format.mjs", import.meta.url));
  const code = [
    'import childProcess from "node:child_process";',
    'import { syncBuiltinESMExports } from "node:module";',
    'for (const name of ["spawn", "spawnSync", "exec", "execSync", "execFile", "execFileSync"]) {',
    '  childProcess[name] = () => { throw new Error("Import must not launch a process"); };',
    "}",
    "syncBuiltinESMExports();",
    `await import(${JSON.stringify(pathToFileURL(modulePath).href)});`,
    'process.stdout.write("loaded\\n");',
  ].join("\n");
  const output = execFileSync(
    process.execPath,
    ["--input-type=module", "-e", code],
    { cwd: root, encoding: "utf8", timeout: 10000 },
  );
  assert.equal(output, "loaded\n");
});
