import pandas as pd
import numpy as np
import re
import unicodedata
from datetime import datetime


# ==========================================================
# 1. LISTE OFFICIELLE DES CHARGEUSES SISE
# ==========================================================

CHARGEUSES_SISE = [
    "N012009",
    "N012010",
    "N022012",
    "N022013",
    "N032008",
    "N032009",
    "N042003",
    "N042004",
    "N052001",
    "N052002",
]


# ==========================================================
# 2. MOIS FRANCAIS
# ==========================================================

MOIS_FR = {
    "janvier": 1,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "decembre": 12,
}


# ==========================================================
# 3. NORMALISATION DU TEXTE
# ==========================================================

def normaliser_texte(texte):

    if texte is None:
        return ""

    texte = str(texte)

    texte = unicodedata.normalize(
        "NFD",
        texte
    )

    texte = "".join(
        caractere
        for caractere in texte
        if unicodedata.category(caractere) != "Mn"
    )

    return texte.strip().lower()


# ==========================================================
# 4. PREPARER UNE SOURCE EXCEL
# ==========================================================

def preparer_source(source):

    # Flask FileStorage
    if hasattr(source, "stream"):

        source.stream.seek(0)
        return source.stream

    # fichier déjà ouvert
    if hasattr(source, "seek"):

        source.seek(0)

    return source


# ==========================================================
# 5. TROUVER LA LIGNE D'EN-TETE
# ==========================================================

def trouver_ligne_entete(source, feuille):

    source_preparee = preparer_source(source)

    brut = pd.read_excel(
        source_preparee,
        sheet_name=feuille,
        header=None
    )

    for i in range(min(20, len(brut))):

        valeurs = [
            normaliser_texte(v)
            for v in brut.iloc[i].tolist()
        ]

        texte_ligne = " | ".join(valeurs)

        if (
            "code engin" in texte_ligne
            or "engin" in texte_ligne
        ):
            return i

    raise ValueError(
        f"Impossible de trouver la ligne d'en-tête "
        f"dans la feuille '{feuille}'."
    )


# ==========================================================
# 6. TROUVER LA FEUILLE UTILE
# ==========================================================

def trouver_feuille(source):

    source_preparee = preparer_source(source)

    excel = pd.ExcelFile(
        source_preparee
    )

    for feuille in excel.sheet_names:

        try:

            source_preparee = preparer_source(source)

            brut = pd.read_excel(
                source_preparee,
                sheet_name=feuille,
                header=None
            )

            texte = " ".join(
                normaliser_texte(v)
                for v in brut.head(15).values.flatten()
                if not pd.isna(v)
            )

            if "code engin" in texte:
                return feuille

        except Exception:
            continue

    raise ValueError(
        "Aucune feuille contenant les engins n'a été trouvée."
    )


# ==========================================================
# 7. LIRE AUTOMATIQUEMENT UNE FEUILLE
# ==========================================================

def lire_feuille(source):

    feuille = trouver_feuille(
        source
    )

    ligne_entete = trouver_ligne_entete(
        source,
        feuille
    )

    source_preparee = preparer_source(source)

    df = pd.read_excel(
        source_preparee,
        sheet_name=feuille,
        header=ligne_entete
    )

    return df, feuille


# ==========================================================
# 8. TROUVER UNE COLONNE
# ==========================================================

def trouver_colonne(df, mots):

    for colonne in df.columns:

        nom = normaliser_texte(
            colonne
        )

        if all(
            mot in nom
            for mot in mots
        ):
            return colonne

    return None


# ==========================================================
# 9. COLONNE CODE ENGIN
# ==========================================================

def trouver_colonne_engin(df):

    for colonne in df.columns:

        nom = normaliser_texte(
            colonne
        )

        if (
            "code" in nom
            and "engin" in nom
        ):
            return colonne

    for colonne in df.columns:

        if "engin" in normaliser_texte(colonne):
            return colonne

    raise ValueError(
        "La colonne Code Engin est introuvable."
    )


# ==========================================================
# 10. NETTOYER LES CODES ENGIN
# ==========================================================

