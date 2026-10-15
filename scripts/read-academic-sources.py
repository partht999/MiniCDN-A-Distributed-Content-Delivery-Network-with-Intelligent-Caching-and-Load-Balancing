from pathlib import Path
import json
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

source = Path(r'C:\Users\jayni\OneDrive\Desktop\spit sem 5\mini project')
out = Path('docs/academic/source-extracts')
out.mkdir(parents=True, exist_ok=True)
for path in sorted(source.glob('*.docx')):
    doc = Document(path)
    lines = []
    for item in doc.element.body:
        if item.tag.endswith('}p'):
            text = Paragraph(item, doc).text
            if text.strip(): lines.append(text)
        elif item.tag.endswith('}tbl'):
            for row in Table(item, doc).rows:
                lines.append(' | '.join(cell.text.replace('\n',' / ') for cell in row.cells))
    text = '\n'.join(lines)
    (out / (path.stem + '.txt')).write_text(text, encoding='utf-8')
    print('\nFILE:', path.name, '\n', text)
for path in source.glob('Group*.pdf'):
    pdf = PdfReader(path)
    text = '\n'.join(f'PAGE {i+1}\n{page.extract_text()}' for i, page in enumerate(pdf.pages))
    (out / (path.stem + '.txt')).write_text(text, encoding='utf-8')
    print('\nFILE:',path.name,'\n',text)
