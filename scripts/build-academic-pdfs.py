"""Build shareable reports and vector UML figures from versioned sources."""
import json, re
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Polygon
from reportlab.graphics import renderSVG, renderPM

root=Path(__file__).resolve().parents[1]
out=root/'output/pdf'; out.mkdir(parents=True,exist_ok=True)
figures=root/'docs/academic/figures';figures.mkdir(parents=True,exist_ok=True)
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='Text',fontName='Helvetica',fontSize=9.8,leading=13.5,spaceAfter=7,allowWidows=0,allowOrphans=0))
styles.add(ParagraphStyle(name='Cell',fontName='Helvetica',fontSize=8,leading=11,spaceAfter=0))
styles['Heading1'].textColor=colors.HexColor('#14384A');styles['Heading1'].fontSize=17;styles['Heading1'].leading=21
styles['Heading2'].textColor=colors.HexColor('#176B79');styles['Heading2'].fontSize=12;styles['Heading2'].leading=16
styles['Heading1'].keepWithNext=True;styles['Heading2'].keepWithNext=True
styles['Title'].textColor=colors.HexColor('#14384A')
def paragraph(text,style='Text'):
    links=[]
    def link(match):
        links.append((match.group(1),match.group(2)));return f'LINKTOKEN{len(links)-1}'
    text=re.sub(r'\[([^]]+)\]\(([^)]+)\)',link,text)
    text=text.replace('**','').replace('`','').replace('–','-').replace('—','-').replace('>','&gt;')
    text=escape(text).replace('&amp;gt;','&gt;')
    for index,(label,url) in enumerate(links):text=text.replace(f'LINKTOKEN{index}',f'<link href="{escape(url)}" color="#176B79">{escape(label)}</link>')
    return Paragraph(text,styles[style])
def table(rows,widths=None):
    rows=[[paragraph(cell,'Cell') for cell in row] for row in rows]
    result=Table(rows,colWidths=widths or [495/len(rows[0])]*len(rows[0]),repeatRows=1,hAlign='LEFT')
    result.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E1EFF2')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOX',(0,0),(-1,-1),.4,colors.HexColor('#AAC2C8')),('INNERGRID',(0,0),(-1,-1),.3,colors.HexColor('#CFDADD')),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    return result
def box(d,x,y,w,h,label,stereotype=None):
    d.add(Rect(x,y,w,h,strokeColor=colors.HexColor('#176B79'),fillColor=colors.HexColor('#F0F6F7'),strokeWidth=1))
    if stereotype:d.add(String(x+w/2,y+h-12,stereotype,textAnchor='middle',fontName='Helvetica',fontSize=7))
    for i,line in enumerate(label.split('\n')):d.add(String(x+w/2,y+h-26-i*12,line,textAnchor='middle',fontName='Helvetica',fontSize=9))
def arrow(d,x1,y1,x2,y2,label='',dashed=False):
    line=Line(x1,y1,x2,y2,strokeColor=colors.HexColor('#52747E'),strokeWidth=.8)
    if dashed:line.strokeDashArray=[4,3]
    d.add(line)
    if x1==x2:
        sign=1 if y2>y1 else -1;d.add(Polygon([x2,y2,x2-3,y2-6*sign,x2+3,y2-6*sign],fillColor=colors.HexColor('#52747E'),strokeColor=None))
    else:
        sign=1 if x2>x1 else -1;d.add(Polygon([x2,y2,x2-6*sign,y2+3,x2-6*sign,y2-3],fillColor=colors.HexColor('#52747E'),strokeColor=None))
    if label:d.add(String((x1+x2)/2+3,(y1+y2)/2+6,label,fontName='Helvetica',fontSize=7,textAnchor='middle'))
def architecture():
    d=Drawing(495,330)
    box(d,160,275,130,45,'Client')
    box(d,160,210,130,50,'Router\nRR / CH / adaptive','<<component>>')
    box(d,350,210,125,50,'Control API','<<component>>')
    box(d,350,275,125,45,'Redis registry')
    for x,label in [(10,'Edge 1'),(185,'Edge 2'),(360,'Edge 3')]:box(d,x,120,125,55,label+'\nLRU + fill gates','<<component>>')
    box(d,185,25,125,50,'Origin','<<component>>')
    arrow(d,225,275,225,260);arrow(d,290,235,350,235,'discover');arrow(d,412,260,412,275)
    d.add(Line(72,190,422,190,strokeColor=colors.HexColor('#52747E')));arrow(d,225,210,225,190)
    for x in [72,247,422]:arrow(d,x,190,x,175);d.add(Line(x,120,x,95,strokeColor=colors.HexColor('#52747E')))
    d.add(Line(72,95,422,95,strokeColor=colors.HexColor('#52747E')));arrow(d,247,95,247,75,'HTTP fetch')
    d.add(String(5,6,'Prometheus scrapes router/edges; Grafana queries Prometheus.',fontName='Helvetica',fontSize=9))
    return d
