"""`quotidien/03_rendu` : le ticket en bitmap 576 px pour la TM-m30II-H (#18).

Police DejaVu Sans embarquée (sous-ensemble, licence et recette dans `polices/`) et moteur de
mise en page `BASIC` imposé (Pillow prendrait RAQM là où libfribidi existe, et le crénage
changerait) : le rendu ne dépend que des versions épinglées de Pillow et de sa FreeType. Un
caractère que la police ne sait pas dessiner devient « ? » (`imprimable.py`). QR par segno.
Les réponses du pli (#14) sont imprimées à l'envers sous un pointillé : on plie, on répond, on
retourne. Sortie en 1 bit sans tramage : le papier thermique n'a pas de gris.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import segno
from PIL import Image, ImageDraw, ImageFont

from freinet.imprimable import imprimable, visuel
from freinet.langue import Libelles
from freinet.ticket import Bloc, Ticket, date_longue, etiquette

LARGEUR = 576  # 72 mm imprimables à 203 dpi (papier de 80 mm)
MARGE = 16
UTILE = LARGEUR - 2 * MARGE
RETRAIT = 34
INTERLIGNE = 6
POLICES = Path(__file__).resolve().parent / "polices"
TAILLE = {"entete": 34, "titre": 27, "texte": 24, "petit": 19}
MODULE_QR = 6


@cache
def police(gras: bool, taille: int) -> ImageFont.FreeTypeFont:
    nom = "DejaVuSans-Bold.ttf" if gras else "DejaVuSans.ttf"
    return ImageFont.truetype(str(POLICES / nom), taille, layout_engine=ImageFont.Layout.BASIC)


def couper(texte: str, fonte: ImageFont.FreeTypeFont, largeur: int) -> list[str]:
    """Retour à la ligne au mot, à la largeur en pixels ; un mot trop long est coupé (au moins
    un caractère par ligne, même si la largeur ne suffit pas)."""
    largeur = max(1, largeur)
    lignes: list[str] = []
    courante = ""
    for mot in texte.split():
        essai = f"{courante} {mot}" if courante else mot
        if fonte.getlength(essai) <= largeur:
            courante = essai
            continue
        if courante:
            lignes.append(courante)
        while fonte.getlength(mot) > largeur:
            coupe = next(
                (i for i in range(len(mot), 1, -1) if fonte.getlength(mot[:i]) <= largeur), 1
            )
            lignes.append(mot[:coupe])
            mot = mot[coupe:]
        courante = mot
    return [*lignes, courante] if courante else lignes


class _Toile:
    """Une bande de papier qui s'allonge au fil du dessin (niveaux de gris, fond blanc)."""

    def __init__(self) -> None:
        self.image = Image.new("L", (LARGEUR, 2000), 255)
        self.y = MARGE

    def place(self, hauteur: int) -> ImageDraw.ImageDraw:
        if self.y + hauteur + MARGE > self.image.height:
            plus = Image.new(
                "L", (LARGEUR, max(self.image.height * 2, self.y + hauteur + 500)), 255
            )
            plus.paste(self.image, (0, 0))
            self.image = plus
        return ImageDraw.Draw(self.image)

    def texte(
        self, texte: str, gras: bool = False, taille: int = TAILLE["texte"], x: int = MARGE
    ) -> None:
        fonte = police(gras, taille)
        hauteur = taille + INTERLIGNE
        for ligne in couper(imprimable(texte), fonte, LARGEUR - MARGE - x):
            self.place(hauteur).text((x, self.y), visuel(ligne), font=fonte, fill=0)
            self.y += hauteur

    def trait(self, epaisseur: int = 2, x: int = MARGE, espace: int = 8) -> None:
        self.place(espace * 2 + epaisseur).rectangle(
            (x, self.y + espace, LARGEUR - MARGE, self.y + espace + epaisseur - 1), fill=0
        )
        self.y += espace * 2 + epaisseur

    def ligne_de_reponse(self, x: int = MARGE + RETRAIT) -> None:
        """Une ligne pointillée où écrire au stylo."""
        dessin = self.place(40)
        for debut in range(x, LARGEUR - MARGE, 8):
            dessin.rectangle((debut, self.y + 30, debut + 3, self.y + 31), fill=0)
        self.y += 40

    def cadre(self, lignes: int) -> None:
        """Un cadre vide où écrire : `lignes` hauteurs de ligne à la main."""
        hauteur = lignes * 40
        self.place(hauteur + 8).rectangle(
            (MARGE, self.y + 4, LARGEUR - MARGE, self.y + 4 + hauteur), outline=0, width=2
        )
        self.y += hauteur + 8

    def espace(self, hauteur: int) -> None:
        self.place(hauteur)
        self.y += hauteur

    def image_finale(self) -> Image.Image:
        return self.image.crop((0, 0, LARGEUR, self.y + MARGE))


