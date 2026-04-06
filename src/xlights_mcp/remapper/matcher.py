"""Multi-priority model matching algorithm for sequence remapping.

Implements the priority pipeline:
  0. Manual overrides  (applied first, removes from pools)
  1. Exact name match  (case-insensitive, whitespace-trimmed)
  2. Similar word match (shared significant tokens, pixel tie-break)
  3. Model type match   (same display_as + pixel compatible)
  4. Similar prop match  (shared prop word + pixel compatible)
  5. Pixel count fallback (closest compatible pixel count)
"""

from __future__ import annotations

import logging
from collections import defaultdict

from xlights_mcp.remapper.models import (
    FILLER_WORDS,
    MappingReport,
    MatchCandidate,
    MatchRule,
    ModelMapping,
    UnmatchedModel,
    ImportedModelMeta,
    _tokenize_name,
)
from xlights_mcp.xlights.models import LightModel, ModelGroup

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pixel compatibility helper  (T020)
# ---------------------------------------------------------------------------


def pixel_counts_compatible(a: int, b: int, threshold: float = 0.70) -> bool:
    """Check if two pixel counts are within the threshold ratio.

    Returns False if either count is 0 (unknown).
    """
    if a <= 0 or b <= 0:
        return False
    return min(a, b) / max(a, b) >= threshold


def _pixel_ratio(a: int, b: int) -> float:
    """Compute pixel ratio, returning 0.0 if either is unknown."""
    if a <= 0 or b <= 0:
        return 0.0
    return min(a, b) / max(a, b)


# ---------------------------------------------------------------------------
# Candidate building  (T007, T008)
# ---------------------------------------------------------------------------


def build_candidates_from_user_show(
    models: list[LightModel],
    groups: list[ModelGroup],
) -> list[MatchCandidate]:
    """Convert user's LightModel/ModelGroup lists into MatchCandidates."""
    candidates: list[MatchCandidate] = []

    for m in models:
        candidates.append(
            MatchCandidate(
                name=m.name,
                pixel_count=m.pixel_count,
                display_as=m.display_as,
                is_group=False,
                face_definitions=list(m.face_definitions),
                source="user",
            )
        )

    for g in groups:
        candidates.append(
            MatchCandidate(
                name=g.name,
                pixel_count=0,  # groups don't have a direct pixel count
                display_as="",
                is_group=True,
                source="user",
            )
        )

    return candidates


def build_candidates_from_import(
    model_names: list[str],
    imported_meta: list[ImportedModelMeta] | None = None,
) -> list[MatchCandidate]:
    """Convert imported model names into MatchCandidates.

    When `imported_meta` is provided (from zip package), candidates are
    enriched with display_as, pixel_count, face_definitions.
    """
    meta_lookup: dict[str, ImportedModelMeta] = {}
    if imported_meta:
        for m in imported_meta:
            meta_lookup[m.name] = m

    candidates: list[MatchCandidate] = []
    for name in model_names:
        meta = meta_lookup.get(name)
        if meta:
            candidates.append(
                MatchCandidate(
                    name=name,
                    pixel_count=meta.pixel_count,
                    display_as=meta.display_as,
                    is_group=meta.is_group,
                    face_definitions=list(meta.face_definitions),
                    source="imported",
                )
            )
        else:
            candidates.append(
                MatchCandidate(
                    name=name,
                    source="imported",
                )
            )

    return candidates


# ---------------------------------------------------------------------------
# Priority 0: Manual overrides  (T040)
# ---------------------------------------------------------------------------


