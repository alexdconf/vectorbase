"""
Dynamic search form.

The form is built at runtime from the loaded schema config so that it
reflects whatever fields and filter types the developer has configured.
"""

from __future__ import annotations

from django import forms

# ---------------------------------------------------------------------------
# Form builder
# ---------------------------------------------------------------------------

def build_search_form(config) -> type[forms.Form]:
    """
    Dynamically construct a Form class whose fields mirror the schema config.

    Field naming conventions
    ------------------------
    * Semantic query    → ``q``
    * Range lower bound → ``{field_name}__gte``
    * Range upper bound → ``{field_name}__lte``
    * Category          → ``{field_name}``   (MultipleChoiceField)
    * Value (substring) → ``{field_name}``   (CharField)
    """
    field_dict: dict[str, forms.Field] = {
        "q": forms.CharField(
            required=False,
            label="Search",
            widget=forms.TextInput(attrs={"autofocus": True}),
        )
    }

    for f in config.filter_fields:
        if f.filter_type == "range":
            if f.is_date_range:
                field_dict[f"{f.name}__gte"] = forms.DateField(
                    required=False,
                    label=f"From",
                    widget=forms.DateInput(attrs={"type": "date"}),
                )
                field_dict[f"{f.name}__lte"] = forms.DateField(
                    required=False,
                    label="To",
                    widget=forms.DateInput(attrs={"type": "date"}),
                )
            else:
                field_dict[f"{f.name}__gte"] = forms.DecimalField(
                    required=False,
                    label="From",
                    widget=forms.NumberInput(),
                )
                field_dict[f"{f.name}__lte"] = forms.DecimalField(
                    required=False,
                    label="To",
                    widget=forms.NumberInput(),
                )

        elif f.filter_type == "category":
            choices = [(v, v) for v in f.choices]
            field_dict[f.name] = forms.MultipleChoiceField(
                required=False,
                choices=choices,
                label=f.label,
                widget=forms.SelectMultiple(),
            )

        elif f.filter_type == "value":
            field_dict[f.name] = forms.CharField(
                required=False,
                label=f.label,
                widget=forms.TextInput(),
            )

    return type("SearchForm", (forms.Form,), field_dict)


# ---------------------------------------------------------------------------
# Memoised accessor (rebuilt if config changes, but config is static)
# ---------------------------------------------------------------------------
_search_form_class: type[forms.Form] | None = None


def get_search_form_class() -> type[forms.Form]:
    global _search_form_class
    if _search_form_class is None:
        from portal.config import get_config

        _search_form_class = build_search_form(get_config())
    return _search_form_class