def _numerote(toile: _Toile, prefixe: str, texte: str) -> None:
    debut = toile.y
    toile.place(TAILLE["texte"]).text(
        (MARGE, debut), prefixe, font=police(True, TAILLE["texte"]), fill=0
    )
    decalage = max(RETRAIT, int(police(True, TAILLE["texte"]).getlength(prefixe + " ")))
    decalage = min(decalage, UTILE // 2)  # un numéro retouché démesuré ne mange pas la ligne
    toile.texte(texte, x=MARGE + decalage)
    toile.ligne_de_reponse()


def _bloc(toile: _Toile, bloc: Bloc, lib: Libelles) -> None:
    if bloc.genre == "titre":
        toile.espace(14)
        toile.texte(bloc.texte.upper(), gras=True, taille=TAILLE["titre"])
        toile.trait(1, espace=3)
    elif bloc.genre == "citation":
        debut = toile.y
        toile.texte(bloc.texte, x=MARGE + 18)
        if toile.y > debut:
            toile.place(0).rectangle((MARGE, debut, MARGE + 4, toile.y - INTERLIGNE), fill=0)
    elif bloc.genre == "question":
        _numerote(toile, f"{bloc.numero}.", bloc.texte)
    elif bloc.genre == "pre_test":
        toile.texte(f"{lib.avant_de_lire} :", gras=True)
        toile.texte(bloc.texte, x=MARGE + RETRAIT)
        toile.ligne_de_reponse()
    elif bloc.genre == "source":
        toile.texte(bloc.texte, taille=TAILLE["petit"])
    elif bloc.genre == "avertissement":
        toile.espace(8)
        toile.texte(bloc.texte, gras=True, taille=TAILLE["petit"])
    elif bloc.genre == "quete" and bloc.progression is not None:
        toile.texte(bloc.texte)
        _barre(toile, *bloc.progression)
    elif bloc.genre == "ecrire" and bloc.numero:
        for _ in range(bloc.numero):
            toile.ligne_de_reponse(x=MARGE)
    elif bloc.genre == "cadre" and bloc.numero:
        toile.cadre(bloc.numero)
    elif bloc.genre == "separation":
        toile.espace(18)
        toile.trait(4)
    else:
        toile.texte(bloc.texte)


def _barre(toile: _Toile, acquis: int, total: int) -> None:
    compte = f"{acquis}/{total}"
    fonte = police(True, TAILLE["texte"])
    longueur = UTILE - int(fonte.getlength(compte)) - 16
    part = max(0.0, min(1.0, acquis / total)) if total > 0 else 0.0
    dessin = toile.place(34)
    haut = toile.y + 6
    dessin.rectangle((MARGE, haut, MARGE + longueur, haut + 20), outline=0, width=2)
    if part > 0:
        dessin.rectangle((MARGE, haut, MARGE + round(longueur * part), haut + 20), fill=0)
    dessin.text((MARGE + longueur + 16, toile.y + 2), compte, font=fonte, fill=0)
    toile.y += 34


def _qr(toile: _Toile, lien: str) -> None:
    code = segno.make(lien, error="m", micro=False)
    matrice = code.matrix
    cote = len(matrice) * MODULE_QR
    toile.espace(4 * MODULE_QR)  # zone de silence : 4 modules
    dessin = toile.place(cote)
    gauche = (LARGEUR - cote) // 2
    for rang, ligne in enumerate(matrice):
        for colonne, noir in enumerate(ligne):
            if noir:
                x, y = gauche + colonne * MODULE_QR, toile.y + rang * MODULE_QR
                dessin.rectangle((x, y, x + MODULE_QR - 1, y + MODULE_QR - 1), fill=0)
    toile.y += cote + 4 * MODULE_QR


def _pli(toile: _Toile, ticket: Ticket) -> None:
    toile.espace(24)
    dessin = toile.place(30)
    fonte = police(False, TAILLE["texte"])
    dessin.text((MARGE, toile.y), "✂", font=fonte, fill=0)
    for x in range(MARGE + 36, LARGEUR - MARGE, 14):
        dessin.rectangle((x, toile.y + 14, x + 6, toile.y + 15), fill=0)
    toile.y += 30
    reponses = _Toile()
    reponses.texte(ticket.libelles.reponses, gras=True, taille=TAILLE["titre"])
    for reponse in ticket.reponses:
        reponses.texte(etiquette(reponse) + reponse.texte)
    bloc = reponses.image_finale().rotate(180)
    toile.place(bloc.height)
    toile.image.paste(bloc, (0, toile.y))
    toile.y += bloc.height


def png_ticket(ticket: Ticket) -> Image.Image:
    """Le ticket en 1 bit, 576 px de large."""
    toile = _Toile()
    entete = f"FREINET · {ticket.prenom}" if ticket.prenom else "FREINET"
    toile.texte(entete, gras=True, taille=TAILLE["entete"])
    toile.texte(date_longue(ticket.jour, ticket.libelles))
    toile.trait(4)
    for bloc in ticket.blocs:
        _bloc(toile, bloc, ticket.libelles)
    if ticket.retour:
        _qr(toile, ticket.retour.lien)
        toile.texte(ticket.retour.consigne(ticket.libelles), taille=TAILLE["petit"])
    if ticket.reponses:
        _pli(toile, ticket)
    toile.espace(40)  # marge avant la coupe
    return toile.image_finale().convert("1", dither=Image.Dither.NONE)
