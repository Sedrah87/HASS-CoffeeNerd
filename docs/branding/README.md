# Icon und Logo

Das Icon „Tropfen“ ist dasselbe wie in der CoffeeNørd-App: ein Crema-Tropfen (`#C9772F`) mit einer
hellen Linie (`#F3EDE4`). Für Home Assistant ist der Hintergrund transparent und das Icon eng beschnitten.

| Quelle | Ergebnis |
|---|---|
| `icon.svg` | `custom_components/coffeenord/brand/icon.png` (256 px) und `icon@2x.png` (512 px) |
| `logo-light.svg`, `logo-dark.svg` | `docs/images/logo-light.png`, `logo-dark.png` (für das README) |

Gerendert mit Chrome headless und transparentem Hintergrund, z. B.:

```sh
chrome --headless=new --default-background-color=00000000 --force-device-scale-factor=2 \
  --window-size=256,256 --screenshot=icon@2x.png icon.html   # icon.html bettet icon.svg in 256 × 256 ein
```

Die Schrift im Logo ist eine Systemschrift (SF Pro bzw. Helvetica). Darum gibt es das Logo als PNG.
Die Screenshots in `docs/images/panel-*.png` zeigen Beispieldaten.