def nettoyer_codes(df, colonne_engin):

    df = df.copy()

    df[colonne_engin] = (
        df[colonne_engin]
        .astype(str)
        .str.replace(
            r"\s+",
            "",
            regex=True
        )
        .str.strip()
        .str.upper()
    )

    return df


# ==========================================================
# 11. EXTRAIRE MOIS ET ANNEE D'UN TEXTE
# ==========================================================

def extraire_periode_texte(texte):

    texte_normalise = normaliser_texte(
        texte
    )

    mois = None
    annee = None

    for nom_mois, numero in MOIS_FR.items():

        if nom_mois in texte_normalise:

            mois = numero
            break

    recherche_annee = re.search(
        r"\b(20\d{2})\b",
        texte_normalise
    )

    if recherche_annee:

        annee = int(
            recherche_annee.group(1)
        )

    return mois, annee


# ==========================================================
# 12. EXTRAIRE LA PERIODE D'UN FICHIER
# ==========================================================

def detecter_periode(source, feuille, df):

    mois = None
    annee = None

    # ------------------------------------------------------
    # ESSAI 1 : NOM DE LA FEUILLE
    # ------------------------------------------------------

    mois_feuille, annee_feuille = (
        extraire_periode_texte(
            feuille
        )
    )

    if mois_feuille is not None:
        mois = mois_feuille

    if annee_feuille is not None:
        annee = annee_feuille

    # ------------------------------------------------------
    # ESSAI 2 : TITRE DU FICHIER
    # ------------------------------------------------------

    if mois is None or annee is None:

        source_preparee = preparer_source(
            source
        )

        brut = pd.read_excel(
            source_preparee,
            sheet_name=feuille,
            header=None,
            nrows=5
        )

        texte_titre = " ".join(
            str(v)
            for v in brut.values.flatten()
            if not pd.isna(v)
        )

        mois_titre, annee_titre = (
            extraire_periode_texte(
                texte_titre
            )
        )

        if mois is None:
            mois = mois_titre

        if annee is None:
            annee = annee_titre

    # ------------------------------------------------------
    # ESSAI 3 : NOMS DE COLONNES TYPE 01/07
    # ------------------------------------------------------

    if mois is None:

        for colonne in df.columns:

            recherche = re.search(
                r"\b\d{1,2}/(\d{1,2})\b",
                str(colonne)
            )

            if recherche:

                mois = int(
                    recherche.group(1)
                )
                break

    if mois is None or annee is None:

        raise ValueError(
            "Impossible d'identifier automatiquement "
            "la période du fichier."
        )

    return mois, annee


# ==========================================================
# 13. PREPARER LE FICHIER CARBURANT
# ==========================================================

def lire_carburant(source):

    df, feuille = lire_feuille(
        source
    )

    colonne_engin = trouver_colonne_engin(
        df
    )

    df = nettoyer_codes(
        df,
        colonne_engin
    )

    # ------------------------------------------------------
    # TOTAL CARBURANT
    # ------------------------------------------------------

    colonne_total = None

    for colonne in df.columns:

        if normaliser_texte(colonne) == "total":

            colonne_total = colonne
            break

    if colonne_total is None:

        raise ValueError(
            "La colonne TOTAL du fichier carburant "
            "est introuvable."
        )

    # ------------------------------------------------------
    # MATRICULE ET MODELE
    # ------------------------------------------------------

    colonne_matricule = trouver_colonne(
        df,
        ["matricule"]
    )

    colonne_modele = trouver_colonne(
        df,
        ["modele"]
    )

    mois, annee = detecter_periode(
        source,
        feuille,
        df
    )

    # ------------------------------------------------------
    # FILTRE DES 10 CHARGEUSES
    # ------------------------------------------------------

    df = df[
        df[colonne_engin].isin(
            CHARGEUSES_SISE
        )
    ].copy()

    resultat = pd.DataFrame()

    resultat["engin"] = (
        df[colonne_engin]
    )

    resultat["litres"] = pd.to_numeric(
        df[colonne_total],
        errors="coerce"
    )

    if colonne_matricule is not None:

        resultat["matricule"] = (
            df[colonne_matricule]
        )

    else:

        resultat["matricule"] = np.nan

    if colonne_modele is not None:

        resultat["modele"] = (
            df[colonne_modele]
        )

    else:

        resultat["modele"] = np.nan

    return (
        resultat,
        mois,
        annee
    )


