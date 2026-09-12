import os
import io
import json

import numpy as np
import pandas as pd
import qrcode

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_file,
    Response,
    flash
)

from analyse_nouvelles_donnees import analyser_nouveaux_fichiers
from moteur_sise import analyser_avec_sise


# ==========================================================
# 1. CONFIGURATION
# ==========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "SISE-MARSA-MAROC-2026"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMP_DIR = os.path.join(
    BASE_DIR,
    "temp_sise"
)

os.makedirs(
    TEMP_DIR,
    exist_ok=True
)

FICHIER_RESULTATS_TEMP = os.path.join(
    TEMP_DIR,
    "resultats_courants.json"
)

FICHIER_HISTORIQUE = os.path.join(
    BASE_DIR,
    "dataset_historique_final.xlsx"
)

app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024


# ==========================================================
# 2. MOIS
# ==========================================================

MOIS_FR = {
    1: "Janvier",
    2: "Février",
    3: "Mars",
    4: "Avril",
    5: "Mai",
    6: "Juin",
    7: "Juillet",
    8: "Août",
    9: "Septembre",
    10: "Octobre",
    11: "Novembre",
    12: "Décembre"
}


# ==========================================================
# 3. CONVERSION VALEURS
# ==========================================================

def valeur_simple(valeur):

    if valeur is None:
        return None

    if isinstance(valeur, np.integer):
        return int(valeur)

    if isinstance(valeur, np.floating):

        if np.isnan(valeur):
            return None

        return float(valeur)

    if isinstance(valeur, pd.Timestamp):

        return valeur.strftime(
            "%Y-%m-%d"
        )

    try:

        if pd.isna(valeur):
            return None

    except Exception:
        pass

    return valeur


# ==========================================================
# 4. DATAFRAME -> LISTE
# ==========================================================

def dataframe_vers_records(df):

    records = []

    for _, ligne in df.iterrows():

        element = {}

        for colonne in df.columns:

            element[colonne] = valeur_simple(
                ligne[colonne]
            )

        records.append(element)

    return records


# ==========================================================
# 5. SAUVEGARDE TEMPORAIRE
# ==========================================================

def sauvegarder_resultats_temp(
    df,
    periode
):

    contenu = {
        "periode": periode,
        "resultats": dataframe_vers_records(df)
    }

    with open(
        FICHIER_RESULTATS_TEMP,
        "w",
        encoding="utf-8"
    ) as fichier:

        json.dump(
            contenu,
            fichier,
            ensure_ascii=False,
            indent=2
        )


# ==========================================================
# 6. CHARGER RESULTATS TEMPORAIRES
# ==========================================================

def charger_resultats_temp():

    if not os.path.exists(
        FICHIER_RESULTATS_TEMP
    ):

        return None, None

    try:

        with open(
            FICHIER_RESULTATS_TEMP,
            "r",
            encoding="utf-8"
        ) as fichier:

            contenu = json.load(fichier)

        records = contenu.get(
            "resultats",
            []
        )

        periode = contenu.get(
            "periode"
        )

        if not records:
            return None, None

        return (
            pd.DataFrame(records),
            periode
        )

    except Exception as erreur:

        print(
            "Erreur lecture temporaire :",
            repr(erreur)
        )

        return None, None


# ==========================================================
# 7. SUPPRIMER RESULTATS TEMPORAIRES
# ==========================================================

def supprimer_resultats_temp():

    if os.path.exists(
        FICHIER_RESULTATS_TEMP
    ):

        try:

            os.remove(
                FICHIER_RESULTATS_TEMP
            )

        except Exception:
            pass


# ==========================================================
# 8. CREER NOM PERIODE
# ==========================================================

def creer_periode(
    mois,
    annee
):

    try:

        mois = int(mois)
        annee = int(annee)

        nom_mois = MOIS_FR.get(
            mois,
            str(mois)
        )

        return f"{nom_mois} {annee}"

    except Exception:

        return "Période analysée"


# ==========================================================
# 9. NOM DE L'ETAT
# ==========================================================

def nom_etat(couleur):

    couleur = str(
        couleur
    ).upper()

    if couleur == "ROUGE":
        return "Surconsommation"

    if couleur == "ORANGE":
        return "Sous-consommation"

    if couleur == "JAUNE":
        return "À surveiller"

    if couleur == "VERT":
        return "Normal"

    if couleur == "GRIS":
        return "Historique insuffisant"

    return "Non disponible"


