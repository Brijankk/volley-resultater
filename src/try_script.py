from graphviz import Digraph
import pandas as pd

def test_plot():
    matches = [
        ("QF1", "Alice 2\nBob 0", "SF1"),
        ("QF2", "Cara 1\nDan 2", "SF1"),
        ("QF3", "Eve 2\nFinn 1", "SF2"),
        ("QF4", "Gina 2\nHank 0", "SF2"),
        ("SF1", "Alice 2\nDan 1", "Final"),
        ("SF2", "Eve 2\nGina 0", "Final"),
        ("Final", "Alice 2\nEve 1", None),
    ]

    dot = Digraph(format="png")
    dot.attr(rankdir="LR")

    for match_id, label, _ in matches:
        dot.node(match_id, label, shape="box")

    for match_id, _, next_match in matches:
        if next_match:
            dot.edge(match_id, next_match)

    dot.render("bracket", view=True)


def _clean_match_id(value):
    """Normalize match ids so 12, 12.0, and '12' behave consistently."""
    if pd.isna(value):
        return None

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    return str(value)


def plot_bracket_graphviz(
    df,
    output_name="bracket",
    game_round_col="runde",
    match_id_col="Kampnr.",
    home_col="Hjemmehold",
    away_col="Udehold",
    leg_cols=("leg1", "leg2"),
    file_format="png",
    view=True,
):
    data = df.copy()

    data["_match_id"] = data[match_id_col].apply(_clean_match_id)

    for leg_col in leg_cols:
        data[f"_{leg_col}"] = data[leg_col].apply(_clean_match_id)

    dot = Digraph(format=file_format)

    dot.attr(
        rankdir="LR",
        splines="ortho",
        nodesep="0.45",
        ranksep="1.25",
        concentrate="false",
    )

    dot.attr(
        "node",
        shape="box",
        style="rounded,filled",
        fillcolor="white",
        color="gray55",
        fontname="Arial",
        fontsize="10",
        margin="0.12,0.08",
    )

    dot.attr(
        "edge",
        color="gray60",
        arrowsize="0.6",
        fontname="Arial",
        fontsize="9",
    )

    # Create one node per match
    for _, row in data.iterrows():
        match_id = row["_match_id"]

        label = (
            f"<<TABLE BORDER='0' CELLBORDER='0' CELLSPACING='2'>"
            f"<TR><TD><B>Match {match_id}</B></TD></TR>"
            f"<TR><TD>{row[home_col]}</TD></TR>"
            f"<TR><TD>{row[away_col]}</TD></TR>"
            f"</TABLE>>"
        )

        dot.node(match_id, label=label)

    # Add edges from previous matches into the current match
    for _, row in data.iterrows():
        current_match = row["_match_id"]

        for leg_col in leg_cols:
            previous_match = row[f"_{leg_col}"]

            if previous_match is not None:
                dot.edge(previous_match, current_match)

    # Keep matches from the same round aligned vertically
    for game_round, round_df in data.groupby(game_round_col, sort=True):
        with dot.subgraph(name=f"cluster_round_{game_round}") as s:
            s.attr(rank="same")

            for match_id in round_df["_match_id"]:
                s.node(match_id)

    return dot.render(output_name, view=view, cleanup=True)