# ==========================================================
# 14. EXTRAIRE DATE D'UNE COLONNE COMPTEUR
# ==========================================================

def extraire_jour_mois_colonne(colonne):

    texte = str(
        colonne
    )

    recherche = re.search(
        r"(\d{1,2})/(\d{1,2})",
        texte
    )

    if not recherche:

        return None

    jour = int(
        recherche.group(1)
    )

    mois = int(
        recherche.group(2)
    )

    return jour, mois


# ==========================================================
# 15. TROUVER LES COLONNES COMPTEUR
# ==========================================================

def trouver_colonnes_compteur(df):

    candidats = []

    for colonne in df.columns:

        nom = normaliser_texte(
            colonne
        )

        date = extraire_jour_mois_colonne(
            colonne
        )

        if (
            date is not None
            and (
                "releve" in nom
                or "compteur" in nom
            )
        ):

            candidats.append(
                (
                    colonne,
                    date[0],
                    date[1]
                )
            )

    if len(candidats) >= 2:

        candidats = sorted(
            candidats,
            key=lambda x: (
                x[2],
                x[1]
            )
        )

        debut = candidats[0][0]
        fin = candidats[-1][0]

        return debut, fin

    # ------------------------------------------------------
    # FALLBACK : noms début / fin
    # ------------------------------------------------------

    debut = None
    fin = None

    for colonne in df.columns:

        nom = normaliser_texte(
            colonne
        )

        if (
            "compteur" in nom
            and "debut" in nom
        ):
            debut = colonne

        if (
            "compteur" in nom
            and "fin" in nom
        ):
            fin = colonne

    if debut is not None and fin is not None:

        return debut, fin

    raise ValueError(
        "Impossible d'identifier les deux relevés "
        "du compteur horaire."
    )


# ==========================================================
# 16. PREPARER LE FICHIER COMPTEUR
# ==========================================================

def lire_compteur(source):

    df, feuille = lire_feuille(
        source
    )

    colonne_engin = trouver_colonne_engin(
        df
    )

    df = nettoyer_codes(
        df,
        colonne_engin
    )

    colonne_debut, colonne_fin = (
        trouver_colonnes_compteur(
            df
        )
    )

    mois, annee = detecter_periode(
        source,
        feuille,
        df
    )

    df = df[
        df[colonne_engin].isin(
            CHARGEUSES_SISE
        )
    ].copy()

    resultat = pd.DataFrame()

    resultat["engin"] = (
        df[colonne_engin]
    )

    resultat["compteur_debut"] = (
        pd.to_numeric(
            df[colonne_debut],
            errors="coerce"
        )
    )

    resultat["compteur_fin"] = (
        pd.to_numeric(
            df[colonne_fin],
            errors="coerce"
        )
    )

    return (
        resultat,
        mois,
        annee
    )


# ==========================================================
# 17. CLASSIFICATION QUALITE DES DONNEES
# ==========================================================

def classifier_donnee(row):

    litres = row["litres"]

    compteur_debut = (
        row["compteur_debut"]
    )

    compteur_fin = (
        row["compteur_fin"]
    )

    heures = row["heures"]

    # ------------------------------------------------------
    # DONNEES MANQUANTES
    # ------------------------------------------------------

    if (
        pd.isna(litres)
        or pd.isna(compteur_debut)
        or pd.isna(compteur_fin)
    ):

        return "DONNEE_MANQUANTE"

    # ------------------------------------------------------
    # VALEURS NEGATIVES
    # ------------------------------------------------------

    if (
        litres < 0
        or compteur_debut < 0
        or compteur_fin < 0
    ):

        return "DONNEE_INCORRECTE"

    # ------------------------------------------------------
    # COMPTEUR QUI DIMINUE
    # ------------------------------------------------------

    if compteur_fin < compteur_debut:

        return "DONNEE_INCORRECTE"

    # ------------------------------------------------------
    # ENGINS SANS ACTIVITE
    # ------------------------------------------------------

    if (
        heures == 0
        and litres == 0
    ):

        return "SANS_ACTIVITE"

    # ------------------------------------------------------
    # CARBURANT SANS ACTIVITE
    # ------------------------------------------------------

    if (
        heures == 0
        and litres > 0
    ):

        return "DONNEE_INCORRECTE"

    # ------------------------------------------------------
    # ACTIVITE SANS CARBURANT
    # ------------------------------------------------------

    if (
        heures > 0
        and litres == 0
    ):

        return "DONNEE_INCORRECTE"

    # ------------------------------------------------------
    # DONNEE VALIDE
    # ------------------------------------------------------

    if (
        heures > 0
        and litres > 0
    ):

        return "VALIDE"

    return "DONNEE_INCORRECTE"