# ==========================================================
# 10. PREPARER DASHBOARD
# ==========================================================

def preparer_chargeuses(
    df,
    periode
):

    chargeuses = []
    cartes = []

    for _, ligne in df.iterrows():

        engin = str(
            ligne.get(
                "engin",
                ""
            )
        ).strip()

        couleur = str(
            ligne.get(
                "couleur",
                "GRIS"
            )
        ).upper()

        lh = valeur_simple(
            ligne.get(
                "lh_reel",
                None
            )
        )

        reference = valeur_simple(
            ligne.get(
                "lh_mediane_historique",
                ligne.get(
                    "reference_historique",
                    None
                )
            )
        )

        robust_z = valeur_simple(
            ligne.get(
                "robust_z_lh",
                ligne.get(
                    "robust_z",
                    None
                )
            )
        )

        vote_total = valeur_simple(
            ligne.get(
                "vote_total",
                0
            )
        )

        heures = valeur_simple(
            ligne.get(
                "heures",
                None
            )
        )

        litres = valeur_simple(
            ligne.get(
                "litres",
                None
            )
        )

        fiabilite = str(
            ligne.get(
                "niveau_fiabilite",
                ""
            )
        )

        etat = nom_etat(
            couleur
        )

        chargeuses.append(
            {
                "engin": engin,
                "lh": lh,
                "referenceHistorique": reference,
                "couleur": couleur,
                "etat": etat,
                "robustZ": robust_z,
                "voteML": vote_total,
                "fiabilite": fiabilite,
                "heures": heures,
                "litres": litres
            }
        )

        cartes.append(
            {
                "engin": engin,
                "couleur": couleur,
                "periode": periode,
                "lh": lh,
                "etat": etat
            }
        )

    return chargeuses, cartes


# ==========================================================
# 11. KPI
# ==========================================================

def creer_resume(chargeuses):

    resume = {
        "total": len(chargeuses),
        "rouge": 0,
        "orange": 0,
        "jaune": 0,
        "vert": 0,
        "gris": 0
    }

    for chargeuse in chargeuses:

        couleur = chargeuse.get(
            "couleur",
            "GRIS"
        )

        if couleur == "ROUGE":
            resume["rouge"] += 1

        elif couleur == "ORANGE":
            resume["orange"] += 1

        elif couleur == "JAUNE":
            resume["jaune"] += 1

        elif couleur == "VERT":
            resume["vert"] += 1

        else:
            resume["gris"] += 1

    return resume


# ==========================================================
# 12. ACCUEIL
# ==========================================================
#
# C'EST TOUJOURS LA PREMIERE PAGE.
#
# ==========================================================

@app.route("/")
def accueil():

    return render_template(
        "donnees.html"
    )


# ==========================================================
# 13. PAGE IMPORTATION
# ==========================================================

@app.route("/donnees")
def donnees():

    return redirect(
        url_for("accueil")
    )


# ==========================================================
# 14. ANALYSE
# ==========================================================

