"""Export the existing article text to WordPress HTML without running its PDF build.

Run: python3 paper/v2/build/build_wordpress.py
Outputs a paste-ready body, standalone preview, four figures and upload instructions.
"""
import ast
import html
import json
import re
import shutil
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'build_article.py'
OUT = HERE.parent / 'wordpress'


def inline(text):
    text = re.sub(r'<link href="([^"]+)" color="[^"]+">', r'<a href="\1">', text)
    text = text.replace('</link>', '</a>').replace('<u>', '').replace('</u>', '')
    return text.replace('<b>', '').replace('</b>', '').replace('<i>', '<em>').replace('</i>', '</em>')


def P(text, style='body'):
    tag = {'h1': 'h1', 'h2': 'h2'}.get(style, 'p')
    return (tag, inline(text))


def B(items):
    return [('ul', [inline(item) for item in items])]


def L(url, text=None):
    return f'<a href="{html.escape(url, quote=True)}">{html.escape(text or url)}</a>'


def fig(path, ratio, caption, sc=1.0):
    return ('figure', (Path(path), inline(caption)))


def collect():
    # Only evaluate the article's content-building statements, using HTML stubs.
    # No imports, filesystem setup, PDF rendering or font discovery from the source run.
    tree = ast.parse(SOURCE.read_text())
    chosen = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {'APR', 'ZEN', 'GH', 'rows', 's'} for t in node.targets):
            chosen.append(node)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == 's':
            chosen.append(node)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == 's':
            chosen.append(node)
    env = {name: name for name in ('body', 'h1', 'h2', 'note', 'meta', 'small', 'cap')}
    env.update(P=P, B=B, L=L, fig=fig, FIG=HERE / 'figures', t=('table', None),
               Spacer=lambda *a: ('space', None), HRFlowable=lambda **kw: ('hr', None),
               colors=type('Colours', (), {'HexColor': staticmethod(lambda s: s)}))
    exec(compile(ast.Module(body=chosen, type_ignores=[]), str(SOURCE), 'exec'), env)
    return env['s'], env['rows']


def main():
    blocks, rows = collect()
    OUT.mkdir(exist_ok=True)
    (OUT / 'figures').mkdir(exist_ok=True)
    title = next(text for kind, text in blocks if kind == 'h1')
    alt = {
        'v2_fig4_meals.png': 'Carbohydrate estimates in grams for each meal and model, with reference values and within-model spread.',
        'v2_fig5_violin.png': 'Distributions of estimates relative to each model’s typical answer, comparing April and September sampling.',
        'fig3_risk_by_k.png': 'Variability and reference-based overestimation as the number of calls combined increases from one to twenty.',
        'fig4_overdose_by_photo.png': 'Per-photograph overestimation rates for single calls and twenty-call medians, plotted against model bias.',
    }
    parts = []
    figures = []
    for kind, value in blocks:
        if kind in {'h1', 'space'}:
            continue
        if kind == 'ul':
            parts.append('<ul>\n' + '\n'.join(f'  <li>{item}</li>' for item in value) + '\n</ul>')
        elif kind == 'figure':
            source, caption = value
            filename = source.name
            # Correct an inherited self-reference in the Figure 2 caption.
            caption = caption.replace('matching Figure 2.', 'matching Figure 1.')
            assert filename in alt
            shutil.copy2(source, OUT / 'figures' / filename)
            figures.append(filename)
            parts.append(f'<figure class="wp-block-image">\n  <img src="figures/{filename}" alt="{html.escape(alt[filename], quote=True)}" loading="lazy" />\n  <figcaption>{caption}</figcaption>\n</figure>')
        elif kind == 'table':
            head = ''.join(f'<th scope="col">{html.escape(c)}</th>' for c in rows[0])
            body = '\n'.join('<tr><th scope="row">' + html.escape(r[0]) + '</th>' + ''.join(f'<td>{html.escape(c)}</td>' for c in r[1:]) + '</tr>' for r in rows[1:])
            parts.append(f'<figure class="wp-block-table"><table>\n<caption>US dollars at September 2026 batch prices. Annual costs assume three meals a day.</caption>\n<thead><tr>{head}</tr></thead>\n<tbody>\n{body}\n</tbody></table></figure>')
        elif kind == 'hr':
            parts.append('<hr />')
        else:
            parts.append(f'<{kind}>{value}</{kind}>')
    body = '\n\n'.join(parts) + '\n'
    assert len(figures) == 4 and len(set(figures)) == 4
    assert '<link ' not in body and '<u>' not in body
    (OUT / 'article.html').write_text(body)
    (OUT / 'title.txt').write_text(title + '\n')
    css = '''body{margin:0;background:#f6f7f8;color:#222;font:19px/1.65 Georgia,serif}article{max-width:900px;margin:0 auto;padding:40px 24px;background:white}h1,h2{font-family:system-ui,sans-serif;line-height:1.2}h1{font-size:2.1em}h2{margin-top:1.8em;color:#1f5f8b;font-size:1.35em}a{color:#195f8d;overflow-wrap:anywhere}figure{margin:2em 0}img{max-width:100%;height:auto}figcaption,caption{font-size:.85em;line-height:1.5;color:#444;margin-top:12px}table{border-collapse:collapse;width:100%;font:15px/1.5 system-ui,sans-serif}th,td{border:1px solid #c8d4de;padding:10px;text-align:left}thead{background:#eef4f8}caption{text-align:left;caption-side:bottom}.wp-block-table{overflow-x:auto}@media(max-width:600px){body{font-size:17px}article{padding:24px 16px}h1{font-size:1.7em}th,td{padding:6px}}'''
    (OUT / 'preview.html').write_text(f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title><style>{css}</style></head><body><article><h1>{title}</h1>\n{body}</article></body></html>\n')
    (OUT / 'README.txt').write_text('''September 2026 Diabettech article: WordPress package

1. Open preview.html locally to review the complete article and four figures.
2. Create a WordPress draft. Copy title.txt into the post title field.
3. Upload the four PNG files in figures/ to the WordPress Media Library.
4. Copy article.html into a local text editor and replace each figures/FILENAME.png
   image source with that image's full WordPress Media Library URL.
5. Add a Custom HTML block to the WordPress post and paste the amended article.html.
   The title is deliberately omitted from the body to avoid a duplicate heading.
6. Preview the post on desktop and mobile. Check all four images, the cost table
   and links before publishing. Local image paths will not work on the live site.

article.html is body-only HTML; preview.html includes styles for local review.
No publication, WordPress login or media upload is performed by this package.
The article links to the Zenodo concept DOI, which resolves to the latest version.
Affiliation: Diabettech Ltd. The linked preprint licence is CC BY 4.0.

Source: ../build/build_article.py. Rebuild with:
  python3 paper/v2/build/build_wordpress.py
Article wording and numbers are preserved. The Figure 2 caption's self-reference
was corrected to Figure 1. The HTML cost table adds an explicit currency caption.
''')
    (OUT / 'manifest.json').write_text(json.dumps({'source': 'paper/v2/build/build_article.py', 'title': title, 'figures': figures, 'content_blocks': len(blocks), 'zenodo': 'https://doi.org/10.5281/zenodo.22879139'}, indent=2) + '\n')
    target = OUT.parent / 'deliverables' / 'Diabettech_September_2026_WordPress.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(OUT.rglob('*')):
            if path.is_file():
                archive.write(path, Path('diabettech_september_2026_wordpress') / path.relative_to(OUT))
    print(f'Created {OUT}: {len(figures)} figures, {len(blocks)} source blocks')
    print(f'Created {target}')


if __name__ == '__main__':
    main()
