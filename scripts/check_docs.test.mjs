import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { execFileSync, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { checkDocs, koreanCounterpart } from "./check_docs.mjs";

const readmes = [
  "README.md",
  "docs/i18n/ko/README.md",
  "docs/i18n/ja/README.md",
  "docs/i18n/ru/README.md",
];
const indexes = ["docs/README.md", "docs/i18n/ko/INDEX.md"];
const guide = ["docs/GUIDE.md", "docs/i18n/ko/GUIDE.md"];
const template = [
  ".github/pull_request_template.md",
  "docs/i18n/ko/PULL_REQUEST_TEMPLATE.md",
];

function links(from, destinations) {
  return destinations
    .map(
      (to) => `[${to}](${path.posix.relative(path.posix.dirname(from), to)})`,
    )
    .join("\n");
}

function fixture(context, modify = () => {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "authzest-docs-test-"));
  context.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const sources = {};
  for (const file of readmes) {
    sources[file] = `# Overview\n${links(
      file,
      readmes.filter((other) => file !== other),
    )}\n\n\`\`\`bash\nauthzest --help\n\`\`\`\n`;
  }
  for (const file of indexes)
    sources[file] =
      `# Index\n${links(file, [...readmes, ...indexes, ...guide, ...template])}\n`;
  for (const file of guide) {
    sources[file] = `# 검증\n${links(
      file,
      guide.filter((other) => file !== other),
    )}\n- [x] Completed\n- [ ] Planned\n`;
  }
  for (const file of template)
    sources[file] = `# PR\n${links(
      file,
      template.filter((other) => file !== other),
    )}\n`;
  sources[guide[0]] +=
    "[This heading](#검증)\n[Root heading](../README.md#overview)\n![Image](assets/demo.svg)\n";
  sources["docs/assets/demo.svg"] = '<svg xmlns="http://www.w3.org/2000/svg"/>';
  // A missing translation in vendor content must not become a project documentation failure.
  sources["vendor/README.md"] = "# Third-party README\n";
  modify(sources, root);
  for (const [file, content] of Object.entries(sources)) {
    const absolute = path.join(root, file);
    fs.mkdirSync(path.dirname(absolute), { recursive: true });
    fs.writeFileSync(absolute, content);
  }
  return { root, files: Object.keys(sources) };
}

function runFixture(context, modify) {
  const input = fixture(context, modify);
  return checkDocs(input.root, { files: input.files });
}

test("valid guides cover indexes, template mapping, images, Unicode anchors, and language pairs", (context) => {
  const report = runFixture(context);
  assert.deepEqual(report.issues, []);
  assert.equal(report.counts.markdown, 10);
  assert.equal(report.counts.pairs, 4);
  assert.equal(report.counts.images, 1);
  assert.equal(report.counts.fragments, 2);
  assert.equal(koreanCounterpart("docs/README.md"), "docs/i18n/ko/INDEX.md");
  assert.equal(
    koreanCounterpart(".github/pull_request_template.md"),
    template[1],
  );
});

test("a new guide must have its Korean counterpart", (context) => {
  const report = runFixture(context, (sources) => {
    sources["docs/NEW.md"] = "# New guide\n";
  });
  assert.ok(
    report.issues.includes(
      "docs/NEW.md: missing Korean counterpart docs/i18n/ko/NEW.md",
    ),
  );
});

test("topic paths keep same-basename guides and their Korean sources distinct", (context) => {
  const pairs = [
    ["docs/guides/GUIDE.md", "docs/i18n/ko/guides/GUIDE.md"],
    ["docs/reference/GUIDE.md", "docs/i18n/ko/reference/GUIDE.md"],
    ["CONTRIBUTING.md", "docs/i18n/ko/CONTRIBUTING.md"],
  ];
  const report = runFixture(context, (sources) => {
    for (const pair of pairs) {
      assert.equal(koreanCounterpart(pair[0]), pair[1]);
      for (const file of pair)
        sources[file] = `# Topic\n${links(
          file,
          pair.filter((other) => other !== file),
        )}\n`;
      for (const index of indexes) sources[index] += `${links(index, pair)}\n`;
    }
  });
  assert.deepEqual(report.issues, []);
  assert.equal(report.counts.pairs, 7);
});

test("orphan translations and ambiguous source mappings are rejected", (context) => {
  const report = runFixture(context, (sources) => {
    sources["docs/i18n/ko/reference/ORPHAN.md"] = "# Orphan\n";
    // A root and docs-root guide with the same name cannot share one translation.
    sources["GUIDE.md"] = "# Duplicate mapping\n";
  });
  assert.ok(
    report.issues.includes(
      "docs/i18n/ko/reference/ORPHAN.md: expected exactly one English source",
    ),
  );
  assert.ok(
    report.issues.includes(`${guide[1]}: expected exactly one English source`),
  );
});

test("the old mixed-language directory cannot silently leave stale guides behind", (context) => {
  const report = runFixture(context, (sources) => {
    sources["docs/i18n/GUIDE.ko.md"] = "# Stale translation\n";
  });
  assert.ok(
    report.issues.includes(
      "docs/i18n/GUIDE.ko.md: translations must use a language directory",
    ),
  );
});