# ==========================================================
# 18. ANALYSE GENERIQUE DES DEUX FICHIERS
# ==========================================================

def analyser_nouveaux_fichiers(
    fichier_carburant,
    fichier_compteur
):

    # ------------------------------------------------------
    # LIRE CARBURANT
    # ------------------------------------------------------

    carburant, mois_carburant, annee_carburant = (
        lire_carburant(
            fichier_carburant
        )
    )

    # ------------------------------------------------------
    # LIRE COMPTEUR
    # ------------------------------------------------------

    compteur, mois_compteur, annee_compteur = (
        lire_compteur(
            fichier_compteur
        )
    )

    # ------------------------------------------------------
    # VERIFIER MEME PERIODE
    # ------------------------------------------------------

    if (
        mois_carburant != mois_compteur
        or annee_carburant != annee_compteur
    ):

        raise ValueError(
            "Les deux fichiers ne correspondent pas "
            "à la même période. "
            f"Carburant : {mois_carburant}/{annee_carburant} - "
            f"Compteur : {mois_compteur}/{annee_compteur}"
        )

    mois = mois_carburant
    annee = annee_carburant

    # ------------------------------------------------------
    # CREER UNE BASE AVEC LES 10 CHARGEUSES
    # ------------------------------------------------------

    resultat = pd.DataFrame(
        {
            "engin":
                CHARGEUSES_SISE
        }
    )

    # ------------------------------------------------------
    # AJOUT CARBURANT
    # ------------------------------------------------------

    resultat = resultat.merge(
        carburant,
        on="engin",
        how="left"
    )

    # ------------------------------------------------------
    # AJOUT COMPTEUR
    # ------------------------------------------------------

    resultat = resultat.merge(
        compteur,
        on="engin",
        how="left"
    )

    # ------------------------------------------------------
    # CALCUL DES HEURES
    # ------------------------------------------------------

    resultat["heures"] = (
        resultat["compteur_fin"]
        - resultat["compteur_debut"]
    )

    # ------------------------------------------------------
    # CALCUL DU L/H
    # ------------------------------------------------------

    resultat["lh_reel"] = np.where(
        resultat["heures"] > 0,
        resultat["litres"]
        / resultat["heures"],
        np.nan
    )

    # ------------------------------------------------------
    # PERIODE
    # ------------------------------------------------------

    resultat["annee"] = annee
    resultat["mois"] = mois

    resultat["date"] = pd.Timestamp(
        year=annee,
        month=mois,
        day=1
    )

    # ------------------------------------------------------
    # QUALITE
    # ------------------------------------------------------

    resultat["statut_donnee"] = (
        resultat.apply(
            classifier_donnee,
            axis=1
        )
    )

    # ------------------------------------------------------
    # ARRONDIS
    # ------------------------------------------------------

    resultat["heures"] = (
        resultat["heures"]
        .round(2)
    )

    resultat["litres"] = (
        resultat["litres"]
        .round(2)
    )

    resultat["lh_reel"] = (
        resultat["lh_reel"]
        .round(2)
    )

    # ------------------------------------------------------
    # ORDRE FINAL
    # ------------------------------------------------------

    resultat = resultat[
        [
            "date",
            "annee",
            "mois",
            "engin",
            "matricule",
            "modele",
            "compteur_debut",
            "compteur_fin",
            "heures",
            "litres",
            "lh_reel",
            "statut_donnee",
        ]
    ]

    return resultat