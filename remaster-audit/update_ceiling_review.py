"""Add the generated size comparison to the existing review without rerunning models."""
import base64
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

STAGING = Path('C:/github/REMASTER_STAGING')
TOOLS = Path(__file__).resolve().parent
OUT = STAGING / 'prototypes/4x-UltraSharp/resolution-ceiling'
report = STAGING / 'Review.html'
text = report.read_text(encoding='utf-8')
match = re.search(r'const media = (\{.*?\});\s*const byId', text, re.S)
if not match:
    raise RuntimeError('Expected review media block missing; do not overwrite an unfamiliar report')
media = json.loads(match.group(1))
for size in (1024, 2048, 4096):
    with Image.open(OUT / f'preview-{size}.png') as image:
        buffer = io.BytesIO()
        image.convert('RGB').save(buffer, format='WEBP', quality=97, method=4)
        media[f'ultraFull{size}'] = 'data:image/webp;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')
text = text[:match.start(1)] + json.dumps(media) + text[match.end(1):]
section = (TOOLS / 'ceiling-section.html').read_text(encoding='utf-8')
if '<section id="ultrasharp-ceiling">' not in text:
    text = text.replace('  <h2>Stock-source texture proof</h2>', section + '\n  <h2>Earlier stock-source texture proof</h2>', 1)
    text = text.replace('  <div class="facts">', '  <p><a href="#ultrasharp-ceiling">Jump to the new UltraSharp size comparison</a></p>\n  <div class="facts">', 1)
    text = text.replace('</style>', '''
    .ceiling-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}
    .ceiling-viewport{aspect-ratio:1;overflow:hidden;background:var(--panel)}
    .ceiling-viewport img{width:100%;height:100%;object-fit:contain;transform:scale(1);transform-origin:100% 16.666667%}
    .ceiling-grid h3{font-size:20px;margin:0 0 10px}.ceiling-grid p{font-size:14px}
    @media(max-width:700px){.ceiling-grid{grid-template-columns:1fr}}
  </style>''', 1)
    text = text.replace('</body>', '''<script>
  const ceilingImages = [1024, 2048, 4096].map(size => {
    const image = document.getElementById('ceiling' + size);
    image.src = media['ultraFull' + size];
    return image;
  });
  document.getElementById('ceilingZoom').addEventListener('change', event => {
    const zoom = Number(event.target.value);
    ceilingImages.forEach(image => { image.style.transform = `scale(${zoom})`; });
    document.getElementById('ceilingStatus').textContent = zoom === 1 ? 'Whole texture, equal display size.' : `All three show the same source area at ${zoom}× magnification.`;
  });
</script>
</body>''', 1)
    text = text.replace('<option value="real">RealESRGAN 16×</option><option value="ultra">UltraSharp 16×</option>', '<option value="real">RealESRGAN 16×</option><option value="ultra" selected>UltraSharp 16×</option>', 1)
    text = text.replace("byId('candidate').src = media.real;", "byId('candidate').src = media.ultra;", 1)
report.write_text(text, encoding='utf-8')

# Deliver one directly viewable comparison as well as the interactive page.
try:
    heading = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 25)
    caption = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 19)
except OSError:
    heading = caption = ImageFont.load_default()
board = Image.new('RGB', (1536, 1130), (18, 23, 29))
draw = ImageDraw.Draw(board)
draw.text((18, 10), 'UltraSharp — same stock source, same crop', font=heading, fill=(230, 237, 243))
for col, size in enumerate((1024, 2048, 4096)):
    with Image.open(OUT / f'preview-{size}.png') as image:
        x = col * 512
        draw.text((x + 16, 53), f'{size} × {size}', font=heading, fill=(230, 237, 243))
        full = image.convert('RGB').resize((496, 496), Image.Resampling.LANCZOS)
        board.paste(full, (x + 8, 94))
        # All three crops span the same populated metal panel, not empty atlas space.
        scale = size // 64
        detail = image.crop((48*scale, 8*scale, 64*scale, 24*scale)).convert('RGB')
        detail = detail.resize((496, 496), Image.Resampling.LANCZOS)
        board.paste(detail, (x + 8, 620))
        draw.text((x + 16, 591), 'Same detail enlarged', font=caption, fill=(165, 175, 188))
board.save(OUT / 'comparison.png')
print(json.dumps({'review_bytes': report.stat().st_size,
                  'full_resolution_variants': [1024,2048,4096],
                  'comparison': str(OUT/'comparison.png')}, indent=2))
