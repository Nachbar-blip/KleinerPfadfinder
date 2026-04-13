'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const HTML = path.join(ROOT, 'index.html');
const BERUFE = path.join(__dirname, 'berufe.json');
const ROH = path.join(__dirname, 'berufe_roh.json');

const berufe = JSON.parse(fs.readFileSync(BERUFE, 'utf8'));
const roh = JSON.parse(fs.readFileSync(ROH, 'utf8'));
let html = fs.readFileSync(HTML, 'utf8');

function replaceConst(src, name, value) {
  const re = new RegExp(`const ${name} = \\[[\\s\\S]*?\\];`);
  if (!re.test(src)) throw new Error(`${name} nicht gefunden`);
  return src.replace(re, `const ${name} = ${JSON.stringify(value)};`);
}

html = replaceConst(html, 'BERUFE', berufe);
html = replaceConst(html, 'BERUFE_ROH', roh);

fs.writeFileSync(HTML, html, 'utf8');
console.log(`Eingebettet: ${berufe.length} Berufe, ${roh.length} Roh-Einträge`);
console.log(`index.html: ${(html.length / 1024).toFixed(1)} KB`);
