# -*- coding: utf-8 -*-
"""
Detecta barras VERDES (vida) en los ROIs de recursos de campeones.

• Equipo azul: la barra “vida jungle” se toma como 100 %.
• Equipo rojo: el 100 % es la barra más ancha vista en su ROI.
• Imprime barras de arriba → abajo con % de vida.
"""
import cv2, numpy as np

# ───────── Parámetros ─────────
ROI_SCALE   = 1.33
LOWER_GREEN = np.array([30, 40, 40])
UPPER_GREEN = np.array([80, 250, 250])
AREA_MIN    = 300
ELONG_RATIO = 0.5

TEMPLATE_ROIS = {
    "team1ChampionsResourcesRoi": [[0,135],[86,135],[87,709],[1,711]],
    "team2ChampionsResourcesRoi": [[1835,135],[1918,135],[1919,712],[1835,710]]
}
ROLE_LABELS = ["vida top", "vida jungle", "vida mid", "vida bot", "vida support"]

REFERENCE_BLUE = "vida jungle"  # etiqueta que vale 100 % en equipo azul

# ───────── Helpers ─────────
scale_pts = lambda pts,s: [(round(x*s), round(y*s)) for x,y in pts]
bounds    = lambda pts: (min(x for x,_ in pts), min(y for _,y in pts),
                         max(x for x,_ in pts), max(y for _,y in pts))
def grow(b,w,h,W,H): x0,y0,_,_=b; return x0,y0,min(x0+w,W),min(y0+h,H)

def detectar_barras(img):
    hsv=cv2.cvtColor(img,cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,LOWER_GREEN,UPPER_GREEN)
    mask=cv2.morphologyEx(mask,cv2.MORPH_OPEN,np.ones((3,3),np.uint8))
    mask=cv2.morphologyEx(mask,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    cnts,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    rects=[cv2.boundingRect(c) for c in cnts if cv2.contourArea(c)>AREA_MIN]
    return[(x,y,w,h)for x,y,w,h in rects if h<ELONG_RATIO*w]

def show_fullscreen(name,img):
    try:
        import tkinter as tk
        r=tk.Tk();r.withdraw();W,H=r.winfo_screenwidth(),r.winfo_screenheight();r.destroy()
    except: W,H=1920,1080
    cv2.namedWindow(name,cv2.WINDOW_NORMAL)
    cv2.resizeWindow(name,W,H);cv2.moveWindow(name,0,0);cv2.imshow(name,img)

# ───────── Main ─────────
def main():
    frame=cv2.imread("source.jpg")
    if frame is None:
        print("Error: no se encontró 'source.jpg'."); return
    H_img,W_img=frame.shape[:2]

    # ROIs escalados y normalizados
    scaled={n:scale_pts(v,ROI_SCALE) for n,v in TEMPLATE_ROIS.items()}
    b1,b2=bounds(scaled["team1ChampionsResourcesRoi"]),bounds(scaled["team2ChampionsResourcesRoi"])
    tw,th=max(b1[2]-b1[0],b2[2]-b2[0]),max(b1[3]-b1[1],b2[3]-b2[1])
    boxes=[grow(b1,tw,th,W_img,H_img),grow(b2,tw,th,W_img,H_img)]

    detections={"azul":[], "rojo":[]}

    for idx,(x0,y0,x1,y1) in enumerate(boxes,1):
        team="azul" if idx==1 else "rojo"
        crop=frame[y0:y1,x0:x1]
        for x,y,w,h in detectar_barras(crop):
            gx,gy=x+x0,y+y0
            detections[team].append((gy,gx,w,h))
            cv2.rectangle(frame,(gx,gy),(gx+w,gy+h),(0,255,0),2)
        cv2.rectangle(frame,(x0,y0),(x1,y1),(0,165,255),2)

    # --- Calcular anchura 100 % por equipo ---
    full_width={}
    # Azul: usar barra referencia
    blue_ref = next((w for y,x,w,h in detections["azul"]
                     for label in ROLE_LABELS
                     if (sorted(detections["azul"],key=lambda t:t[0]).index((y,x,w,h))==ROLE_LABELS.index(REFERENCE_BLUE))), None)
    full_width["azul"]=blue_ref if blue_ref else max((w for _,_,w,_ in detections["azul"]), default=None)
    # Rojo: mayor ancho detectado
    full_width["rojo"]=max((w for _,_,w,_ in detections["rojo"]), default=None)

    # --- Salida consola ---
    for team in ("azul","rojo"):
        print(f"\nroi equipo {team}:")
        det_sorted=sorted(detections[team],key=lambda t:t[0])
        for i,label in enumerate(ROLE_LABELS):
            if i<len(det_sorted):
                y,x,w,h=det_sorted[i]
                pct_txt=" ?.?%"
                if full_width[team]:
                    pct_txt=f"{(w/full_width[team]*100):5.1f}%"
                print(f"    {label:<12}: (x={x}, y={y}, w={w}, h={h}) → {pct_txt}")
            else:
                print(f"    {label:<12}: no detectado →  ?.?%")

    show_fullscreen("Barras de vida (verde)",frame)
    cv2.waitKey(0);cv2.destroyAllWindows()

if __name__=="__main__":
    main()