def _apply_overrides(
    overrides: dict[str, str],
    imported_pool: dict[str, MatchCandidate],
    user_pool: dict[str, MatchCandidate],
) -> tuple[list[ModelMapping], list[str]]:
    """Apply manual overrides, removing matched pairs from pools.

    Returns (mappings, warnings).
    """
    mappings: list[ModelMapping] = []
    warnings: list[str] = []

    for imp_name, usr_name in overrides.items():
        # Find imported candidate (case-insensitive)
        imp_key = None
        for k in imported_pool:
            if k.lower().strip() == imp_name.lower().strip():
                imp_key = k
                break

        usr_key = None
        for k in user_pool:
            if k.lower().strip() == usr_name.lower().strip():
                usr_key = k
                break

        if imp_key is None:
            warnings.append(
                f"Override ignored: imported model '{imp_name}' not found in sequence"
            )
            continue
        if usr_key is None:
            warnings.append(
                f"Override ignored: user model '{usr_name}' not found in show"
            )
            continue

        mappings.append(
            ModelMapping(
                imported_name=imported_pool[imp_key].name,
                user_name=user_pool[usr_key].name,
                rule=MatchRule.MANUAL_OVERRIDE,
                confidence=1.0,
                notes=f"Manual override: '{imp_name}' → '{usr_name}'",
            )
        )
        del imported_pool[imp_key]
        del user_pool[usr_key]

    return mappings, warnings


# ---------------------------------------------------------------------------
# Priority 1: Exact name match  (T009)
# ---------------------------------------------------------------------------


def _match_exact_name(
    imported_pool: dict[str, MatchCandidate],
    user_pool: dict[str, MatchCandidate],
) -> list[ModelMapping]:
    """Match by case-insensitive, whitespace-trimmed exact name."""
    mappings: list[ModelMapping] = []

    # Build normalised lookup for user pool
    user_by_norm: dict[str, str] = {}
    for key, cand in user_pool.items():
        user_by_norm[cand.normalized_name] = key

    matched_imported: list[str] = []
    matched_user: list[str] = []

    for imp_key, imp_cand in imported_pool.items():
        usr_key = user_by_norm.get(imp_cand.normalized_name)
        if usr_key and usr_key not in matched_user:
            mappings.append(
                ModelMapping(
                    imported_name=imp_cand.name,
                    user_name=user_pool[usr_key].name,
                    rule=MatchRule.EXACT_NAME,
                    confidence=1.0,
                    notes="Exact name match (case-insensitive)",
                )
            )
            matched_imported.append(imp_key)
            matched_user.append(usr_key)

    for k in matched_imported:
        del imported_pool[k]
    for k in matched_user:
        del user_pool[k]

    return mappings


# ---------------------------------------------------------------------------
# Priority 2: Similar word match  (T021)
# ---------------------------------------------------------------------------


