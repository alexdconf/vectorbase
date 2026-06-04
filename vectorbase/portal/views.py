"""
Portal views: semantic + metadata search over the configured pgvector table.
"""

from __future__ import annotations

import sys
import logging
from datetime import date

from django.conf import settings
from django.db.models import F
from django.shortcuts import render
from django_ratelimit.decorators import ratelimit

from logs.services import record_event
from portal.config import get_config
from portal.forms import get_search_form_class
from portal.models import DailyQuota

logger = logging.getLogger(__name__)


@ratelimit(key="ip", rate=settings.SEARCH_RATE_LIMIT, method=["GET"], block=False)
def search(request):
    """
    Main search view.

    GET with no parameters → empty search form.
    GET with ``q`` and/or filter params → execute search, render results.

    Rate limiting (per-IP) and global daily quota are checked before any
    search is executed.  Both render ``portal/429.html`` with HTTP 429 on
    exhaustion.
    """
    # --- Per-IP rate limit check ----------------------------------------
    if getattr(request, "limited", False):
        return render(request, "portal/429.html", {}, status=429)

    cfg = get_config()
    SearchFormClass = get_search_form_class()
    form = SearchFormClass(request.GET or None)

    # Determine whether the user actually submitted a search
    has_input = bool(request.GET.get("q") or any(
        request.GET.get(f.name) or
        request.GET.get(f"{f.name}__gte") or
        request.GET.get(f"{f.name}__lte")
        for f in cfg.filter_fields
    ))

    results = []
    result_count = None
    form_has_errors = False  # True only when the user submitted but validation failed

    if has_input:
        if not form.is_valid():
            # Validation failed — errors are already on the form; surface them
            # clearly rather than silently discarding the submission.
            form_has_errors = True
        else:
            # --- Global daily quota check -----------------------------------
            quota, _ = DailyQuota.objects.get_or_create(date=date.today())
            if quota.count >= settings.GLOBAL_DAILY_QUOTA:
                return render(
                    request,
                    "portal/429.html",
                    {"quota_exceeded": True},
                    status=429,
                )

            # --- Execute search ---------------------------------------------
            cleaned = form.cleaned_data
            query_text = cleaned.get("q", "")
            # Only pass filter keys that have a meaningful value; None / [] / ""
            # are handled gracefully by search() but cleaner to exclude here.
            filters = {
                k: v
                for k, v in cleaned.items()
                if k != "q" and v is not None and v != "" and v != []
            }

            from portal import search as search_module

            raw_results = search_module.search(
                query_text=query_text,
                filters=filters,
                top_k=cfg.top_k,
            )

            # --- Increment quota atomically --------------------------------
            DailyQuota.objects.filter(date=date.today()).update(count=F("count") + 1)

            # --- Log to Logs ----------------------------------------------
            try:
                record_event(
                    level=logging.CRITICAL,
                    message=dict(
                        query_text=query_text,
                        filters={k: str(v) for k, v in filters.items()},
                        result_count=len(raw_results)
                    )
                )
            except Exception as exc:  # noqa: BLE001
                sys.stderr.write(f"Could not write audit log: {exc}")

            # --- Shape results for template --------------------------------
            result_count = len(raw_results)
            results = [
                {
                    "fields": [
                        (field.label, row.get(field.name))
                        for field in cfg.result_fields
                    ],
                    "similarity": row.get("similarity"),
                }
                for row in raw_results
            ]

    # --- Build filter groups for template rendering --------------------
    filter_groups = _build_filter_groups(cfg, form)

    return render(
        request,
        "portal/search.html",
        {
            "form": form,
            "filter_groups": filter_groups,
            "results": results,
            "result_count": result_count,
            "has_input": has_input,
            "form_has_errors": form_has_errors,
        },
    )


def _build_filter_groups(cfg, form) -> list[dict]:
    """
    Construct a list of filter-group dicts for the template.

    Each dict describes one filter widget or widget pair (for range filters).
    """
    groups = []
    for field_cfg in cfg.filter_fields:
        fname = field_cfg.name
        if field_cfg.filter_type == "range":
            groups.append(
                {
                    "label": field_cfg.label,
                    "type": "range",
                    "field_gte": form[f"{fname}__gte"],
                    "field_lte": form[f"{fname}__lte"],
                }
            )
        elif field_cfg.filter_type == "category":
            groups.append(
                {
                    "label": field_cfg.label,
                    "type": "category",
                    "field": form[fname],
                }
            )
        elif field_cfg.filter_type == "value":
            groups.append(
                {
                    "label": field_cfg.label,
                    "type": "value",
                    "field": form[fname],
                }
            )
    return groups
