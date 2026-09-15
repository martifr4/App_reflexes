#!/usr/bin/env node
/* Freeze the Ojalá pages into standalone single-file HTML.
 *
 *   node build.mjs              → dist/ojala-demo-es.html, dist/ojala-demo-en.html
 *   node build.mjs --linked     → same, but the ES/EN switch still works between them
 *
 * Each output inlines ojala.css, ecb-data.js and ojala.js, so the file works on
 * its own: mail it, drop it in Drive, open it from a USB stick. The only thing
 * still fetched from the network is the Google Fonts stylesheet — online it
 * looks as designed, offline it falls back to system fonts.
 *
 * No dependencies. The script fails loudly rather than writing a broken file,
 * so if someone renames an asset or changes how it is linked, you hear about it.
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const dist = join(here, 'dist');
const linked = process.argv.includes('--linked');

const PAGES = [
  { src: 'index.html', out: 'ojala-demo-es.html', label: 'Spanish', sibling: 'en.html',    siblingOut: 'ojala-demo-en.html' },
  { src: 'en.html',    out: 'ojala-demo-en.html', label: 'English', sibling: 'index.html', siblingOut: 'ojala-demo-es.html' }
];

const read = f => readFileSync(join(here, f), 'utf8');

/* Replace exactly once, or explain what to fix. */
function swap(html, needle, replacement, what) {
  const n = html.split(needle).length - 1;
  if (n !== 1) {
    throw new Error(
      `expected exactly 1 "${what}" to inline, found ${n}.\n` +
      `  Looked for: ${needle.split('\n')[0].slice(0, 80)}\n` +
      `  The page markup changed — update PAGES/swap() in build.mjs to match.`
    );
  }
  return html.replace(needle, () => replacement);
}

const css  = read('assets/ojala.css').trimEnd();
const data = read('assets/ecb-data.js').trimEnd();
const js   = read('assets/ojala.js').trimEnd();

/* A literal </style> or </script> inside an asset would end the tag early and
 * silently spill code into the page as text. Refuse to build. */
for (const [name, body, closer] of [
  ['assets/ojala.css',   css,  '</style'],
  ['assets/ecb-data.js', data, '</script'],
  ['assets/ojala.js',    js,   '</script']
]) {
  if (body.toLowerCase().includes(closer)) {
    console.error(`✗ ${name} contains a literal "${closer}>" — that would break inlining.`);
    process.exit(1);
  }
}

const stamp = new Date().toISOString().slice(0, 10);
mkdirSync(dist, { recursive: true });

let failed = false;
for (const page of PAGES) {
  try {
    let html = read(page.src);

    html = swap(html,
      '<link rel="stylesheet" href="assets/ojala.css">',
      `<style>\n${css}\n</style>`,
      'stylesheet link');

    html = swap(html,
      '<script src="assets/ecb-data.js"></script>\n<script src="assets/ojala.js"></script>',
      `<script>\n${data}\n</script>\n\n<script>\n${js}\n</script>`,
      'script tags');

    // The ES/EN switch points at a file that is not being sent alongside.
    const langLink = new RegExp(`[ \\t]*<a class="lang" href="${page.sibling}"[^>]*>[^<]*</a>\\r?\\n`);
    if (!langLink.test(html)) {
      throw new Error(`could not find the language switch link to "${page.sibling}" — update the regex in build.mjs.`);
    }
    html = linked
      ? html.replace(langLink, m => m.replace(page.sibling, page.siblingOut))
      : html.replace(langLink, '');

    html = html.replace('<head>\n',
      `<head>\n<!-- Ojalá demo (${page.label}) - self-contained single file, frozen ${stamp}.\n` +
      `     Built from the ojala/ project by build.mjs: styles and scripts inlined.\n` +
      `     Edit the source project and re-run the build, not this file. -->\n`);

    // Nothing local may remain: every src/href must be a fragment or a font URL.
    const leftovers = [...html.matchAll(/(?:src|href)="([^"]*)"/g)]
      .map(m => m[1])
      .filter(u => !u.startsWith('#') && !u.startsWith('https://fonts.'))
      .filter(u => !(linked && u === page.siblingOut));
    if (leftovers.length) {
      throw new Error(`output still references local files: ${[...new Set(leftovers)].join(', ')}`);
    }

    const target = join(dist, page.out);
    writeFileSync(target, html);
    const kb = (Buffer.byteLength(html) / 1024).toFixed(0);
    console.log(`✓ ${page.label.padEnd(7)} → dist/${page.out}  (${kb} KB)`);
  } catch (err) {
    console.error(`✗ ${page.label} (${page.src}): ${err.message}`);
    failed = true;
  }
}

if (failed) {
  console.error('\nBuild failed — no usable output for the pages marked ✗.');
  process.exit(1);
}
console.log(
  `\nFrozen ${stamp} into ${basename(dist)}/. Send either file on its own; ` +
  (linked ? 'the ES/EN switch works when both travel together.' : 'the ES/EN switch is removed (use --linked to keep it).')
);
