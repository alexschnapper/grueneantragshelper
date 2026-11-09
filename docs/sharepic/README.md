# Sharepics

| Datei | Format | Gedacht für |
|---|---|---|
| `sharepic-1080x1350.png` | Hochformat | Instagram, Facebook |
| `sharepic-1200x675.png` | Querformat | Mastodon, Bluesky, LinkedIn, X |

Begleittexte für Instagram/Facebook, Mastodon, Bluesky, X und LinkedIn sowie ein Alternativtext
stehen in [`begleittext.md`](begleittext.md).

Beide sind als **KI-generiert** gekennzeichnet und tragen den Hinweis, dass es sich um ein
inoffizielles Projekt handelt. Logo, Sonnenblume und Hausschrift der Partei werden bewusst
nicht verwendet.

Neu erzeugen (macOS, Google Chrome):

```sh
cd docs/sharepic
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$C" --headless=new --hide-scrollbars --force-device-scale-factor=1 --window-size=1080,1350 \
  --screenshot="$PWD/sharepic-1080x1350.png" "file://$PWD/portrait.html"
"$C" --headless=new --hide-scrollbars --force-device-scale-factor=1 --window-size=1200,675 \
  --screenshot="$PWD/sharepic-1200x675.png" "file://$PWD/landscape.html"
```
