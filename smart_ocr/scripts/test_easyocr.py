import easyocr, re, json
reader = easyocr.Reader(["it"], gpu=False, verbose=False)
result = reader.readtext("../TEST1/WhatsApp Image 2026-03-22 at 03.15.39.jpeg")
print("Testi: " + str(len(result)))
items = {}
for bbox, text, conf in result:
    tc = text.strip().replace(" ", "")
    x1 = min(p[0] for p in bbox)
    y1 = min(p[1] for p in bbox)
    x2 = max(p[0] for p in bbox)
    y2 = max(p[1] for p in bbox)
    if re.match(r"^[0-9]{1,2}$", tc):
        num = int(tc)
        if 1 <= num <= 56 and y1 > 300:
            if num not in items or conf > items[num]["conf"]:
                items[num] = {"item": num, "x": (x1+x2)/2, "y": (y1+y2)/2, "conf": conf}
print("Item trovati: " + str(len(items)) + "/56")
for n in sorted(items.keys()):
    it = items[n]
    col = "SX" if it["x"] < 600 else "DX"
    print("  %3d  x=%6.0f y=%6.0f  conf=%.2f  %s" % (n, it["x"], it["y"], it["conf"], col))
json.dump({str(k): v for k, v in items.items()}, open("/tmp/ocr_items.json", "w"), indent=2)
print("Salvato /tmp/ocr_items.json")
