#!/usr/bin/env python3
"""
Ders programını Excel'den index.html'in içine ŞİFRELİ olarak gömer.

Kullanım:
    python3 araclar/guncelle.py "yeni akşam programı.xlsx"
    python3 araclar/guncelle.py aksam.xlsx uyum.xlsx
    python3 araclar/guncelle.py --parola-degistir            (veriye dokunmadan parolayı değiştir)

Seçenekler:
    --parola PAROLA         mevcut parola (verilmezse sorulur)
    --yeni-parola PAROLA    veriyi yeni parolayla yeniden şifreler
    --parola-degistir       xlsx vermeden yalnız parolayı değiştirir

Hangi dosyanın hangi program olduğunu kendi anlar; yalnızca verdiğiniz
dosyaların karşılığını değiştirir, ötekine dokunmaz.
Gerekenler: Python 3 ve Node.js (şifreleme için).
Sonrasında:  git commit -am "program güncellendi" && git push
"""
import getpass, json, os, re, subprocess, sys, zipfile
import xml.etree.ElementTree as ET

NS  = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(KOK, 'index.html')
SIFRE = os.path.join(KOK, 'araclar', 'sifrele.js')


def node_calistir(argv, girdi):
    try:
        r = subprocess.run(['node', SIFRE] + argv, input=girdi,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise SystemExit('HATA: Node.js bulunamadı. Şifreleme için gerekli.\n'
                         '  Kurulum:  brew install node')
    if r.returncode != 0:
        raise SystemExit((r.stderr.decode('utf-8', 'replace').strip() or 'HATA: şifreleme adımı başarısız.'))
    return r.stdout


def sifreli_blok_oku(html):
    m = re.search(r'<script type="application/json" id="bakedEnc">(.*?)</script>', html, re.S)
    if not m:
        raise SystemExit('HATA: index.html içinde "bakedEnc" veri bloğu bulunamadı.')
    return m.group(1)


def sayfalari_oku(yol):
    """xlsx -> [{'name':..., 'grid':[[hücre,...],...]}]  (biçimli metin değerleri)"""
    with open(yol, 'rb') as f:
        if f.read(2) != b'PK':
            raise SystemExit('HATA: "%s" geçerli bir .xlsx değil. Excel\'de '
                             '"Farklı Kaydet → Excel Çalışma Kitabı (.xlsx)" ile kaydedin.' % yol)
    z = zipfile.ZipFile(yol)
    ortak = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(NS + 'si'):
            ortak.append(''.join(t.text or '' for t in si.iter(NS + 't')))
    rels = {r.get('Id'): r.get('Target').lstrip('/')
            for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}

    def sutun(ref):
        m = re.match(r'([A-Z]+)(\d+)', ref)
        c = 0
        for ch in m.group(1):
            c = c * 26 + ord(ch) - 64
        return c - 1, int(m.group(2))

    cikti = []
    for sh in ET.fromstring(z.read('xl/workbook.xml')).find(NS + 'sheets'):
        hedef = rels[sh.get(RNS + 'id')]
        if not hedef.startswith('xl/'):
            hedef = 'xl/' + hedef
        kok = ET.fromstring(z.read(hedef))
        hucre, mr, mc = {}, 0, 0
        for row in kok.find(NS + 'sheetData'):
            for c in row:
                v, isEl = c.find(NS + 'v'), c.find(NS + 'is')
                if c.get('t') == 's' and v is not None:
                    d = ortak[int(v.text)]
                elif isEl is not None:
                    d = ''.join(x.text or '' for x in isEl.iter(NS + 't'))
                elif v is not None:
                    d = v.text or ''
                else:
                    continue
                d = re.sub(r'\s+', ' ', d).strip()
                if not d:
                    continue
                ci, ri = sutun(c.get('r'))
                hucre[(ri, ci)] = d
                mr, mc = max(mr, ri), max(mc, ci)
        g = []
        for ri in range(1, mr + 1):
            satir = [hucre.get((ri, ci), '') for ci in range(mc + 1)]
            while satir and satir[-1] == '':
                satir.pop()
            g.append(satir)
        while g and not g[-1]:
            g.pop()
        cikti.append({'name': sh.get('name').strip(),
                      'hidden': sh.get('state') in ('hidden', 'veryHidden'),
                      'grid': g})
    return cikti


def aksam_sayfasi(grid):
    """Sütun başına bir öğretmen düzeni mi? Öyleyse öğrenci sayısını döndür."""
    basliklar = [i for i, r in enumerate(grid)
                 if sum(1 for c in range(2, len(r)) if r[c] and re.search(r'\(.+\)', r[c])) >= 4]
    if not basliklar:
        return 0
    anahtar = re.compile(r'^(DESTEK|ÖYG|OYG|PROJE|BYF|UYUM|ATÖLYE|ATOLYE|KULÜP|KULUP)', re.I)
    n = 0
    for r in grid:
        for c in range(2, len(r)):
            if r[c] and not anahtar.match(r[c]):
                n += 1
    return n if any(anahtar.match(r[c]) for r in grid for c in range(2, len(r)) if r[c]) else 0


def uyum_dosyasi(sayfalar):
    """Sayfa başına bir öğretmen düzeni mi?"""
    return sum(1 for sh in sayfalar
               for r in sh['grid'][:6]
               for v in r
               if re.search(r'HAFTALIK\s+DERS\s+PROGRAMI', v or '', re.I))


def gom(html, sifreli):
    if '</script' in sifreli.lower():
        raise SystemExit('HATA: şifreli blokta </script> geçiyor.')
    desen = re.compile(r'(<script type="application/json" id="bakedEnc">)(.*?)(</script>)', re.S)
    return desen.sub(lambda m: m.group(1) + sifreli + m.group(3), html, count=1)


def main(argv):
    parola = yeni_parola = None
    yalniz_parola = False
    yollar = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == '--parola':
            i += 1; parola = argv[i]
        elif a == '--yeni-parola':
            i += 1; yeni_parola = argv[i]
        elif a == '--parola-degistir':
            yalniz_parola = True
        elif a in ('-h', '--help'):
            raise SystemExit(__doc__)
        else:
            yollar.append(a)
        i += 1

    if not yollar and not yalniz_parola and not yeni_parola:
        raise SystemExit(__doc__)

    html = open(HTML, encoding='utf-8').read()
    if parola is None:
        parola = getpass.getpass('Mevcut parola: ')
    veri = json.loads(node_calistir(['--coz', parola], sifreli_blok_oku(html).encode('utf-8')))

    degisen = []
    for yol in yollar:
        yol = os.path.expanduser(yol)
        if not os.path.exists(yol):
            raise SystemExit('HATA: dosya yok: ' + yol)
        sayfalar = sayfalari_oku(yol)

        n_uyum = uyum_dosyasi(sayfalar)
        if n_uyum:
            veri['uyum'] = [{'name': s['name'], 'hidden': s['hidden'], 'grid': s['grid']} for s in sayfalar]
            degisen.append('UYUM  <- %s  (%d ogretmen sayfasi, %d sayfa)'
                           % (os.path.basename(yol), n_uyum, len(sayfalar)))
            continue

        en_iyi = None
        for s in sayfalar:
            n = aksam_sayfasi(s['grid'])
            if n and (en_iyi is None or n > en_iyi[0]):
                en_iyi = (n, s)
        if en_iyi:
            veri['aksam'] = en_iyi[1]['grid']
            degisen.append('AKSAM <- %s  (sayfa: %s, ~%d isim hucresi)'
                           % (os.path.basename(yol), en_iyi[1]['name'], en_iyi[0]))
            continue

        raise SystemExit('HATA: "%s" icinde taninan bir program yok.\n'
                         '  Aksam programi: bir satirda en az 4 hucrede "Ad (BRANS)" olmali.\n'
                         '  Uyum programi: her ogretmen sayfasinda "... HAFTALIK DERS PROGRAMI" basligi olmali.'
                         % os.path.basename(yol))

    if yalniz_parola and yeni_parola is None:
        yeni_parola = getpass.getpass('Yeni parola: ')
        if yeni_parola != getpass.getpass('Yeni parola (tekrar): '):
            raise SystemExit('HATA: parolalar uyusmadi.')

    kullanilan = yeni_parola or parola
    sifreli = node_calistir([kullanilan], json.dumps(veri, ensure_ascii=False).encode('utf-8')).decode('utf-8')
    json.loads(sifreli)
    html = gom(html, sifreli)
    open(HTML, 'w', encoding='utf-8').write(html)

    print('index.html guncellendi:')
    for d in degisen:
        print('  ' + d)
    if yeni_parola:
        print('  PAROLA degistirildi.')
    if not degisen and not yeni_parola:
        print('  (veri degismedi, yalnizca yeniden sifrelendi)')
    print('\nTarayicida acip kontrol edin, sonra:')
    print('  git -C "%s" commit -am "ders programi guncellendi" && git -C "%s" push' % (KOK, KOK))


if __name__ == '__main__':
    main(sys.argv[1:])