def sequence():
    d=Drawing(495,375); labels=['Client','Router','Edge','Fill gate','Cache','Origin'];positions=[35,120,205,290,375,460]
    for label,x in zip(labels,positions):
        box(d,x-34,330,68,35,label)
        line=Line(x,325,x,15,strokeColor=colors.HexColor('#9CB5BD'),strokeWidth=.6);line.strokeDashArray=[3,3];d.add(line)
    messages=[(0,1,'GET resource',False),(1,2,'reserve / proxy',False),(2,4,'fresh lookup: miss',False),(2,3,'acquire key gate',False),(2,4,'recheck: miss',False),(2,5,'GET / conditional GET',False),(5,2,'200 body or 304',True),(2,4,'admit / renew',False),(2,3,'release gate',False),(2,1,'content response',True),(1,0,'release / response',True)]
    for index,(a,b,label,dashed) in enumerate(messages):arrow(d,positions[a],315-index*26,positions[b],315-index*26,label,dashed)
    d.add(String(5,4,'Cacheable GET miss path. Separate UML source contains alternative branches.',fontName='Helvetica',fontSize=8))
    return d
def classes():
    d=Drawing(495,285)
    entries=[(0,145,'Ring','replicas; ring; hashMap','GetCandidates(key)\nSetNodes(nodes)'),(275,145,'selector','loads; next; mutex','reserve(mode, ids, slack)\nload(id)'),(0,5,'Cache','items; order; usedBytes','Get / Set / Stale\nDeletePrefix / Clear'),(275,5,'CacheEntry','Body; Header; Expiration','StatusCode\nIsExpired()')]
    for x,y,name,fields,methods in entries:
        box(d,x,y,220,125,name)
        d.add(Line(x,y+85,x+220,y+85,strokeColor=colors.HexColor('#176B79')))
        d.add(String(x+8,y+67,fields,fontName='Helvetica',fontSize=8))
        d.add(Line(x,y+53,x+220,y+53,strokeColor=colors.HexColor('#176B79')))
        for i,method in enumerate(methods.split('\n')):d.add(String(x+8,y+35-i*13,method,fontName='Helvetica',fontSize=8))
    # Composition: one Cache owns zero or more CacheEntry objects.
    d.add(Polygon([220,65,228,70,236,65,228,60],fillColor=colors.HexColor('#176B79'),strokeColor=None))
    d.add(Line(236,65,275,65,strokeColor=colors.HexColor('#176B79')))
    d.add(String(242,75,'0..*',fontName='Helvetica',fontSize=8))
    return d
drawings={'architecture':architecture(),'sequence':sequence(),'classes':classes()}
for name,drawing in drawings.items():
    renderSVG.drawToFile(drawing,str(figures/(name+'.svg')))
    try:renderPM.drawToFile(drawing,str(figures/(name+'.png')),fmt='PNG',dpi=160)
    except Exception as error:print('PNG renderer unavailable:',error)
def markdown_story(file):
    story=[];lines=file.read_text(encoding='utf-8').splitlines();index=0;code=False;last_heading=''
    while index<len(lines):
        line=lines[index]
        if line.startswith('```'):
            code=not code;index+=1;continue
        if code or not line.strip():index+=1;continue
        if line.startswith('|'):
            rows=[]
            while index<len(lines) and lines[index].startswith('|'):
                cells=[x.strip() for x in lines[index].strip('|').split('|')]
                if not all(re.fullmatch(r'[: -]+',x) for x in cells):rows.append(cells)
                index+=1
            story += [table(rows),Spacer(1,12)];continue
        if line.startswith('#'):
            heading=line.lstrip('#').strip();last_heading=heading
            title=paragraph(heading,'Heading1' if line.startswith('# ') else 'Heading2')
            figure=next((drawings[key] for key,match in [('architecture','component/deployment'),('sequence','miss sequence'),('classes','class relationships')] if match in heading),None)
            if figure:story.append(KeepTogether([title,figure,Spacer(1,12)]))
            else:story.append(title)
        else:
            story.append(paragraph(line))
        index+=1
    return story
