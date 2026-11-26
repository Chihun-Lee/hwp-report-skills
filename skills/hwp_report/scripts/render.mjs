// hwpx → 쪽별 SVG (rhwp WASM, 헤드리스). 한컴 없이 쪽 나눔·표·그림 배치를 빠르게 본다.
//   node render.mjs report.hwpx outdir      (보통은 hr.py render 로 부른다 — PNG 변환·두 쪽 묶음까지)
// 한계: 글자 폭은 근사(CJK 1em, ASCII 0.55em)라 줄바꿈 위치가 한컴과 조금 다를 수 있다.
//       큰 그림이 쪽 경계에 걸리면 뒤 내용을 빠뜨릴 수 있으니 최종 배치는 한컴 PDF로 확인한다.
import fs from 'fs';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));
const V = path.join(here, '..', 'vendor', 'rhwp');
globalThis.measureTextWidth = (font, text) => {
  const s = parseFloat((font.match(/([\d.]+)px/) || [0, 12])[1]);
  let w = 0;
  for (const c of text) { const k = c.codePointAt(0); w += (k > 0x2E80 ? 1 : (k === 32 ? 0.3 : 0.55)) * s; }
  return w;
};
const m = await import(pathToFileURL(path.join(V, 'rhwp.js')).href);   // Windows: 절대경로는 file:// URL로
m.initSync({ module: fs.readFileSync(path.join(V, 'rhwp_bg.wasm')) });
const [src, out] = process.argv.slice(2);
if (!src || !out) { console.error('usage: node render.mjs <hwpx> <outdir>'); process.exit(2); }
fs.mkdirSync(out, { recursive: true });
const doc = new m.HwpDocument(fs.readFileSync(src));
const n = doc.pageCount();
for (let i = 0; i < n; i++) fs.writeFileSync(path.join(out, `p${String(i + 1).padStart(2, '0')}.svg`), doc.renderPageSvg(i));
console.log('pages', n);
