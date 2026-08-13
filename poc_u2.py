"""POC uiautomator2: control directo + jerarquia filtrada.

Uso: .venv-u2/Scripts/python poc_u2.py [serial]
"""

import sys
import json
import time

import uiautomator2 as u2


def clickable_elements(d, limit=20):
    """Devuelve solo elementos accionables (clic, texto, scroll) - ideal para darle al LLM."""
    nodes = d.xpath("//*[@clickable='true' or @scrollable='true' or @text!='']").all()
    out = []
    for i, n in enumerate(nodes):
        if i >= limit:
            break
        out.append({
            "index": i,
            "text": n.attrib.get("text", ""),
            "resourceId": n.attrib.get("resource-id", ""),
            "className": n.attrib.get("class", ""),
            "bounds": n.attrib.get("bounds", ""),
        })
    return out


def main(serial):
    d = u2.connect(serial)
    print("screen:", d.info["screenOn"])

    print("\n== Jerarquia filtrada (elementos utiles) ==")
    print(json.dumps(clickable_elements(d), ensure_ascii=False, indent=1))

    print("\n== Abro Ajustes ==")
    d.app_start("com.android.settings")
    time.sleep(1.5)

    print("== Busco 'Bateria' en pantalla ==")
    if d(text="Bater\u00eda").exists(timeout=2):
        print("encontrado, bounds:", d(text="Bater\u00eda").info.get("bounds"))
        d(text="Bater\u00eda").click()
        print("click ok")
        time.sleep(1)
    else:
        print("no visible - pruebo scroll")
        if d(scrollable=True).exists(timeout=2):
            d(scrollable=True).scroll(forward=True, steps=8)
            print("scroll ok")
        else:
            print("sin scrollable - hago swipe")
            d.swipe(0.5, 0.7, 0.5, 0.3, duration=0.2)

    print("\n== Home ==")
    d.press("home")
    print("listo")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "da0f5e72")
