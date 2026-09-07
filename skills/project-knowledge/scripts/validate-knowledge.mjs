#!/usr/bin/env node

import { access, readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";

function githubAnchor(heading) {
  return heading
    .trim()
    .toLowerCase()
    .replace(/<[^>]*>/g, "")
    .replace(/[`*~]/g, "")
    .replace(/[^\p{L}\p{N}_\s-]/gu, "")
    .trim()
    .replace(/\s+/g, "-");
}

function maskMarkup(text, pattern) {
  return text.replace(pattern, (match) => match.replace(/[^\n]/g, " "));
}

function markdownInfo(content) {
  const bodyLines = [];
  const anchors = new Set();
  const anchorNames = new Map();
  const duplicateAnchors = [];
  const headings = [];
  const mermaidBlocks = [];
  const withoutFrontmatter = maskMarkup(
    content,
    /^---\s*\r?\n[\s\S]*?\r?\n---\s*(?:\r?\n|$)/,
  );
  const visibleContent = maskMarkup(
    withoutFrontmatter,
    /<!--[\s\S]*?(?:-->|$)/g,
  );
  let fenced = false;
  let fenceMarker = null;
  let mermaid = null;

  function addHeading(rawName, level, line) {
    const anchor = githubAnchor(rawName);
    const name = rawName.trim().toLowerCase();
    if (anchors.has(anchor) && anchorNames.get(anchor) !== name)
      duplicateAnchors.push({ line, anchor });
    anchors.add(anchor);
    anchorNames.set(anchor, name);
    headings.push({ line, level, name, rawName: rawName.trim() });
  }

  for (const [index, line] of visibleContent.split("\n").entries()) {
    if (!fenced) {
      const fence = line.match(/^ {0,3}(`{3,}|~{3,})\s*([^\s`]*)?/);
      if (fence) {
        fenced = true;
        fenceMarker = fence[1];
        if ((fence[2] ?? "").toLowerCase() === "mermaid")
          mermaid = { line: index + 1, lines: [] };
        bodyLines.push("");
        continue;
      }
    } else {
      const closingFence = line.match(/^ {0,3}(`{3,}|~{3,})\s*$/);
      if (
        closingFence &&
        closingFence[1][0] === fenceMarker[0] &&
        closingFence[1].length >= fenceMarker.length
      ) {
        if (mermaid) mermaidBlocks.push(mermaid);
        fenced = false;
        fenceMarker = null;
        mermaid = null;
      } else if (mermaid) {
        mermaid.lines.push(line);
      }
      bodyLines.push("");
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+?)\s*#*\s*$/);
    if (heading) addHeading(heading[2], heading[1].length, index + 1);

    const setext = line.match(/^ {0,3}(=+|-+)\s*$/);
    const previousLine = bodyLines.at(-1)?.trim();
    if (setext && previousLine && !/^#{1,6}\s/.test(previousLine))
      addHeading(previousLine, setext[1][0] === "=" ? 1 : 2, index);

    bodyLines.push(line);
  }

  const body = maskMarkup(
    bodyLines.join("\n"),
    /(`+)[\s\S]*?\1/g,
  );
  return {
    body,
    anchors,
    duplicateAnchors,
    headings,
    mermaidBlocks,
    unclosedMermaidLine: mermaid?.line ?? null,
  };
}

async function existsWithExactCase(root, target) {
  const relative = path.relative(root, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) return false;

  let current = root;
  for (const segment of relative.split(path.sep).filter(Boolean)) {
    let entries;
    try {
      entries = await readdir(current);
    } catch {
      return false;
    }
    if (!entries.includes(segment)) return false;
    current = path.join(current, segment);
  }

  try {
    await access(current);
    return true;
  } catch {
    return false;
  }
}

function linkTarget(rawTarget) {
  const target = rawTarget.trim().replace(/^<|>$/g, "");
  if (!target || /^[a-z][a-z0-9+.-]*:/i.test(target)) return null;
  const withoutTitle =
    target.match(/^(\S+)(?:\s+["'][^"']*["'])?$/)?.[1] ?? target;
  const [targetPath, rawFragment = ""] = withoutTitle.split("#", 2);
  return {
    path: decodeURIComponent(targetPath.split("?", 1)[0]),
    fragment: rawFragment ? decodeURIComponent(rawFragment) : null,
  };
}

function inlineLinkTargets(body) {
  const targets = [];
  const opener = /!?\[[^\]\n]*\]\(/g;
  let match;

  while ((match = opener.exec(body))) {
    const start = opener.lastIndex;
    let depth = 1;
    let escaped = false;
    let inAngleTarget = body[start] === "<";

    for (let index = start; index < body.length; index += 1) {
      const char = body[index];
      if (escaped) {
        escaped = false;
        continue;
      }
      if (char === "\\") {
        escaped = true;
        continue;
      }
      if (inAngleTarget) {
        if (char === ">") inAngleTarget = false;
        continue;
      }
      if (char === "(") depth += 1;
      if (char === ")") depth -= 1;
      if (depth === 0) {
        targets.push(body.slice(start, index));
        opener.lastIndex = index + 1;
        break;
      }
    }
  }

  return targets;
}

function referenceLinks(body) {
  const definitions = new Map();
  const targets = [];
  const definitionPattern =
    /^ {0,3}\[([^\]\n]+)\]:\s*(<[^>\n]*>|\S+)(?:\s+.*)?$/gm;
  const normalizeLabel = (label) =>
    label.trim().replace(/\s+/g, " ").toLowerCase();

  for (const match of body.matchAll(definitionPattern)) {
    definitions.set(normalizeLabel(match[1]), match[2]);
    targets.push(match[2]);
  }

  const undefinedLabels = [];
  for (const match of body.matchAll(/!?\[([^\]\n]+)\]\[([^\]\n]*)\]/g)) {
    const label = normalizeLabel(match[2] || match[1]);
    if (!definitions.has(label)) undefinedLabels.push(label);
  }

  return { targets, undefinedLabels };
}

function stripQuotedText(text) {
  let output = "";
  let quote = null;
  let escaped = false;

  for (const char of text) {
    if (quote) {
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === quote) quote = null;
      output += " ";
    } else if (char === '"' || char === "'" || char === "`") {
      quote = char;
      output += " ";
    } else {
      output += char;
    }
  }

  return output;
}

function mermaidErrors(inputPath, block) {
  const errors = [];
  const text = stripQuotedText(block.lines.join("\n")).replace(/%%.*$/gm, "");
  const first = block.lines
    .find((line) => line.trim() && !line.trim().startsWith("%%"))
    ?.trim();
  if (!first) return [`${inputPath}:${block.line}: empty Mermaid block`];

  const declaration = first.match(
    /^[a-zA-Z][\w-]*(?:\s+(?![-=.()[\]{}]).*)?$/,
  );
  if (!declaration)
    errors.push(
      `${inputPath}:${block.line}: Mermaid block must declare a diagram type`,
    );

  const pairs = { "(": ")", "[": "]", "{": "}" };
  const stack = [];
  for (const char of text) {
    if (pairs[char]) stack.push(pairs[char]);
    else if (Object.values(pairs).includes(char) && stack.pop() !== char) {
      errors.push(
        `${inputPath}:${block.line}: Mermaid block has unbalanced delimiters`,
      );
      break;
    }
  }
  if (stack.length)
    errors.push(
      `${inputPath}:${block.line}: Mermaid block has unbalanced delimiters`,
    );
  return errors;
}

export async function validateKnowledge(rootPath, filePaths) {
  const root = path.resolve(rootPath);
  const errors = [];

  for (const inputPath of filePaths) {
    const file = path.resolve(root, inputPath);
    if (!(await existsWithExactCase(root, file))) {
      errors.push(`${inputPath}: file does not exist with exact path casing`);
      continue;
    }

    const info = markdownInfo(await readFile(file, "utf8"));
    const body = info.body;
    const headings = new Set();
    let previousLevel = 0;

    for (const duplicate of info.duplicateAnchors) {
      errors.push(
        `${inputPath}:${duplicate.line}: duplicate heading anchor "${duplicate.anchor}"`,
      );
    }

    for (const heading of info.headings) {
      const { level, name } = heading;
      if (headings.has(name))
        errors.push(
          `${inputPath}:${heading.line}: duplicate heading "${heading.rawName}"`,
        );
      if (previousLevel === 0 && level !== 1)
        errors.push(`${inputPath}:${heading.line}: first heading must be level 1`);
      if (previousLevel > 0 && level > previousLevel + 1)
        errors.push(
          `${inputPath}:${heading.line}: heading level skips from ${previousLevel} to ${level}`,
        );
      headings.add(name);
      previousLevel = level;
    }

    const references = referenceLinks(body);
    for (const label of references.undefinedLabels)
      errors.push(`${inputPath}: undefined reference link "${label}"`);

    const rawTargets = [
      ...inlineLinkTargets(body),
      ...references.targets,
    ];

    for (const rawTarget of rawTargets) {
      let target;
      try {
        target = linkTarget(rawTarget);
      } catch {
        errors.push(`${inputPath}: invalid encoded link target "${rawTarget}"`);
        continue;
      }
      if (!target) continue;

      const sameFileLink = target.path === "";
      const resolved = sameFileLink
        ? file
        : path.resolve(path.dirname(file), target.path);
      if (!(await existsWithExactCase(root, resolved))) {
        errors.push(
          `${inputPath}: unresolved or case-mismatched link "${target.path}"`,
        );
        continue;
      }

      const markdownTarget =
        sameFileLink || /\.(?:md|markdown)$/i.test(target.path);
      if (target.fragment && markdownTarget) {
        const targetInfo = sameFileLink
          ? info
          : markdownInfo(await readFile(resolved, "utf8"));
        if (!targetInfo.anchors.has(target.fragment.toLowerCase())) {
          errors.push(
            `${inputPath}: unresolved heading link "${target.path}#${target.fragment}"`,
          );
        }
      }
    }

    if (info.unclosedMermaidLine)
      errors.push(
        `${inputPath}:${info.unclosedMermaidLine}: unclosed Mermaid block`,
      );
    for (const block of info.mermaidBlocks)
      errors.push(...mermaidErrors(inputPath, block));
  }

  return errors;
}

async function main() {
  const [root, ...files] = process.argv.slice(2);
  if (!root || files.length === 0) {
    console.error(
      "Usage: validate-knowledge.mjs <repository-root> <knowledge-file>...",
    );
    process.exitCode = 2;
    return;
  }

  const errors = await validateKnowledge(root, files);
  if (errors.length > 0) {
    console.error(errors.join("\n"));
    process.exitCode = 1;
    return;
  }

  console.log(`Validated ${files.length} knowledge document(s).`);
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href
) {
  await main();
}
