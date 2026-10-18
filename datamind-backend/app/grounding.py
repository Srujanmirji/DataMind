"""Conservative checks between the user's words and the selected dataset's plan."""

import re
import unicodedata
from decimal import Decimal

from app.models import Plan


def words(value: str) -> str:
    # Preserve word boundaries before ASCII conversion drops Unicode punctuation.
    value = "".join(
        " " if (unicodedata.category(char).startswith("P") or char == "ʼ") else char for char in value
    )
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", value.lower()))


def mentioned(question: str, aliases: list[str]) -> bool:
    text = " " + words(question) + " "
    return any(
        " " + words(alias) + " " in text
        and (
            not (alias.isupper() and len(alias) <= 3) or re.search(r"\b" + re.escape(alias) + r"\b", question)
        )
        for alias in aliases
        if words(alias)
    )


def clarification(dataset: dict, question: str = "", missing_fields: list[str] | None = None) -> Plan:
    time = dataset.get("time_coverage")
    metric_named = any(mentioned(question, d.get("question_terms", [])) for d in dataset["metrics"].values())
    prompts = {
        "metric": "Which available measure do you mean?",
        "entity": "Which entity or group in the selected dataset should I use?",
        "baseline": "Which entity, group or period should I compare against?",
        "aggregation": "Do you want a total, an average, or separate results for each group?",
        "period": f"Which year or year range ({time['start']}–{time['end']}) should I use?"
        if time
        else "Which time period should I use?",
    }
    requested = list(
        dict.fromkeys(
            f
            for f in (missing_fields if isinstance(missing_fields, list) else [])
            if isinstance(f, str) and f in prompts
        )
    )
    if requested:
        return Plan(
            status="needs_clarification",
            message=" ".join(prompts[f] for f in requested)
            + " Please repeat your complete question with these details.",
        )
    if time and metric_named and not re.search(r"\b(?:19|20)\d{2}\b", question):
        message = f"Which year or year range ({time['start']}–{time['end']}) should I use? Please repeat your question with that period."
    else:
        message = f"For {dataset['name']}, which metric, country or group, and time period do you mean? Please include these details in a complete question."
    return Plan(status="needs_clarification", message=message)


def unsupported(dataset: dict) -> Plan:
    return Plan(
        status="unsupported",
        message=(
            "The selected dataset does not contain the information needed to answer the full request. "
            f"Ask a question about {dataset['name']}, or select a different dataset."
        ),
    )


