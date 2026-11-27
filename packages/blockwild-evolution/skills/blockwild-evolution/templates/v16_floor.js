// Material for the real 3D walkable plaza, derived from stone-only pixels of
// the owner-provided image; each atlas cell is a unique source-textured stone.
const BW16StoneImage=new Image();
BW16StoneImage.decoding='async';
BW16StoneImage.onload=()=>{if(ROYAL_ART)ROYAL_ART.base=null;};
BW16StoneImage.src=BW16_STONE_ALBEDO;
function bw16DrawFloorTexture(g,W,H,U,center){
 if(!BW16StoneImage.complete||!BW16StoneImage.naturalWidth)return;
 const P=(x,z)=>royalP(x,z,0,center,U,W,H);
 const p=P(-30,-30),px=P(94,-30),pz=P(-30,94);
 const w=BW16StoneImage.naturalWidth,h=BW16StoneImage.naturalHeight;
 g.save();
 g.globalAlpha=.72;
 g.imageSmoothingEnabled=true;
 g.imageSmoothingQuality='high';
 g.setTransform((px[0]-p[0])/w,(px[1]-p[1])/w,
                (pz[0]-p[0])/h,(pz[1]-p[1])/h,p[0],p[1]);
 g.drawImage(BW16StoneImage,0,0);
 g.restore();
}