@app.route(
    "/analyser",
    methods=["POST"]
)
def analyser():

    fichier_carburant = request.files.get(
        "fichier_carburant"
    )

    fichier_compteur = request.files.get(
        "fichier_compteur"
    )

    # ------------------------------------------------------
    # VERIFIER LES DEUX FICHIERS
    # ------------------------------------------------------

    if (
        fichier_carburant is None
        or fichier_compteur is None
    ):

        flash(
            "Veuillez sélectionner les deux fichiers."
        )

        return redirect(
            url_for("accueil")
        )

    if (
        fichier_carburant.filename == ""
        or fichier_compteur.filename == ""
    ):

        flash(
            "Veuillez sélectionner les deux fichiers."
        )

        return redirect(
            url_for("accueil")
        )

    if not fichier_carburant.filename.lower().endswith(
        ".xlsx"
    ):

        flash(
            "Le fichier carburant doit être au format .xlsx."
        )

        return redirect(
            url_for("accueil")
        )

    if not fichier_compteur.filename.lower().endswith(
        ".xlsx"
    ):

        flash(
            "Le fichier compteur doit être au format .xlsx."
        )

        return redirect(
            url_for("accueil")
        )

    try:

        # ==================================================
        # 1. LECTURE DES NOUVEAUX FICHIERS
        # ==================================================

        nouvelles_donnees = (
            analyser_nouveaux_fichiers(
                fichier_carburant,
                fichier_compteur
            )
        )

        if nouvelles_donnees is None:

            raise ValueError(
                "Aucune donnée extraite."
            )

        if nouvelles_donnees.empty:

            raise ValueError(
                "Aucune donnée exploitable."
            )

        # ==================================================
        # 2. MOTEUR SISE
        # ==================================================

        resultats = analyser_avec_sise(
            nouvelles_donnees
        )

        if resultats is None:

            raise ValueError(
                "Le moteur SISE n'a retourné aucun résultat."
            )

        if not isinstance(
            resultats,
            pd.DataFrame
        ):

            resultats = pd.DataFrame(
                resultats
            )

        if resultats.empty:

            raise ValueError(
                "Aucun résultat SISE."
            )

        # ==================================================
        # 3. PERIODE
        # ==================================================

        if (
            "mois" in nouvelles_donnees.columns
            and
            "annee" in nouvelles_donnees.columns
        ):

            mois = nouvelles_donnees[
                "mois"
            ].iloc[0]

            annee = nouvelles_donnees[
                "annee"
            ].iloc[0]

            periode = creer_periode(
                mois,
                annee
            )

        else:

            periode = "Période analysée"

        # ==================================================
        # 4. SAUVEGARDE TEMPORAIRE
        # ==================================================

        sauvegarder_resultats_temp(
            resultats,
            periode
        )

        # ==================================================
        # 5. DASHBOARD
        # ==================================================

        return redirect(
            url_for("dashboard")
        )

    except Exception as erreur:

        print(
            "ERREUR ANALYSE SISE :",
            repr(erreur)
        )

        flash(
            "Erreur pendant l'analyse : "
            + str(erreur)
        )

        return redirect(
            url_for("accueil")
        )


# ==========================================================
# 15. DASHBOARD
# ==========================================================

@app.route("/dashboard")
def dashboard():

    df, periode = (
        charger_resultats_temp()
    )

    # Dashboard impossible avant une analyse
    if df is None:

        return redirect(
            url_for("accueil")
        )

    chargeuses, cartes = (
        preparer_chargeuses(
            df,
            periode
        )
    )

    resume = creer_resume(
        chargeuses
    )

    return render_template(
        "index.html",

        chargeuses=chargeuses,

        cartes=cartes,

        resume=resume,

        total=resume["total"],
        nb_rouge=resume["rouge"],
        nb_orange=resume["orange"],
        nb_jaune=resume["jaune"],
        nb_vert=resume["vert"],
        nb_gris=resume["gris"],

        mois_importe=True,

        periode_importee=periode
    )


# ==========================================================
# 16. DETAIL D'UNE CHARGEUSE
# ==========================================================