def _match_similar_word(
    imported_pool: dict[str, MatchCandidate],
    user_pool: dict[str, MatchCandidate],
) -> list[ModelMapping]:
    """Match by shared significant tokens, tie-break by pixel closeness."""
    if not imported_pool or not user_pool:
        return []

    # Build token → user candidates index
    user_by_token: dict[str, list[str]] = defaultdict(list)
    for key, cand in user_pool.items():
        for token in cand.name_tokens:
            user_by_token[token].append(key)

    # Find all potential pairs with shared tokens
    pairs: list[tuple[str, str, list[str], float]] = []
    for imp_key, imp_cand in imported_pool.items():
        for token in imp_cand.name_tokens:
            for usr_key in user_by_token.get(token, []):
                usr_cand = user_pool[usr_key]
                shared = sorted(
                    set(imp_cand.name_tokens) & set(usr_cand.name_tokens)
                )
                if shared:
                    # Confidence = shared / max tokens
                    max_tokens = max(
                        len(imp_cand.name_tokens),
                        len(usr_cand.name_tokens),
                        1,
                    )
                    confidence = len(shared) / max_tokens
                    pairs.append((imp_key, usr_key, shared, confidence))

    # Deduplicate pairs
    seen: set[tuple[str, str]] = set()
    unique_pairs: list[tuple[str, str, list[str], float]] = []
    for imp_key, usr_key, shared, conf in pairs:
        if (imp_key, usr_key) not in seen:
            seen.add((imp_key, usr_key))
            unique_pairs.append((imp_key, usr_key, shared, conf))

    # Sort: more shared tokens first, then by pixel closeness
    def _sort_key(pair: tuple[str, str, list[str], float]) -> tuple[float, float]:
        imp_key, usr_key, shared, conf = pair
        imp_px = imported_pool[imp_key].pixel_count
        usr_px = user_pool[usr_key].pixel_count
        px_ratio = _pixel_ratio(imp_px, usr_px) if imp_px and usr_px else 0.0
        return (-conf, -px_ratio)

    unique_pairs.sort(key=_sort_key)

    mappings: list[ModelMapping] = []
    used_imported: set[str] = set()
    used_user: set[str] = set()

    for imp_key, usr_key, shared, conf in unique_pairs:
        if imp_key in used_imported or usr_key in used_user:
            continue
        imp_cand = imported_pool[imp_key]
        usr_cand = user_pool[usr_key]

        px = _pixel_ratio(imp_cand.pixel_count, usr_cand.pixel_count)
        note_parts = [f"Shared word(s): {', '.join(shared)}"]
        if px > 0:
            note_parts.append(
                f"pixel ratio {imp_cand.pixel_count}/{usr_cand.pixel_count}="
                f"{px:.2f}"
            )

        mappings.append(
            ModelMapping(
                imported_name=imp_cand.name,
                user_name=usr_cand.name,
                rule=MatchRule.SIMILAR_WORD,
                confidence=round(conf, 2),
                shared_tokens=shared,
                notes=", ".join(note_parts),
            )
        )
        used_imported.add(imp_key)
        used_user.add(usr_key)

    for k in used_imported:
        del imported_pool[k]
    for k in used_user:
        del user_pool[k]

    return mappings


# ---------------------------------------------------------------------------
# Priority 3: Model type match  (T025)
# ---------------------------------------------------------------------------


def _match_model_type(
    imported_pool: dict[str, MatchCandidate],
    user_pool: dict[str, MatchCandidate],
    threshold: float = 0.70,
) -> list[ModelMapping]:
    """Match by same display_as value + pixel count compatibility.

    Skipped entirely if no imported candidates have display_as set.
    """
    if not imported_pool or not user_pool:
        return []

    # Skip if no imported candidate has type info
    has_type = any(c.display_as for c in imported_pool.values())
    if not has_type:
        return []

    # Build type → user candidates index
    user_by_type: dict[str, list[str]] = defaultdict(list)
    for key, cand in user_pool.items():
        if cand.display_as:
            user_by_type[cand.display_as.lower()].append(key)

    mappings: list[ModelMapping] = []
    used_imported: set[str] = set()
    used_user: set[str] = set()

    # Sort imported by pixel count descending (larger models first)
    sorted_imported = sorted(
        imported_pool.items(),
        key=lambda kv: kv[1].pixel_count,
        reverse=True,
    )

    for imp_key, imp_cand in sorted_imported:
        if imp_key in used_imported or not imp_cand.display_as:
            continue

        type_key = imp_cand.display_as.lower()
        candidates_for_type = user_by_type.get(type_key, [])

        best_usr_key = None
        best_ratio = 0.0

        for usr_key in candidates_for_type:
            if usr_key in used_user:
                continue
            usr_cand = user_pool[usr_key]
            if pixel_counts_compatible(
                imp_cand.pixel_count, usr_cand.pixel_count, threshold
            ):
                ratio = _pixel_ratio(imp_cand.pixel_count, usr_cand.pixel_count)
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_usr_key = usr_key

        if best_usr_key is not None:
            usr_cand = user_pool[best_usr_key]
            mappings.append(
                ModelMapping(
                    imported_name=imp_cand.name,
                    user_name=usr_cand.name,
                    rule=MatchRule.MODEL_TYPE,
                    confidence=round(best_ratio, 2),
                    pixel_ratio=round(best_ratio, 4),
                    notes=(
                        f"Same type '{imp_cand.display_as}', "
                        f"pixel ratio {imp_cand.pixel_count}/{usr_cand.pixel_count}="
                        f"{best_ratio:.2f}"
                    ),
                )
            )
            used_imported.add(imp_key)
            used_user.add(best_usr_key)

    for k in used_imported:
        del imported_pool[k]
    for k in used_user:
        del user_pool[k]

    return mappings