test("heading normalization preserves formatted text, Unicode, duplicates, and explicit anchors", (context) => {
  const report = runFixture(context, (sources) => {
    for (const file of guide) {
      sources[file] +=
        "\n# <em>Formatted</em> and [linked](https://example.com)\n" +
        "[Formatted heading](#formatted-and-linked)\n" +
        "# Café e\u0301!\n[Unicode heading](#café-e%CC%81)\n" +
        "# Repeat\n# Repeat\n[Second repetition](#repeat-1)\n" +
        '<span id="manual-anchor"></span>\n[Explicit anchor](#manual-anchor)\n';
    }
  });
  assert.deepEqual(report.issues, []);
  assert.equal(report.counts.fragments, 10);
});

test("missing files and heading fragments identify their source document", (context) => {
  const report = runFixture(context, (sources) => {
    sources[guide[0]] +=
      "[Missing](absent.md)\n[Wrong heading](../README.md#not-a-heading)\n";
  });
  assert.ok(
    report.issues.some(
      (issue) =>
        issue.includes("docs/GUIDE.md:") &&
        issue.includes("missing link/image target: absent.md"),
    ),
  );
  assert.ok(
    report.issues.some((issue) =>
      issue.includes("missing heading #not-a-heading in README.md"),
    ),
  );
});

test("translated fenced commands must match their source", (context) => {
  const report = runFixture(context, (sources) => {
    sources[readmes[2]] = sources[readmes[2]].replace(
      "authzest --help",
      "authzest --version",
    );
  });
  assert.ok(
    report.issues.includes(
      `README command/structure parity differs: ${readmes[2]}`,
    ),
  );
});

test("inline commands and TODO completion state must match for ordinary guides", (context) => {
  const report = runFixture(context, (sources) => {
    sources[guide[0]] += "Run `node scripts/check_docs.mjs`.\n";
    sources[guide[1]] = sources[guide[1]].replace("[x]", "[ ]");
  });
  assert.ok(
    report.issues.includes(
      `${guide[0]} / ${guide[1]}: inline command parity differs`,
    ),
  );
  assert.ok(
    report.issues.includes(
      `${guide[0]} / ${guide[1]}: TODO completion sequence differs`,
    ),
  );
});

test("language links must be reciprocal and a new guide must appear in both indexes", (context) => {
  const report = runFixture(context, (sources) => {
    sources[guide[1]] = "# 검증\n- [x] Completed\n- [ ] Planned\n";
    sources[indexes[0]] = sources[indexes[0]]
      .split("\n")
      .filter((line) => !line.includes(guide[1]))
      .join("\n");
  });
  assert.ok(
    report.issues.includes(
      `${guide[1]}: missing reciprocal language link to ${guide[0]}`,
    ),
  );
  assert.ok(report.issues.includes(`${indexes[0]}: missing guide ${guide[1]}`));
});

test("shell blocks are parsed but never executed", (context) => {
  const input = fixture(context, (sources) => {
    for (const file of guide) sources[file] += "\n```bash\nexit 37\n```\n";
  });
  const report = checkDocs(input.root, { files: input.files });
  assert.deepEqual(report.issues, []);
  assert.equal(report.counts.bash + report.counts.bashSkipped, 6);
});

test("an invalid Bash example fails validation when Bash is installed", (context) => {
  const report = runFixture(context, (sources) => {
    for (const file of guide) sources[file] += "\n```bash\nif then\n```\n";
  });
  if (report.counts.bashSkipped) {
    context.skip(
      "Bash is unavailable; syntax-only checks are explicitly skipped",
    );
    return;
  }
  assert.ok(report.issues.some((issue) => issue.includes("Bash syntax:")));
});

test("a symlink entrypoint actually checks documents and exits nonzero for failures", (context) => {
  const input = fixture(context);
  execFileSync("git", ["init", "--quiet", input.root]);
  const entrypoint = path.join(input.root, "check-docs-entry.mjs");
  try {
    fs.symlinkSync(
      fileURLToPath(new URL("./check_docs.mjs", import.meta.url)),
      entrypoint,
      "file",
    );
  } catch (error) {
    if (["EPERM", "EACCES", "ENOSYS"].includes(error.code)) {
      context.skip("Symbolic link creation is unavailable on this platform");
      return;
    }
    throw error;
  }

  const invoke = () =>
    spawnSync(process.execPath, [entrypoint, input.root], {
      cwd: os.tmpdir(),
      encoding: "utf8",
    });
  const successful = invoke();
  assert.equal(successful.status, 0, successful.stderr);
  const report = JSON.parse(successful.stdout);
  assert.equal(report.counts.markdown, 10);
  assert.deepEqual(report.issues, []);

  fs.writeFileSync(
    path.join(input.root, "docs/NEW.md"),
    "# Missing translation\n",
  );
  const failed = invoke();
  assert.equal(failed.status, 1, failed.stderr);
  assert.ok(
    JSON.parse(failed.stdout).issues.includes(
      "docs/NEW.md: missing Korean counterpart docs/i18n/ko/NEW.md",
    ),
  );
});

test("importing with a non-file argv does not run the checker or throw", () => {
  const moduleUrl = new URL("./check_docs.mjs", import.meta.url).href;
  const imported = spawnSync(
    process.execPath,
    [
      "--input-type=module",
      "--eval",
      "process.argv[1] = 'not-an-existing-entrypoint'; await import(process.env.AUTHZEST_CHECKER_MODULE);",
    ],
    {
      encoding: "utf8",
      env: { ...process.env, AUTHZEST_CHECKER_MODULE: moduleUrl },
    },
  );
  assert.equal(imported.status, 0, imported.stderr);
  assert.equal(imported.stdout, "");
});
