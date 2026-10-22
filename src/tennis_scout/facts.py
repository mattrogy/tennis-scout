"""Website reports: the numbered list of verified facts the model may cite.

Each fact is one sentence built by code from the tool answers (for example
"F12: Jannik Sinner's return points won vs 2nd serve (clay, 30 matches): 54.3%, 96th percentile of 108 players,
strength"). The model never writes a number or a fact: it writes short headlines and cites fact IDs, and the code
copies the cited facts word for word under each headline (see headlines.py).

Every fact also has a "topic": a plain headline with no numbers, used when a model's headline is rejected, and
its "labels": whose stat it is ("scouted" or "coach") and its label, so headlines.py can check that a headline's
direction (praise, target, danger) matches what the facts say.
"""

from tennis_scout.sections import (PRESSURE_NAMES, RETURN_NAMES, SERVE_NAMES, _answers, _comparison, _filter_label,
                                   _value, walkovers)

AREAS = (("serve_stats", "serve", SERVE_NAMES), ("return_stats", "return", RETURN_NAMES))
SMALL = ", small sample (fewer than 10 matches)"


class FactList:
    """Collects facts and numbers them F1, F2, ..."""

    def __init__(self):
        self.facts = []

    def add(self, text, topic, kind, main=True, labels=()):
        """main=False for side facts (all-surface comparison, the coach's player) that a default summary skips.
        labels: (player, label) pairs, for example [("scouted", "weakness")]."""
        self.facts.append({"id": f"F{len(self.facts) + 1}", "text": text, "topic": topic, "kind": kind,
                           "main": main, "labels": [{"player": player, "label": label} for player, label in labels]})


def _label(compared):
    """strength, average or weakness; anything else ("not enough data", "not enough peers", none) is not judged."""
    label = (compared or {}).get("label")
    return label if label in ("strength", "average", "weakness") else "not judged"


def _stat_facts(facts, player, answer, values_key, names, kind, main, role):
    """One fact per stat, plus one fact with the label counts of this answer."""
    where = f"{_filter_label(answer)}, {answer['matches_used']} matches"
    small = SMALL if answer["small_sample"] else ""
    area = "serve" if values_key == "serve" else "return"
    if answer[values_key] is None:
        facts.add(f"{player}'s {area} ({_filter_label(answer)}): {answer['message']}",
                  f"{player}'s {area} numbers", kind, main)
        return
    counts = answer["label_counts"]
    facts.add(f"{player}'s {area} stats ({where}): {counts['strength']} labelled strength, "
              f"{counts['average']} average, "
              f"{counts['weakness']} weakness, {counts['not judged']} not judged{small}.",
              f"How {player}'s {area} is labelled", "labels", main)
    for stat, name in names.items():
        compared = answer["compared_to_tour"].get(stat)
        facts.add(f"{player}'s {name.lower()} ({where}): {_value(stat, answer[values_key][stat])}, "
                  f"{_comparison(compared)}{small}.",
                  f"{player}'s {area} numbers", kind, main, labels=[(role, _label(compared))])


def _pressure_facts(facts, player, answer, main):
    where = f"{_filter_label(answer)}, {answer['matches_used']} matches"
    small = SMALL if answer["small_sample"] else ""
    for key, stat in (("tie_breaks", "tie_breaks_won_pct"), ("deciding_sets", "deciding_sets_won_pct")):
        record, compared = answer[key], answer["compared_to_tour"].get(stat)
        facts.add(f"{player}'s {PRESSURE_NAMES[stat].lower()} ({where}): {record['won']} won, {record['lost']} lost, "
                  f"{_value(stat, record['won_pct'])}, {_comparison(compared)}{small}.",
                  f"{player} under pressure", "pressure", main, labels=[("scouted", _label(compared))])


def _head_to_head_facts(facts, data):
    if not data["coach_player"]:
        facts.add("No coach's player was given, so there is no head-to-head.", "Head-to-head", "head_to_head")
        return
    answer = _answers(data, "head_to_head")[0]
    if not answer["matches"]:
        facts.add(answer["message"], "Head-to-head", "head_to_head")
        return
    a, b = answer["player_a"]["name"], answer["player_b"]["name"]
    where = (data["surface"] or "all surfaces").lower()
    small = SMALL if answer["small_sample"] else ""
    tiebreaks, deciding = answer["tiebreak_summary"], answer["deciding_set_summary"]
    facts.add(f"Head-to-head ({where}, all meetings since 2015): {a} {answer['wins'][a]} wins, {b} "
              f"{answer['wins'][b]} wins ({answer['matches_used']} matches counted){small}.",
              "Head-to-head record", "head_to_head")
    facts.add(f"Head-to-head tie-breaks ({where}): {tiebreaks['tiebreaks_played']} played in "
              f"{tiebreaks['matches_with_a_tiebreak']} matches; {a} won {tiebreaks['tiebreaks_won'][a]}, {b} won "
              f"{tiebreaks['tiebreaks_won'][b]}.", "Head-to-head in close sets", "head_to_head")
    facts.add(f"Head-to-head deciding sets ({where}): {deciding['matches_that_went_to_a_deciding_set']} matches went "
              f"to a deciding set; {a} won {deciding['deciding_sets_won'][a]}, {b} won "
              f"{deciding['deciding_sets_won'][b]}.", "Head-to-head in close sets", "head_to_head")
    recent = answer["most_recent_meeting"]
    facts.add(f"Most recent meeting: {recent['tournament']} {recent['round']}, {recent['date']}, won by "
              f"{recent['winner']}.", "The most recent meeting", "head_to_head")