# ---------------------------------------------------------------------------
# Priority 4: Similar prop match  (T026)
# ---------------------------------------------------------------------------

# Common prop-type words that indicate similar physical props
_PROP_WORDS = frozenset(
    {
        "snowflake",
        "arch",
        "tree",
        "candy",
        "cane",
        "star",
        "wreath",
        "deer",
        "reindeer",
        "snowman",
        "present",
        "gift",
        "candle",
        "icicle",
        "spiral",
        "spinner",
        "globe",
        "sphere",
        "matrix",
        "mega",
        "mini",
        "window",
        "garland",
        "fence",
        "bush",
        "net",
        "pixel",
        "stake",
        "flood",
        "spot",
        "leaping",
        "light",
    }
)


def _match_similar_prop(
    imported_pool: dict[str, MatchCandidate],
    user_pool: dict[str, MatchCandidate],
    threshold: float = 0.70,
) -> list[ModelMapping]:
    """Match by shared prop-type word + pixel count compatibility."""
    if not imported_pool or not user_pool:
        return []

    # Build prop-word → user candidates index
    user_by_prop: dict[str, list[str]] = defaultdict(list)
    for key, cand in user_pool.items():
        for token in cand.name_tokens:
            if token in _PROP_WORDS:
                user_by_prop[token].append(key)

    mappings: list[ModelMapping] = []
    used_imported: set[str] = set()
    used_user: set[str] = set()

    for imp_key, imp_cand in list(imported_pool.items()):
        if imp_key in used_imported:
            continue

        imp_props = [t for t in imp_cand.name_tokens if t in _PROP_WORDS]
        if not imp_props:
            continue

        best_usr_key = None
        best_ratio = 0.0
        best_shared: list[str] = []

        for prop_word in imp_props:
            for usr_key in user_by_prop.get(prop_word, []):
                if usr_key in used_user:
                    continue
                usr_cand = user_pool[usr_key]
                if not pixel_counts_compatible(
                    imp_cand.pixel_count, usr_cand.pixel_count, threshold
                ):
                    continue
                ratio = _pixel_ratio(imp_cand.pixel_count, usr_cand.pixel_count)
                shared = sorted(
                    set(imp_props) & {t for t in usr_cand.name_tokens if t in _PROP_WORDS}
                )
                if ratio > best_ratio and shared:
                    best_ratio = ratio
                    best_usr_key = usr_key
                    best_shared = shared

        if best_usr_key is not None:
            usr_cand = user_pool[best_usr_key]
            mappings.append(
                ModelMapping(
                    imported_name=imp_cand.name,
                    user_name=usr_cand.name,
                    rule=MatchRule.SIMILAR_PROP,
                    confidence=round(best_ratio, 2),
                    pixel_ratio=round(best_ratio, 4),
                    shared_tokens=best_shared,
                    notes=(
                        f"Shared prop word(s): {', '.join(best_shared)}, "
                        f"pixel ratio {imp_cand.pixel_count}/{usr_cand.pixel_count}="
                        f"{best_ratio:.2f}"
                    ),
                )
            )
            used_imported.add(imp_key)
            used_user.add(best_usr_key)

    for k in used_imported:
        del imported_pool[k]
    for k in used_user:
        del user_pool[k]

    return mappings


# ---------------------------------------------------------------------------
# Priority 5: Pixel count fallback  (T032)
# ---------------------------------------------------------------------------


