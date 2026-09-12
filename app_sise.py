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

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

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

app.config["MAX_CONTENT_LENGTH"] = (
    20 * 1024 * 1024
)


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
    12: "Décembre",
}


# ==========================================================
# 3. VALEUR SIMPLE
# ==========================================================

def valeur_simple(valeur):

    if valeur is None:
        return None

    if isinstance(
        valeur,
        np.integer
    ):
        return int(valeur)

    if isinstance(
        valeur,
        np.floating
    ):

        if np.isnan(valeur):
            return None

        return float(valeur)

    if isinstance(
        valeur,
        pd.Timestamp
    ):

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
# 4. DATAFRAME -> RECORDS
# ==========================================================

def dataframe_vers_records(df):

    records = []

    for _, ligne in df.iterrows():

        element = {}

        for colonne in df.columns:

            element[colonne] = (
                valeur_simple(
                    ligne[colonne]
                )
            )

        records.append(
            element
        )

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
        "resultats":
            dataframe_vers_records(df)
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

            contenu = json.load(
                fichier
            )

        records = contenu.get(
            "resultats",
            []
        )

        periode = contenu.get(
            "periode",
            None
        )

        if not records:

            return None, None

        return (
            pd.DataFrame(records),
            periode
        )

    except Exception as erreur:

        print(
            "Erreur lecture résultats temporaires :",
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
# 8. NOM DE PERIODE
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

        return (
            f"{nom_mois} {annee}"
        )

    except Exception:

        return "Période analysée"


# ==========================================================
# 9. NOM AFFICHABLE DE L'ETAT
# ==========================================================

def nom_etat(
    couleur,
    type_anomalie=None
):

    couleur = str(
        couleur
    ).upper()

    type_anomalie = str(
        type_anomalie
        if type_anomalie is not None
        else ""
    ).upper()

    if (
        type_anomalie
        == "DONNEE_NON_EXPLOITABLE"
    ):
        return "Donnée non exploitable"

    if (
        type_anomalie
        == "ANALYSE_INCOMPLETE"
    ):
        return "Analyse incomplète"

    if (
        type_anomalie
        == "HISTORIQUE_INSUFFISANT"
    ):
        return "Historique insuffisant"

    if couleur == "ROUGE":
        return "Surconsommation"

    if couleur == "ORANGE":
        return "Sous-consommation"

    if couleur == "JAUNE":
        return "À surveiller"

    if couleur == "VERT":
        return "Normal"

    return "Non disponible"


# ==========================================================
# 10. PREPARER CHARGEUSES POUR DASHBOARD
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

        # CORRECTION IMPORTANTE
        couleur = str(
            ligne.get(
                "couleur_SISE",
                "GRIS"
            )
        ).upper()

        type_anomalie = str(
            ligne.get(
                "type_anomalie_SISE",
                ""
            )
        )

        etat = nom_etat(
            couleur,
            type_anomalie
        )

        lh = valeur_simple(
            ligne.get(
                "lh_reel",
                None
            )
        )

        reference = valeur_simple(
            ligne.get(
                "lh_mediane_historique",
                None
            )
        )

        robust_z = valeur_simple(
            ligne.get(
                "robust_z_lh",
                None
            )
        )

        vote_total = valeur_simple(
            ligne.get(
                "vote_total",
                0
            )
        )

        vote_if = valeur_simple(
            ligne.get(
                "vote_IF",
                0
            )
        )

        vote_lof = valeur_simple(
            ligne.get(
                "vote_LOF",
                0
            )
        )

        vote_ocsvm = valeur_simple(
            ligne.get(
                "vote_OCSVM",
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
                "NON_EVALUEE"
            )
        )

        confiance_ml = str(
            ligne.get(
                "confiance_ML",
                "NON_EVALUEE"
            )
        )

        item = {

            "engin":
                engin,

            "lh":
                lh,

            "lh_reel":
                lh,

            "referenceHistorique":
                reference,

            "reference_historique":
                reference,

            "couleur":
                couleur,

            "couleur_SISE":
                couleur,

            "etat":
                etat,

            "typeAnomalie":
                type_anomalie,

            "type_anomalie":
                type_anomalie,

            "robustZ":
                robust_z,

            "robust_z":
                robust_z,

            "voteML":
                vote_total,

            "vote_total":
                vote_total,

            "vote_IF":
                vote_if,

            "vote_LOF":
                vote_lof,

            "vote_OCSVM":
                vote_ocsvm,

            "fiabilite":
                fiabilite,

            "niveau_fiabilite":
                fiabilite,

            "confiance_ML":
                confiance_ml,

            "heures":
                heures,

            "litres":
                litres,

            "periode":
                periode
        }

        chargeuses.append(
            item
        )

        cartes.append(
            {
                "engin":
                    engin,

                "couleur":
                    couleur,

                "couleur_SISE":
                    couleur,

                "periode":
                    periode,

                "lh":
                    lh,

                "lh_reel":
                    lh,

                "etat":
                    etat,

                "type_anomalie":
                    type_anomalie
            }
        )

    return (
        chargeuses,
        cartes
    )


# ==========================================================
# 11. KPI
# ==========================================================

def creer_resume(
    chargeuses
):

    resume = {
        "total": len(chargeuses),
        "rouge": 0,
        "orange": 0,
        "jaune": 0,
        "vert": 0,
        "gris": 0
    }

    for chargeuse in chargeuses:

        couleur = str(
            chargeuse.get(
                "couleur",
                "GRIS"
            )
        ).upper()

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

@app.route("/")
def accueil():

    return render_template(
        "donnees.html"
    )


# ==========================================================
# 13. PAGE DONNEES
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

    fichier_carburant = (
        request.files.get(
            "fichier_carburant"
        )
    )

    fichier_compteur = (
        request.files.get(
            "fichier_compteur"
        )
    )

    # ------------------------------------------------------
    # VERIFIER LES FICHIERS
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
        # ETAPE 1 : ANALYSE DES DEUX FICHIERS
        # ==================================================

        nouvelles_donnees = (
            analyser_nouveaux_fichiers(
                fichier_carburant,
                fichier_compteur
            )
        )

        if nouvelles_donnees is None:

            raise ValueError(
                "Aucune donnée n'a été extraite."
            )

        if nouvelles_donnees.empty:

            raise ValueError(
                "Aucune donnée exploitable "
                "n'a été trouvée."
            )

        # ==================================================
        # ETAPE 2 : MOTEUR SISE
        # ==================================================

        resultats = (
            analyser_avec_sise(
                nouvelles_donnees
            )
        )

        if resultats is None:

            raise ValueError(
                "Le moteur SISE n'a retourné "
                "aucun résultat."
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
                "Le moteur SISE n'a produit "
                "aucun diagnostic."
            )

        # ==================================================
        # DEBUG UTILE
        # ==================================================

        print(
            "Colonnes résultats SISE :",
            list(resultats.columns)
        )

        if "couleur_SISE" in resultats.columns:

            print(
                "Répartition couleurs :"
            )

            print(
                resultats[
                    "couleur_SISE"
                ].value_counts(
                    dropna=False
                )
            )

        # ==================================================
        # ETAPE 3 : PERIODE
        # ==================================================

        if (
            "mois"
            in nouvelles_donnees.columns
            and
            "annee"
            in nouvelles_donnees.columns
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

            periode = (
                "Période analysée"
            )

        # ==================================================
        # ETAPE 4 : STOCKAGE TEMPORAIRE
        # ==================================================

        sauvegarder_resultats_temp(
            resultats,
            periode
        )

        # ==================================================
        # ETAPE 5 : DASHBOARD
        # ==================================================

        return redirect(
            url_for(
                "dashboard"
            )
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
            url_for(
                "accueil"
            )
        )


# ==========================================================
# 15. DASHBOARD
# ==========================================================

@app.route("/dashboard")
def dashboard():

    df, periode = (
        charger_resultats_temp()
    )

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

    print(
        "Résumé dashboard :",
        resume
    )

    return render_template(

        "index.html",

        chargeuses=
            chargeuses,

        cartes=
            cartes,

        resume=
            resume,

        total=
            resume["total"],

        nb_rouge=
            resume["rouge"],

        nb_orange=
            resume["orange"],

        nb_jaune=
            resume["jaune"],

        nb_vert=
            resume["vert"],

        nb_gris=
            resume["gris"],

        mois_importe=
            True,

        periode_importee=
            periode
    )


# ==========================================================
# 16. DETAIL CHARGEUSE
# ==========================================================

@app.route(
    "/chargeuse/<engin>"
)
def detail_chargeuse(
    engin
):

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

    # ======================================================
    # CORRECTION DES NOMS DU MOTEUR SISE
    # ======================================================

    couleur = str(
        ligne.get(
            "couleur_SISE",
            "GRIS"
        )
    ).upper()

    type_anomalie = str(
        ligne.get(
            "type_anomalie_SISE",
            "NON_DISPONIBLE"
        )
    )

    etat = nom_etat(
        couleur,
        type_anomalie
    )

    data = {

        "engin":
            str(engin),

        "periode":
            periode,

        "couleur":
            couleur,

        "couleur_SISE":
            couleur,

        "etat":
            etat,

        "type_anomalie":
            type_anomalie,

        "type_anomalie_SISE":
            type_anomalie,

        "lh_reel":
            valeur_simple(
                ligne.get(
                    "lh_reel",
                    None
                )
            ),

        "reference_historique":
            valeur_simple(
                ligne.get(
                    "lh_mediane_historique",
                    None
                )
            ),

        "lh_mediane_historique":
            valeur_simple(
                ligne.get(
                    "lh_mediane_historique",
                    None
                )
            ),

        "lh_mad_historique":
            valeur_simple(
                ligne.get(
                    "lh_mad_historique",
                    None
                )
            ),

        "heures_mediane_historique":
            valeur_simple(
                ligne.get(
                    "heures_mediane_historique",
                    None
                )
            ),

        "nb_historique_precedent":
            valeur_simple(
                ligne.get(
                    "nb_historique_precedent",
                    None
                )
            ),

        "historique_suffisant":
            valeur_simple(
                ligne.get(
                    "historique_suffisant",
                    False
                )
            ),

        "heures":
            valeur_simple(
                ligne.get(
                    "heures",
                    None
                )
            ),

        "litres":
            valeur_simple(
                ligne.get(
                    "litres",
                    None
                )
            ),

        "compteur_debut":
            valeur_simple(
                ligne.get(
                    "compteur_debut",
                    None
                )
            ),

        "compteur_fin":
            valeur_simple(
                ligne.get(
                    "compteur_fin",
                    None
                )
            ),

        "statut_donnee":
            str(
                ligne.get(
                    "statut_donnee",
                    ""
                )
            ),

        "ecart_lh_pct":
            valeur_simple(
                ligne.get(
                    "ecart_lh_pct",
                    None
                )
            ),

        "robust_z":
            valeur_simple(
                ligne.get(
                    "robust_z_lh",
                    None
                )
            ),

        "robust_z_lh":
            valeur_simple(
                ligne.get(
                    "robust_z_lh",
                    None
                )
            ),

        "ratio_activite":
            valeur_simple(
                ligne.get(
                    "ratio_heures_historique",
                    None
                )
            ),

        "ratio_heures_historique":
            valeur_simple(
                ligne.get(
                    "ratio_heures_historique",
                    None
                )
            ),

        "vote_total":
            valeur_simple(
                ligne.get(
                    "vote_total",
                    0
                )
            ),

        "vote_IF":
            valeur_simple(
                ligne.get(
                    "vote_IF",
                    0
                )
            ),

        "vote_LOF":
            valeur_simple(
                ligne.get(
                    "vote_LOF",
                    0
                )
            ),

        "vote_OCSVM":
            valeur_simple(
                ligne.get(
                    "vote_OCSVM",
                    0
                )
            ),

        "nb_detections_IF":
            valeur_simple(
                ligne.get(
                    "nb_detections_IF",
                    0
                )
            ),

        "nb_detections_LOF":
            valeur_simple(
                ligne.get(
                    "nb_detections_LOF",
                    0
                )
            ),

        "nb_detections_OCSVM":
            valeur_simple(
                ligne.get(
                    "nb_detections_OCSVM",
                    0
                )
            ),

        "confiance_ML":
            str(
                ligne.get(
                    "confiance_ML",
                    "NON_EVALUEE"
                )
            ),

        "niveau_fiabilite":
            str(
                ligne.get(
                    "niveau_fiabilite",
                    "NON_EVALUEE"
                )
            ),

        "raison_fiabilite":
            str(
                ligne.get(
                    "raison_fiabilite",
                    ""
                )
            ),

        "interpretation_consommation":
            str(
                ligne.get(
                    "interpretation_consommation",
                    ""
                )
            ),

        "interpretation_activite":
            str(
                ligne.get(
                    "interpretation_activite",
                    ""
                )
            ),

        "interpretation_ML":
            str(
                ligne.get(
                    "interpretation_ML",
                    ""
                )
            ),

        "conclusion":
            str(
                ligne.get(
                    "conclusion_SISE",
                    ""
                )
            ),

        "conclusion_SISE":
            str(
                ligne.get(
                    "conclusion_SISE",
                    ""
                )
            ),

        "explication":
            str(
                ligne.get(
                    "explication_SISE",
                    ""
                )
            ),

        "explication_SISE":
            str(
                ligne.get(
                    "explication_SISE",
                    ""
                )
            ),

        "action":
            str(
                ligne.get(
                    "action_recommandee",
                    ""
                )
            ),

        "action_recommandee":
            str(
                ligne.get(
                    "action_recommandee",
                    ""
                )
            ),

        "nouveau_mois":
            True
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

            if (
                "engin"
                in historique.columns
            ):

                historique["engin"] = (
                    historique["engin"]
                    .astype(str)
                    .str.replace(
                        " ",
                        "",
                        regex=False
                    )
                    .str.strip()
                    .str.upper()
                )

                historique_engin = (
                    historique[
                        historique["engin"]
                        ==
                        str(engin)
                        .replace(" ", "")
                        .strip()
                        .upper()
                    ]
                    .copy()
                )

                if (
                    "date"
                    in historique_engin.columns
                ):

                    historique_engin[
                        "date"
                    ] = pd.to_datetime(
                        historique_engin[
                            "date"
                        ],
                        errors="coerce"
                    )

                    historique_engin = (
                        historique_engin
                        .sort_values(
                            "date"
                        )
                    )

                for _, hist in (
                    historique_engin
                    .iterrows()
                ):

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

                    lh_hist = valeur_simple(
                        hist.get(
                            "lh_reel",
                            None
                        )
                    )

                    history.append(
                        {
                            "periode":
                                nom_periode,

                            "lh_reel":
                                lh_hist,

                            "lh":
                                lh_hist,

                            "nouveau":
                                False
                        }
                    )

        except Exception as erreur:

            print(
                "ERREUR HISTORIQUE :",
                repr(erreur)
            )

    # ======================================================
    # AJOUT DU NOUVEAU MOIS AU GRAPHIQUE UNIQUEMENT
    # ======================================================

    history.append(
        {
            "periode":
                periode,

            "lh_reel":
                data[
                    "lh_reel"
                ],

            "lh":
                data[
                    "lh_reel"
                ],

            "nouveau":
                True
        }
    )

    return render_template(

        "detail.html",

        data=
            data,

        history=
            history,

        history_json=
            json.dumps(
                history,
                ensure_ascii=False
            )
    )


# ==========================================================
# 17. QR CODE
# ==========================================================

@app.route(
    "/qr/<engin>.png"
)
def qr_chargeuse(
    engin
):

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
                "attachment; "
                "filename=resultats_SISE.csv"
        }
    )


# ==========================================================
# 19. RETIRER ANALYSE
# ==========================================================

@app.route(
    "/reinitialiser-analyse"
)
def reinitialiser_analyse():

    supprimer_resultats_temp()

    return redirect(
        url_for("accueil")
    )


# ==========================================================
# 20. NOUVELLE ANALYSE
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
# 21. LANCEMENT LOCAL
# ==========================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )