import sys,os,subprocess,glob
from PIL import Image,ImageOps
from concurrent.futures import ThreadPoolExecutor
vids=sys.argv[1:]
def do(p):
    out=p.replace('.png','.t3')
    if os.path.exists(out): return
    im=Image.open(p).convert('L'); im=im.resize((im.width*3,im.height*3),Image.LANCZOS); im=ImageOps.autocontrast(ImageOps.invert(im))
    tmp=p.replace('.png','_u3.png'); im.save(tmp)
    t=subprocess.run(['tesseract',tmp,'-','--psm','6'],capture_output=True,text=True).stdout
    open(out,'w').write(t); os.remove(tmp)
fs=[f for v in vids for f in sorted(glob.glob(f'frames/{v}/*.png'))]
with ThreadPoolExecutor(2) as ex: list(ex.map(do,fs))
print('done',len(fs))
