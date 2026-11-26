from PIL import Image, ImageDraw, ImageFilter
import numpy as np, json, base64, random, math, io
from pathlib import Path

OUT=Path('/mnt/data/bw12_assets.json')
N=48; H=64
PALETTE={
1:(206,187,168),2:(244,224,190),3:(164,157,148),4:(222,179,92),5:(251,208,98),6:(41,85,122),7:(94,57,39),
8:(35,91,52),9:(58,126,59),10:(80,151,69),11:(119,177,74),12:(156,195,91),13:(199,221,139),
14:(247,232,185),15:(255,254,234),16:(240,193,82),17:(194,115,144),18:(245,167,171),19:(104,164,201),
20:(64,117,128),21:(36,103,111),22:(20,69,87),23:(28,39,61),24:(220,184,112),25:(246,211,146),
26:(164,109,57),27:(107,71,50),28:(73,46,40),29:(250,203,122),30:(224,177,82),
31:(226,199,146),32:(245,209,157),33:(195,149,93),34:(93,46,40),35:(56,34,31),
36:(223,170,131),37:(122,77,54),38:(243,222,173),39:(189,126,105),40:(234,183,120),
41:(249,242,206),42:(52,127,137),43:(89,168,164),44:(241,233,217),45:(130,85,64),
46:(43,61,49),47:(227,166,82),48:(145,102,71),49:(67,76,76),50:(240,150,60),
}
rng=np.random.default_rng(71891)
YY,ZZ,XX=np.mgrid[0:H,0:N,0:N]


def make_vol():return np.zeros((H,N,N),dtype=np.uint8)
def ell(v,c,r,mat,mode='replace'):
    x,y,z=c;rx,ry,rz=r
    mask=((XX-x)/rx)**2+((YY-y)/ry)**2+((ZZ-z)/rz)**2<=1
    if mode=='empty':v[mask]=0
    else:v[mask]=mat
    return mask

def block(v,x0,x1,y0,y1,z0,z1,mat):v[max(0,y0):min(H,y1),max(0,z0):min(N,z1),max(0,x0):min(N,x1)]=mat

