import os
import glob
import json
import numpy as np
import cv2

def load_roi_templates(folder_path):
    templates = {}
    for file_path in glob.glob(os.path.join(folder_path, "*.json")):
        with open(file_path, "r") as file:
            data = json.load(file)
        name = os.path.splitext(os.path.basename(file_path))[0]
        templates[name] = data
    return templates

def get_bounding_box(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)

def subdivide_roi(bbox, subdivisions=5):
    min_x, min_y, max_x, max_y = bbox
    width = max_x - min_x
    sub_width = width // subdivisions
    sub_boxes = []
    for i in range(subdivisions):
        x1 = min_x + i * sub_width
        x2 = min_x + (i + 1) * sub_width if i < subdivisions - 1 else max_x
        sub_boxes.append((x1, min_y, x2, max_y))
    return sub_boxes

def load_champion_images(folder_path):
    images = {}
    for path in glob.glob(os.path.join(folder_path, "*")):
        if path.lower().endswith(('.jpg', '.jpeg', '.png')):
            name = os.path.basename(path).split('_')[0].lower()
            img = cv2.imread(path)
            if img is not None:
                images[name] = img
    return images

def draw_matches(detector, img1, img2, kp1, kp2, matches):
    return cv2.drawMatchesKnn(img1, kp1, img2, kp2, matches, None,
                              flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)

def extract_and_match(detector_name, detector, query_img, target_imgs, matcher_type='bf'):
    kp1, des1 = detector.detectAndCompute(query_img, None)
    if des1 is None or len(kp1) == 0:
        return [], kp1, {}

    if matcher_type == 'bf':
        use_l2 = detector_name in ["SIFT", "SURF", "KAZE"]
        norm_type = cv2.NORM_L2 if use_l2 else cv2.NORM_HAMMING
        matcher = cv2.BFMatcher(norm_type)
    elif matcher_type == 'flann':
        if detector_name in ["SIFT", "SURF", "KAZE"]:
            matcher = cv2.FlannBasedMatcher(dict(algorithm=1, trees=5), dict())
        elif detector_name in ["ORB", "BRISK", "AKAZE"]:
            flann_params = dict(algorithm=6, table_number=6, key_size=12, multi_probe_level=1)
            matcher = cv2.FlannBasedMatcher(flann_params, {})
        else:
            return [], kp1, {}

    results = []
    match_data = {}
    for name, target_img in target_imgs.items():
        kp2, des2 = detector.detectAndCompute(target_img, None)
        if des2 is None or len(kp2) == 0:
            continue
        try:
            matches = matcher.knnMatch(des1, des2, k=2)
            good = [m for m_n in matches if len(m_n) == 2 for m, n in [m_n] if m.distance < 0.75 * n.distance]
            results.append((name, len(good)))
            match_data[name] = (kp2, matches)
        except cv2.error:
            continue

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:5], kp1, match_data

def create_detectors():
    detectors = {}
    if hasattr(cv2, 'SIFT_create'):
        detectors["SIFT"] = cv2.SIFT_create()
    if hasattr(cv2, 'ORB_create'):
        detectors["ORB"] = cv2.ORB_create()
    if hasattr(cv2, 'AKAZE_create'):
        detectors["AKAZE"] = cv2.AKAZE_create()
    if hasattr(cv2, 'BRISK_create'):
        detectors["BRISK"] = cv2.BRISK_create()
    if hasattr(cv2, 'xfeatures2d'):
        try:
            detectors["SURF"] = cv2.xfeatures2d.SURF_create()
        except:
            pass
    if hasattr(cv2, 'KAZE_create'):
        detectors["KAZE"] = cv2.KAZE_create()
    return detectors

def normalize_name(name):
    return name.lower().split("_")[0]

GROUND_TRUTH = {
    "blue": ["yorick", "pantheon", "taliyah", "kaisa", "rell"],
    "red": ["ambessa", "vi", "ahri", "xayah", "rakan"]
}

def main():
    os.makedirs("./results", exist_ok=True)

    screenshot = cv2.imread("./screenshot.png")
    templates = load_roi_templates("../roi/templates/output")
    champion_images = load_champion_images("../data/images/loading_screen")

    bbox_blue = get_bounding_box(templates["champ_select_rois"]["team1ChampionsRoi"])
    sub_boxes_blue = subdivide_roi(bbox_blue, 5)

    bbox_red = get_bounding_box(templates["champ_select_rois"]["team2ChampionsRoi"])
    sub_boxes_red = subdivide_roi(bbox_red, 5)

    detectors = create_detectors()
    db_images = {normalize_name(name): img for name, img in champion_images.items()}

    all_boxes = sub_boxes_blue + sub_boxes_red
    all_gt = GROUND_TRUTH["blue"] + GROUND_TRUTH["red"]
    all_teams = ["blue"] * 5 + ["red"] * 5

    scores = {(d, m): {"top1": 0, "top5": 0} for d in detectors for m in ['bf', 'flann']}

    print("\n============== PREDICCIONES POR EQUIPO ==============")

    for idx, ((x1, y1, x2, y2), gt, team) in enumerate(zip(all_boxes, all_gt, all_teams)):
        subbox_img = screenshot[y1:y2, x1:x2]
        print(f"\n--- Predicciones Equipo {team.upper()} ---")
        print(f"Campeón {idx % 5 + 1} (Ground Truth: {gt})")

        for det_name, detector in detectors.items():
            for matcher_type in ['bf', 'flann']:
                results, kp1, match_data = extract_and_match(det_name, detector, subbox_img, db_images, matcher_type)
                pred_names = [normalize_name(name) for name, _ in results]
                result_str = ', '.join(pred_names) if pred_names else "Sin coincidencias"

                if not pred_names:
                    status = "Campeón no reconocido"
                elif pred_names[0] == gt:
                    status = "Acierto exacto"
                    scores[(det_name, matcher_type)]["top1"] += 1
                    scores[(det_name, matcher_type)]["top5"] += 1
                elif gt in pred_names:
                    status = "Acierto en el top N"
                    scores[(det_name, matcher_type)]["top5"] += 1
                else:
                    status = "Campeón no reconocido"

                matcher_name = "BFMatcher" if matcher_type == "bf" else "FLANN"
                print(f"Técnica {det_name} con {matcher_name}: {result_str} → {status}")

                technique_dir = f"./results/{gt}/{det_name}_{matcher_type}"
                os.makedirs(technique_dir, exist_ok=True)

                for pred_name, _ in results:
                    if pred_name not in champion_images or pred_name not in match_data:
                        continue
                    target_img = champion_images[pred_name]
                    kp2, raw_matches = match_data[pred_name]
                    try:
                        vis = draw_matches(detector, subbox_img, target_img, kp1, kp2, raw_matches)
                        out_path = f"{technique_dir}/{pred_name}.jpg"
                        cv2.imwrite(out_path, vis)
                    except:
                        continue

    print("\n============== RESUMEN GLOBAL DE TÉCNICAS + MATCHERS ==============")
    sorted_scores = sorted(scores.items(), key=lambda x: (x[1]["top1"], x[1]["top5"]), reverse=True)
    for (det_name, matcher), res in sorted_scores:
        matcher_name = "BFMatcher" if matcher == "bf" else "FLANN"
        print(f"{det_name} con {matcher_name}: {res['top1']} exactos, {res['top5']} en top 5")

if __name__ == "__main__":
    main()