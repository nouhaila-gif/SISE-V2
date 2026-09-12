// ==========================================================
// PALETTE SISE
// ==========================================================

const couleursSISE = {

    ROUGE: "#f04444",

    ORANGE: "#d97706",

    JAUNE: "#e7a500",

    VERT: "#0aa374",

    GRIS: "#8da2b2",

    BLEU: "#147abd"

};


function getCouleurSISE(couleur) {

    if (!couleur) {

        return couleursSISE.GRIS;

    }

    return (
        couleursSISE[
            String(couleur).toUpperCase()
        ]
        || couleursSISE.GRIS
    );

}


// ==========================================================
// RECHERCHE DANS LE PARC
// ==========================================================

const fleetSearch =
    document.getElementById(
        "fleetSearch"
    );


if (fleetSearch) {

    fleetSearch.addEventListener(
        "input",
        function () {

            const recherche =
                this.value
                    .toLowerCase()
                    .trim();


            const lignes =
                document.querySelectorAll(
                    ".fleet-item"
                );


            lignes.forEach(
                ligne => {

                    const engin =
                        (
                            ligne.dataset.engine
                            || ""
                        )
                        .toLowerCase();


                    if (
                        engin.includes(
                            recherche
                        )
                    ) {

                        ligne.style.display =
                            "grid";

                    }

                    else {

                        ligne.style.display =
                            "none";

                    }

                }
            );

        }
    );

}


// ==========================================================
// GRAPHIQUE PRINCIPAL
// ==========================================================

const fleetCanvas =
    document.getElementById(
        "fleetChart"
    );


if (
    fleetCanvas
    && typeof chargeuses !== "undefined"
) {

    const labels =
        chargeuses.map(
            c => c.engin
        );


    const valeursReelles =
        chargeuses.map(
            c => {

                if (
                    c.lh === null
                    || c.lh === undefined
                ) {

                    return null;

                }

                return Number(
                    c.lh
                );

            }
        );


    const references =
        chargeuses.map(
            c => {

                const valeur =
                    c.referenceHistorique;

                if (
                    valeur === null
                    || valeur === undefined
                ) {

                    return null;

                }

                return Number(
                    valeur
                );

            }
        );


    const couleurs =
        chargeuses.map(
            c =>
                getCouleurSISE(
                    c.couleur
                )
        );


    const couleursFond =
        couleurs.map(
            couleur =>
                couleur + "25"
        );


    // ------------------------------------------------------
    // LABELS AU-DESSUS DES BARRES
    // ------------------------------------------------------

    const valuesPlugin = {

        id:
            "valuesPlugin",

        afterDatasetsDraw(chart) {

            const ctx =
                chart.ctx;


            const metaBarres =
                chart.getDatasetMeta(0);


            ctx.save();


            metaBarres.data.forEach(
                (barre, index) => {

                    const valeur =
                        valeursReelles[index];


                    if (
                        valeur === null
                        || valeur === undefined
                    ) {

                        return;

                    }


                    ctx.font =
                        "600 10px Segoe UI";


                    ctx.fillStyle =
                        couleurs[index];


                    ctx.textAlign =
                        "center";


                    ctx.fillText(
                        Number(valeur)
                            .toFixed(1),
                        barre.x,
                        barre.y - 8
                    );

                }
            );


            ctx.restore();

        }

    };


    new Chart(
        fleetCanvas,
        {

            type:
                "bar",


            data: {

                labels:
                    labels,


                datasets: [

                    {

                        label:
                            "L/h du mois",

                        data:
                            valeursReelles,

                        backgroundColor:
                            couleursFond,

                        borderColor:
                            couleurs,

                        borderWidth:
                            2,

                        borderRadius:
                            7,

                        borderSkipped:
                            false,

                        maxBarThickness:
                            48,

                        order:
                            2

                    },


                    {

                        type:
                            "line",

                        label:
                            "Référence historique",

                        data:
                            references,

                        borderColor:
                            couleursSISE.BLEU,

                        backgroundColor:
                            couleursSISE.BLEU,

                        borderWidth:
                            2.5,

                        borderDash:
                            [
                                7,
                                5
                            ],

                        pointRadius:
                            4,

                        pointHoverRadius:
                            6,

                        pointBackgroundColor:
                            couleursSISE.BLEU,

                        pointBorderColor:
                            couleursSISE.BLEU,

                        tension:
                            0.28,

                        spanGaps:
                            false,

                        order:
                            1

                    }

                ]

            },


            options: {

                responsive:
                    true,

                maintainAspectRatio:
                    false,


                interaction: {

                    mode:
                        "index",

                    intersect:
                        false

                },


                plugins: {

                    legend: {

                        display:
                            false

                    },


                    tooltip: {

                        backgroundColor:
                            "#16242f",

                        titleColor:
                            "#ffffff",

                        bodyColor:
                            "#ffffff",

                        padding:
                            12,

                        displayColors:
                            false,


                        callbacks: {

                            title:
                                function (
                                    tooltipItems
                                ) {

                                    const index =
                                        tooltipItems[0]
                                            .dataIndex;


                                    return (
                                        chargeuses[index]
                                            .engin
                                    );

                                },


                            afterBody:
                                function (
                                    tooltipItems
                                ) {

                                    if (
                                        !tooltipItems
                                        || tooltipItems.length === 0
                                    ) {

                                        return [];

                                    }


                                    const index =
                                        tooltipItems[0]
                                            .dataIndex;


                                    const c =
                                        chargeuses[index];


                                    const lignes = [];


                                    lignes.push(
                                        "État : "
                                        + (
                                            c.etat
                                            || "Non disponible"
                                        )
                                    );


                                    if (
                                        c.lh !== null
                                        && c.lh !== undefined
                                    ) {

                                        lignes.push(
                                            "Consommation : "
                                            + c.lh
                                            + " L/h"
                                        );

                                    }


                                    if (
                                        c.referenceHistorique
                                        !== null
                                        && c.referenceHistorique
                                        !== undefined
                                    ) {

                                        lignes.push(
                                            "Référence : "
                                            + c.referenceHistorique
                                            + " L/h"
                                        );

                                    }


                                    if (
                                        c.robustZ !== null
                                        && c.robustZ !== undefined
                                    ) {

                                        lignes.push(
                                            "Robust Z : "
                                            + c.robustZ
                                        );

                                    }


                                    if (
                                        c.voteML !== null
                                        && c.voteML !== undefined
                                    ) {

                                        lignes.push(
                                            "Convergence ML : "
                                            + c.voteML
                                            + "/3"
                                        );

                                    }


                                    return lignes;

                                }

                        }

                    }

                },


                scales: {

                    x: {

                        grid: {

                            display:
                                false

                        },


                        border: {

                            display:
                                false

                        },


                        ticks: {

                            color:
                                "#536d80",

                            font: {

                                family:
                                    "Segoe UI",

                                size:
                                    10,

                                weight:
                                    "600"

                            }

                        }

                    },


                    y: {

                        beginAtZero:
                            true,


                        suggestedMax:
                            50,


                        grid: {

                            color:
                                "#dbe7ee",

                            lineWidth:
                                1

                        },


                        border: {

                            display:
                                false

                        },


                        ticks: {

                            color:
                                "#60798b",

                            font: {

                                family:
                                    "Segoe UI",

                                size:
                                    10

                            },


                            callback:
                                function (
                                    value
                                ) {

                                    return (
                                        value
                                        + " L/h"
                                    );

                                }

                        },


                        title: {

                            display:
                                true,

                            text:
                                "Consommation spécifique (L/h)",

                            color:
                                "#577184",

                            font: {

                                family:
                                    "Segoe UI",

                                size:
                                    11,

                                weight:
                                    "500"

                            }

                        }

                    }

                }

            },


            plugins: [

                valuesPlugin

            ]

        }
    );

}


