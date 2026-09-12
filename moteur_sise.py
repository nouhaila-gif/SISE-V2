import os
import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM


# ==========================================================
# 1. CHEMINS
# ==========================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

FICHIER_HISTORIQUE = os.path.join(
    BASE_DIR,
    "dataset_historique_final.xlsx"
)

FICHIER_ML = os.path.join(
    BASE_DIR,
    "dataset_pret_ml.xlsx"
)


# ==========================================================
# 2. PARAMETRES SISE
# ==========================================================

NB_HISTORIQUE_MIN = 5

FEATURES_ML = [
    "ratio_heures_historique",
    "log_lh",
    "ecart_lh_pct"
]


# ==========================================================
# 3. OUTILS
# ==========================================================

def safe_float(value):

    try:

        if value is None:
            return np.nan

        if pd.isna(value):
            return np.nan

        return float(value)

    except Exception:

        return np.nan


def nettoyer_engin(value):

    if pd.isna(value):
        return ""

    return (
        str(value)
        .replace(" ", "")
        .strip()
        .upper()
    )


def format_nombre(
    valeur,
    decimals=2,
    suffixe=""
):

    valeur = safe_float(
        valeur
    )

    if np.isnan(valeur):

        return "Non disponible"

    texte = (
        f"{valeur:.{decimals}f}"
    )

    if suffixe:

        texte += suffixe

    return texte


# ==========================================================
# 4. CHARGER HISTORIQUE
# ==========================================================