def _match_pixel_count_fallback(
    imported_pool: dict[str, MatchCandidate],
    user_pool: dict[str, MatchCandidate],
    threshold: float = 0.70,
) -> list[ModelMapping]:
    """Match remaining models purely by closest compatible pixel count."""
    if not imported_pool or not user_pool:
        return []

    mappings: list[ModelMapping] = []
    used_imported: set[str] = set()
    used_user: set[str] = set()

    # Sort imported by pixel count descending
    sorted_imported = sorted(
        imported_pool.items(),
        key=lambda kv: kv[1].pixel_count,
        reverse=True,
    )

    for imp_key, imp_cand in sorted_imported:
        if imp_key in used_imported or imp_cand.pixel_count <= 0:
            continue

        best_usr_key = None
        best_diff = float("inf")
        best_ratio = 0.0

        for usr_key, usr_cand in user_pool.items():
            if usr_key in used_user or usr_cand.pixel_count <= 0:
                continue
            if not pixel_counts_compatible(
                imp_cand.pixel_count, usr_cand.pixel_count, threshold
            ):
                continue
            diff = abs(imp_cand.pixel_count - usr_cand.pixel_count)
            if diff < best_diff:
                best_diff = diff
                best_ratio = _pixel_ratio(imp_cand.pixel_count, usr_cand.pixel_count)
                best_usr_key = usr_key

        if best_usr_key is not None:
            usr_cand = user_pool[best_usr_key]
            mappings.append(
                ModelMapping(
                    imported_name=imp_cand.name,
                    user_name=usr_cand.name,
                    rule=MatchRule.PIXEL_COUNT_FALLBACK,
                    confidence=round(best_ratio, 2),
                    pixel_ratio=round(best_ratio, 4),
                    notes=(
                        f"Pixel count fallback: "
                        f"{imp_cand.pixel_count}→{usr_cand.pixel_count} "
                        f"(ratio {best_ratio:.2f})"
                    ),
                )
            )
            used_imported.add(imp_key)
            used_user.add(best_usr_key)

    for k in used_imported:
        del imported_pool[k]
    for k in used_user:
        del user_pool[k]

    return mappings


# ---------------------------------------------------------------------------
# Unmatched reasoning  (T036)
# ---------------------------------------------------------------------------


def _generate_unmatched_reasons(
    imported_pool: dict[str, MatchCandidate],
    user_pool: dict[str, MatchCandidate],
    threshold: float,
) -> tuple[list[UnmatchedModel], list[UnmatchedModel]]:
    """Generate human-readable reasons for each unmatched model."""
    unmatched_imported: list[UnmatchedModel] = []
    for cand in imported_pool.values():
        if cand.is_singing and not any(
            u.is_singing for u in user_pool.values()
        ):
            reason = "Singing model with no singing target in user show"
        elif cand.pixel_count <= 0:
            reason = "No pixel count data available for matching"
        else:
            reason = (
                f"No compatible user model: no name overlap, "
                f"pixel count {cand.pixel_count} "
                f"below {threshold:.0%} threshold with remaining candidates"
            )
        unmatched_imported.append(
            UnmatchedModel(
                name=cand.name,
                source="imported",
                reason=reason,
                pixel_count=cand.pixel_count,
                display_as=cand.display_as,
                is_singing=cand.is_singing,
                is_group=cand.is_group,
            )
        )

    unmatched_user: list[UnmatchedModel] = []
    for cand in user_pool.values():
        unmatched_user.append(
            UnmatchedModel(
                name=cand.name,
                source="user",
                reason="No imported model matched this user model",
                pixel_count=cand.pixel_count,
                display_as=cand.display_as,
                is_singing=cand.is_singing,
                is_group=cand.is_group,
            )
        )

    return unmatched_imported, unmatched_user


# ---------------------------------------------------------------------------
# Report statistics  (T035)
# ---------------------------------------------------------------------------


