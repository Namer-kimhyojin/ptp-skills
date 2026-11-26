"""Fill the guestbook template with ten-attendee pages. The signature column is always blank.
Never modify the source document.
"""
from pathlib import Path
from copy import deepcopy
from math import ceil
import argparse,csv,json,zipfile,hashlib
from lxml import etree as E

NS={'hp':'http://www.hancom.co.kr/hwpml/2011/paragraph'}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()
def q(prefix,name):return '{'+NS[prefix]+'}'+name
def read_attendees(path):
    path=Path(path)
    if path.suffix.lower()=='.json':
        rows=json.loads(path.read_text(encoding='utf-8-sig'))
        if isinstance(rows,dict):rows=rows.get('attendees')
    else:
        with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    if not isinstance(rows,list) or not rows:raise ValueError('An explicit nonempty attendee list is required.')
    result=[]
    for i,row in enumerate(rows,1):
        def value(*keys):
            for key in keys:
                v=str(row.get(key) or '').strip()
                if v:return v
            return ''
        a={'affiliation':value('affiliation','소속'),'title':value('title','직위'),'name':value('name','성명')}
        if not all(a.values()):raise ValueError(f'Attendee {i} requires affiliation/title/name. No names are inferred.')
        result.append(a)
    return result
def fill(cell,text):
    """Replace the whole cell content with one plain-text paragraph."""
    paragraphs=cell.findall('hp:subList/hp:p',NS)
    for extra in paragraphs[1:]:extra.getparent().remove(extra)
    p=paragraphs[0];char=p.find('hp:run',NS).get('charPrIDRef')
    for el in list(p):p.remove(el)
    run=E.SubElement(p,q('hp','run'),charPrIDRef=char)
    if text:E.SubElement(run,q('hp','t')).text=text
def signature_blank(cell):
    """True when the cell holds only empty paragraphs: no text, picture, shape or control."""
    allowed={q('hp','p'),q('hp','run')}
    return all(el.tag in allowed for el in cell.find('hp:subList',NS).iterdescendants())

def build(source,attendees_path,output,meeting_name=None,date=None,time=None,place=None):
    source=Path(source).resolve();output=Path(output).resolve()
    if source==output:raise ValueError('Output must differ from source.')
    if output.exists():raise FileExistsError('Refusing to overwrite an existing output.')
    attendees=read_attendees(attendees_path);source_sha=sha(source)
    with zipfile.ZipFile(source) as z:parts={n:z.read(n) for n in z.namelist()}
    section=E.fromstring(parts['Contents/section0.xml'])
    # A source with embedded images could carry signatures into the output.
    if any(n.startswith('BinData/') for n in parts) or section.findall('.//hp:pic',NS):
        raise ValueError('Source contains images. Use a blank guestbook template.')
    direct=section.findall('hp:p',NS)
    hosts=[p for p in direct if p.find('.//hp:tbl',NS) is not None]
    if len(hosts)!=1:raise ValueError('Source must contain exactly one guestbook table.')
    host=hosts[0];table=host.find('.//hp:tbl',NS)
    if table.get('rowCnt')!='11' or table.get('colCnt')!='5':raise ValueError('Source must have a header plus ten attendee rows and five columns.')
    before=direct[:direct.index(host)]
    if len(before)!=3:raise ValueError('Source must have exactly title/date/place before the table.')
    for p,text in zip(before,[meeting_name,('◦ 일시 : '+date+' '+time) if date and time else None,('◦ 장소 : '+place) if place else None]):
        if text is not None:
            ts=p.findall('.//hp:t',NS);ts[0].text=text
            for t in ts[1:]:t.text=''
    template=[*before,host]
    page_count=ceil(len(attendees)/10)
    for c in list(section):section.remove(c)
    signature_cells=[]
    for page in range(page_count):
        body=[deepcopy(p) for p in template]
        if page:
            body[0].set('pageBreak','1')
            for e in list(body[0].xpath('.//hp:secPr|.//hp:colPr',namespaces=NS)):e.getparent().remove(e)
            for e in list(body[0].xpath('.//hp:ctrl',namespaces=NS)):
                if not len(e):e.getparent().remove(e)
        table_copy=body[3].find('.//hp:tbl',NS)
        table_copy.set('id',table.get('id') if page==0 else str(1800000000+page))
        for local,tr in enumerate(table_copy.findall('hp:tr',NS)[1:]):
            index=page*10+local;cs=tr.findall('hp:tc',NS);fill(cs[0],str(index+1))
            a=attendees[index] if index<len(attendees) else {}
            for cell,key in zip(cs[1:4],('affiliation','title','name')):fill(cell,a.get(key,''))
            fill(cs[4],'')
            signature_cells.append(cs[4])
        for p in body:section.append(p)
    # Unique paragraph IDs across all cloned pages.
    for i,p in enumerate(section.xpath('.//hp:p',namespaces=NS)):p.set('id',str(i))
    if not all(signature_blank(c) for c in signature_cells):raise ValueError('Signature column is not blank. Use a blank guestbook template.')
    parts['Contents/section0.xml']=E.tostring(section,encoding='UTF-8',xml_declaration=True,standalone=True)
    parts['Preview/PrvText.txt']=('\n'.join(section.xpath('.//hp:t/text()',namespaces=NS))).encode('utf-8')
    parts.pop('Preview/PrvImage.png',None)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x') as z:
        for n,raw in parts.items():z.writestr(n,raw,compress_type=zipfile.ZIP_STORED if n=='mimetype' else zipfile.ZIP_DEFLATED)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        for n in z.namelist():
            if n.endswith(('.xml','.hpf')):E.fromstring(z.read(n))
    ids=section.xpath('.//hp:p/@id',namespaces=NS)
    assert len(ids)==len(set(ids))
    assert len(section.findall('.//hp:secPr',NS))==1
    assert len(section.findall('.//hp:colPr',NS))==1
    assert sum(p.get('pageBreak')=='1' for p in section.findall('hp:p',NS))==page_count-1
    assert sha(source)==source_sha
    report={'source':str(source),'source_sha256':source_sha,'source_preserved':True,'output':str(output),'attendees':len(attendees),'logical_pages':page_count,'table_count':len(section.findall('.//hp:tbl',NS)),'signature_cells_blank':True,'native_render_status':'not performed; logical pageBreak/table structure validation only'}
    output.with_suffix('.validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=Path(__file__).resolve().parent.parent/'assets'/'방명록 양식.hwpx')
    p.add_argument('--meeting-name')
    p.add_argument('--date')
    p.add_argument('--time')
    p.add_argument('--place')
    p.add_argument('--attendees',type=Path,required=True,help='UTF-8 CSV or JSON: affiliation/title/name or 소속/직위/성명')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(build(a.source,a.attendees,a.output,a.meeting_name,a.date,a.time,a.place),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
