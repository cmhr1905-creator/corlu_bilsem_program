#!/usr/bin/env node
/* stdin: düz metin (JSON)  ·  argv[2]: parola  →  stdout: {"v":1,"it":..,"salt":..,"iv":..,"ct":..}
   AES-256-GCM, anahtar PBKDF2-SHA256 ile türetilir. Tarayıcı tarafı Web Crypto ile açar. */
const crypto = require("crypto");
const IT = 250000;

const cozMod = process.argv[2] === "--coz";
const parola = cozMod ? process.argv[3] : process.argv[2];
if(!parola){
  console.error("kullanım:\n  node sifrele.js <parola>          (düz metin stdin → şifreli JSON stdout)\n  node sifrele.js --coz <parola>    (şifreli JSON stdin → düz metin stdout)");
  process.exit(1);
}

let buf = [];
process.stdin.on("data", d => buf.push(d));
process.stdin.on("end", () => {
  const duz = Buffer.concat(buf);

  if(cozMod){
    let blob;
    try{ blob = JSON.parse(duz.toString("utf8")); }
    catch(e){ console.error("HATA: şifreli blok okunamadı."); process.exit(2); }
    const b = s => Buffer.from(s, "base64");
    const key = crypto.pbkdf2Sync(Buffer.from(parola, "utf8"), b(blob.salt), blob.it || IT, 32, "sha256");
    const ct = b(blob.ct);
    const d = crypto.createDecipheriv("aes-256-gcm", key, b(blob.iv));
    d.setAuthTag(ct.slice(ct.length - 16));
    try{
      process.stdout.write(Buffer.concat([d.update(ct.slice(0, ct.length - 16)), d.final()]));
    }catch(e){ console.error("HATA: parola yanlış."); process.exit(3); }
    return;
  }

  const salt = crypto.randomBytes(16);
  const iv = crypto.randomBytes(12);
  const key = crypto.pbkdf2Sync(Buffer.from(parola, "utf8"), salt, IT, 32, "sha256");
  const c = crypto.createCipheriv("aes-256-gcm", key, iv);
  const ct = Buffer.concat([c.update(duz), c.final(), c.getAuthTag()]);
  process.stdout.write(JSON.stringify({
    v: 1, it: IT,
    salt: salt.toString("base64"),
    iv: iv.toString("base64"),
    ct: ct.toString("base64")
  }));
});
