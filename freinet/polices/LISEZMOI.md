# Polices du ticket

DejaVu Sans et DejaVu Sans Bold (licence Bitstream Vera / Arev : `LICENSE_DEJAVU`), réduites aux
caractères utiles pour garder le dépôt léger. Source : `matplotlib/mpl-data/fonts/ttf/` (wheel
PyPI de matplotlib, qui embarque DejaVu 2.x).

Refaire le sous-ensemble (outil `fonttools`, hors des dépendances du projet) :

    PLAGES="U+0020-007E,U+00A0-017F,U+0192,U+0218-021B,U+02C6-02DC,U+0300-036F,U+0370-03FF,U+0590-05FF,U+2000-206F,U+2070-209F,U+20A0-20CF,U+2100-214F,U+2150-218F,U+2190-21FF,U+2200-22FF,U+2500-257F,U+2580-259F,U+25A0-25FF,U+2600-26FF,U+2700-27BF,U+FB00-FB06"
    for f in DejaVuSans DejaVuSans-Bold; do
      pyftsubset "$DEJAVU/$f.ttf" --unicodes="$PLAGES" --output-file="$f.ttf" \
        --layout-features='kern,liga' --no-hinting --desubroutinize
    done

Source vérifiée : wheel `matplotlib==3.9.4` (`pip3 download matplotlib==3.9.4 --no-deps
--only-binary=:all:`). L'hébreu (U+0590-05FF) sert au mot du jour : Pillow tourne sans bidi,
`imprimable.visuel` retourne les suites hébraïques avant le dessin. `couverture.txt` se
régénère avec le script Python du plan PROF-8a (Task 1, Step 4).

`couverture.txt` liste les caractères présents dans les deux graisses (plages hexadécimales) :
`freinet/imprimable.py` le lit. Le fan-out refuse un texte qui en sort, et le rendu remplace
un caractère absent par « ? » plutôt que de l'effacer en silence. Après un nouveau sous-ensemble,
régénérer ce fichier depuis la table `cmap` des deux polices, puis `pytest --update-ref`.
