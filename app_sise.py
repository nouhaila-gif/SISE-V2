from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    Response,
    send_file
)

import pandas as pd
import numpy as np
import os
import json
import uuid
import io

import qrcode

from analyse_nouvelles_donnees import analyser_nouveaux_fichiers
from moteur_sise import analyser_avec_sise


# ==========================================================
# APPLICATION
# ==========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SISE_SECRET_KEY",
    "sise-local-development-key"
)


# ==========================================================
# DOSSIERS
# ==========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

FICHIER_SISE = os.path.join(
    BASE_DIR,
    "resultats_regles_SISE_detaillees.xlsx"
)

FICHIER_HISTORIQUE = os.path.join(
    BASE_DIR,
    "dataset_historique_final.xlsx"
)

DOSSIER_TEMP = os.path.join(
    BASE_DIR,
    "temp_sise"
)

os.makedirs(
    DOSSIER_TEMP,
    exist_ok=True
)


# ==========================================================
# CHARGEUSES
# ==========================================================

CHARGEUSES = [
    "N012009",
    "N012010",
    "N022012",
    "N022013",
    "N032008",
    "N032009",
    "N042003",
    "N042004",
    "N052001",
    "N052002"
]


# ==========================================================
# OUTILS
# ==========================================================

def safe_float(value, decimals=2):

    try:

        if value is None:
            return None

        if pd.isna(value):
            return None

        return round(
            float(value),
            decimals
        )

    except Exception:

        return None


def safe_int(value, default=0):

    try:

        if value is None or pd.isna(value):
            return default

        return int(value)

    except Exception:

        return default


def safe_text(value, default="Non disponible"):

    try:

        if value is None or pd.isna(value):
            return default

    except Exception:
        pass

    texte = str(value).strip()

    if texte == "":
        return default

    return texte


def normaliser_engin(value):

    return (
        str(value)
        .replace(" ", "")
        .strip()
        .upper()
    )


def format_date(value):

    try:

        date = pd.to_datetime(value)

        if pd.isna(date):
            return "Non disponible"

        return date.strftime("%Y-%m")

    except Exception:

        return "Non disponible"


def format_periode_fr(value):

    mois = {
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

    try:

        date = pd.to_datetime(value)

        if pd.isna(date):
            return "Non disponible"

        return f"{mois[date.month]} {date.year}"

    except Exception:

        return "Non disponible"


def description_etat(couleur):

    couleur = safe_text(
        couleur,
        "GRIS"
    ).upper()

    if couleur == "ROUGE":
        return "Surconsommation"

    if couleur == "ORANGE":
        return "Sous-consommation"

    if couleur == "JAUNE":
        return "À surveiller"

    if couleur == "VERT":
        return "Normal"

    return "Historique insuffisant"


# ==========================================================
# HISTORIQUE PERMANENT
# ==========================================================

def charger_historique():

    if not os.path.exists(FICHIER_HISTORIQUE):
        return pd.DataFrame()

    try:

        df = pd.read_excel(
            FICHIER_HISTORIQUE,
            sheet_name="Donnees_valides"
        )

    except Exception:

        return pd.DataFrame()

    df["engin"] = (
        df["engin"]
        .apply(normaliser_engin)
    )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    for colonne in [
        "heures",
        "litres",
        "lh_reel"
    ]:

        if colonne in df.columns:

            df[colonne] = pd.to_numeric(
                df[colonne],
                errors="coerce"
            )

    return df


def charger_resultats_sise():

    if not os.path.exists(FICHIER_SISE):
        return pd.DataFrame()

    try:

        df = pd.read_excel(
            FICHIER_SISE,
            sheet_name="Analyse_SISE"
        )

    except Exception:

        return pd.DataFrame()

    df["engin"] = (
        df["engin"]
        .apply(normaliser_engin)
    )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )

    return df


df_historique = charger_historique()
df_sise_historique = charger_resultats_sise()


# ==========================================================
# STOCKAGE TEMPORAIRE DU MOIS IMPORTE
# ==========================================================

def nettoyer_pour_json(df):

    data = df.copy()

    for colonne in data.columns:

        if pd.api.types.is_datetime64_any_dtype(
            data[colonne]
        ):

            data[colonne] = (
                data[colonne]
                .dt.strftime("%Y-%m-%d")
            )

    data = data.replace(
        {
            np.nan: None,
            np.inf: None,
            -np.inf: None
        }
    )

    return data.to_dict(
        orient="records"
    )