def _recent_form_facts(facts, data, player):
    answer = _answers(data, "recent_form")[0]
    ranking, summary = answer["current_ranking"], answer["summary"]
    points = f" ({ranking['points']} points)" if ranking["points"] is not None else ""
    facts.add(f"{player}'s current ranking: {ranking['rank']}{points}, as of {ranking['as_of']}.",
              "Current ranking", "form")
    facts.add(f"{player}'s last {len(answer['matches'])} matches: {summary['wins']} wins, {summary['losses']} losses "
              f"({walkovers(summary['walkovers_listed_not_counted'])} listed, not counted). {summary['retired_text']}",
              "Recent form", "form")
    facts.add(f"In {player}'s last {len(answer['matches'])} matches, {summary['matches_that_went_to_a_deciding_set']} "
              f"went to a deciding set and {summary['matches_with_a_tiebreak']} had a tie-break.",
              "Recent form in close matches", "form")


def _angle_facts(facts, data):
    """Code-computed tactical angles: where one player's strength meets the other's weakness, from the labels."""
    scouted, coach = data["scouted_player"], data["coach_player"]
    target_for = coach["name"] if coach else "the coach's player"
    if coach:
        matchup = _answers(data, "matchup")[0]
        for key, pairs in matchup.items():
            if not key.startswith("when "):
                continue
            for pair in pairs:
                server, returner = pair["server"], pair["returner"]
                labels = {server.get("label"), returner.get("label")}
                if labels != {"strength", "weakness"}:
                    continue
                edge = server["name"] if server["label"] == "strength" else returner["name"]
                role = {scouted["name"]: "scouted", coach["name"]: "coach"}
                serve_value = _value(server["stat"], server["value"])
                facts.add(f"Tactical angle ({_filter_label(matchup)}): when {server['name']} serves, "
                          f"{server['name']}'s {SERVE_NAMES[server['stat']].lower()} ({serve_value}, "
                          f"{server['label']}) meets {returner['name']}'s {RETURN_NAMES[returner['stat']].lower()} "
                          f"({_value(returner['stat'], returner['value'])}, {returner['label']}): an edge for {edge}.",
                          "A tactical angle from the matchup", "angle",
                          labels=[(role[server["name"]], server["label"]), (role[returner["name"]], returner["label"])])
    for tool, values_key, names in AREAS:
        answer = _answers(data, tool, scouted["player_key"], surface=data["surface"])[0]
        for stat in answer.get("labels_summary", {}).get("weakness", []):
            facts.add(f"Tactical angle: {scouted['name']}'s {names[stat].lower()} is labelled a weakness "
                      f"({_value(stat, answer[values_key][stat])}, {_comparison(answer['compared_to_tour'][stat])}, "
                      f"{answer['matches_used']} matches): a possible target for {target_for}.",
                      f"A weakness of {scouted['name']} to target", "angle", labels=[("scouted", "weakness")])
        if coach:
            own = _answers(data, tool, coach["player_key"])[0]
            for stat in own.get("labels_summary", {}).get("weakness", []):
                facts.add(f"Tactical angle: {coach['name']}'s own {names[stat].lower()} is labelled a weakness "
                          f"({_value(stat, own[values_key][stat])}, {_comparison(own['compared_to_tour'][stat])}, "
                          f"{own['matches_used']} matches): a risk to manage.",
                          f"A risk for {coach['name']} to manage", "angle", labels=[("coach", "weakness")])


def build_facts(data):
    """The numbered list of verified facts for one report."""
    facts = FactList()
    scouted, coach = data["scouted_player"], data["coach_player"]
    period = data["period"]
    facts.add(f"Period covered: {period['label']} ({period['date_from']} to {period['date_to']}), tournament start "
              f"weeks. Head-to-head uses all meetings since 2015.", "Period covered", "period")
    for tool, values_key, names in AREAS:
        for answer in _answers(data, tool, scouted["player_key"]):  # the chosen surface first, then all surfaces
            main = answer["filters"]["surface"] == data["surface"]
            _stat_facts(facts, scouted["name"], answer, values_key, names, values_key, main, "scouted")
    for answer in _answers(data, "pressure_stats", scouted["player_key"]):
        _pressure_facts(facts, scouted["name"], answer, main=answer["filters"]["surface"] == data["surface"])
    if coach:
        for tool, values_key, names in AREAS:
            _stat_facts(facts, coach["name"], _answers(data, tool, coach["player_key"])[0], values_key, names,
                        "coach", main=False, role="coach")
    _head_to_head_facts(facts, data)
    _recent_form_facts(facts, data, scouted["name"])
    _angle_facts(facts, data)
    return facts.facts