def check_scope(question: str, plan: Plan, dataset: dict, requested_metrics: list[str] | None = None) -> None:
    """Reject invented scope; the model may repair once, otherwise ask the user."""
    fields = {**dataset["dimensions"], **dataset["filter_fields"]}
    filters = [*plan.filters, *plan.reference_filters]
    if (
        plan.analysis == "aggregate"
        and plan.dimensions
        and plan.time_selection == "explicit"
        and re.search(r"\b(?:average|mean|total)\b.*\b(?:across|of)\b", question, re.IGNORECASE)
        and not re.search(
            r"\b(top|bottom|highest|lowest|rank|ranking|list|each|every|group|by|which|trend|yearly)\b|\bover time\b",
            question,
            re.IGNORECASE,
        )
    ):
        raise ValueError("Grouping was not explicitly requested; use one aggregate or ask for clarification.")
    years = set(re.findall(r"\b(?:19|20)\d{2}\b", question))
    time = dataset.get("time_coverage")
    latest = plan.time_selection == "latest_available"
    if latest and (years or not re.search(r"\b(?:latest|newest|most recent)\b", question, re.IGNORECASE)):
        raise ValueError("Latest available selection must be explicitly requested without a fixed year.")
    if time:
        if any(not time["start"] <= int(y) <= time["end"] for y in years):
            raise ValueError(
                f"This dataset covers {time['start']}–{time['end']}; choose a year in that range."
            )
        if not years and not latest:
            raise ValueError(
                f"Which year or explicit year range ({time['start']}–{time['end']}) should be used?"
            )
        if not latest and not any(f.field == time["field"] for f in filters):
            raise ValueError("The requested year is missing from the plan's filters.")
        if len(years) == 1 and not re.search(
            r"\b(since|after|before|from|until|through|onwards|onward|earlier|later)\b",
            question,
            re.IGNORECASE,
        ):
            for scope in (
                [plan.filters, plan.reference_filters]
                if plan.analysis in ("compare", "share")
                else [plan.filters]
            ):
                scoped_years = [f for f in scope if f.field == time["field"]]
                if (
                    len(scoped_years) != 1
                    or scoped_years[0].operator not in ("eq", "in")
                    or scoped_years[0].values != [int(next(iter(years)))]
                ):
                    raise ValueError(
                        "Use the exact requested calendar year for each scope; do not broaden or omit it."
                    )
    if requested_metrics is not None:
        if (
            not isinstance(requested_metrics, list)
            or not requested_metrics
            or any(not isinstance(name, str) or name not in dataset["metrics"] for name in requested_metrics)
            or set(plan.metrics) != set(requested_metrics)
        ):
            raise ValueError("The plan must include exactly the metrics identified in the full request.")
    else:
        # Literal terms catch explicit substitutions; semantic paraphrases belong to the planner.
        named_terms = {
            name: [term for term in definition.get("question_terms", []) if mentioned(question, [term])]
            for name, definition in dataset["metrics"].items()
        }
        for metric in plan.metrics:
            terms = named_terms.get(metric, [])
            other_terms = [
                term for name, matches in named_terms.items() if name != metric for term in matches
            ]
            # Generic words such as "people" or "countries" also occur in questions about other measures.
            explicit_other = [
                term
                for term in other_terms
                if words(term) not in ("people", "residents", "countries", "economies", "territories")
            ]
            if not terms and explicit_other:
                raise ValueError(
                    "A selected metric was not requested. Ask which supported metric the user means."
                )
            if mentioned(question, dataset["metrics"].get(metric, {}).get("incompatible_terms", [])):
                raise ValueError(
                    "The selected measure changes the meaning of the requested metric; clarify it."
                )
    numeric_literals = {
        Decimal(value.replace(",", ""))
        for value in re.findall(r"(?<![\w.])-?\d+(?:,\d{3})*(?:\.\d+)?(?![\w.])", question)
    }
    question_numbers = set(re.findall(r"\b\d+\b", question))
    for item in filters:
        definition = fields.get(item.field, {})
        aliases = definition.get("value_aliases", {})
        for value in item.values:
            if definition.get("type") == "integer" and str(value) not in question_numbers:
                raise ValueError("A numeric filter was invented; use only explicit question values.")
            if definition.get("type") == "number" and Decimal(str(value)) not in numeric_literals:
                raise ValueError("A numeric threshold was invented; preserve the exact requested value.")
            if definition.get("type") == "text":
                names = aliases.get(str(value).upper(), [str(value)])
                if not mentioned(question, names):
                    raise ValueError(
                        "A category or country filter was not requested; remove it or ask for clarification."
                    )
    # Check named countries in both directions: no additions, omissions or wrong ISO codes.
    for name, definition in fields.items():
        aliases = definition.get("value_aliases", {})
        if not definition.get("require_mentioned_values"):
            continue
        matches = []
        text = " " + words(question) + " "
        for value, names in aliases.items():
            for alias in names:
                if (
                    alias.isupper()
                    and len(alias) <= 3
                    and not re.search(r"\b" + re.escape(alias) + r"\b", question)
                ):
                    continue
                term = " " + words(alias) + " "
                start = text.find(term)
                if start >= 0:
                    matches.append((start, start + len(term), value))
        # "Niger" must not match Nigeria; "Guinea" inside "Equatorial Guinea" is the longer name only.
        requested = {
            v
            for a, b, v in matches
            if not any(c <= a and d >= b and (d - c) > (b - a) for c, d, _ in matches)
        }
        selected = {str(v).upper() for f in filters if f.field == name for v in f.values}
        if requested != selected:
            raise ValueError(
                "Named countries must match their dataset codes exactly; ask to clarify the country if uncertain."
            )
