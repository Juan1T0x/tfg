# -*- coding: utf-8 -*-
"""
Detecta barras AZULES en los ROIs de recursos de campeones,
escaladas por ROI_SCALE y normalizadas.

• Separa equipo azul y rojo.
• El 100 % de cada equipo = anchura máxima hallada en su zona.
• Imprime barras ordenadas de arriba → abajo con su % de maná.
"""
import cv2, numpy as np

# ───────── Parámetros ─────────
ROI_SCALE   = 1.33
LOWER_BLUE  = np.array([95, 50, 50])
UPPER_BLUE  = np.array([125, 255, 255])
AREA_MIN    = 300
ELONG_RATIO = 0.5

TEMPLATE_ROIS = {
    "team1ChampionsResourcesRoi": [[0,135],[86,135],[87,709],[1,711]],
    "team2ChampionsResourcesRoi": [[1835,135],[1918,135],[1919,712],[1835,710]]
}
ROLE_LABELS = ["mana top", "mana jungle", "mana mid", "mana bot", "mana support"]

# ───────── Helpers ─────────
scale_pts = lambda pts,s: [(round(x*s),round(y*s)) for x,y in pts]
bounds    = lambda pts: (min(x for x,_ in pts),min(y for _,y in pts),
                         max(x for x,_ in pts),max(y for _,y in pts))
def grow(b,w,h,W,H): x0,y0,_,_=b; return x0,y0,min(x0+w,W),min(y0+h,H)

def barras(img):
    hsv=cv2.cvtColor(img,cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,LOWER_BLUE,UPPER_BLUE)
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    cnts,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    rects=[cv2.boundingRect(c) for c in cnts if cv2.contourArea(c)>AREA_MIN]
    return[(x,y,w,h) for x,y,w,h in rects if h<ELONG_RATIO*w]

# ───────── UI ─────────
def scr():      # pantalla
    try:
        import tkinter as tk
        r=tk.Tk();r.withdraw();w,h=r.winfo_screenwidth(),r.winfo_screenheight();r.destroy();return w,h
    except: return 1920,1080
def show(name,img): W,H=scr();cv2.namedWindow(name,cv2.WINDOW_NORMAL);cv2.resizeWindow(name,W,H);cv2.moveWindow(name,0,0);cv2.imshow(name,img)

# ───────── Main ─────────
def main():
    frame=cv2.imread("source.jpg")
    if frame is None: print("No se encontró 'source.jpg'"); return
    h_img,w_img=frame.shape[:2]

    # Escalar ROIs
    scaled={n:scale_pts(pts,ROI_SCALE) for n,pts in TEMPLATE_ROIS.items()}
    b1,b2=bounds(scaled["team1ChampionsResourcesRoi"]),bounds(scaled["team2ChampionsResourcesRoi"])
    tw,th=max(b1[2]-b1[0],b2[2]-b2[0]),max(b1[3]-b1[1],b2[3]-b2[1])
    norm_boxes=[grow(b1,tw,th,w_img,h_img),grow(b2,tw,th,w_img,h_img)]

    detections={"azul":[], "rojo":[]}

    # 1. Detección y dibujo
    for idx,(x0,y0,x1,y1) in enumerate(norm_boxes,1):
        team="azul" if idx==1 else "rojo"
        crop=frame[y0:y1,x0:x1]
        for x,y,w,h in barras(crop):
            gx,gy=x+x0, y+y0
            detections[team].append((gy,gx,w,h))
            cv2.rectangle(frame,(gx,gy),(gx+w,gy+h),(255,0,0),2)
        cv2.rectangle(frame,(x0,y0),(x1,y1),(0,255,0),2)

    # 2. Calcular full-width (máx ancho por equipo)
    full_width={team:(max(w for _,_,w,_ in dets) if dets else None)
                for team,dets in detections.items()}

    # 3. Salida ordenada
    for team in ("azul","rojo"):
        print(f"\nroi equipo {team}:")
        dets_sorted=sorted(detections[team], key=lambda t:t[0])
        for i,label in enumerate(ROLE_LABELS):
            if i<len(dets_sorted):
                y,x,w,h=dets_sorted[i]
                pct=" ?.?%"
                if full_width[team]:
                    pct=f"{(w/full_width[team]*100):5.1f}%"
                print(f"    {label:<12}: (x={x}, y={y}, w={w}, h={h}) → {pct}")
            else:
                print(f"    {label:<12}: no detectado →  ?.?%")

    show(f"Champions mana (scale={ROI_SCALE})",frame)
    cv2.waitKey(0);cv2.destroyAllWindows()

if __name__=="__main__":
    main()
