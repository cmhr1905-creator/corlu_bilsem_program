#!/usr/bin/env node
/* "Program düzeltme" (yama katmanı) bölümünü GERÇEK tarayıcıda uçtan uca sınar.
 *
 *   node araclar/duzeltme_testi.mjs
 *
 * Neden gerçek tarayıcı: yama katmanı localStorage'a yazıyor, şifre çözme
 * Web Crypto istiyor ve panel yönetici kapısının arkasında. Üçü de ancak
 * sayfanın kendi içinde sınanır.
 *
 * TUZAK: file:// üzerinde localStorage "null" kaynağa düşüp sessizce boş
 * dönebiliyor — bu yüzden test sayfayı 127.0.0.1'den servis eder.
 */
import { spawn, execSync } from 'child_process';
import http from 'http';
import fs from 'fs';
import path from 'path';

const KOK = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const PROF = path.join(process.env.TMPDIR || '/tmp', 'bilsem-duzeltme-profil');
const CDP = 9352, WEB = 9353;
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ACILIS = 'bilsem2018', YONETICI = 'corlu2026admin';
const OGR = 'GÜLCE BAHAR ÖZŞAHİN';

const sunucu = http.createServer((rq, rs) => {
  const dosya = rq.url === '/' ? 'index.html' : decodeURIComponent(rq.url.split('?')[0]).slice(1);
  const tam = path.join(KOK, dosya);
  if (!tam.startsWith(KOK) || !fs.existsSync(tam)) { rs.writeHead(404); rs.end(); return; }
  rs.writeHead(200, { 'content-type': dosya.endsWith('.html') ? 'text/html; charset=utf-8' : 'application/octet-stream' });
  rs.end(fs.readFileSync(tam));
});
await new Promise(r => sunucu.listen(WEB, '127.0.0.1', r));

const sleep = ms => new Promise(r => setTimeout(r, ms));
/* Öldürülen Chrome profile yazmayı hemen bırakmıyor: beklemeden silmek
   ENOTEMPTY veriyordu. */
