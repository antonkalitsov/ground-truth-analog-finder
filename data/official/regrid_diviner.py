import numpy as np
f="data/raw/diviner/dlre_prp_south.tab"
m=np.memmap(f,dtype='S1',mode='r',offset=210).reshape(-1,210)
col=lambda a,b: np.char.strip(m[:,a-1:a-1+b].copy().view('S%d'%b).ravel()).astype(float)
lon=col(127,15); lat=col(144,15); tavg=col(178,8); tmax=col(188,8); ice=col(198,11)
for name,sel in [('neg1',ice==-1),('zero',ice==0),('small',(ice>0)&(ice<0.1)),('deep',ice>1),('inv',ice==-999)]:
    print(name, sel.sum(), 'tavg p5/50/95', np.percentile(tavg[sel],[5,50,95]).round(1), 'tmax', np.percentile(tmax[sel],[5,50,95]).round(1), 'lat p50', np.median(lat[sel]).round(2))
R=1737400.0; LEFT=-457440.0; TOP=457440.0; P=476; MPP=914880.0/P
rho=2*R*np.tan(np.radians(90+lat)/2); x=rho*np.sin(np.radians(lon)); y=rho*np.cos(np.radians(lon))
j=np.floor((x-LEFT)/MPP).astype(int); i=np.floor((TOP-y)/MPP).astype(int)
ok=(i>=0)&(j>=0)&(i<P)&(j<P)&(tavg>0); idx=(i*P+j)[ok]
B=lambda w=None: np.bincount(idx, w, P*P).reshape(P,P).astype(np.float32)
iv=ice[ok]
out=dict(n=B(), tavg=B(tavg[ok]), tmax=B(tmax[ok]),
  ice_surface=B(((iv==0)|(iv==-1)).astype(float)), ice_shallow=B(((iv>=-1)&(iv<=1)).astype(float)),
  ice_any=B((iv>=-1).astype(float)), ice_neg1=B((iv==-1).astype(float)),
  ice_depth_sum=B(np.where(iv>=0,iv,0)), ice_n=B((iv>=0).astype(float)), tmin_n=np.zeros((P,P),np.float32))
np.savez_compressed("data/official/diviner_prp_south_476.npz", header="fixed-width v2", columns=np.array([127,144,178,188,198]), has_tmin=False, sample=np.zeros((0,5),np.float32), **out)
print('cells', (out['n']>0).sum(), 'rows used', ok.sum())
