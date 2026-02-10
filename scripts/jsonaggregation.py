import json
from pathlib import Path

input_dir = Path(r"C:\Users\pqhun\Downloads\incidents1\2026-02-10_schema_v2_3_new_v2.3_dataset_166json_20260210T045316Z\data\structured\incidents\schema_v2_3")
out_path = Path(r"C:\Users\pqhun\OneDrive\Practicum\JSONdatav1\incidents.json")

incidents = []
for fp in sorted(input_dir.rglob("*.json")):
    try:
        obj = json.loads(fp.read_text(encoding="utf-8"))
        obj["_source_file"] = str(fp)
        incidents.append(obj)
    except Exception as e:
        print(f"Skipping {fp}: {e}")

out_path.write_text(json.dumps(incidents, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Wrote {len(incidents)} incidents -> {out_path}")
