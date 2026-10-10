"""Collect linked primary-source PDFs for private team review and extract text."""
import json, hashlib, urllib.request
from pathlib import Path
from pypdf import PdfReader

root = Path(__file__).resolve().parents[1]
papers = json.loads((root / 'docs/academic/research-papers.json').read_text(encoding='utf-8'))
out = root / 'docs/academic/papers'
out.mkdir(parents=True, exist_ok=True)
for paper in papers:
    file = out / (paper['id'] + '.pdf')
    try:
        if not file.exists():
            request = urllib.request.Request(paper['pdf'], headers={'User-Agent':'MiniCDN academic literature review'})
            data = urllib.request.urlopen(request, timeout=45).read()
            if not data.startswith(b'%PDF'): raise ValueError('Source did not return a PDF')
            file.write_bytes(data)
        reader = PdfReader(file)
        (out / (paper['id']+'.txt')).write_text('\n'.join(page.extract_text() or '' for page in reader.pages), encoding='utf-8')
        print(paper['id'], 'pages',len(reader.pages),'sha256',hashlib.sha256(file.read_bytes()).hexdigest())
    except Exception as error:
        print(paper['id'], 'FAILED', str(error))