def footer(canvas,doc):
    canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#52747E'))
    canvas.drawString(50,25,'MiniCDN / Group 21 / 10 October 2026')
    canvas.drawRightString(A4[0]-50,25,str(doc.page))
def build(name,story):
    doc=SimpleDocTemplate(str(out/name),pagesize=A4,rightMargin=50,leftMargin=50,topMargin=45,bottomMargin=45,title=name.replace('.pdf',''),author='MiniCDN Group 21')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print(name)
build('MiniCDN-Five-Paper-Research-Review.pdf',markdown_story(root/'docs/academic/research-review.md'))
technical=markdown_story(root/'docs/academic/design-and-srs.md')
technical += [PageBreak(),paragraph('Integration and experimental evidence','Heading1')]
resultfile=root/'docs/academic/results/routing-comparison.json'
if resultfile.exists():
    data=json.loads(resultfile.read_text());rows=data['rows']
    if len(rows)!=36 or any(r['errors'] for r in rows):raise ValueError('Cannot publish incomplete or failed comparison as final evidence')
    technical.append(paragraph('Measurements come from the recorded local Docker trials. Means below average repetitions within each workload/policy; they do not combine unlike workloads. See the CSV and JSONL for individual trials and request timings.'))
    tableRows=[['Workload / policy','Hit %','Origin attempts','P95 mean [range] ms','Errors']]
    for workload in ['uniform','zipf','changing_hot','cold_burst']:
        for policy in ['consistent_hash','round_robin','adaptive']:
            group=[r for r in rows if r['workload']==workload and r['policy']==policy]
            if not group:continue
            mean=lambda key:sum(r[key] for r in group)/len(group)
            tableRows.append([workload+' / '+policy,f"{100*mean('hits')/mean('requests'):.1f}",f"{mean('origin_attempts'):.1f}",f"{mean('p95_ms'):.1f} [{min(r['p95_ms'] for r in group):.1f}-{max(r['p95_ms'] for r in group):.1f}]",str(sum(r['errors'] for r in group))])
    technical += [table(tableRows,[175,50,75,155,40]),Spacer(1,12)]
    technical.append(paragraph('This comparison uses three edges on one machine, 64 KiB body capacity per edge, 256 one-KiB objects, concurrency 16, 768 requests per trial and 20 ms synthetic origin delay. All cache and origin policy settings are shared. Live Grafana aggregates traffic across trials; the trial counters and client trace are the comparison evidence.'))
    technical.append(paragraph('36 trials completed on 10 October 2026: 27,648 requests and zero request/body-validation errors. Seed 2100260; three repetitions; cold caches and no warmup; policy order rotates. P95 values are means of trial percentiles, with minimum and maximum across runs, not pooled request percentiles or confidence intervals.'))
    technical.append(paragraph('Consistent hashing reduced origin work relative to round robin in each tested workload. Round robin had exactly equal request counts on the three healthy edges. Adaptive routing traded some locality for request balance and did not consistently improve P95. The wide latency ranges indicate host variability; these results do not establish a production or regional advantage. Uniform-cache hits were below the proposal target of 85%, so that target has not been generally achieved.'))
else:technical.append(paragraph('Benchmark results are not yet recorded. Do not submit numerical performance claims until the comparison completes.'))
integration=root/'docs/academic/results/integration-check.json'
if integration.exists():
    data=json.loads(integration.read_text())
    technical += [paragraph('Functional integration checks','Heading2'),table([['Check','Result']]+[[r['name'],'PASS' if r['passed'] else 'FAIL'] for r in data['results']],[395,100])]
    technical.append(paragraph('One request after its owning edge was stopped completed in 567 ms. Timing begins after docker stop completes; it is not a distribution of crash detection delays. A separate network-disconnection test verified missed-purge recovery without a process restart. Native Go 1.27 tests and Linux Go 1.21 race tests passed; the coordinated cold-burst test was repeated ten times.'))
technical += [PageBreak()]+markdown_story(root/'docs/academic/submission-plan.md')
build('MiniCDN-Design-and-Phase-IV-Report.pdf',technical)
