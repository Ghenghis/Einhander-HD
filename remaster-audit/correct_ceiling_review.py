"""Correct the visual conclusion without rerunning any image model."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

STAGING = Path('C:/github/REMASTER_STAGING')
OUT = STAGING / 'prototypes/4x-UltraSharp/resolution-ceiling'
report = STAGING / 'Review.html'
text = report.read_text(encoding='utf-8')
heading = '<h2>UltraSharp side by side: 1024, 2048 and 4096</h2>'
replacement = '''<h2>The visible improvement: stock versus UltraSharp</h2>
    <p>The larger three-way comparison did not demonstrate a meaningful visible gain beyond 1024 for this source. Keep the 1024 candidate for this tile. The useful improvement is the restoration from the 64-pixel stock source.</p>
    <div class="split">
      <figure><h3>Stock source: 64 x 64</h3><img id="stockSourceCompare" class="source" style="width:100%;aspect-ratio:1" alt="Original stock-source backup at 64 by 64 pixels, enlarged for comparison"><figcaption>Same source, enlarged with nearest-neighbor sampling for display.</figcaption></figure>
      <figure><h3>UltraSharp: 1024 x 1024</h3><img id="stockUltraCompare" style="width:100%;aspect-ratio:1" alt="The existing UltraSharp 1024 by 1024 restoration"><figcaption>Existing restored candidate. No new generation was performed.</figcaption></figure>
    </div>
    <p class="note">1024, 2048 and 4096 looked effectively identical at the reviewed sizes. The extra pass enlarged an already restored image; it did not establish more useful detail. The previous recommendation to prefer 2048 for this sample was unsupported. This result does not establish the best asset sizes for other textures or the game's render resolution.</p>
    <h2>Enlargement test: no meaningful visible gain shown</h2>'''
if 'id="stockSourceCompare"' not in text:
    if heading not in text:
        raise RuntimeError('Expected enlargement section missing')
    text = text.replace(heading, replacement, 1)
    text = text.replace('</body>', '''<script>
  document.getElementById('stockSourceCompare').src = media.original;
  document.getElementById('stockUltraCompare').src = media.ultraFull1024;
</script>
</body>''', 1)
    text = text.replace('Jump to the new UltraSharp size comparison', 'View the stock-to-UltraSharp improvement and enlargement result', 1)
report.write_text(text, encoding='utf-8')

manifest_path = OUT / 'manifest.json'
manifest = json.loads(manifest_path.read_text())
manifest['visual_review'] = {
    'finding': 'No meaningful visible gain demonstrated between 1024, 2048 and 4096 at reviewed display sizes.',
    'user_feedback': 'All three look identical.',
    'decision_for_this_tile': 'Keep existing 1024 candidate; do not enlarge further.',
    'correction': 'Earlier recommendation to prefer 2048 was unsupported.',
    'in_game_result': 'not tested; this review does not establish the game render-resolution ceiling',
}
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

# Reuse the already-authored previews; this is a presentation-only comparison.
native = Path('C:/github/Einhander/remaster-audit/previews/view-0.png')
restored = OUT / 'preview-1024.png'
board = Image.new('RGB', (1280, 710), (18, 23, 29))
draw = ImageDraw.Draw(board)
font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 25)
for index, (path, label, filtering) in enumerate([
    (native, 'Stock source: 64 x 64', Image.Resampling.NEAREST),
    (restored, 'UltraSharp: 1024 x 1024', Image.Resampling.LANCZOS),
]):
    x = index * 640
    draw.text((x + 16, 12), label, font=font, fill=(230, 237, 243))
    with Image.open(path) as image:
        image = image.convert('RGBA').resize((624, 624), filtering)
        board.paste(image, (x + 8, 58), image)
board.save(OUT / 'stock-vs-ultrasharp.png')
print('Corrected review and manifest; comparison reused existing files; no model inference run.')