@app.route(
    "/chargeuse/<engin>"
)
def detail_chargeuse(engin):

    df, periode = (
        charger_resultats_temp()
    )

    if df is None:

        return redirect(
            url_for("accueil")
        )

    if "engin" not in df.columns:

        return (
            "Colonne engin introuvable.",
            500
        )

    selection = df[
        df["engin"]
        .astype(str)
        .str.strip()
        ==
        str(engin).strip()
    ]

    if selection.empty:

        return (
            "Chargeuse introuvable.",
            404
        )

    ligne = selection.iloc[0]

    couleur = str(
        ligne.get(
            "couleur",
            "GRIS"
        )
    ).upper()

    data = {

        "engin": engin,

        "periode": periode,

        "couleur": couleur,

        "etat": nom_etat(
            couleur
        ),

        "lh_reel": valeur_simple(
            ligne.get(
                "lh_reel",
                None
            )
        ),

        "reference_historique": valeur_simple(
            ligne.get(
                "lh_mediane_historique",
                ligne.get(
                    "reference_historique",
                    None
                )
            )
        ),

        "heures": valeur_simple(
            ligne.get(
                "heures",
                None
            )
        ),

        "litres": valeur_simple(
            ligne.get(
                "litres",
                None
            )
        ),

        "type_anomalie": str(
            ligne.get(
                "type_anomalie",
                "NON_DISPONIBLE"
            )
        ),

        "ecart_lh_pct": valeur_simple(
            ligne.get(
                "ecart_lh_pct",
                None
            )
        ),

        "robust_z": valeur_simple(
            ligne.get(
                "robust_z_lh",
                ligne.get(
                    "robust_z",
                    None
                )
            )
        ),

        "ratio_activite": valeur_simple(
            ligne.get(
                "ratio_heures_historique",
                None
            )
        ),

        "vote_total": valeur_simple(
            ligne.get(
                "vote_total",
                0
            )
        ),

        "vote_IF": valeur_simple(
            ligne.get(
                "vote_IF",
                0
            )
        ),

        "vote_LOF": valeur_simple(
            ligne.get(
                "vote_LOF",
                0
            )
        ),

        "vote_OCSVM": valeur_simple(
            ligne.get(
                "vote_OCSVM",
                0
            )
        ),

        "niveau_fiabilite": str(
            ligne.get(
                "niveau_fiabilite",
                "NON_DISPONIBLE"
            )
        ),

        "raison_fiabilite": str(
            ligne.get(
                "raison_fiabilite",
                ""
            )
        ),

        "explication": str(
            ligne.get(
                "analyse_detaillee_SISE",
                ligne.get(
                    "explication_type_anomalie",
                    ""
                )
            )
        ),

        "action": str(
            ligne.get(
                "action_recommandee",
                ""
            )
        ),

        "nouveau_mois": True
    }

    # ======================================================
    # HISTORIQUE POUR LE GRAPHIQUE
    # ======================================================

    history = []

    if os.path.exists(
        FICHIER_HISTORIQUE
    ):

        try:

            historique = pd.read_excel(
                FICHIER_HISTORIQUE,
                sheet_name="Donnees_valides"
            )

            if "engin" in historique.columns:

                historique["engin"] = (
                    historique["engin"]
                    .astype(str)
                    .str.strip()
                )

                historique_engin = historique[
                    historique["engin"]
                    ==
                    str(engin).strip()
                ].copy()

                if "date" in historique_engin.columns:

                    historique_engin["date"] = (
                        pd.to_datetime(
                            historique_engin["date"],
                            errors="coerce"
                        )
                    )

                    historique_engin = (
                        historique_engin
                        .sort_values("date")
                    )

                for _, hist in historique_engin.iterrows():

                    date_hist = hist.get(
                        "date",
                        None
                    )

                    if isinstance(
                        date_hist,
                        pd.Timestamp
                    ):

                        nom_periode = (
                            date_hist.strftime(
                                "%m/%Y"
                            )
                        )

                    else:

                        nom_periode = str(
                            date_hist
                        )

                    history.append(
                        {
                            "periode": nom_periode,

                            "lh_reel": valeur_simple(
                                hist.get(
                                    "lh_reel",
                                    None
                                )
                            ),

                            "nouveau": False
                        }
                    )

        except Exception as erreur:

            print(
                "ERREUR HISTORIQUE :",
                repr(erreur)
            )

    # Nouveau mois uniquement pour l'affichage
    history.append(
        {
            "periode": periode,

            "lh_reel": data[
                "lh_reel"
            ],

            "nouveau": True
        }
    )

    return render_template(
        "detail.html",
        data=data,
        history=history
    )


# ==========================================================
# 17. QR CODE
# ==========================================================

@app.route(
    "/qr/<engin>.png"
)
def qr_chargeuse(engin):

    adresse = url_for(
        "detail_chargeuse",
        engin=engin,
        _external=True
    )

    qr = qrcode.QRCode(
        version=1,
        box_size=8,
        border=2
    )

    qr.add_data(
        adresse
    )

    qr.make(
        fit=True
    )

    image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG"
    )

    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="image/png"
    )


# ==========================================================
# 18. EXPORT CSV
# ==========================================================

@app.route(
    "/export-csv"
)
def export_csv():

    df, periode = (
        charger_resultats_temp()
    )

    if df is None:

        return redirect(
            url_for("accueil")
        )

    csv = df.to_csv(
        index=False,
        sep=";",
        encoding="utf-8-sig"
    )

    return Response(
        "\ufeff" + csv,

        mimetype="text/csv",

        headers={
            "Content-Disposition":
            "attachment; filename=resultats_SISE.csv"
        }
    )


# ==========================================================
# 19. NOUVELLE ANALYSE
# ==========================================================

@app.route(
    "/nouvelle-analyse"
)
def nouvelle_analyse():

    supprimer_resultats_temp()

    return redirect(
        url_for("accueil")
    )


# ==========================================================
# 20. LANCEMENT LOCAL
# ==========================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )