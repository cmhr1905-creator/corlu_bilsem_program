#!/usr/bin/env node
/* Öğretmen (ya da öğrenci) çıktısını GERÇEK yazdırma yolundan üretip ölçer.
 *
 *   node araclar/baski_testi.mjs "GÜNEŞ TUNCEL"            -> cikti.pdf
 *   node araclar/baski_testi.mjs "NİL DORA DEMİREL" ogrenci
 *   node araclar/baski_testi.mjs --hepsi                    -> tüm öğretmenler
 *
 * window.print susturulur, sayfanın kendi yazdir() fonksiyonu çağrılır ve
 * Page.printToPDF `preferCSSPageSize:true` ile alınır — yani kağıt ölçüsünü
 * biz dayatmayız, sayfanın @page kuralı belirler. PDF'ten /MediaBox ile
 * kağıt+yön, /Count ile sayfa sayısı okunur.
 *
 * TUZAKLAR:
 * · Kalıntı headless Chrome eski sayfayı gösterir: her koşuda profil silinir.
 * · Doluluğu .wrap yüksekliğiyle ÖLÇME — sarmalayıcı uzasa da gün kutuları
 *   kısa kalabilir. Üretilen PDF'e bak: `qlmanage -t -s 2000 -o . cikti.pdf`
 * · --virtual-time-budget kullanma: Web Crypto gerçek zamanda çalışır.
 */
import { spawn, execSync } from 'child_process';
import http from 'http';
import fs from 'fs';
import path from 'path';

const KOK = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const HTML = 'file://' + path.join(KOK, 'index.html');
const PROF = path.join(process.env.TMPDIR || '/tmp', 'bilsem-baski-profil');
const PORT = 9351;
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ACILIS = 'bilsem2018', OGRETMEN_SIFRE = '1905';

const arg = process.argv.slice(2);
const hepsi = arg[0] === '--hepsi';
const KIM = hepsi ? null : (arg[0] || 'DR. MUSTAFA CEM KAYNAR');
const KIP = arg[1] || 'ogretmen';
/* Çıktılar ÖĞRENCİ ADI içerir; depo public olduğu için varsayılan yer
   depo değil, geçici dizindir. */
const CIKTI_DIZIN = process.env.TMPDIR || '/tmp';
const CIKTI = arg[2] || path.join(CIKTI_DIZIN, 'cikti.pdf');

try { execSync(`pkill -f "remote-debugging-port=${PORT}"`); } catch (e) {}
fs.rmSync(PROF, { recursive: true, force: true });

const chrome = spawn(CHROME, ['--headless=new', '--remote-debugging-port=' + PORT,
  '--user-data-dir=' + PROF, '--no-first-run', '--disable-gpu', HTML], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const list = () => new Promise((res, rej) => {
  http.get({ host: '127.0.0.1', port: PORT, path: '/json/list' }, r => {
    let b = ''; r.on('data', c => b += c);
    r.on('end', () => { try { res(JSON.parse(b)); } catch (e) { rej(e); } });
  }).on('error', rej);
});
let t = null;
for (let i = 0; i < 60 && !t; i++) {
  try { t = (await list()).find(x => x.type === 'page' && x.webSocketDebuggerUrl); } catch (e) {}
  if (!t) await sleep(300);
}
const ws = new WebSocket(t.webSocketDebuggerUrl);
let id = 0; const pend = new Map();
ws.onmessage = e => { const m = JSON.parse(e.data); if (pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
await new Promise(r => ws.onopen = r);
const send = (m, p = {}) => { const i = ++id; ws.send(JSON.stringify({ id: i, method: m, params: p })); return new Promise(r => pend.set(i, r)); };
const ev = async x => {
  const r = await send('Runtime.evaluate', { expression: x, returnByValue: true });
  if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 300));
  return r.result?.result?.value;
};
await send('Runtime.enable'); await sleep(800);
/* açılış kilidi (#unlockForm/#upass) ile öğretmen kapısı (#gateForm/#pass) AYRIDIR */
await ev(`(function(){document.getElementById("upass").value=${JSON.stringify(ACILIS)};
  document.getElementById("unlockForm").dispatchEvent(new Event("submit",{cancelable:true,bubbles:true}));})()`);
for (let i = 0; i < 60; i++) { if (await ev('!!(window.state&&state.students&&state.students.size)')) break; await sleep(400); }

async function bas(kim, kip, cikti) {
  if (kip === 'ogretmen') {
    const r = await ev(`(function(){
      document.getElementById("tabTeacher").click();
      var g=document.getElementById("pass");
      if(g && !g.closest("[hidden]")){ g.value=${JSON.stringify(OGRETMEN_SIFRE)};
        document.getElementById("gateForm").dispatchEvent(new Event("submit",{cancelable:true,bubbles:true})); }
      var sel=document.getElementById("tsel");
      var hit=[...sel.options].find(function(o){return o.textContent.toUpperCase().indexOf(${JSON.stringify(kim)})>=0;});
      if(!hit) return null;
      sel.value=hit.value; sel.dispatchEvent(new Event("change",{bubbles:true}));
      return hit.textContent;
    })()`);
    if (!r) { console.log(`${kim.padEnd(24)} BULUNAMADI`); return; }
  } else {
    await ev(`(function(){var q=document.getElementById("q"); q.value=${JSON.stringify(kim)};
      q.dispatchEvent(new Event("input",{bubbles:true}));
      var f=document.getElementById("searchForm");
      if(f) f.dispatchEvent(new Event("submit",{cancelable:true,bubbles:true}));})()`);
  }
  await sleep(600);
  await ev(`(function(){ window.print=function(){}; yazdir(${JSON.stringify(kip)}); })()`);
  await sleep(400);
  const pdf = await send('Page.printToPDF', { printBackground: true, preferCSSPageSize: true });
  const buf = Buffer.from(pdf.result.data, 'base64');
  fs.writeFileSync(cikti, buf);
  const txt = buf.toString('latin1');
  const sayfa = [...txt.matchAll(/\/Count\s+(\d+)/g)].map(m => +m[1]);
  const kutu = [...txt.matchAll(/\/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]/g)]
    .map(m => ({ w: +m[3] - +m[1], h: +m[4] - +m[2] }))[0] || { w: 0, h: 0 };
  const mm = v => Math.round(v / 72 * 25.4);
  console.log(`${kim.padEnd(24)} ${sayfa.length ? Math.max(...sayfa) : '?'} sayfa · ${mm(kutu.w)}x${mm(kutu.h)} mm · ${kutu.w > kutu.h ? 'YATAY' : 'DİKEY'} · ${cikti}`);
  await ev('yazdirTemizle()');
}

if (hepsi) {
  const adlar = await ev(`(function(){
    document.getElementById("tabTeacher").click();
    var g=document.getElementById("pass");
    if(g && !g.closest("[hidden]")){ g.value=${JSON.stringify(OGRETMEN_SIFRE)};
      document.getElementById("gateForm").dispatchEvent(new Event("submit",{cancelable:true,bubbles:true})); }
    return [...document.getElementById("tsel").options].map(function(o){return o.textContent.split(" — ")[0];});
  })()`);
  for (const a of adlar) await bas(a, 'ogretmen', path.join(CIKTI_DIZIN, 'baski-' + a.replace(/[^\wÇĞİÖŞÜçğıöşü]+/g, '_') + '.pdf'));
} else {
  await bas(KIM, KIP, CIKTI);
}
ws.close(); chrome.kill(); process.exit(0);