def enregistrer_analyse_temporaire(df):

    ancien_token = session.get(
        "analyse_token"
    )

    if ancien_token:

        ancien_fichier = os.path.join(
            DOSSIER_TEMP,
            f"{ancien_token}.json"
        )

        if os.path.exists(ancien_fichier):

            try:
                os.remove(ancien_fichier)
            except Exception:
                pass

    token = uuid.uuid4().hex

    chemin = os.path.join(
        DOSSIER_TEMP,
        f"{token}.json"
    )

    contenu = nettoyer_pour_json(df)

    with open(
        chemin,
        "w",
        encoding="utf-8"
    ) as fichier:

        json.dump(
            contenu,
            fichier,
            ensure_ascii=False,
            indent=2
        )

    session["analyse_token"] = token


def charger_analyse_temporaire():

    token = session.get(
        "analyse_token"
    )

    if not token:
        return pd.DataFrame()

    chemin = os.path.join(
        DOSSIER_TEMP,
        f"{token}.json"
    )

    if not os.path.exists(chemin):
        return pd.DataFrame()

    try:

        with open(
            chemin,
            "r",
            encoding="utf-8"
        ) as fichier:

            contenu = json.load(fichier)

        df = pd.DataFrame(contenu)

        if df.empty:
            return df

        if "engin" in df.columns:

            df["engin"] = (
                df["engin"]
                .apply(normaliser_engin)
            )

        if "date" in df.columns:

            df["date"] = pd.to_datetime(
                df["date"],
                errors="coerce"
            )

        return df

    except Exception:

        return pd.DataFrame()


# ==========================================================
# DERNIERES DONNEES HISTORIQUES
# ==========================================================

def derniere_analyse_historique(engin):

    if df_sise_historique.empty:
        return None

    data = df_sise_historique[
        df_sise_historique["engin"]
        == engin
    ].copy()

    if data.empty:
        return None

    data = data.sort_values("date")

    return data.iloc[-1]


def derniere_observation_historique(engin):

    if df_historique.empty:
        return None

    data = df_historique[
        df_historique["engin"]
        == engin
    ].copy()

    if data.empty:
        return None

    data = data.sort_values("date")

    return data.iloc[-1]


# ==========================================================
# CARTE DU NOUVEAU MOIS
# ==========================================================

def carte_nouveau_mois(row):

    couleur = safe_text(
        row.get("couleur_SISE"),
        "GRIS"
    ).upper()

    reference = safe_float(
        row.get("lh_mediane_historique")
    )

    return {

        "engin":
            normaliser_engin(
                row.get("engin")
            ),

        "date":
            format_date(
                row.get("date")
            ),

        "periode":
            format_periode_fr(
                row.get("date")
            ),

        "couleur":
            couleur,

        "etat":
            description_etat(
                couleur
            ),

        "type_anomalie":
            safe_text(
                row.get(
                    "type_anomalie_SISE"
                )
            ),

        "fiabilite":
            safe_text(
                row.get(
                    "niveau_fiabilite"
                )
            ),

        "lh":
            safe_float(
                row.get("lh_reel")
            ),

        "reference_historique":
            reference,

        "referenceHistorique":
            reference,

        "heures":
            safe_float(
                row.get("heures")
            ),

        "litres":
            safe_float(
                row.get("litres")
            ),

        "robust_z":
            safe_float(
                row.get("robust_z_lh")
            ),

        "robustZ":
            safe_float(
                row.get("robust_z_lh")
            ),

        "ecart_lh_pct":
            safe_float(
                row.get("ecart_lh_pct")
            ),

        "ratio_activite":
            safe_float(
                row.get(
                    "ratio_heures_historique"
                )
            ),

        "vote_ml":
            safe_int(
                row.get("vote_total"),
                0
            ),

        "voteML":
            safe_int(
                row.get("vote_total"),
                0
            ),

        "explication":
            safe_text(
                row.get("explication_SISE")
            ),

        "action":
            safe_text(
                row.get("action_recommandee")
            ),

        "nouveau_mois":
            True
    }


# ==========================================================
# CARTE HISTORIQUE
# ==========================================================