def tree(variant=0):
    rr=np.random.default_rng(791+variant);v=make_vol()
    # Branching trunk and root flare, actual connected mass.
    for y in range(3,40):
        cx=24+round(math.sin(y*.15+variant)*.7);cz=24+round(math.sin(y*.23)*.4)
        r=3.4 if y<13 else 2.5
        m=((XX[y]-cx)**2+(ZZ[y]-cz)**2<r*r)
        v[y][m]=np.where(rr.random((N,N))[m]>.37,26,27)
    ell(v,(24,3,24),(5,4,5),27)
    # Branches connect canopy lobes; organic irregular silhouette.
    for k,(ax,az,yy) in enumerate([(-11,0,37),(9,-8,40),(8,9,44),(-5,10,43),(-1,-11,48)]):
        for frac in np.linspace(.1,1,16):
            x=round(24+ax*frac);z=round(24+az*frac);y=round(30+(yy-30)*frac)
            ell(v,(x,y,z),(1.7,1.8,1.7),26)
    lobes=[(-9,0,42,10,8,11),(10,1,47,12,8,10),(0,-9,49,11,10,10),(-5,9,51,11,9,11),(7,-8,54,9,7,9),(-12,-9,52,9,7,8),(11,10,52,8,6,9),(0,4,58,12,6,10)]
    for ax,az,yy,rx,ry,rz in lobes:
        mat=int(rr.integers(8,12));mask=ell(v,(24+ax,yy,24+az),(rx,ry,rz),mat)
        jitter=rr.random(v.shape)
        v[mask & (jitter>.49)]=9
        v[mask & (jitter>.83)]=11
        v[mask & (jitter>.96)]=12
    # Sparse highlights and flower petals on top-facing canopy cells.
    top=np.zeros_like(v,bool);top[:-1]= (v[:-1]>=8)&(v[:-1]<=13)&(v[1:]==0)
    visible=np.where(top)
    if len(visible[0]):
        sel=rr.choice(len(visible[0]),size=min(200,len(visible[0])//13),replace=False)
        for i in sel:
            y,z,x=[int(arr[i]) for arr in visible];v[y,z,x]=rr.choice([12,13,14,15,17],p=[.35,.38,.20,.04,.03]);
    return v

def column(lantern=True):
    v=make_vol()
    for y in range(0,9):block(v,17-(y<3),31+(y<3),y,y+1,17-(y<3),31+(y<3),1 if y%4 else 2)
    for y in range(9,46):
        block(v,20,28,y,y+1,20,28,1 if y%8 else 3)
        if y in (13,20,27,35):block(v,19,29,y,y+1,19,29,2)
    block(v,17,31,46,49,17,31,2);block(v,19,29,49,52,19,29,4);block(v,21,27,52,54,21,27,5)
    if lantern:
        # Gold lamp on front left, blue textile banner with golden edging.
        block(v,11,17,32,35,19,24,4);block(v,11,15,23,33,19,23,5)
        block(v,12,14,25,31,20,22,50)
        block(v,22,26,15,39,29,30,6)
        for y in range(16,39):block(v,22,23,y,y+1,30,31,5);block(v,25,26,y,y+1,30,31,5)
        block(v,22,26,38,40,29,31,5)
    return v

def arch():
    v=make_vol()
    for xx in [(5,12),(36,43)]:
        block(v,xx[0]-2,xx[1]+2,0,6,17,31,1)
        block(v,xx[0],xx[1],6,49,19,29,1)
        block(v,xx[0]-1,xx[1]+1,49,52,17,31,2)
    block(v,6,42,50,56,18,29,1)
    block(v,5,43,56,58,17,30,2)
    block(v,8,40,58,60,20,27,4)
    for x in range(10,40,6):block(v,x,x+2,52,56,17,19,3)
    return v

def flowerbed():
    v=make_vol();rr=np.random.default_rng(27)
    block(v,6,42,0,5,7,40,1);block(v,5,43,5,8,6,41,2)
    block(v,9,39,8,10,9,38,27)
    # Don't cover flowers with border solid top.
    for i in range(44):
        x=int(rr.integers(11,38));z=int(rr.integers(11,37));y=int(rr.integers(12,17));
        ell(v,(x,y,z),(rr.integers(3,5),rr.integers(4,7),rr.integers(3,5)),int(rr.choice([8,9,10,11])))
        ell(v,(x,y+4,z),(1.5,1.5,1.5),int(rr.choice([15,17,18,16])))
        if i%3==0:ell(v,(x,y+4,z),(1,1,1),5)
    return v

def bush():
    v=make_vol();rr=np.random.default_rng(298)
    for i in range(10):
        x=int(rr.integers(17,32));z=int(rr.integers(17,31));y=int(rr.integers(5,13))
        ell(v,(x,y,z),(rr.integers(5,8),rr.integers(5,8),rr.integers(5,8)),int(rr.choice([8,9,10,11])))
    for i in range(24):
        x=int(rr.integers(15,35));z=int(rr.integers(14,34));y=int(rr.integers(8,18))
        if v[y,z,x]: v[y,z,x]=int(rr.choice([12,13,14,15,18]));
    return v

def npc(hair='blond',pose=0,orient='front',seed=1):
    rr=np.random.default_rng(seed);v=make_vol()
    x0=z0=24
    # legs and boots: different independently authored 3D poses, same anatomy.
    moving=pose in [1,2,3]
    for side in [-1,1]:
        swing=side*(2 if pose==1 else -2 if pose==2 else 0)
        legx=round(x0+side*3+swing)
        block(v,legx-2,legx+2,2,12,21,27,22)
        block(v,legx-3,legx+3,0,4,20,30,28)
    # coat body broad with golden trim
    ell(v,(x0,16,z0),(7,9,6),42 if seed%2 else 21)
    block(v,18,30,11,14,20,29,29);block(v,19,29,19,20,19,30,30)
    # shoulders, walking arms have alternating positions
    for side in [-1,1]:
        armx=round(24+side*8)
        armDy=(2 if moving else 0)*side*(1 if pose==1 else -1)
        ell(v,(armx,17+armDy,24),(3,7,3),42)
        ell(v,(armx,12+armDy,24),(2.2,3.3,2.2),36)
    # collar and neck
    block(v,21,27,23,27,21,27,25)
    ell(v,(24,29,24),(6.4,7,6),36)
    # hair cap: dark-haired hero and blond citizens preserve distinct appearances
    mat=34 if hair=='dark' else 29
    mask=ell(v,(24,34,24),(6.6,5.0,6.5),mat)
    # retain face by overriding hair at front
    ell(v,(24,29,24),(6.2,5.6,5.8),36)
    for x in (19,22,26,29):
        ell(v,(x,36+(x%3),24+((x%2)*2-1)),(3,3,3),mat)
    if orient=='back':
        block(v,20,28,26,32,29,31,mat)
    elif orient=='front':
        # Eyes toward screen (front z negative, source +z toward camera in baked rendering)
        for x in (21,27):
            v[30:32,29:31,x]=23
        v[28,30,24]=39
    elif orient=='left':
        v[30:32,24:26,29:31]=23
    elif orient=='right':
        v[30:32,24:26,18:20]=23
    return v

def render_volume(v):
    # Actual transparent horizontal RGBA volume cross-sections. Each y slice is
    # composited at a y-dependent elevation; no 2D silhouette extrusion.
    img=Image.new('RGBA',(320,302),(0,0,0,0));d=ImageDraw.Draw(img,'RGBA')
    P=PALETTE;dx=1.92;dz=.91;lift=2.57;originX=160;originY=256
    filled=v!=0
    coords=np.argwhere(filled)
    # Far-to-near ordering within each ascending slice.
    if len(coords)>0:
      order=np.lexsort((coords[:,2],coords[:,1], coords[:,2]+coords[:,1],coords[:,0]))
      coords=coords[order]
    for y,z,x in coords:
      y=int(y);z=int(z);x=int(x)
      color=P[int(v[y,z,x])]
      sx=originX+(x-z)*dx; sy=originY+(x+z-47)*dz-y*lift
      # Only exposed voxels in the slice, or top rims, contribute visible facets.
      top=y>=H-1 or not filled[y+1,z,x]
      side1=x>=N-1 or not filled[y,z,x+1]
      side2=z>=N-1 or not filled[y,z+1,x]
      if not (top or side1 or side2):continue
      # Lambertian brightness with warm northeast key and cool occlusion.
      jitter=1.0+.034*math.sin(x*1.7+z*2.3+y*.77)
      def col(f,a=255):return tuple(min(255,max(0,int(q*f*jitter))) for q in color)+(a,)
      if side1:
        d.polygon([(sx+dx,sy),(sx,sy+dz),(sx,sy+dz+lift),(sx+dx,sy+lift)],fill=col(.70))
      if side2:
        d.polygon([(sx,sy+dz),(sx-dx,sy),(sx-dx,sy+lift),(sx,sy+dz+lift)],fill=col(.85))
      if top:
        d.polygon([(sx,sy-dz),(sx+dx,sy),(sx,sy+dz),(sx-dx,sy)],fill=col(1.10))
    bbox=img.getbbox()
    if not bbox:return None
    margin=4;left=max(0,bbox[0]-margin);top=max(0,bbox[1]-margin);right=min(320,bbox[2]+margin);bottom=min(302,bbox[3]+margin)
    img=img.crop((left,top,right,bottom))
    # Subtle antialiasing smoothes jagged facets without softening the material texture.
    # Keep alpha intact and preserve original colored volume pixels.
    buf=io.BytesIO();img.save(buf,'PNG',optimize=True)
    return {'uri':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode(), 'base':[160-left,256-top], 'size':list(img.size), 'layers':int(np.count_nonzero(np.any(v!=0,axis=(1,2))))}

models={
 'tree0':tree(0),'tree1':tree(1),'tree2':tree(2),
 'pillar':column(True),'column':column(False),'arch':arch(),
 'flowers':flowerbed(),'bush':bush(),
}
for face in ('front','back','left','right'):
 for phase in range(3):
  models[f'hero_{face}_{phase}']=npc('dark',phase,face,1)
  models[f'citizen_{face}_{phase}']=npc('blond',phase,face,4)
export={}
for name,volume in models.items():
 spr=render_volume(volume)
 if spr: export[name]=spr
OUT.write_text(json.dumps(export,separators=(',',':')))
print('rendered',len(export),'assets','total json KiB',round(OUT.stat().st_size/1024),'avg layers',round(np.mean([x['layers'] for x in export.values()]),1))
for key in ['tree0','pillar','hero_front_0','flowers']:
 z=export[key];print(key,z['size'],z['base'],z['layers'])
 raw=base64.b64decode(z['uri'].split(',')[1]);Path('/mnt/data/bw12_'+key+'.png').write_bytes(raw)
