"""Validate local repository structure, traceability and links; no third-party dependencies."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import hashlib, json, re, struct, sys, zlib

ROOT=Path(__file__).resolve().parents[1]
errors=[]
def check(ok, message):
    if not ok: errors.append(message)

catalog=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
check(catalog['name']=='ai-to-agent-style-systems-02','Repo name mismatch')
check(catalog['version']==(ROOT/'VERSION').read_text(encoding='utf-8').strip(),'Version mismatch')
styles=[s for c in catalog['collections'] for s in c['styles']]
check([s['id'] for s in styles]==[f'AS-{i:03d}' for i in range(10,19)],'Style IDs mismatch')
check(catalog['next_style_id']=='AS-019','Next ID mismatch')
for s in styles:
    for k in ('spec','prompt','source_cover','card'): check((ROOT/s[k]).is_file(),f'Missing {s[k]}')
manifest=[m for c in catalog['collections'] for m in json.loads((ROOT/f"collections/{c['id']}/sources/manifest.json").read_text(encoding='utf-8'))]
check(len(manifest)==63,'Source count mismatch')
for m in manifest:
    p=ROOT/m['path']
    check(p.is_file(),f'Missing source {p}')
    if p.is_file(): check(hashlib.sha256(p.read_bytes()).hexdigest()==m['sha256'],f'Hash mismatch {p}')
cards=[p for c in catalog['collections'] for p in (ROOT/f"collections/{c['id']}/cards").glob('*.png')]
check(len(cards)==10,'Card count mismatch')
png_count=0
for p in ROOT.rglob('*.png'):
    b=p.read_bytes();png_count+=1
    check(b[:8]==b'\x89PNG\r\n\x1a\n',f'Bad PNG signature {p}')
    pos=8;ended=False
    while pos+12<=len(b):
        n=struct.unpack('>I',b[pos:pos+4])[0];kind=b[pos+4:pos+8]
        end=pos+12+n
        if end>len(b): errors.append(f'Truncated PNG {p}');break
        check(zlib.crc32(b[pos+4:pos+8+n])&0xffffffff==struct.unpack('>I',b[pos+8+n:end])[0],f'PNG CRC mismatch {p}')
        pos=end
        if kind==b'IEND':ended=True;break
    check(ended,f'No PNG IEND {p}')
    if '/sources/' in p.as_posix(): check(struct.unpack('>II',b[16:24])==(2160,2700),f'Source size mismatch {p}')

spec=(ROOT/'collections/02/SPECIFICATION.md').read_text(encoding='utf-8')
rules=re.findall(r'^#### (AS-\d+-R\d+)',spec,re.M)
rules2=rules
questions=re.findall(r'^\| (?:AS-\d+-Q\d+|G-Q\d+)',spec,re.M)
questions2=[]
check(len(rules)==63 and len(set(rules))==63,'Rule group mismatch')
check(len(questions)==25,'Question count mismatch')
for m in json.loads((ROOT/'collections/02/cards/manifest.json').read_text(encoding='utf-8')):
    check(hashlib.sha256((ROOT/m['path']).read_bytes()).hexdigest()==m['sha256'],'Card hash mismatch')
class Links(HTMLParser):
    def __init__(self): super().__init__();self.links=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.add(a['id'])
        for k in ('href','src'):
            if k in a:self.links.append(a[k])

link_count=0
for p in list(ROOT.rglob('*.md'))+list(ROOT.rglob('*.html')):
    text=p.read_text(encoding='utf-8');parser=Links();parser.feed(text)
    links=parser.links+re.findall(r'\]\(([^)\s]+)(?:\s+"[^"]*")?\)',text)
    for href in links:
        if urlsplit(href).scheme or href.startswith('//'):continue
        loc,_,anchor=href.partition('#')
        target=(p.parent/unquote(loc)).resolve() if loc else p
        link_count+=1
        check(target.is_relative_to(ROOT),f'Outside-root link {p}: {href}')
        check(target.exists(),f'Broken link {p}: {href}')
        if anchor and target.suffix=='.html' and target.exists():
            ap=Links();ap.feed(target.read_text(encoding='utf-8'));check(anchor in ap.ids,f'Broken anchor {href}')

for p in ROOT.rglob('*'):
    if p.is_file():
        check(p.stat().st_size<100*1024*1024,f'File exceeds GitHub limit: {p}')
        check(p.name not in ('.env','id_rsa','id_ed25519'),f'Sensitive file name: {p}')

result={'status':'FAIL' if errors else 'PASS','styles':len(styles),'source_pngs':len(manifest),'cards':len(cards),'pngs_checked':png_count,'rule_groups':len(rules),'open_questions':len(questions)+len(questions2),'local_links_checked':link_count,'errors':errors,'not_verified':['remote publishing','browser interaction','font and color-area accuracy','six-medium generation']}
print(json.dumps(result,ensure_ascii=False,indent=2))
sys.exit(1 if errors else 0)