def carte_historique(engin):

    analyse = derniere_analyse_historique(
        engin
    )

    if analyse is not None:

        couleur = safe_text(
            analyse.get(
                "couleur_SISE"
            ),
            "GRIS"
        ).upper()

        lh = safe_float(
            analyse.get("lh_reel")
        )

        ecart = safe_float(
            analyse.get("ecart_lh_pct")
        )

        reference = None

        if (
            lh is not None
            and ecart is not None
            and abs(
                1 + ecart / 100
            ) > 1e-9
        ):

            reference = round(
                lh / (
                    1 + ecart / 100
                ),
                2
            )

        return {

            "engin": engin,

            "date":
                format_date(
                    analyse.get("date")
                ),

            "periode":
                format_periode_fr(
                    analyse.get("date")
                ),

            "couleur":
                couleur,

            "etat":
                description_etat(
                    couleur
                ),

            "type_anomalie":
                safe_text(
                    analyse.get(
                        "type_anomalie_SISE"
                    )
                ),

            "fiabilite":
                safe_text(
                    analyse.get(
                        "niveau_fiabilite"
                    )
                ),

            "lh":
                lh,

            "reference_historique":
                reference,

            "referenceHistorique":
                reference,

            "heures":
                safe_float(
                    analyse.get("heures")
                ),

            "litres":
                safe_float(
                    analyse.get("litres")
                ),

            "robust_z":
                safe_float(
                    analyse.get("robust_z_lh")
                ),

            "robustZ":
                safe_float(
                    analyse.get("robust_z_lh")
                ),

            "vote_ml":
                safe_int(
                    analyse.get("vote_total"),
                    0
                ),

            "voteML":
                safe_int(
                    analyse.get("vote_total"),
                    0
                ),

            "nouveau_mois":
                False
        }

    observation = (
        derniere_observation_historique(
            engin
        )
    )

    if observation is not None:

        return {

            "engin":
                engin,

            "date":
                format_date(
                    observation.get("date")
                ),

            "periode":
                format_periode_fr(
                    observation.get("date")
                ),

            "couleur":
                "GRIS",

            "etat":
                "Historique insuffisant",

            "type_anomalie":
                "HISTORIQUE_INSUFFISANT",

            "fiabilite":
                "NON_EVALUEE",

            "lh":
                safe_float(
                    observation.get("lh_reel")
                ),

            "reference_historique":
                None,

            "referenceHistorique":
                None,

            "heures":
                safe_float(
                    observation.get("heures")
                ),

            "litres":
                safe_float(
                    observation.get("litres")
                ),

            "robust_z":
                None,

            "robustZ":
                None,

            "vote_ml":
                0,

            "voteML":
                0,

            "nouveau_mois":
                False
        }

    return {

        "engin": engin,

        "date": "Non disponible",

        "periode": "Non disponible",

        "couleur": "GRIS",

        "etat": "Historique insuffisant",

        "type_anomalie":
            "HISTORIQUE_INSUFFISANT",

        "fiabilite":
            "NON_EVALUEE",

        "lh": None,

        "reference_historique":
            None,

        "referenceHistorique":
            None,

        "heures": None,

        "litres": None,

        "robust_z": None,

        "robustZ": None,

        "vote_ml": 0,

        "voteML": 0,

        "nouveau_mois": False
    }


# ==========================================================
# DASHBOARD
# ==========================================================

def construire_dashboard():

    analyse_temp = (
        charger_analyse_temporaire()
    )

    cartes = []

    for engin in CHARGEUSES:

        nouvelle = pd.DataFrame()

        if not analyse_temp.empty:

            nouvelle = analyse_temp[
                analyse_temp["engin"]
                == engin
            ]

        if not nouvelle.empty:

            carte = carte_nouveau_mois(
                nouvelle.iloc[-1]
            )

        else:

            carte = carte_historique(
                engin
            )

        cartes.append(carte)

    return cartes


def construire_resume(cartes):

    return {

        "total": len(cartes),

        "rouge":
            sum(
                c["couleur"] == "ROUGE"
                for c in cartes
            ),

        "orange":
            sum(
                c["couleur"] == "ORANGE"
                for c in cartes
            ),

        "jaune":
            sum(
                c["couleur"] == "JAUNE"
                for c in cartes
            ),

        "vert":
            sum(
                c["couleur"] == "VERT"
                for c in cartes
            ),

        "gris":
            sum(
                c["couleur"] == "GRIS"
                for c in cartes
            )
    }


# ==========================================================
# ACCUEIL
# ==========================================================

@app.route("/")
def accueil():

    cartes = construire_dashboard()

    resume = construire_resume(
        cartes
    )

    analyse_temp = (
        charger_analyse_temporaire()
    )

    mois_importe = not analyse_temp.empty

    periode_importee = None

    if mois_importe:

        periode_importee = (
            format_periode_fr(
                analyse_temp.iloc[0]["date"]
            )
        )

    return render_template(
        "index.html",
        cartes=cartes,
        chargeuses=cartes,
        resume=resume,
        mois_importe=mois_importe,
        periode_importee=periode_importee
    )


