#!/usr/bin/env python3
"""Ana Excel'i ve içindeki öğretmen sayfalarını okumak, düzenlemek ve
doğrulamak için küçük bir takım. Kaynak dosyalar depoda DEĞİL (öğrenci adı
içeriyor); bu araç dosyayı dışarıdan yol vererek çalışır.

    python3 araclar/xlsx_arac.py dok     <dosya.xlsx> [sayfa]
    python3 araclar/xlsx_arac.py yaz     <dosya.xlsx> <sayfa> K39="AD SOYAD" H61=
    python3 araclar/xlsx_arac.py fark    <eski.xlsx> <yeni.xlsx>
    python3 araclar/xlsx_arac.py senkron <dosya.xlsx>
    python3 araclar/xlsx_arac.py dogrula <dosya.xlsx>

TUZAKLAR (pahalıya öğrenildi):
· Hücreleri regex ile ayrıştırırken `<c r="X"[^>]*(?:/>|>.*?</c>)` deseni
  kendi kendine kapanan hücrede geri izleyip SONRAKİ hücreleri yutar.
  Doğrusu HUCRE deseni: `<c\\b[^>]*?/>|<c\\b[^>]*?>.*?</c>`.
· `<v xml:space="preserve">` olan hücreleri `<v>(.*?)</v>` kaçırır; yeniden
  yazarken niteliği düşürürsen sondaki boşluklar kaybolur.
· Öğretmen sayfaları FORMÜLLÜDÜR (`='2025-2026 AKŞAM PROGRAM'!H61`). Hücreyi
  elle yazınca Excel yeniden hesaplamaz, önbellekteki `<v>` bayat kalır →
  `senkron` bunu tazeler. workbook.xml'de `fullCalcOnLoad="1"` de duruyor.
· Her düzenlemeden sonra `fark` ile beklenen hücre sayısını DOĞRULA.
"""
import json
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
HUCRE = re.compile(rb'<c\b[^>]*?/>|<c\b[^>]*?>.*?</c>', re.S)
ANA = '2025-2026 AKŞAM PROGRAM'

# Öğretmen sayfası düzeni: sütun = gün, satır bandı = ders saati.
# (gün, sayfadaki sütun, ana sayfada 1-2-3. ders bandı, 4-5. ders bandı)
BANTLAR = [('SALI', 'B', (2, 18), (19, 36)),
           ('ÇARŞAMBA', 'C', (38, 59), (60, 83)),
           ('PERŞEMBE', 'D', (85, 100), (101, 119)),
           ('CUMA', 'E', (121, 140), (141, 151)),
           ('CUMARTESİ SABAH', 'G', (153, 171), (172, 189)),
           ('CUMARTESİ ÖĞLEDEN SONRA', 'I', (191, 205), (206, 217))]
BANT_BAS = {0: 4, 1: 33}          # sayfadaki başlangıç satırları


def sutun_no(harf):
    n = 0
    for ch in harf:
        n = n * 26 + ord(ch) - 64
    return n


