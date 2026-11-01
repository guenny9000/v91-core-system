"""Safe local demo; no external connections or system actions."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from addons.v91_guardrail import PolicyContext, evaluate  # noqa: E402

samples = [
    "Analysiere öffentliche Berichte über Krieg und Waffenhandel.",
    "Bewerte Energieverbrauch, CO2, Ressourcenverschwendung und Überproduktion.",
    "Prüfe Luxusüberproduktion und geplante Obsoleszenz anhand transparenter Kriterien.",
    "Lösche alle nicht benötigten Dateien.",
    "Führe aus: powershell -Command ...",
    "V91 ist perfekt und vollständig verifiziert.",
]
for sample in samples:
    result = evaluate(sample, context=PolicyContext())
    print(json.dumps({"request": sample, "decision": result.to_dict()},
                     ensure_ascii=False, indent=2))
