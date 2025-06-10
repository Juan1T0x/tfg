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

def extract_and_match(detector_name, detector, query_img, target_imgs):
    kp1, des1 = detector.detectAndCompute(query_img, None)
    results = []
    if des1 is None or len(kp1) == 0:
        return []

    use_l2 = detector_name in ["SIFT", "SURF", "KAZE"]
    norm_type = cv2.NORM_L2 if use_l2 else cv2.NORM_HAMMING
    matcher = cv2.BFMatcher(norm_type)

    for name, target_img in target_imgs.items():
        kp2, des2 = detector.detectAndCompute(target_img, None)
        if des2 is None or len(kp2) == 0:
            continue
        try:
            matches = matcher.knnMatch(des1, des2, k=2)
            good = [m for m_n in matches if len(m_n) == 2 for m, n in [m_n] if m.distance < 0.75 * n.distance]
            results.append((name, len(good)))
        except cv2.error as e:
            continue

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:5]

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

GROUND_TRUTH = {
    "blue": ["yorick", "pantheon", "taliyah", "kaisa", "rell"],
    "red": ["ambessa", "vi", "ahri", "xayah", "rakan"]
}

def normalize_name(name):
    return name.lower().split("_")[0]

def resize_if_needed(img, resize_flag):
    return cv2.resize(img, (100, 100)) if resize_flag else img

def main():
    
    screenshot = cv2.imread("./screenshot.png")
    templates = load_roi_templates("../roi/templates/output")
    champion_images = load_champion_images("../data/images/loading_screen")

    bbox_blue = get_bounding_box(templates["champ_select_rois"]["team1ChampionsRoi"])
    sub_boxes_blue = subdivide_roi(bbox_blue, 5)

    bbox_red = get_bounding_box(templates["champ_select_rois"]["team2ChampionsRoi"])
    sub_boxes_red = subdivide_roi(bbox_red, 5)

    detectors = create_detectors()

    resize_settings = [
        (True, False, "resize_bbox_only"),
        (False, True, "resize_db_only"),
        (True, True, "resize_both"),
        (False, False, "resize_none")
    ]

    for resize_bbox, resize_db, label in resize_settings:
        print(f"\n=========================\nEstrategia: {label}\n=========================")
        scores = {det: {"top1": 0, "top5": 0} for det in detectors}

        # Preprocesar base de datos si hace falta
        db_images = {
            normalize_name(name): resize_if_needed(img, resize_db)
            for name, img in champion_images.items()
        }

        all_boxes = sub_boxes_blue + sub_boxes_red
        all_gt = GROUND_TRUTH["blue"] + GROUND_TRUTH["red"]

        for idx, (x1, y1, x2, y2) in enumerate(all_boxes):
            gt = all_gt[idx]
            subbox_img = screenshot[y1:y2, x1:x2]
            subbox_img = resize_if_needed(subbox_img, resize_bbox)

            for det_name, detector in detectors.items():
                results = extract_and_match(det_name, detector, subbox_img, db_images)
                pred_names = [normalize_name(name) for name, _ in results]

                if pred_names:
                    if pred_names[0] == gt:
                        scores[det_name]["top1"] += 1
                    if gt in pred_names:
                        scores[det_name]["top5"] += 1

        for det, res in scores.items():
            print(f"{det}: {res['top1']} exactos, {res['top5']} en top 5")

if __name__ == "__main__":
    main()