def sutun_ad(n):                  # 1-tabanlı
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _sayfa_yolu(z, ad):
    rels = {r.get('Id'): r.get('Target').lstrip('/')
            for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
    for sh in ET.fromstring(z.read('xl/workbook.xml')).find(NS + 'sheets'):
        if sh.get('name').strip() == ad:
            h = rels[sh.get(RNS + 'id')]
            return h if h.startswith('xl/') else 'xl/' + h
    raise SystemExit('sayfa yok: ' + ad)


def _ortak(z):
    if 'xl/sharedStrings.xml' not in z.namelist():
        return []
    return [''.join(t.text or '' for t in si.iter(NS + 't'))
            for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall(NS + 'si')]


def oku(yol, sayfa=None, ham=False):
    """{sayfa_adı: {(satır, 1-tabanlı sütun): metin}}"""
    z = zipfile.ZipFile(yol)
    ortak = _ortak(z)
    cikti = {}
    for sh in ET.fromstring(z.read('xl/workbook.xml')).find(NS + 'sheets'):
        ad = sh.get('name').strip()
        if sayfa and ad != sayfa:
            continue
        h = _sayfa_yolu(z, ad)
        hucre = {}
        for row in ET.fromstring(z.read(h)).find(NS + 'sheetData'):
            for c in row:
                v, isel, t = c.find(NS + 'v'), c.find(NS + 'is'), c.get('t')
                if t == 's' and v is not None:
                    d = ortak[int(v.text)]
                elif isel is not None:
                    d = ''.join(x.text or '' for x in isel.iter(NS + 't'))
                elif v is not None:
                    d = v.text or ''
                else:
                    continue
                if not ham:
                    d = re.sub(r'\s+', ' ', d).strip()
                    if not d:
                        continue
                m = re.match(r'([A-Z]+)(\d+)', c.get('r'))
                hucre[(int(m.group(2)), sutun_no(m.group(1)))] = d
        cikti[ad] = hucre
    return cikti


def _kacis(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _paketle(z, yol, yeni_icerik):
    tmp = yol + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as out:
        for it in z.infolist():
            out.writestr(it, yeni_icerik.get(it.filename, z.read(it.filename)))
    z.close()
    shutil.move(tmp, yol)


def yaz(yol, sayfa, degisiklikler):
    """{'K39': 'AD SOYAD', 'H61': ''} — '' hücreyi boşaltır, stil korunur."""
    z = zipfile.ZipFile(yol)
    hedef = _sayfa_yolu(z, sayfa)
    xml = z.read(hedef)
    parca = [(m.start(), m.end(), m.group(0)) for m in HUCRE.finditer(xml)]
    for i in range(1, len(parca)):
        assert parca[i][0] >= parca[i - 1][1], 'hücre tokenleri örtüşüyor'
    yeni, imlec, bulundu = bytearray(), 0, set()
    for a, b, gov in parca:
        m = re.match(rb'<c\b[^>]*?r="([A-Z]+\d+)"', gov)
        ref = m.group(1).decode() if m else None
        if ref in degisiklikler:
            bulundu.add(ref)
            sm = re.search(rb'\ss="(\d+)"', gov)
            stil = (' s="%s"' % sm.group(1).decode()) if sm else ''
            metin = degisiklikler[ref]
            gov = (('<c r="%s"%s/>' % (ref, stil)) if metin == '' else
                   ('<c r="%s"%s t="inlineStr"><is><t>%s</t></is></c>'
                    % (ref, stil, _kacis(metin)))).encode('utf-8')
        yeni += xml[imlec:a] + gov
        imlec = b
    yeni += xml[imlec:]
    eksik = set(degisiklikler) - bulundu
    if eksik:
        raise SystemExit('hücre bulunamadı: ' + ', '.join(sorted(eksik)))
    _paketle(z, yol, {hedef: bytes(yeni)})
    return bulundu


def _ana_hucreler(z):
    """(satır, sütun) -> ('s'|'n', HAM metin)"""
    ortak = _ortak(z)
    d = {}
    for row in ET.fromstring(z.read(_sayfa_yolu(z, ANA))).find(NS + 'sheetData'):
        for c in row:
            v, isel, t = c.find(NS + 'v'), c.find(NS + 'is'), c.get('t')
            if t == 's' and v is not None:
                tip, metin = 's', ortak[int(v.text)]
            elif isel is not None:
                tip, metin = 's', ''.join(x.text or '' for x in isel.iter(NS + 't'))
            elif t in ('str', 'inlineStr') and v is not None:
                tip, metin = 's', (v.text or '')
            elif v is not None:
                tip, metin = 'n', (v.text or '')
            else:
                continue
            m = re.match(r'([A-Z]+)(\d+)', c.get('r'))
            d[(int(m.group(2)), sutun_no(m.group(1)))] = (tip, metin)
    return d


def senkron(yol, sayfalar):
    """Formüllerin ÖNBELLEKLİ değerlerini ana sayfadan yeniden hesaplar."""
    basit = re.compile(r"^'%s'!\$?([A-Z]{1,2})\$?(\d+)$" % re.escape(ANA))
    z = zipfile.ZipFile(yol)
    ana = _ana_hucreler(z)
    yeni_icerik, rapor = {}, {}
    for s in sayfalar:
        p = _sayfa_yolu(z, s)
        xml = z.read(p)
        parca = [(m.start(), m.end(), m.group(0)) for m in HUCRE.finditer(xml)]
        out, imlec, degisen = bytearray(), 0, []
        for a, b, gov in parca:
            g = gov.decode('utf-8')
            fm = re.search(r'<f[^>]*>(.*?)</f>', g, re.S)
            mm = basit.match(fm.group(1)) if fm else None
            if mm:
                ref = re.match(r'<c r="([A-Z]+\d+)"', g).group(1)
                sm = re.search(r'\ss="(\d+)"', g)
                stil = (' s="%s"' % sm.group(1)) if sm else ''
                tip, metin = ana.get((int(mm.group(2)), sutun_no(mm.group(1))), (None, None))
                if tip is None or (tip == 's' and metin == ''):
                    t_attr, v = '', '0'          # boş kaynak -> Excel 0 döndürür
                elif tip == 'n':
                    t_attr, v = '', metin
                else:
                    t_attr, v = ' t="str"', _kacis(metin)
                eski = re.search(r'<v[^>]*>(.*?)</v>', g, re.S)
                if (eski.group(1) if eski else None) != v:
                    degisen.append((ref, eski.group(1) if eski else None, v))
                vs = ' xml:space="preserve"' if v != v.strip() else ''
                g = ('<c r="%s"%s%s><f>%s</f><v%s>%s</v></c>'
                     % (ref, stil, t_attr, fm.group(1), vs, v))
                gov = g.encode('utf-8')
            out += xml[imlec:a] + gov
            imlec = b
        out += xml[imlec:]
        yeni_icerik[p] = bytes(out)
        rapor[s] = degisen
    wb = z.read('xl/workbook.xml').decode('utf-8')
    if 'fullCalcOnLoad' not in wb:
        yeni_icerik['xl/workbook.xml'] = re.sub(
            r'<calcPr([^>]*?)/>', r'<calcPr\1 fullCalcOnLoad="1"/>', wb).encode('utf-8')
    _paketle(z, yol, yeni_icerik)
    return rapor


def ogretmen_sayfalari(yol):
    """{sayfa adı: ana sayfadaki sütun harfi} — sayfanın kendi formüllerinden."""
    basit = re.compile(r"^'%s'!\$?([A-Z]{1,2})\$?\d+$" % re.escape(ANA))
    z = zipfile.ZipFile(yol)
    esleme = {}
    for sh in ET.fromstring(z.read('xl/workbook.xml')).find(NS + 'sheets'):
        ad = sh.get('name').strip()
        if ad == ANA:
            continue
        xml = z.read(_sayfa_yolu(z, ad)).decode('utf-8', 'ignore')
        say = {}
        for f in re.findall(r'<f[^>]*>(.*?)</f>', xml, re.S):
            m = basit.match(f)
            if m:
                say[m.group(1)] = say.get(m.group(1), 0) + 1
        if say:
            esleme[ad] = max(say, key=say.get)
    return esleme


def dogrula(yol):
    """Her öğretmen sayfası kendi sütununu doğru satırlardan okuyor mu?"""
    sayfalar = oku(yol)
    ana = sayfalar[ANA]
    esleme = ogretmen_sayfalari(yol)
    toplam = hata = 0
    satirlar = []
    for sayfa, kol in sorted(esleme.items()):
        sh = sayfalar[sayfa]
        yanlis = 0
        for _gun, shk, b0, b1 in BANTLAR:
            for bant, (bas, son) in ((0, b0), (1, b1)):
                for k, r in enumerate(range(bas, son + 1)):
                    toplam += 1
                    bekle = ana.get((r, sutun_no(kol)), '') or '0'
                    if sh.get((BANT_BAS[bant] + k, sutun_no(shk)), '') != bekle:
                        yanlis += 1
        hata += yanlis
        basl = ana.get((1, sutun_no(kol)), '?')
        satirlar.append('  %-10s sütun %-2s  %-46s %s'
                        % (sayfa, kol, basl[:44], 'TAMAM' if not yanlis else '%d UYUŞMAZ' % yanlis))
    return toplam, hata, satirlar


def main(argv):
    if not argv:
        print(__doc__)
        return
    komut, argv = argv[0], argv[1:]
    if komut == 'dok':
        for ad, h in oku(argv[0], argv[1] if len(argv) > 1 else None).items():
            print('---', ad)
            for (r, c), v in sorted(h.items()):
                print('  %s%d = %r' % (sutun_ad(c), r, v))
    elif komut == 'yaz':
        yol, sayfa = argv[0], argv[1]
        d = {}
        for p in argv[2:]:
            k, _, v = p.partition('=')
            d[k] = v
        print('yazıldı:', sorted(yaz(yol, sayfa, d)))
    elif komut == 'fark':
        A, B = oku(argv[0]), oku(argv[1])
        n = 0
        for ad in A:
            if ad not in B:
                print('SAYFA YOK:', ad)
                continue
            for k in sorted(set(A[ad]) | set(B[ad])):
                x, y = A[ad].get(k, ''), B[ad].get(k, '')
                if x != y:
                    n += 1
                    print('%s %s%d: %r -> %r' % (ad, sutun_ad(k[1]), k[0], x, y))
        print('TOPLAM FARK:', n)
    elif komut == 'senkron':
        r = senkron(argv[0], list(ogretmen_sayfalari(argv[0])))
        n = 0
        for s, d in r.items():
            for ref, e, y in d:
                n += 1
                print('  %s %s: %r -> %r' % (s, ref, e, y))
        print('tazelenen hücre:', n)
    elif komut == 'dogrula':
        toplam, hata, satirlar = dogrula(argv[0])
        print('\n'.join(satirlar))
        print('\nkarşılaştırılan %d hücre · uyuşmayan %d' % (toplam, hata))
        if hata:
            sys.exit(1)
    else:
        raise SystemExit('bilinmeyen komut: ' + komut)


if __name__ == '__main__':
    main(sys.argv[1:])