def charger_historique():

    if not os.path.exists(
        FICHIER_HISTORIQUE
    ):

        raise FileNotFoundError(
            "Le fichier dataset_historique_final.xlsx "
            "est introuvable."
        )

    df = pd.read_excel(
        FICHIER_HISTORIQUE,
        sheet_name="Donnees_valides"
    )

    df["engin"] = (
        df["engin"]
        .apply(nettoyer_engin)
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

    df = df.dropna(
        subset=[
            "engin",
            "date",
            "heures",
            "lh_reel"
        ]
    ).copy()

    return df


# ==========================================================
# 5. CHARGER DATASET ML
# ==========================================================

def charger_dataset_ml():

    if not os.path.exists(
        FICHIER_ML
    ):

        raise FileNotFoundError(
            "Le fichier dataset_pret_ml.xlsx "
            "est introuvable."
        )

    df = pd.read_excel(
        FICHIER_ML,
        sheet_name="Dataset_ML"
    )

    colonnes_absentes = [
        c
        for c in FEATURES_ML
        if c not in df.columns
    ]

    if colonnes_absentes:

        raise ValueError(
            "Features ML absentes : "
            + ", ".join(
                colonnes_absentes
            )
        )

    for colonne in FEATURES_ML:

        df[colonne] = pd.to_numeric(
            df[colonne],
            errors="coerce"
        )

    df = df.dropna(
        subset=FEATURES_ML
    ).copy()

    return df


# ==========================================================
# 6. MAD
# ==========================================================

def calculer_mad(serie):

    serie = pd.Series(
        serie
    ).dropna()

    if len(serie) == 0:

        return np.nan

    mediane = serie.median()

    ecarts = (
        serie
        - mediane
    ).abs()

    return float(
        ecarts.median()
    )


# ==========================================================
# 7. PROFIL HISTORIQUE
# ==========================================================

def calculer_profil_historique(
    historique,
    engin,
    date_nouvelle
):

    data = historique[
        (
            historique["engin"]
            == engin
        )
        &
        (
            historique["date"]
            < date_nouvelle
        )
    ].copy()

    data = data.dropna(
        subset=[
            "lh_reel",
            "heures"
        ]
    )

    nb_historique = len(
        data
    )

    if nb_historique == 0:

        return {

            "nb_historique_precedent":
                0,

            "historique_suffisant":
                False,

            "lh_mediane_historique":
                np.nan,

            "lh_mad_historique":
                np.nan,

            "heures_mediane_historique":
                np.nan
        }

    lh_mediane = float(
        data["lh_reel"].median()
    )

    lh_mad = calculer_mad(
        data["lh_reel"]
    )

    heures_mediane = float(
        data["heures"].median()
    )

    return {

        "nb_historique_precedent":
            nb_historique,

        "historique_suffisant":
            nb_historique
            >= NB_HISTORIQUE_MIN,

        "lh_mediane_historique":
            lh_mediane,

        "lh_mad_historique":
            lh_mad,

        "heures_mediane_historique":
            heures_mediane
    }


# ==========================================================
# 8. FEATURES DU NOUVEAU MOIS
# ==========================================================

def calculer_features_nouvelle_observation(
    row,
    profil
):

    lh = safe_float(
        row["lh_reel"]
    )

    heures = safe_float(
        row["heures"]
    )

    mediane_lh = safe_float(
        profil[
            "lh_mediane_historique"
        ]
    )

    mad_lh = safe_float(
        profil[
            "lh_mad_historique"
        ]
    )

    mediane_heures = safe_float(
        profil[
            "heures_mediane_historique"
        ]
    )

    # ------------------------------------------------------
    # ECART L/H
    # ------------------------------------------------------

    if (
        not np.isnan(lh)
        and not np.isnan(mediane_lh)
        and mediane_lh != 0
    ):

        ecart_lh = (
            lh
            - mediane_lh
        )

        ecart_lh_pct = (
            ecart_lh
            / mediane_lh
        ) * 100

    else:

        ecart_lh = np.nan
        ecart_lh_pct = np.nan

    # ------------------------------------------------------
    # ROBUST Z
    # ------------------------------------------------------

    if (
        not np.isnan(lh)
        and not np.isnan(mediane_lh)
        and not np.isnan(mad_lh)
        and mad_lh > 0
    ):

        robust_z = (
            lh
            - mediane_lh
        ) / (
            1.4826
            * mad_lh
        )

    else:

        robust_z = np.nan

    # ------------------------------------------------------
    # RATIO ACTIVITE
    # ------------------------------------------------------

    if (
        not np.isnan(heures)
        and not np.isnan(mediane_heures)
        and mediane_heures > 0
    ):

        ratio_heures = (
            heures
            / mediane_heures
        )

    else:

        ratio_heures = np.nan

    # ------------------------------------------------------
    # LOG L/H
    # ------------------------------------------------------

    if (
        not np.isnan(lh)
        and lh >= 0
    ):

        log_lh = np.log1p(
            lh
        )

    else:

        log_lh = np.nan

    return {

        "ecart_lh_historique":
            ecart_lh,

        "ecart_lh_pct":
            ecart_lh_pct,

        "robust_z_lh":
            robust_z,

        "ratio_heures_historique":
            ratio_heures,

        "log_lh":
            log_lh
    }


# ==========================================================
# 9. ISOLATION FOREST
# ==========================================================

def analyser_isolation_forest(
    X_train,
    x_new
):

    contaminations = [
        0.05,
        0.10,
        0.15
    ]

    detections = 0

    scaler = StandardScaler()

    X_scaled = scaler.fit_transform(
        X_train
    )

    x_scaled = scaler.transform(
        x_new
    )

    for contamination in contaminations:

        modele = IsolationForest(
            n_estimators=300,
            contamination=contamination,
            random_state=42
        )

        modele.fit(
            X_scaled
        )

        prediction = modele.predict(
            x_scaled
        )[0]

        if prediction == -1:

            detections += 1

    vote = int(
        detections >= 2
    )

    return detections, vote


# ==========================================================
# 10. LOF
# ==========================================================

def analyser_lof(
    X_train,
    x_new
):

    voisins = [
        5,
        10,
        15,
        20
    ]

    detections = 0
    tests_effectues = 0

    scaler = StandardScaler()

    X_scaled = scaler.fit_transform(
        X_train
    )

    x_scaled = scaler.transform(
        x_new
    )

    for n_neighbors in voisins:

        if len(X_train) <= n_neighbors:

            continue

        modele = LocalOutlierFactor(
            n_neighbors=n_neighbors,
            contamination=0.10,
            novelty=True
        )

        modele.fit(
            X_scaled
        )

        prediction = modele.predict(
            x_scaled
        )[0]

        tests_effectues += 1

        if prediction == -1:

            detections += 1

    vote = int(
        detections >= 3
    )

    return (
        detections,
        tests_effectues,
        vote
    )


# ==========================================================
# 11. ONE CLASS SVM
# ==========================================================

def analyser_ocsvm(
    X_train,
    x_new
):

    valeurs_nu = [
        0.05,
        0.10,
        0.15
    ]

    valeurs_gamma = [
        0.10,
        0.33,
        0.50,
        1.00
    ]

    detections = 0
    total_tests = 0

    scaler = StandardScaler()

    X_scaled = scaler.fit_transform(
        X_train
    )

    x_scaled = scaler.transform(
        x_new
    )

    for nu in valeurs_nu:

        for gamma in valeurs_gamma:

            modele = OneClassSVM(
                kernel="rbf",
                nu=nu,
                gamma=gamma
            )

            modele.fit(
                X_scaled
            )

            prediction = modele.predict(
                x_scaled
            )[0]

            total_tests += 1

            if prediction == -1:

                detections += 1

    vote = int(
        detections >= 7
    )

    return (
        detections,
        total_tests,
        vote
    )


# ==========================================================
# 12. FIABILITE
# ==========================================================

def calculer_fiabilite(
    heures
):

    heures = safe_float(
        heures
    )

    if np.isnan(
        heures
    ):

        return (
            "NON_EVALUEE",
            (
                "Le nombre d'heures d'activité "
                "n'est pas disponible."
            )
        )

    if heures < 5:

        return (
            "FAIBLE",
            (
                "L'observation repose sur moins de "
                "5 heures d'activité. Dans cette situation, "
                "le ratio L/h peut être très sensible "
                "à une petite variation des litres ou "
                "des heures."
            )
        )

    if heures < 15:

        return (
            "LIMITEE",
            (
                "L'observation repose sur moins de "
                "15 heures d'activité. Le résultat reste "
                "exploitable mais doit être interprété "
                "avec prudence."
            )
        )

    return (
        "NORMALE",
        (
            "Le volume d'activité du mois est suffisant "
            "pour interpréter normalement les indicateurs "
            "de consommation."
        )
    )


# ==========================================================
# 13. REGLES SISE
# ==========================================================

def appliquer_regles_sise(
    robust_z,
    vote_total,
    historique_suffisant
):

    if not historique_suffisant:

        return (
            "GRIS",
            "HISTORIQUE_INSUFFISANT",
            "NON_EVALUEE"
        )

    robust_z_valide = (
        not np.isnan(
            robust_z
        )
    )

    if vote_total == 3:

        confiance = "ELEVEE"

    elif vote_total == 2:

        confiance = "MOYENNE"

    elif vote_total == 1:

        confiance = "FAIBLE"

    else:

        confiance = (
            "AUCUNE_CONFIRMATION_ML"
        )

    # ------------------------------------------------------
    # SURCONSOMMATION FORTE
    # ------------------------------------------------------

    if (
        robust_z_valide
        and robust_z >= 3
    ):

        if vote_total >= 2:

            return (
                "ROUGE",
                "ANOMALIE_COMBINEE",
                confiance
            )

        return (
            "ROUGE",
            "ANOMALIE_DE_CONSOMMATION",
            confiance
        )

    # ------------------------------------------------------
    # SOUS-CONSOMMATION FORTE
    # ------------------------------------------------------

    if (
        robust_z_valide
        and robust_z <= -3
    ):

        if vote_total >= 2:

            return (
                "ORANGE",
                "ANOMALIE_COMBINEE",
                confiance
            )

        return (
            "ORANGE",
            "ANOMALIE_DE_CONSOMMATION",
            confiance
        )

    # ------------------------------------------------------
    # Z ENTRE 2 ET 3
    # ------------------------------------------------------

    if (
        robust_z_valide
        and abs(robust_z) >= 2
    ):

        return (
            "JAUNE",
            "CONSOMMATION_A_SURVEILLER",
            confiance
        )

    # ------------------------------------------------------
    # ANOMALIE MULTIVARIEE
    # ------------------------------------------------------

    if vote_total >= 2:

        return (
            "JAUNE",
            "ANOMALIE_MULTIVARIEE",
            confiance
        )

    # ------------------------------------------------------
    # NORMAL
    # ------------------------------------------------------

    return (
        "VERT",
        "PAS_D_ANOMALIE_SIGNIFICATIVE",
        confiance
    )


# ==========================================================
# 14. INTERPRETATION CONSOMMATION
# ==========================================================

def interpreter_consommation(
    resultat
):

    lh = safe_float(
        resultat.get(
            "lh_reel"
        )
    )

    reference = safe_float(
        resultat.get(
            "lh_mediane_historique"
        )
    )

    ecart = safe_float(
        resultat.get(
            "ecart_lh_pct"
        )
    )

    robust_z = safe_float(
        resultat.get(
            "robust_z_lh"
        )
    )

    if (
        np.isnan(lh)
        or np.isnan(reference)
    ):

        return (
            "La comparaison de consommation "
            "ne peut pas être effectuée."
        )

    texte = (
        f"La consommation observée est de "
        f"{lh:.2f} L/h, contre une référence "
        f"historique de {reference:.2f} L/h."
    )

    if not np.isnan(ecart):

        if ecart > 0:

            texte += (
                f" Elle est supérieure de "
                f"{abs(ecart):.1f} % à la référence."
            )

        elif ecart < 0:

            texte += (
                f" Elle est inférieure de "
                f"{abs(ecart):.1f} % à la référence."
            )

        else:

            texte += (
                " Elle est pratiquement identique "
                "à la référence historique."
            )

    if not np.isnan(robust_z):

        if robust_z >= 3:

            texte += (
                f" Le Robust Z vaut {robust_z:.2f}, "
                "ce qui indique une hausse de consommation "
                "très inhabituelle par rapport aux variations "
                "historiques de cette chargeuse."
            )

        elif robust_z <= -3:

            texte += (
                f" Le Robust Z vaut {robust_z:.2f}, "
                "ce qui indique une baisse de consommation "
                "très inhabituelle par rapport à son historique."
            )

        elif abs(robust_z) >= 2:

            texte += (
                f" Le Robust Z vaut {robust_z:.2f}. "
                "L'écart est notable et mérite une surveillance."
            )

        else:

            texte += (
                f" Le Robust Z vaut {robust_z:.2f}. "
                "Même si le L/h diffère de la médiane, "
                "cet écart reste compatible avec la "
                "variabilité historique observée."
            )

    return texte


# ==========================================================
# 15. INTERPRETATION ACTIVITE
# ==========================================================

def interpreter_activite(
    resultat
):

    heures = safe_float(
        resultat.get(
            "heures"
        )
    )

    heures_mediane = safe_float(
        resultat.get(
            "heures_mediane_historique"
        )
    )

    ratio = safe_float(
        resultat.get(
            "ratio_heures_historique"
        )
    )

    if (
        np.isnan(heures)
        or np.isnan(ratio)
    ):

        return (
            "Le niveau d'activité ne peut pas "
            "être comparé de manière fiable."
        )

    texte = (
        f"La chargeuse a fonctionné "
        f"{heures:.1f} heures pendant le mois."
    )

    if not np.isnan(heures_mediane):

        texte += (
            f" La médiane historique de son activité "
            f"est de {heures_mediane:.1f} heures."
        )

    if ratio >= 2:

        texte += (
            f" Le ratio d'activité vaut {ratio:.2f}, "
            "ce qui signifie que l'activité est très "
            "supérieure à son niveau historique habituel."
        )

    elif ratio >= 1.5:

        texte += (
            f" Le ratio d'activité vaut {ratio:.2f}. "
            "L'activité est sensiblement supérieure "
            "au niveau historique."
        )

    elif ratio <= 0.5:

        texte += (
            f" Le ratio d'activité vaut {ratio:.2f}. "
            "L'activité est nettement inférieure "
            "à son niveau historique habituel."
        )

    elif ratio <= 0.75:

        texte += (
            f" Le ratio d'activité vaut {ratio:.2f}. "
            "L'activité est inférieure à l'habitude."
        )

    else:

        texte += (
            f" Le ratio d'activité vaut {ratio:.2f}. "
            "L'activité reste globalement proche "
            "de son niveau historique."
        )

    return texte


# ==========================================================
# 16. INTERPRETATION ML
# ==========================================================

def interpreter_ml(
    resultat
):

    vote_if = int(
        resultat.get(
            "vote_IF",
            0
        )
    )

    vote_lof = int(
        resultat.get(
            "vote_LOF",
            0
        )
    )

    vote_ocsvm = int(
        resultat.get(
            "vote_OCSVM",
            0
        )
    )

    vote_total = (
        vote_if
        + vote_lof
        + vote_ocsvm
    )

    noms = []

    if vote_if == 1:

        noms.append(
            "Isolation Forest"
        )

    if vote_lof == 1:

        noms.append(
            "LOF"
        )

    if vote_ocsvm == 1:

        noms.append(
            "One-Class SVM"
        )

    if vote_total == 0:

        return (
            "Aucun des trois modèles de détection "
            "d'anomalies ne classe cette observation "
            "comme atypique. La convergence ML est donc "
            "de 0/3. Le comportement multivarié reste "
            "compatible avec les observations historiques "
            "utilisées pour entraîner les modèles."
        )

    if vote_total == 1:

        return (
            f"Un seul modèle sur trois détecte "
            f"l'observation comme atypique : "
            f"{noms[0]}. "
            "Le signal ML reste faible et n'est pas "
            "suffisamment convergent pour conclure seul "
            "à une anomalie robuste."
        )

    if vote_total == 2:

        return (
            f"Deux modèles sur trois détectent une "
            f"observation atypique : "
            f"{', '.join(noms)}. "
            "La convergence ML est moyenne et indique "
            "une combinaison inhabituelle entre activité, "
            "niveau de consommation et écart historique."
        )

    return (
        "Les trois modèles — Isolation Forest, LOF "
        "et One-Class SVM — détectent cette observation "
        "comme atypique. La convergence ML est de 3/3. "
        "Le signal multivarié est donc particulièrement fort."
    )


# ==========================================================
# 17. CONCLUSION SISE
# ==========================================================

def generer_conclusion(
    resultat
):

    type_anomalie = resultat.get(
        "type_anomalie_SISE"
    )

    robust_z = safe_float(
        resultat.get(
            "robust_z_lh"
        )
    )

    vote_total = int(
        resultat.get(
            "vote_total",
            0
        )
    )

    if (
        type_anomalie
        == "HISTORIQUE_INSUFFISANT"
    ):

        return (
            "Le SISE ne produit pas de conclusion "
            "d'anomalie, car l'historique disponible "
            "pour cette chargeuse est insuffisant."
        )

    if (
        type_anomalie
        == "ANOMALIE_COMBINEE"
    ):

        if (
            not np.isnan(robust_z)
            and robust_z > 0
        ):

            return (
                "Le diagnostic final est une anomalie "
                "combinée avec surconsommation. "
                "La consommation est statistiquement "
                "très élevée et les modèles ML confirment "
                "également une situation multivariée atypique."
            )

        return (
            "Le diagnostic final est une anomalie "
            "combinée avec sous-consommation. "
            "La baisse de consommation est statistiquement "
            "très inhabituelle et les modèles ML confirment "
            "également un comportement multivarié atypique."
        )

    if (
        type_anomalie
        == "ANOMALIE_DE_CONSOMMATION"
    ):

        if (
            not np.isnan(robust_z)
            and robust_z > 0
        ):

            return (
                "Le diagnostic final est une anomalie "
                "de consommation de type surconsommation. "
                "Le signal provient principalement du L/h "
                "par rapport à l'historique propre "
                "de la chargeuse."
            )

        return (
            "Le diagnostic final est une anomalie "
            "de consommation de type sous-consommation. "
            "Le signal provient principalement du L/h "
            "par rapport à l'historique propre "
            "de la chargeuse."
        )

    if (
        type_anomalie
        == "ANOMALIE_MULTIVARIEE"
    ):

        return (
            "Le diagnostic final est une anomalie "
            "multivariée. Le L/h n'est pas suffisamment "
            "extrême pour parler de surconsommation ou "
            "de sous-consommation forte, mais au moins "
            "deux modèles ML détectent une combinaison "
            "inhabituelle des variables."
        )

    if (
        type_anomalie
        == "CONSOMMATION_A_SURVEILLER"
    ):

        return (
            "Le mois est classé à surveiller. "
            "Le L/h s'écarte du profil historique, "
            "mais l'écart ne dépasse pas le seuil retenu "
            "pour une anomalie forte."
        )

    return (
        "Le diagnostic final est normal. "
        f"La convergence ML est de {vote_total}/3 "
        "et les indicateurs statistiques ne montrent "
        "pas de signal suffisamment fort pour classer "
        "ce mois comme anomalie significative."
    )


# ==========================================================
# 18. EXPLICATION COMPLETE
# ==========================================================

def generer_explication(
    resultat
):

    consommation = (
        interpreter_consommation(
            resultat
        )
    )

    activite = (
        interpreter_activite(
            resultat
        )
    )

    ml = (
        interpreter_ml(
            resultat
        )
    )

    conclusion = (
        generer_conclusion(
            resultat
        )
    )

    return (
        f"{consommation} "
        f"{activite} "
        f"{ml} "
        f"{conclusion}"
    )


# ==========================================================
# 19. ACTION
# ==========================================================

def generer_action(
    type_anomalie
):

    if (
        type_anomalie
        == "ANOMALIE_COMBINEE"
    ):

        return (
            "Vérification prioritaire recommandée. "
            "Contrôler d'abord la cohérence des relevés "
            "carburant et compteur. Si les données sont "
            "confirmées, examiner les conditions "
            "d'exploitation et l'état de la chargeuse."
        )

    if (
        type_anomalie
        == "ANOMALIE_DE_CONSOMMATION"
    ):

        return (
            "Contrôler les relevés puis rechercher "
            "la cause de l'écart de consommation. "
            "Comparer également avec les prochains mois "
            "afin de déterminer si le phénomène persiste."
        )

    if (
        type_anomalie
        == "ANOMALIE_MULTIVARIEE"
    ):

        return (
            "Examiner principalement le niveau d'activité "
            "et les conditions d'utilisation de la chargeuse. "
            "Le L/h seul n'indique pas nécessairement "
            "une surconsommation."
        )

    if (
        type_anomalie
        == "CONSOMMATION_A_SURVEILLER"
    ):

        return (
            "Surveiller la chargeuse lors du prochain relevé. "
            "Si l'écart persiste ou augmente, procéder à une "
            "vérification plus approfondie."
        )

    if (
        type_anomalie
        == "HISTORIQUE_INSUFFISANT"
    ):

        return (
            "Continuer la collecte mensuelle afin de "
            "constituer un historique suffisant avant "
            "de produire un diagnostic robuste."
        )

    return (
        "Aucune intervention particulière n'est suggérée "
        "par le SISE pour ce mois. Poursuivre le suivi "
        "mensuel normal de la chargeuse."
    )


# ==========================================================
# 20. ANALYSE COMPLETE
# ==========================================================

def analyser_avec_sise(
    nouvelles_donnees
):

    historique = (
        charger_historique()
    )

    dataset_ml = (
        charger_dataset_ml()
    )

    X_train = dataset_ml[
        FEATURES_ML
    ].copy()

    resultats = []

    for _, row in nouvelles_donnees.iterrows():

        nouvelle = row.copy()

        engin = nettoyer_engin(
            nouvelle["engin"]
        )

        statut = str(
            nouvelle[
                "statut_donnee"
            ]
        )

        date_nouvelle = pd.to_datetime(
            nouvelle["date"],
            errors="coerce"
        )

        resultat = (
            nouvelle.to_dict()
        )

        resultat["engin"] = engin

        # ==================================================
        # DONNEE NON VALIDE
        # ==================================================

        if statut != "VALIDE":

            resultat.update(
                {

                    "nb_historique_precedent":
                        np.nan,

                    "historique_suffisant":
                        False,

                    "lh_mediane_historique":
                        np.nan,

                    "lh_mad_historique":
                        np.nan,

                    "heures_mediane_historique":
                        np.nan,

                    "ecart_lh_pct":
                        np.nan,

                    "robust_z_lh":
                        np.nan,

                    "ratio_heures_historique":
                        np.nan,

                    "nb_detections_IF":
                        0,

                    "vote_IF":
                        0,

                    "nb_detections_LOF":
                        0,

                    "vote_LOF":
                        0,

                    "nb_detections_OCSVM":
                        0,

                    "vote_OCSVM":
                        0,

                    "vote_total":
                        0,

                    "couleur_SISE":
                        "GRIS",

                    "type_anomalie_SISE":
                        "DONNEE_NON_EXPLOITABLE",

                    "confiance_ML":
                        "NON_EVALUEE",

                    "niveau_fiabilite":
                        "NON_EVALUEE",

                    "raison_fiabilite":
                        (
                            "La donnée n'a pas passé "
                            "le contrôle qualité."
                        ),

                    "interpretation_consommation":
                        (
                            "La consommation ne peut pas "
                            "être analysée tant que les "
                            "données ne sont pas valides."
                        ),

                    "interpretation_activite":
                        (
                            "L'activité ne peut pas être "
                            "interprétée avec une donnée "
                            "non valide."
                        ),

                    "interpretation_ML":
                        (
                            "Les modèles ML ne sont pas "
                            "exécutés sur une donnée "
                            "non exploitable."
                        ),

                    "conclusion_SISE":
                        (
                            "Aucun diagnostic SISE "
                            "n'est produit."
                        ),

                    "explication_SISE":
                        (
                            "Le SISE ne peut pas analyser "
                            "cette observation car les "
                            "données importées ne sont pas "
                            "considérées comme valides."
                        ),

                    "action_recommandee":
                        (
                            "Vérifier le fichier carburant "
                            "et le fichier compteur."
                        )
                }
            )

            resultats.append(
                resultat
            )

            continue

        # ==================================================
        # PROFIL HISTORIQUE
        # ==================================================

        profil = (
            calculer_profil_historique(
                historique,
                engin,
                date_nouvelle
            )
        )

        features = (
            calculer_features_nouvelle_observation(
                nouvelle,
                profil
            )
        )

        resultat.update(
            profil
        )

        resultat.update(
            features
        )

        # ==================================================
        # FIABILITE
        # ==================================================

        (
            niveau_fiabilite,
            raison_fiabilite
        ) = calculer_fiabilite(
            nouvelle["heures"]
        )

        resultat[
            "niveau_fiabilite"
        ] = niveau_fiabilite

        resultat[
            "raison_fiabilite"
        ] = raison_fiabilite

        # ==================================================
        # HISTORIQUE INSUFFISANT
        # ==================================================

        if not profil[
            "historique_suffisant"
        ]:

            resultat.update(
                {

                    "nb_detections_IF":
                        0,

                    "vote_IF":
                        0,

                    "nb_detections_LOF":
                        0,

                    "vote_LOF":
                        0,

                    "nb_detections_OCSVM":
                        0,

                    "vote_OCSVM":
                        0,

                    "vote_total":
                        0,

                    "couleur_SISE":
                        "GRIS",

                    "type_anomalie_SISE":
                        "HISTORIQUE_INSUFFISANT",

                    "confiance_ML":
                        "NON_EVALUEE"
                }
            )

            resultat[
                "interpretation_consommation"
            ] = (
                "Le L/h du mois est disponible, "
                "mais il n'existe pas encore assez "
                "d'observations historiques pour "
                "construire une référence robuste."
            )

            resultat[
                "interpretation_activite"
            ] = (
                "Le nombre d'heures est affiché "
                "à titre descriptif."
            )

            resultat[
                "interpretation_ML"
            ] = (
                "Les modèles ML ne sont pas utilisés "
                "pour conclure car le profil individuel "
                "de cette chargeuse reste insuffisant."
            )

            resultat[
                "conclusion_SISE"
            ] = (
                "Historique insuffisant pour conclure."
            )

            resultat[
                "explication_SISE"
            ] = (
                "Le mois importé est affiché dans le "
                "graphique, mais cette chargeuse ne possède "
                "pas encore suffisamment d'observations "
                "historiques pour produire un diagnostic "
                "SISE robuste."
            )

            resultat[
                "action_recommandee"
            ] = generer_action(
                "HISTORIQUE_INSUFFISANT"
            )

            resultats.append(
                resultat
            )

            continue

        # ==================================================
        # FEATURES ML
        # ==================================================

        x_new = pd.DataFrame(
            [
                {

                    "ratio_heures_historique":
                        resultat[
                            "ratio_heures_historique"
                        ],

                    "log_lh":
                        resultat[
                            "log_lh"
                        ],

                    "ecart_lh_pct":
                        resultat[
                            "ecart_lh_pct"
                        ]

                }
            ]
        )

        if x_new[
            FEATURES_ML
        ].isna().any().any():

            resultat.update(
                {

                    "nb_detections_IF":
                        0,

                    "vote_IF":
                        0,

                    "nb_detections_LOF":
                        0,

                    "vote_LOF":
                        0,

                    "nb_detections_OCSVM":
                        0,

                    "vote_OCSVM":
                        0,

                    "vote_total":
                        0,

                    "couleur_SISE":
                        "GRIS",

                    "type_anomalie_SISE":
                        "ANALYSE_INCOMPLETE",

                    "confiance_ML":
                        "NON_EVALUEE",

                    "interpretation_consommation":
                        interpreter_consommation(
                            resultat
                        ),

                    "interpretation_activite":
                        interpreter_activite(
                            resultat
                        ),

                    "interpretation_ML":
                        (
                            "Certaines variables nécessaires "
                            "aux modèles ML ne peuvent pas "
                            "être calculées."
                        ),

                    "conclusion_SISE":
                        (
                            "Analyse SISE incomplète."
                        ),

                    "explication_SISE":
                        (
                            "Certaines variables nécessaires "
                            "au diagnostic SISE ne peuvent "
                            "pas être calculées."
                        ),

                    "action_recommandee":
                        (
                            "Vérifier l'historique disponible "
                            "pour cette chargeuse."
                        )
                }
            )

            resultats.append(
                resultat
            )

            continue

        # ==================================================
        # IF
        # ==================================================

        (
            nb_if,
            vote_if
        ) = analyser_isolation_forest(
            X_train,
            x_new
        )

        # ==================================================
        # LOF
        # ==================================================

        (
            nb_lof,
            total_lof,
            vote_lof
        ) = analyser_lof(
            X_train,
            x_new
        )

        # ==================================================
        # OCSVM
        # ==================================================

        (
            nb_ocsvm,
            total_ocsvm,
            vote_ocsvm
        ) = analyser_ocsvm(
            X_train,
            x_new
        )

        vote_total = (
            vote_if
            + vote_lof
            + vote_ocsvm
        )

        resultat.update(
            {

                "nb_detections_IF":
                    nb_if,

                "nb_tests_IF":
                    3,

                "vote_IF":
                    vote_if,

                "nb_detections_LOF":
                    nb_lof,

                "nb_tests_LOF":
                    total_lof,

                "vote_LOF":
                    vote_lof,

                "nb_detections_OCSVM":
                    nb_ocsvm,

                "nb_tests_OCSVM":
                    total_ocsvm,

                "vote_OCSVM":
                    vote_ocsvm,

                "vote_total":
                    vote_total

            }
        )

        # ==================================================
        # REGLES SISE
        # ==================================================

        (
            couleur,
            type_anomalie,
            confiance
        ) = appliquer_regles_sise(
            resultat[
                "robust_z_lh"
            ],
            vote_total,
            True
        )

        resultat[
            "couleur_SISE"
        ] = couleur

        resultat[
            "type_anomalie_SISE"
        ] = type_anomalie

        resultat[
            "confiance_ML"
        ] = confiance

        # ==================================================
        # INTERPRETATIONS
        # ==================================================

        resultat[
            "interpretation_consommation"
        ] = interpreter_consommation(
            resultat
        )

        resultat[
            "interpretation_activite"
        ] = interpreter_activite(
            resultat
        )

        resultat[
            "interpretation_ML"
        ] = interpreter_ml(
            resultat
        )

        resultat[
            "conclusion_SISE"
        ] = generer_conclusion(
            resultat
        )

        resultat[
            "explication_SISE"
        ] = generer_explication(
            resultat
        )

        resultat[
            "action_recommandee"
        ] = generer_action(
            type_anomalie
        )

        resultats.append(
            resultat
        )

    return pd.DataFrame(
        resultats
    )