try { execSync(`pkill -f "remote-debugging-port=${CDP}"`); await sleep(500); } catch (e) {}
fs.rmSync(PROF, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
const chrome = spawn(CHROME, ['--headless=new', '--remote-debugging-port=' + CDP,
  '--user-data-dir=' + PROF, '--no-first-run', '--disable-gpu',
  `http://127.0.0.1:${WEB}/index.html`], { stdio: 'ignore' });

const list = () => new Promise((res, rej) => {
  http.get({ host: '127.0.0.1', port: CDP, path: '/json/list' }, r => {
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
  const r = await send('Runtime.evaluate', { expression: x, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 400));
  return r.result?.result?.value;
};
await send('Runtime.enable'); await sleep(700);

let gecti = 0, kaldi = 0;
function ol(ad, kosul, ek) {
  if (kosul) { gecti++; console.log('  ✓ ' + ad); }
  else { kaldi++; console.log('  ✗ ' + ad + (ek ? '\n      ' + JSON.stringify(ek) : '')); }
}

/* --- açılış --- */
await ev(`(function(){document.getElementById("upass").value=${JSON.stringify(ACILIS)};
  document.getElementById("unlockForm").dispatchEvent(new Event("submit",{cancelable:true,bubbles:true}));})()`);
for (let i = 0; i < 60; i++) { if (await ev('!!(window.state&&state.students&&state.students.size)')) break; await sleep(400); }
await ev('localStorage.removeItem("corlu-bilsem-yama-v1"); boot(true);');
await sleep(300);

const prog = `(function(){var s=state.students.get(fold(${JSON.stringify(OGR)}));
  return s ? s.lessons.map(function(L){return L.dayKey+" "+L.slot+" "+L.teacher;}).sort() : null;})()`;

console.log('\n1) Gömülü yamalar açılışta biniyor mu');
ol('513 öğrenci yüklendi', await ev('state.students.size') === 513, await ev('state.students.size'));
/* Gömülü yama sayısı zamanla değişir; sayıyı veriden AL, sabitleme. */
const N = await ev('state.yamaSonuc.length');
ol('gömülü düzeltme var (' + N + ')', N >= 3);
ol('hepsi uygulandı', (await ev('state.yamaSonuc.filter(function(x){return x.ok;}).length')) === N,
   await ev('state.yamaSonuc.map(function(x){return x.ok?"ok":x.hata;})'));
const p0 = await ev(prog);
ol('Gülce: Salı yok, Cuma Emine+İlkay, Cumartesi Burcu+Tülay',
   p0.length === 4 && !p0.some(x => x.indexOf('SALI') === 0) &&
   p0.indexOf('CUMA 1-2-3. ders EMİNE GÜL ÖZKAN') >= 0 &&
   p0.indexOf('CUMA 4-5. ders İLKAY TUNCEL') >= 0 &&
   p0.indexOf('CUMARTESİ 1-2-3. ders DR. BURCU ÇALIŞKAN KARAKULAK') >= 0 &&
   p0.indexOf('CUMARTESİ 4-5. ders TÜLAY COŞKUN') >= 0, p0);

console.log('\n2) Yönetici kapısı');
ol('panel şifresiz kapalı', await ev('document.getElementById("fixSection").hidden') === true);
await ev(`(function(){document.getElementById("fixOpen").click();
  document.getElementById("fpass").value=${JSON.stringify(YONETICI)};
  document.getElementById("fixForm").dispatchEvent(new Event("submit",{cancelable:true,bubbles:true}));})()`);
ol('doğru şifreyle açıldı', await ev('document.getElementById("fixSection").hidden') === false);
ol('liste ' + N + ' satır çizdi', await ev('document.querySelectorAll("#fixList .yrow").length') === N);
ol('hepsi "yayında" diyor',
   await ev('[].slice.call(document.querySelectorAll("#fixList .durum")).every(function(d){return d.textContent==="yayında";})'));

console.log('\n3) Yeni düzeltme yazma');
await ev(`(function(){document.getElementById("fixText").value="Gülce Bahar Özşahin:\\ncuma 1-2-3 Ahmet Mehmet";
  document.getElementById("fixParse").click();})()`);
const onizleme = await ev('document.getElementById("fixPrev").textContent');
ol('olmayan öğretmen reddedildi', /bulunamadı/.test(onizleme), onizleme.slice(0, 200));
await ev(`(function(){document.getElementById("fixText").value="Gülce Bahar Özşahin:\\ncuma 4-5 Şenol Kuru";
  document.getElementById("fixParse").click();})()`);
ol('o saatte dersi olmayan öğretmen reddedildi',
   /tutmuyor|vermiyor/.test(await ev('document.getElementById("fixPrev").textContent')),
   (await ev('document.getElementById("fixPrev").textContent')).slice(0, 200));

await ev(`(function(){document.getElementById("fixText").value="Gülce Bahar Özşahin:\\ncumartesi sabah 4-5 sil";
  document.getElementById("fixParse").click();})()`);
ol('geçerli komut önizlendi', /Cumartesi/.test(await ev('document.getElementById("fixPrev").textContent')));
await ev(`[].slice.call(document.querySelectorAll("#fixPrev button")).filter(function(b){return b.textContent.indexOf("Evet")>=0;})[0].click()`);
await sleep(200);
const p1 = await ev(prog);
ol('uygulandı: Cumartesi 4-5 düştü', p1.length === 3 && !p1.some(x => x.indexOf('CUMARTESİ 4-5') === 0), p1);
ol('liste bir satır uzadı', await ev('document.querySelectorAll("#fixList .yrow").length') === N + 1);
ol('yenisi "bu tarayıcıda" diyor',
   await ev('[].slice.call(document.querySelectorAll("#fixList .durum")).map(function(d){return d.textContent;}).indexOf("bu tarayıcıda")>=0'));

console.log('\n4) Kalıcılık ve geri alma');
await ev('boot(false)'); await sleep(300);
ol('sayfa yeniden kurulunca düzeltme duruyor', (await ev(prog)).length === 3);
await ev(`[].slice.call(document.querySelectorAll("#fixList .yrow")).filter(function(r){
  return r.textContent.indexOf("bu tarayıcıda")>=0;})[0].querySelector("button").click()`);
await sleep(200);
const p2 = await ev(prog);
ol('geri alınca eski hale döndü', JSON.stringify(p2) === JSON.stringify(p0), p2);

console.log('\n5) Yama metni');
const metin = await ev(`(function(){return JSON.stringify(yamaListesi().map(function(y){
  var k={}; for(var a in y) if(a!=="gomulu") k[a]=y[a]; return k;}));})()`);
let coz = null; try { coz = JSON.parse(metin); } catch (e) {}
ol('kopyalanacak metin geçerli JSON ve ' + N + ' kayıt', Array.isArray(coz) && coz.length === N, coz && coz.length);
ol('her kaydın kimliği ve işlemi var', coz && coz.every(y => y.id && y.op && y.ogrenci && y.gun));

console.log('\n6) Gömülü yamayı geri alma (yayından düşürme)');
await ev(`[].slice.call(document.querySelectorAll("#fixList .yrow")).filter(function(r){
  return r.textContent.indexOf("SALI")>=0||r.textContent.indexOf("Salı")>=0;})[0].querySelector("button").click()`);
await sleep(200);
const p3 = await ev(prog);
ol('Salı yaması iptal edilince Salı dersleri geri geldi', p3.some(x => x.indexOf('SALI') === 0), p3);
ol('kopyalanacak listede bir eksik kayıt var', (await ev('yamaListesi().length')) === N - 1);

/* temizlik: test izlerini bırakma */
await ev('localStorage.removeItem("corlu-bilsem-yama-v1")');

console.log(`\n${kaldi === 0 ? '✅' : '❌'}  ${gecti} geçti, ${kaldi} kaldı`);
try { chrome.kill(); } catch (e) {}
sunucu.close();
process.exit(kaldi === 0 ? 0 : 1);
