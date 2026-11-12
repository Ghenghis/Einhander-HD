"""Publish observed engine capability and actual reconstruction dimensions."""
import base64
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

STAGING = Path('C:/github/REMASTER_STAGING')
OUT = STAGING / 'prototypes'
report = STAGING / 'Review.html'
draft = OUT / 'reconstructed-material-draft-v1.png'
with Image.open(draft) as image:
    actual_size = list(image.size)
    buffer = io.BytesIO()
    image.convert('RGB').save(buffer, format='WEBP', quality=97)
    embedded = 'data:image/webp;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')

capability = {
    'method': 'Compiled current project hd_texture_pack.cpp with a standalone hidden-window OpenGL upload probe',
    'gpu': 'NVIDIA GeForce RTX 3090 Ti/PCIe/SSE2',
    'opengl': '4.6.0 NVIDIA 621.14', 'GL_MAX_TEXTURE_SIZE': 32768,
    'renderer_decode_budget_mib': 256,
    'checks': [
        {'size':[1024,1024], 'rgba8_mib':4, 'status':'PASS', 'GL_error':0, 'input':'existing texture prototype'},
        {'size':[2048,2048], 'rgba8_mib':16, 'status':'PASS', 'GL_error':0, 'input':'existing texture prototype'},
        {'size':[4096,4096], 'rgba8_mib':64, 'status':'PASS', 'GL_error':0, 'input':'existing texture prototype'},
        {'size':[8192,8192], 'rgba8_mib':256, 'status':'PASS', 'GL_error':0, 'input':'synthetic solid-color capability fixture'},
    ],
    'probe_exit_code':0,
    'scope':'Actual project PNG loader and GPU upload. Not guest-game draw matching, gameplay, frame time, or full-pack residency.',
    'conclusion':'4096 is supported by the tested loader/upload path and is not a hard engine size ceiling.',
}
(OUT / 'engine-texture-capability.json').write_text(json.dumps(capability,indent=2)+'\n',encoding='utf-8')
review = {
    'source':'C:/github/Einhander/remaster-audit/previews/view-0.png',
    'source_role':'stock-source layout reference, 64x64',
    'output':str(draft), 'actual_native_size':actual_size,
    'requested_native_size':[4096,4096], 'tool':'built-in image_gen',
    'is_native_4096':False, 'installed_in_game':False,
    'review':'More visible material detail, but shifted/reinterpreted contours and panel details. UV registration and faithful-layout checks not passed.',
    'status':'artwork experiment; not an accepted engine replacement',
    'prompt':'C:/github/REMASTER_STAGING/prototypes/reconstruction-prompt-v1.txt',
}
(OUT / 'reconstructed-material-review-v1.json').write_text(json.dumps(review,indent=2)+'\n',encoding='utf-8')

text=report.read_text(encoding='utf-8')
match=re.search(r'const media = (\{.*?\});\s*const byId',text,re.S)
if not match:raise RuntimeError('Expected media block missing')
media=json.loads(match.group(1));media['reconstructedDraft']=embedded
text=text[:match.start(1)]+json.dumps(media)+text[match.end(1):]
section='''<section id="engine-capability-proof">
    <h2>Verified engine support, and a new artwork experiment</h2>
    <p>The actual project PNG loader and your 3090 Ti successfully uploaded 1024, 2048, 4096 and a synthetic 8192-square texture. 4096 is not a hard engine ceiling. This does not verify gameplay draw matching, frame rate or a whole pack.</p>
    <p>The GPU reports a maximum texture edge of 32768. The live HD renderer configures a 256 MiB decoded-image cache. A 4096 RGBA8 image uses 64 MiB; a single 8192 image uses all 256 MiB. These are constraints to manage, not quality targets.</p>
    <div class="ceiling-grid">
      <figure><h3>Stock reference</h3><img id="engineStockPreview" class="source" style="width:100%;aspect-ratio:1" alt="Stock-source 64 pixel atlas"><figcaption>64 x 64 source. Original layout and colors.</figcaption></figure>
      <figure><h3>UltraSharp restoration</h3><img id="engineUltraPreview" style="width:100%;aspect-ratio:1" alt="Earlier UltraSharp 1024 restoration"><figcaption>1024 x 1024. Existing source-based upscale.</figcaption></figure>
      <figure><h3>Artwork reconstruction draft</h3><img id="engineDraftPreview" style="width:100%;aspect-ratio:1" alt="New image-generated material reconstruction experiment"><figcaption>Actual generated size: 1254 x 1254, not 4096. Adds material detail but changes some contours; not accepted for installation.</figcaption></figure>
    </div>
    <p class="note">This demonstrates the difference between creating more artwork detail and only increasing dimensions. The reconstruction is not a native-4K master and has not passed faithful UV/layout checks. It remains a draft. A complete, visibly improved in-game 4K result has not been demonstrated yet.</p>
    <p><a href="prototypes/engine-texture-capability.json">Loader/GPU probe results</a> · <a href="prototypes/reconstructed-material-draft-v1.png">Full reconstruction draft</a> · <a href="prototypes/reconstructed-material-review-v1.json">Actual dimensions and review</a> · <a href="prototypes/reconstruction-prompt-v1.txt">Image-tool prompt</a></p>
  </section>
  '''
if 'id="engine-capability-proof"' not in text:
    text=text.replace('<h2>The visible improvement: stock versus UltraSharp</h2>',section+'<h2>The visible improvement: stock versus UltraSharp</h2>',1)
    text=text.replace('</body>', '''<script>
  document.getElementById('engineStockPreview').src=media.original;
  document.getElementById('engineUltraPreview').src=media.ultraFull1024;
  document.getElementById('engineDraftPreview').src=media.reconstructedDraft;
</script>
</body>''',1)
report.write_text(text,encoding='utf-8')

font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',23)
small=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',17)
board=Image.new('RGB',(1536,605),(18,23,29));draw=ImageDraw.Draw(board)
samples=[
    ('Stock: 64 x 64',Path('C:/github/Einhander/remaster-audit/previews/view-0.png'),Image.Resampling.NEAREST),
    ('UltraSharp: 1024 x 1024',OUT/'4x-UltraSharp/resolution-ceiling/preview-1024.png',Image.Resampling.LANCZOS),
    ('Reconstruction draft: 1254 x 1254',draft,Image.Resampling.LANCZOS),
]
for index,(label,path,filtering) in enumerate(samples):
    x=index*512;draw.text((x+10,10),label,font=font,fill=(230,237,243))
    with Image.open(path) as image:
        image=image.convert('RGBA').resize((496,496),filtering)
        board.paste(image,(x+8,55),image)
    footer='Layout fidelity still needs correction' if index==2 else 'Original visual identity is the reference'
    draw.text((x+10,562),footer,font=small,fill=(165,175,188))
board.save(OUT/'reconstruction-comparison-v1.png')
print(json.dumps({'draft_actual_size':actual_size,'report_bytes':report.stat().st_size,'engine_probe':'1024/2048/4096 and synthetic 8192 PASS; gameplay not tested'},indent=2))
