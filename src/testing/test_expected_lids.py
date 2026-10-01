"""
Tests für die Zielfunktion von Option B (erwartete Deckelveränderung).

Kernprüfung: Für kleine Tische werden alle Kombinationen der Gegnerergebnisse
aufgezählt und mit der echten Spiellogik aus Game.resolve_round() ausgewertet.
Die so exakt bestimmte erwartete Deckelveränderung muss mit der Formel
übereinstimmen.

Ausführen mit:  pytest testing/test_expected_lids.py -v
"""

import sys
from itertools import product
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from schocken.classification import classify  # noqa: E402
from schocken.distribution import (  # noqa: E402
    hidden_distribution,
    joint_distribution,
    roll_distribution,
)
from schocken.game import Game, Player, compare_results  # noqa: E402
from schocken.state import decide_after_roll  # noqa: E402
from schocken.strategies.absolute import GreedyAllIn  # noqa: E402
from schocken.strategies.optimal import (  # noqa: E402
    ExpectedLidsObjective,
    Objective,
    OptimalStrategy,
)
from schocken.types import GameState, PublicPlayerState, RoundContext  # noqa: E402

TOLERANCE = 1e-10
DICE_OF_RANK = {classify(roll): roll for roll in roll_distribution(3)}


def start_state(n_rolls: int) -> GameState:
    return GameState(
        held_ones=0,
        rolls_left=n_rolls,
        rolls_used=0,
        visible_state=None,
        must_continue=False,
        dice_to_roll=3,
    )


@pytest.fixture(scope="module")
def follower_tables() -> dict[int, dict]:
    return {m: joint_distribution(start_state(m), GreedyAllIn()) for m in (1, 2, 3)}


# --------------------------------------------------------------------------
# Referenz: vollständige Aufzählung mit der echten Spiellogik
# --------------------------------------------------------------------------


def exact_expected_change(
    rank: tuple[int, ...],
    rolls_used: int,
    position: int,
    opponents: list[tuple[int, int, dict]],
    own_lids: int,
    pot: int,
) -> float:
    """
    Erwartete Deckelveränderung durch Aufzählung aller Gegnerkombinationen.

    Jede Kombination wird über compare_results() und Game.resolve_round()
    aufgelöst, also mit genau der Logik, die auch die Simulation verwendet.
    """
    seats = sorted([position] + [seat for seat, _, _ in opponents])
    lids_by_seat = {seat: lids for seat, lids, _ in opponents}
    lids_by_seat[position] = own_lids

    expected = 0.0
    distributions = [list(dist.items()) for _, _, dist in opponents]

    for combination in product(*distributions):
        probability = 1.0
        outcomes = {position: (rank, rolls_used)}
        for (seat, _, _), (outcome, p) in zip(opponents, combination):
            outcomes[seat] = outcome
            probability *= p

        players = [Player(f"S{seat}", GreedyAllIn()) for seat in seats]
        for player, seat in zip(players, seats):
            player.lids = lids_by_seat[seat]
        game = Game(players, starting_lids=pot)
        game.pot = pot

        results = [
            {
                "rank": outcomes[seat][0],
                "rolls_used": outcomes[seat][1],
                "final": DICE_OF_RANK[outcomes[seat][0]],
                "turn_order": seat,
                "player_index": index,
            }
            for index, seat in enumerate(seats)
        ]

        winner = results[0]
        for result in results[1:]:
            winner = compare_results(result, winner)
        loser = results[0]
        for result in results[1:]:
            if compare_results(result, loser) is loser:
                loser = result

        game.resolve_round(winner, loser)
        me = players[seats.index(position)]
        expected += probability * (me.lids - own_lids)

    return expected


def make_objective(position, opponents, own_lids, pot, follower_tables, **kwargs):
    lids = [0] * (1 + len(opponents))
    lids[position] = own_lids
    for seat, seat_lids, _ in opponents:
        lids[seat] = seat_lids
    return ExpectedLidsObjective(
        opponents=opponents,
        position=position,
        n_positions=len(lids),
        pot=pot,
        own_lids=own_lids,
        total_lids=pot + sum(lids),
        follower_distributions=follower_tables,
        is_opener=False,
        max_rolls=3,
        **kwargs,
    )


SCENARIOS = {
    # Phase 2, ein (teil)verdeckter Vorgänger, ein offener, ein Nachfolger
    "phase2_mixed": dict(
        position=2,
        own_lids=5,
        pot=0,
        opponents=[
            (0, 4, hidden_distribution(1, 3)),
            (1, 3, {(classify((5, 4, 3)), 3): 1.0}),
            (3, 1, None),
        ],
    ),
    # Phase 1, Pot fast leer: Deckelwert wird durch den Pot begrenzt
    "phase1_small_pot": dict(
        position=1,
        own_lids=2,
        pot=2,
        opponents=[
            (0, 3, hidden_distribution(2, 3)),
            (2, 4, None),
        ],
    ),
    # Phase 2, hohe Schock-Out-Gefahr durch zwei Vorgänger mit (1, 1)
    "phase2_shock_out_heavy": dict(
        position=2,
        own_lids=6,
        pot=0,
        opponents=[
            (0, 4, hidden_distribution(2, 3)),
            (1, 3, hidden_distribution(2, 3)),
        ],
    ),
}

PROBES = [
    ((1, 1, 1), 3),
    ((6, 1, 1), 2),
    ((3, 1, 1), 3),
    ((4, 4, 4), 3),
    ((6, 5, 4), 1),
    ((6, 5, 3), 3),
    ((3, 2, 2), 3),
]