# ==========================================================
# IMPORT
# ==========================================================

@app.route(
    "/donnees",
    methods=["GET", "POST"]
)
def donnees():

    if request.method == "GET":

        return render_template(
            "donnees.html"
        )

    fichier_carburant = request.files.get(
        "fichier_carburant"
    )

    fichier_compteur = request.files.get(
        "fichier_compteur"
    )

    if (
        fichier_carburant is None
        or fichier_compteur is None
    ):

        return render_template(
            "erreur_import.html",
            erreur=(
                "Les deux fichiers "
                "sont nécessaires."
            )
        ), 400

    try:

        nouvelles_donnees = (
            analyser_nouveaux_fichiers(
                fichier_carburant,
                fichier_compteur
            )
        )

        resultats_sise = (
            analyser_avec_sise(
                nouvelles_donnees
            )
        )

        enregistrer_analyse_temporaire(
            resultats_sise
        )

        return redirect(
            url_for("accueil")
        )

    except Exception as e:

        return render_template(
            "erreur_import.html",
            erreur=str(e)
        ), 400


# ==========================================================
# EXPORT CSV
# ==========================================================

@app.route("/export-csv")
def export_csv():

    df = charger_analyse_temporaire()

    if df.empty:

        return Response(
            "Aucune analyse temporaire à exporter.",
            status=404,
            mimetype="text/plain"
        )

    colonnes = [
        "date",
        "engin",
        "heures",
        "litres",
        "lh_reel",
        "lh_mediane_historique",
        "ecart_lh_pct",
        "robust_z_lh",
        "ratio_heures_historique",
        "vote_IF",
        "vote_LOF",
        "vote_OCSVM",
        "vote_total",
        "couleur_SISE",
        "type_anomalie_SISE",
        "niveau_fiabilite",
        "explication_SISE",
        "action_recommandee"
    ]

    colonnes_disponibles = [
        c
        for c in colonnes
        if c in df.columns
    ]

    export = df[
        colonnes_disponibles
    ].copy()

    buffer = io.StringIO()

    export.to_csv(
        buffer,
        index=False,
        sep=";",
        encoding="utf-8-sig"
    )

    contenu = buffer.getvalue()

    date = pd.to_datetime(
        df.iloc[0]["date"],
        errors="coerce"
    )

    if pd.isna(date):

        nom = "analyse_SISE.csv"

    else:

        nom = (
            f"analyse_SISE_"
            f"{date.year}_"
            f"{date.month:02d}.csv"
        )

    return Response(
        contenu,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="{nom}"'
        }
    )


# ==========================================================
# QR CODE
# ==========================================================

