#!/usr/bin/env node

import { access, readFile, readdir } from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'

function markdownBody(content) {
  let fenced = false
  return content
    .split('\n')
    .map((line) => {
      if (/^\s*(```|~~~)/.test(line)) {
        fenced = !fenced
        return ''
      }
      return fenced ? '' : line
    })
    .join('\n')
}

async function existsWithExactCase(root, target) {
  const relative = path.relative(root, target)
  if (relative.startsWith('..') || path.isAbsolute(relative)) return false

  let current = root
  for (const segment of relative.split(path.sep).filter(Boolean)) {
    let entries
    try {
      entries = await readdir(current)
    } catch {
      return false
    }
    if (!entries.includes(segment)) return false
    current = path.join(current, segment)
  }

  try {
    await access(current)
    return true
  } catch {
    return false
  }
}

function linkTarget(rawTarget) {
  const target = rawTarget.trim().replace(/^<|>$/g, '')
  if (!target || target.startsWith('#') || /^[a-z][a-z0-9+.-]*:/i.test(target)) return null
  const withoutTitle = target.match(/^(\S+)(?:\s+["'][^"']*["'])?$/)?.[1] ?? target
  return decodeURIComponent(withoutTitle.split(/[?#]/, 1)[0])
}

export async function validateKnowledge(rootPath, filePaths) {
  const root = path.resolve(rootPath)
  const errors = []

  for (const inputPath of filePaths) {
    const file = path.resolve(root, inputPath)
    if (!(await existsWithExactCase(root, file))) {
      errors.push(`${inputPath}: file does not exist with exact path casing`)
      continue
    }

    const body = markdownBody(await readFile(file, 'utf8'))
    const headings = new Set()
    let previousLevel = 0

    for (const [index, line] of body.split('\n').entries()) {
      const heading = line.match(/^(#{1,6})\s+(.+?)\s*#*\s*$/)
      if (!heading) continue

      const level = heading[1].length
      const name = heading[2].trim().toLowerCase()
      if (headings.has(name))
        errors.push(`${inputPath}:${index + 1}: duplicate heading "${heading[2].trim()}"`)
      if (previousLevel === 0 && level !== 1)
        errors.push(`${inputPath}:${index + 1}: first heading must be level 1`)
      if (previousLevel > 0 && level > previousLevel + 1)
        errors.push(
          `${inputPath}:${index + 1}: heading level skips from ${previousLevel} to ${level}`
        )
      headings.add(name)
      previousLevel = level
    }

    for (const match of body.matchAll(/!?\[[^\]]*\]\(([^)]+)\)/g)) {
      let target
      try {
        target = linkTarget(match[1])
      } catch {
        errors.push(`${inputPath}: invalid encoded link target "${match[1]}"`)
        continue
      }
      if (!target) continue

      const resolved = path.resolve(path.dirname(file), target)
      if (!(await existsWithExactCase(root, resolved))) {
        errors.push(`${inputPath}: unresolved or case-mismatched link "${target}"`)
      }
    }
  }

  return errors
}

async function main() {
  const [root, ...files] = process.argv.slice(2)
  if (!root || files.length === 0) {
    console.error('Usage: validate-knowledge.mjs <repository-root> <knowledge-file>...')
    process.exitCode = 2
    return
  }

  const errors = await validateKnowledge(root, files)
  if (errors.length > 0) {
    console.error(errors.join('\n'))
    process.exitCode = 1
    return
  }

  console.log(`Validated ${files.length} knowledge document(s).`)
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  await main()
}
