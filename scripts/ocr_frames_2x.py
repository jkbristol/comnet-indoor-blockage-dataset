import sys,os,subprocess,glob
from PIL import Image,ImageOps
from concurrent.futures import ThreadPoolExecutor
def do(p):
    out=p.replace('.png','.txt')
    if os.path.exists(out): return
    im=Image.open(p).convert('L'); im=im.resize((im.width*2,im.height*2),Image.LANCZOS); im=ImageOps.invert(im)
    tmp=p.replace('.png','_u.png'); im.save(tmp)
    t=subprocess.run(['tesseract',tmp,'-','--psm','6'],capture_output=True,text=True).stdout
    open(out,'w').write(t); os.remove(tmp)
fs=sorted(glob.glob('frames/*/*.png')); fs=[f for f in fs if int(os.path.basename(f)[:4])%5==1]
with ThreadPoolExecutor(2) as ex: list(ex.map(do,fs))
print('done',len(fs))