def _compute_report_statistics(
    mappings: list[ModelMapping],
) -> dict[str, int]:
    """Compute match rule distribution from the mapping list."""
    dist: dict[str, int] = {}
    for m in mappings:
        key = m.rule.value
        dist[key] = dist.get(key, 0) + 1
    return dist


# ---------------------------------------------------------------------------
# Main orchestrator  (T010)
# ---------------------------------------------------------------------------


def match_models(
    imported_candidates: list[MatchCandidate],
    user_candidates: list[MatchCandidate],
    threshold: float = 0.70,
    overrides: dict[str, str] | None = None,
    imported_source: str = "",
    has_imported_metadata: bool = False,
    timing_tracks_preserved: int = 0,
    extracted_assets: list | None = None,
) -> MappingReport:
    """Run the full priority matching pipeline.

    Steps:
        0. Apply manual overrides (if any)
        1. Partition into singing / non-singing pools
        2. Run priority 1–5 on singing pool, then non-singing pool
        3. Assemble MappingReport with statistics and reasons
    """
    # Build pools keyed by name for O(1) removal
    imported_pool: dict[str, MatchCandidate] = {c.name: c for c in imported_candidates}
    user_pool: dict[str, MatchCandidate] = {c.name: c for c in user_candidates}

    total_imported = len(imported_pool)
    total_user = len(user_pool)

    all_mappings: list[ModelMapping] = []
    all_warnings: list[str] = []

    # --- Priority 0: Manual overrides ---
    if overrides:
        override_mappings, override_warnings = _apply_overrides(
            overrides, imported_pool, user_pool
        )
        all_mappings.extend(override_mappings)
        all_warnings.extend(override_warnings)

    # --- Partition into singing / non-singing ---
    def _partition(
        pool: dict[str, MatchCandidate],
    ) -> tuple[dict[str, MatchCandidate], dict[str, MatchCandidate]]:
        singing = {k: v for k, v in pool.items() if v.is_singing}
        non_singing = {k: v for k, v in pool.items() if not v.is_singing}
        return singing, non_singing

    singing_imp, non_singing_imp = _partition(imported_pool)
    singing_usr, non_singing_usr = _partition(user_pool)

    # --- Run priority pipeline on each pool ---
    def _run_pipeline(
        imp_pool: dict[str, MatchCandidate],
        usr_pool: dict[str, MatchCandidate],
    ) -> list[ModelMapping]:
        results: list[ModelMapping] = []
        # P1: Exact name
        results.extend(_match_exact_name(imp_pool, usr_pool))
        # P2: Similar word
        results.extend(_match_similar_word(imp_pool, usr_pool))
        # P3: Model type (only if metadata available)
        results.extend(_match_model_type(imp_pool, usr_pool, threshold))
        # P4: Similar prop
        results.extend(_match_similar_prop(imp_pool, usr_pool, threshold))
        # P5: Pixel count fallback
        results.extend(_match_pixel_count_fallback(imp_pool, usr_pool, threshold))
        return results

    all_mappings.extend(_run_pipeline(singing_imp, singing_usr))
    all_mappings.extend(_run_pipeline(non_singing_imp, non_singing_usr))

    # --- Merge remaining pools for unmatched reasoning ---
    remaining_imported = {**singing_imp, **non_singing_imp}
    remaining_user = {**singing_usr, **non_singing_usr}

    unmatched_imported, unmatched_user = _generate_unmatched_reasons(
        remaining_imported, remaining_user, threshold
    )

    # --- Statistics ---
    dist = _compute_report_statistics(all_mappings)

    return MappingReport(
        mappings=all_mappings,
        unmatched_imported=unmatched_imported,
        unmatched_user=unmatched_user,
        extracted_assets=extracted_assets or [],
        warnings=all_warnings,
        total_imported_models=total_imported,
        total_user_models=total_user,
        total_matched=len(all_mappings),
        match_rule_distribution=dist,
        imported_source=imported_source,
        has_imported_metadata=has_imported_metadata,
        timing_tracks_preserved=timing_tracks_preserved,
    )