@pytest.mark.parametrize("name", SCENARIOS)
@pytest.mark.parametrize("dice, rolls", PROBES)
def test_expected_change_matches_game_logic(follower_tables, name, dice, rolls):
    scenario = SCENARIOS[name]
    opponents = [
        (seat, lids, dist if dist is not None else follower_tables[3])
        for seat, lids, dist in scenario["opponents"]
    ]
    objective = make_objective(
        scenario["position"],
        scenario["opponents"],
        scenario["own_lids"],
        scenario["pot"],
        follower_tables,
    )
    rank = classify(dice)
    expected = exact_expected_change(
        rank,
        rolls,
        scenario["position"],
        opponents,
        scenario["own_lids"],
        scenario["pot"],
    )
    assert abs(objective.expected_change(rank, rolls) - expected) < TOLERANCE


# --------------------------------------------------------------------------
# Konsistenz mit Option A
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", SCENARIOS)
@pytest.mark.parametrize("dice, rolls", PROBES)
def test_lose_probability_matches_option_a(follower_tables, name, dice, rolls):
    """P(Verlierer) aus Option B ist exakt 1 minus der Wert von Option A."""
    scenario = SCENARIOS[name]
    position = scenario["position"]
    open_predecessors, hidden_predecessors = [], []
    n_followers = 0
    for seat, _, dist in scenario["opponents"]:
        if dist is None:
            n_followers += 1
        elif len(dist) == 1:
            ((rank_o, rolls_o),) = dist
            open_predecessors.append((rank_o, rolls_o))
        else:
            (_, rolls_o), *_ = dist
            hidden_predecessors.append((_held_ones(dist), rolls_o))

    option_a = Objective(
        open_predecessors,
        hidden_predecessors,
        n_followers,
        follower_tables,
        is_opener=False,
        max_rolls=3,
    )
    option_b = make_objective(
        position,
        scenario["opponents"],
        scenario["own_lids"],
        scenario["pot"],
        follower_tables,
    )
    rank = classify(dice)
    p_lose = option_b.outcome_probabilities(rank, rolls)["p_lose"]
    assert abs((1 - p_lose) - option_a(rank, rolls)) < TOLERANCE


def _held_ones(distribution: dict) -> int:
    """Rekonstruiert h aus einer bedingten Verteilung (Test-Hilfsfunktion)."""
    for h in range(4):
        candidate = hidden_distribution(h, next(iter(distribution))[1])
        if candidate.keys() == distribution.keys():
            return h
    raise ValueError("keine passende bedingte Verteilung")


def test_degenerates_to_option_a(follower_tables):
    """
    Jeder Deckelwert 1, großer Pot, Schock-Out ohne Sonderregel:
    E[Δ] = P(Verlierer).
    """
    scenario = SCENARIOS["phase2_mixed"]
    objective = make_objective(
        scenario["position"],
        scenario["opponents"],
        scenario["own_lids"],
        pot=100,
        follower_tables=follower_tables,
        value_fn=lambda rank: 1,
        shock_out_clears=False,
    )
    for dice, rolls in PROBES:
        rank = classify(dice)
        parts = objective.outcome_probabilities(rank, rolls)
        assert abs(objective.expected_change(rank, rolls) - parts["p_lose"]) < TOLERANCE


# --------------------------------------------------------------------------
# Verhalten der Strategie
# --------------------------------------------------------------------------


def predecessor(seat: int, visible, rolls: int) -> PublicPlayerState:
    return PublicPlayerState(
        player=f"P{seat}", turn_order=seat, visible_state=visible, rolls_used=rolls
    )


def five_player_context(pot: int, lids: list[int]) -> RoundContext:
    return RoundContext(
        n_active=5,
        max_rolls=3,
        public_table_state=[predecessor(i, (1, 1), 3) for i in range(4)],
        pot=pot,
        lids=lids,
    )


AFTER_FIRST_ROLL = GameState(
    held_ones=0,
    rolls_left=2,
    rolls_used=1,
    visible_state=None,
    must_continue=False,
    dice_to_roll=3,
)


@pytest.mark.parametrize("objective", ["not_lose", "expected_lids"])
@pytest.mark.parametrize(
    "roll, action",
    [
        ((6, 1, 1), "stop"),
        ((5, 1, 1), "stop"),
        ((4, 1, 1), "stop"),
        ((3, 1, 1), "stop"),
        ((2, 1, 1), "continue"),
    ],
)
def test_five_player_stop_table(follower_tables, objective, roll, action):
    """Stopptabelle aus ERKENNTNISSE.md, Abschnitt 12, für beide Zielfunktionen."""
    context = five_player_context(pot=0, lids=[3, 2, 4, 3, 1])
    strategy = OptimalStrategy(
        follower_distributions=follower_tables, objective=objective
    )
    decision = decide_after_roll(AFTER_FIRST_ROLL, roll, strategy, context)
    assert decision["action"] == action


def test_phase2_many_lids_values_height(follower_tables):
    """
    Phase 2, zwei Spieler: Der Gewinnerterm macht ein hohes Bild wertvoller,
    je mehr Deckel man selbst hat.
    """

    def objective_for(own_lids):
        return make_objective(
            position=0,
            opponents=[(1, 4, None)],
            own_lids=own_lids,
            pot=0,
            follower_tables=follower_tables,
        )

    schock_6, strasse = classify((6, 1, 1)), classify((6, 5, 4))
    gap_few = objective_for(1)(schock_6, 1) - objective_for(1)(strasse, 1)
    gap_many = objective_for(8)(schock_6, 1) - objective_for(8)(strasse, 1)
    assert gap_many > gap_few


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