@app.route("/qr/<engin>.png")
def qr_chargeuse(engin):

    engin = normaliser_engin(engin)

    if engin not in CHARGEUSES:

        return (
            "Chargeuse inconnue",
            404
        )

    url_chargeuse = url_for(
        "detail_chargeuse",
        engin=engin,
        _external=True
    )

    qr = qrcode.QRCode(
        version=4,
        box_size=8,
        border=4
    )

    qr.add_data(
        url_chargeuse
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
# HISTORIQUE DU GRAPHIQUE
# ==========================================================

def construire_historique_graphique(
    engin
):

    points = []

    if not df_historique.empty:

        data = (
            df_historique[
                df_historique["engin"]
                == engin
            ]
            .copy()
            .sort_values("date")
        )

        for _, row in data.iterrows():

            lh = safe_float(
                row.get("lh_reel")
            )

            if lh is None:
                continue

            points.append(
                {
                    "date":
                        format_date(
                            row.get("date")
                        ),

                    "periode":
                        format_periode_fr(
                            row.get("date")
                        ),

                    "lh_reel":
                        lh,

                    "heures":
                        safe_float(
                            row.get("heures")
                        ),

                    "nouveau":
                        False
                }
            )

    analyse_temp = (
        charger_analyse_temporaire()
    )

    if not analyse_temp.empty:

        nouvelle = analyse_temp[
            analyse_temp["engin"]
            == engin
        ]

        if not nouvelle.empty:

            row = nouvelle.iloc[-1]

            lh = safe_float(
                row.get("lh_reel")
            )

            if lh is not None:

                nouvelle_date = (
                    format_date(
                        row.get("date")
                    )
                )

                points = [
                    p
                    for p in points
                    if p["date"]
                    != nouvelle_date
                ]

                points.append(
                    {
                        "date":
                            nouvelle_date,

                        "periode":
                            format_periode_fr(
                                row.get("date")
                            ),

                        "lh_reel":
                            lh,

                        "heures":
                            safe_float(
                                row.get("heures")
                            ),

                        "nouveau":
                            True
                    }
                )

    points = sorted(
        points,
        key=lambda p: p["date"]
    )

    return points


# ==========================================================
# DETAILS
# ==========================================================

def detail_nouveau(row):

    couleur = safe_text(
        row.get("couleur_SISE"),
        "GRIS"
    ).upper()

    return {

        "engin":
            normaliser_engin(
                row.get("engin")
            ),

        "periode":
            format_periode_fr(
                row.get("date")
            ),

        "couleur":
            couleur,

        "etat":
            description_etat(
                couleur
            ),

        "type_anomalie":
            safe_text(
                row.get(
                    "type_anomalie_SISE"
                )
            ),

        "lh_reel":
            safe_float(
                row.get("lh_reel")
            ),

        "reference_historique":
            safe_float(
                row.get(
                    "lh_mediane_historique"
                )
            ),

        "ecart_lh_pct":
            safe_float(
                row.get("ecart_lh_pct")
            ),

        "robust_z":
            safe_float(
                row.get("robust_z_lh")
            ),

        "heures":
            safe_float(
                row.get("heures")
            ),

        "litres":
            safe_float(
                row.get("litres")
            ),

        "ratio_activite":
            safe_float(
                row.get(
                    "ratio_heures_historique"
                )
            ),

        "vote_IF":
            safe_int(
                row.get("vote_IF")
            ),

        "vote_LOF":
            safe_int(
                row.get("vote_LOF")
            ),

        "vote_OCSVM":
            safe_int(
                row.get("vote_OCSVM")
            ),

        "vote_total":
            safe_int(
                row.get("vote_total")
            ),

        "niveau_fiabilite":
            safe_text(
                row.get(
                    "niveau_fiabilite"
                )
            ),

        "explication":
            safe_text(
                row.get(
                    "explication_SISE"
                )
            ),

        "action":
            safe_text(
                row.get(
                    "action_recommandee"
                )
            ),

        "nouveau_mois":
            True
    }


def detail_historique(engin):

    carte = carte_historique(
        engin
    )

    return {

        "engin":
            engin,

        "periode":
            carte["periode"],

        "couleur":
            carte["couleur"],

        "etat":
            carte["etat"],

        "type_anomalie":
            carte["type_anomalie"],

        "lh_reel":
            carte["lh"],

        "reference_historique":
            carte[
                "reference_historique"
            ],

        "ecart_lh_pct":
            None,

        "robust_z":
            carte["robust_z"],

        "heures":
            carte["heures"],

        "litres":
            carte["litres"],

        "ratio_activite":
            None,

        "vote_total":
            carte["vote_ml"],

        "niveau_fiabilite":
            carte["fiabilite"],

        "explication":
            (
                "Dernière analyse historique "
                "disponible."
            ),

        "action":
            (
                "Poursuivre le suivi."
            ),

        "nouveau_mois":
            False
    }


@app.route("/chargeuse/<engin>")
def detail_chargeuse(engin):

    engin = normaliser_engin(
        engin
    )

    if engin not in CHARGEUSES:

        return (
            "Chargeuse inconnue",
            404
        )

    analyse_temp = (
        charger_analyse_temporaire()
    )

    nouvelle = pd.DataFrame()

    if not analyse_temp.empty:

        nouvelle = analyse_temp[
            analyse_temp["engin"]
            == engin
        ]

    if not nouvelle.empty:

        data = detail_nouveau(
            nouvelle.iloc[-1]
        )

    else:

        data = detail_historique(
            engin
        )

    history = (
        construire_historique_graphique(
            engin
        )
    )

    return render_template(
        "detail.html",
        data=data,
        history=history
    )


# ==========================================================
# REINITIALISER LE MOIS IMPORTE
# ==========================================================

@app.route("/reinitialiser-analyse")
def reinitialiser_analyse():

    token = session.pop(
        "analyse_token",
        None
    )

    if token:

        chemin = os.path.join(
            DOSSIER_TEMP,
            f"{token}.json"
        )

        if os.path.exists(chemin):

            try:
                os.remove(chemin)
            except Exception:
                pass

    return redirect(
        url_for("accueil")
    )


# ==========================================================
# LANCEMENT
# ==========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )