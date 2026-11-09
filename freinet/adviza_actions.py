"""Les actions de l'API ADVIZA (contrat v1, PROF-A3) : liste fermée, idempotentes.

`noter` et `joker` appellent les fonctions de la page du QR (`retour.noter`, `retour.joker`) :
mêmes règles (le plan fait foi, fenêtre de 7 jours, correction compensatoire, `revue` en ajout
seul) ; seul le canal change (`adviza`). `choisir_carte` inscrit l'élève à une carte publiée,
validée comme la commande de Marius (`eleves.valider_inscription`). L'élève est toujours celui
du jeton : aucun paramètre ne le désigne. Idempotence : clé et réponse s'écrivent en ajout
seul (`adviza_requete`) ; la même clé rend la même réponse sans rien rejouer, et la même clé
pour une autre requête est refusée (409). Seules les réponses définitives s'enregistrent
(succès, refus métier) : une panne ou un conflit passager (`EnvoiConcurrent`) laisse la clé
libre. Une seule API par racine (son port est lié) : le verrou de processus suffit ; si une
clé est tout de même prise entre lecture et enregistrement, la réponse enregistrée fait foi.
`repondre` n'existe pas en v1.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from freinet.adviza_lectures import Contexte, Json
from freinet.base import Base, ErreurSQLite
from freinet.base.plans import PlanAcces
from freinet.bibliotheque import charger
from freinet.eleves import Refus, valider_inscription
from freinet.retour import EnvoiConcurrent, RetourRefuse, joker, noter

ACTIONS = ("noter", "joker", "choisir_carte")
CANAL = "adviza"


class RequeteInvalide(Exception):
    """Paramètres mal formés : 400, rien n'est enregistré, la clé reste libre."""


class NonEnregistree(Exception):
    """L'action a pu s'appliquer mais sa réponse n'a pas été enregistrée : la clé reste libre,
    et le rejeu est sûr (le domaine est idempotent en dessous)."""


@dataclass(frozen=True)
class Resultat:
    statut: int  # 200, 409 ou 422
    corps: Json
    rejoue: bool = False


def _champs(params: Json, requis: frozenset[str], facultatifs: frozenset[str]) -> None:
    if not requis <= params.keys() or not params.keys() <= requis | facultatifs:
        attendus = [*sorted(requis), *(f"{f}?" for f in sorted(facultatifs))]
        raise RequeteInvalide(f"paramètres attendus : {', '.join(attendus) or 'aucun'}")


def _texte(params: Json, cle: str) -> str:
    valeur = params.get(cle)
    if not isinstance(valeur, str) or not 0 < len(valeur) <= 128:
        raise RequeteInvalide(f"{cle} : texte attendu")
    return valeur


def _plan(base: Base, ctx: Contexte, params: Json) -> PlanAcces:
    """Le plan du jour demandé (`jour`, AAAA-MM-JJ ; défaut : aujourd'hui pour l'élève)."""
    jour = ctx.jour
    if "jour" in params:
        try:
            jour = date.fromisoformat(_texte(params, "jour"))
        except ValueError:
            raise RequeteInvalide("jour : AAAA-MM-JJ attendu") from None
    plan = base.plan_de(ctx.eleve.brainiac_id, jour)
    if plan is None:
        raise RetourRefuse(f"aucun ticket le {jour.isoformat()}")
    return plan


def _noter(base: Base, ctx: Contexte, params: Json) -> Json:
    _champs(params, frozenset({"question_id", "note"}), frozenset({"jour"}))
    question, note = _texte(params, "question_id"), params["note"]
    if type(note) is not int:
        raise RequeteInvalide("note : entier de 1 à 4 attendu")
    plan = _plan(base, ctx, params)
    resultat = noter(base, ctx.racine, plan, question, note, ctx.instant, CANAL)
    jour = plan.jour.isoformat()
    return {"jour": jour, "question_id": question, "note": note, "resultat": resultat}


def _joker(base: Base, ctx: Contexte, params: Json) -> Json:
    _champs(params, frozenset(), frozenset({"jour"}))
    plan = _plan(base, ctx, params)
    joker(base, ctx.racine, plan, ctx.instant)
    return {"jour": plan.jour.isoformat(), "joker": True}


def _choisir_carte(base: Base, ctx: Contexte, params: Json) -> Json:
    _champs(params, frozenset({"carte_id"}), frozenset({"quete_id"}))
    carte = _texte(params, "carte_id")
    quete = None if params.get("quete_id") is None else _texte(params, "quete_id")
    valider_inscription(charger(ctx.racine / "bibliotheque"), carte, quete)
    base.inscrire(ctx.eleve.brainiac_id, carte, quete)
    return {"carte_id": carte, "quete_id": quete}


FAIRE: dict[str, Callable[[Base, Contexte, Json], Json]] = {
    "noter": _noter,
    "joker": _joker,
    "choisir_carte": _choisir_carte,
}


def _empreinte(nom: str, params: Json) -> str:
    """Empreinte canonique : ordre des clés indifférent, `null` = paramètre absent."""
    presents = {cle: valeur for cle, valeur in params.items() if valeur is not None}
    canon = json.dumps({"action": nom, "params": presents}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _rejouer(connue: tuple[str, str, str], nom: str, signature: str) -> Resultat:
    if connue[:2] != (nom, signature):
        motif = "clé d'idempotence déjà utilisée pour une autre requête"
        return Resultat(409, {"ok": False, "motif": motif})
    enregistree = json.loads(connue[2])
    return Resultat(int(enregistree["statut"]), enregistree["corps"], rejoue=True)


def traiter(
    base: Base, ctx: Contexte, nom: str, params: object, cle: str, verrou: threading.Lock
) -> Resultat:
    """Exécute l'action `nom` une seule fois pour cette clé et cet élève ; `RequeteInvalide`
    si les paramètres sont mal formés, `EnvoiConcurrent` ou `NonEnregistree` si rien n'a pu
    être enregistré (la clé reste libre dans les trois cas)."""
    if not isinstance(params, dict):
        raise RequeteInvalide("paramètres : objet JSON attendu")
    signature, brainiac_id = _empreinte(nom, params), ctx.eleve.brainiac_id
    with verrou:  # une seule API par racine : vérifier, agir et enregistrer sans entrelacement
        connue = base.requete_adviza(brainiac_id, cle)
        if connue is not None:
            return _rejouer(connue, nom, signature)
        try:
            resultat = Resultat(200, {"ok": True, "effet": FAIRE[nom](base, ctx, params)})
        except EnvoiConcurrent:
            raise  # passager : ne rien figer
        except (RetourRefuse, Refus) as refus:
            resultat = Resultat(422, {"ok": False, "motif": str(refus)})
        reponse = json.dumps(
            {"statut": resultat.statut, "corps": resultat.corps}, ensure_ascii=False
        )
        try:
            nouvelle = base.enregistrer_requete_adviza(brainiac_id, cle, nom, signature, reponse)
        except ErreurSQLite as erreur:
            raise NonEnregistree(str(erreur)) from erreur
        if not nouvelle:  # prise entre-temps (autre processus) : la première fait foi
            connue = base.requete_adviza(brainiac_id, cle)
            if connue is None:
                raise NonEnregistree(f"clé {cle} annoncée prise mais introuvable")
            return _rejouer(connue, nom, signature)
        return resultat