// ==========================================================
// GRAPHIQUE PAGE DETAIL
// ==========================================================

const detailCanvas =
    document.getElementById(
        "detailChart"
    );


if (
    detailCanvas
    && typeof historyData !== "undefined"
) {

    const labels =
        historyData.map(
            p => p.periode
        );


    const valeurs =
        historyData.map(
            p => Number(
                p.lh_reel
            )
        );


    const pointsCouleur =
        historyData.map(
            p => {

                if (p.nouveau) {

                    return "#147abd";

                }

                return "#075f8d";

            }
        );


    const rayonPoints =
        historyData.map(
            p => {

                if (p.nouveau) {

                    return 7;

                }

                return 3;

            }
        );


    new Chart(
        detailCanvas,
        {

            type:
                "line",


            data: {

                labels:
                    labels,


                datasets: [

                    {

                        label:
                            "Consommation L/h",

                        data:
                            valeurs,

                        borderColor:
                            "#075f8d",

                        backgroundColor:
                            "rgba(7,95,141,0.08)",

                        fill:
                            true,

                        tension:
                            0.25,

                        borderWidth:
                            2,

                        pointBackgroundColor:
                            pointsCouleur,

                        pointBorderColor:
                            pointsCouleur,

                        pointRadius:
                            rayonPoints,

                        pointHoverRadius:
                            7

                    }

                ]

            },


            options: {

                responsive:
                    true,

                maintainAspectRatio:
                    false,


                plugins: {

                    legend: {

                        display:
                            false

                    },


                    tooltip: {

                        callbacks: {

                            afterLabel:
                                function (
                                    context
                                ) {

                                    const point =
                                        historyData[
                                            context.dataIndex
                                        ];


                                    if (
                                        point.nouveau
                                    ) {

                                        return (
                                            "Nouveau mois importé"
                                        );

                                    }


                                    return (
                                        "Observation historique"
                                    );

                                }

                        }

                    }

                },


                scales: {

                    x: {

                        grid: {

                            display:
                                false

                        },


                        ticks: {

                            autoSkip:
                                true,

                            maxTicksLimit:
                                14

                        }

                    },


                    y: {

                        beginAtZero:
                            true,


                        grid: {

                            color:
                                "#e0e9ee"

                        },


                        title: {

                            display:
                                true,

                            text:
                                "L/h"

                        }

                    }

                }

            }

        }
    );

}