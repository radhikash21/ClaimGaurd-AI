
# Preliminary repair-to-damage mapping.
# These are category-level associations, not exact component localization.

REPAIR_DAMAGE_MAPPING = {
    "bumper": ["dent", "scratch", "crack"],
    "headlight": ["lamp broken", "glass shatter", "crack"],
    "windshield": ["glass shatter", "crack"],
    "window": ["glass shatter", "crack"],
    "tire": ["tire flat"],
    "tyre": ["tire flat"]
}


def compare_repairs_with_damage(repair_items, detected_damages):
    """Compare invoice repair descriptions with detected damage classes."""

    detected = {
        damage.lower()
        for damage in detected_damages
    }

    comparison = []

    for item in repair_items:
        description = item["description"]
        description_lower = description.lower()

        # Labour charges require separate review.
        if "labour" in description_lower or "labor" in description_lower:
            status = "Service charge - separate review"
            matched_damages = []

        else:
            possible_matches = []

            for component, damage_classes in REPAIR_DAMAGE_MAPPING.items():
                if component in description_lower:
                    possible_matches.extend(damage_classes)

            matched_damages = sorted(
                set(possible_matches).intersection(detected)
            )

            if matched_damages:
                status = "Potentially supported by detected damage"
            else:
                status = "Needs manual verification"

        comparison.append({
            "repair_description": description,
            "repair_amount": item["amount"],
            "status": status,
            "related_detected_damages": matched_damages
        })

    return comparison


def find_unbilled_damages(detected_damages, repair_comparison):
    """Identify detected categories not associated with invoice repairs."""

    billed_damage_categories = set()

    for item in repair_comparison:
        billed_damage_categories.update(
            item["related_detected_damages"]
        )

    unbilled = sorted(
        {
            damage.lower()
            for damage in detected_damages
        } - billed_damage_categories
    )

    return unbilled


def calculate_claim_risk(
    total_validation,
    repair_comparison,
    unbilled_damages
):
    """
    Calculate a preliminary audit-priority score.

    This score is a rule-based review indicator,
    NOT a probability of fraud.
    """

    score = 0
    reasons = []

    stated_total = total_validation.get("stated_total")
    calculated_total = total_validation.get("calculated_total")
    total_matches = total_validation.get("matches", False)

    # Invoice mismatch: 30 points.
    if stated_total is not None and not total_matches:
        score += 30
        reasons.append("Invoice total does not match calculated total.")

    elif stated_total is None:
        reasons.append("Invoice total could not be verified.")

    # Unmatched repair items: 10 points each, maximum 20.
    unmatched_repairs = [
        item for item in repair_comparison
        if item["status"] == "Needs manual verification"
    ]

    repair_points = min(len(unmatched_repairs) * 10, 20)
    score += repair_points

    if unmatched_repairs:
        reasons.append(
            f"{len(unmatched_repairs)} repair item(s) require manual verification."
        )

    # Potentially unbilled damage: 10 points each, maximum 20.
    unbilled_points = min(len(unbilled_damages) * 10, 20)
    score += unbilled_points

    if unbilled_damages:
        reasons.append(
            f"{len(unbilled_damages)} detected damage category/categories "
            "are not associated with invoice repairs."
        )

    score = min(score, 100)

    if score >= 60:
        priority = "High"
    elif score >= 30:
        priority = "Medium"
    else:
        priority = "Low"

    return {
        "risk_score": score,
        "priority": priority,
        "reasons": reasons,
        "is_fraud_probability": False
    }


def generate_audit_report(invoice_record, damage_result):
    """Combine invoice and damage results into one audit report."""

    repair_items = invoice_record["repair_items"]

    detected_damages = damage_result.get(
        "detected_damages", []
    )

    total_validation = invoice_record["total_validation"]

    repair_comparison = compare_repairs_with_damage(
        repair_items,
        detected_damages
    )

    unbilled_damages = find_unbilled_damages(
        detected_damages,
        repair_comparison
    )

    risk_assessment = calculate_claim_risk(
        total_validation,
        repair_comparison,
        unbilled_damages
    )

    return {
        "invoice_details": invoice_record["invoice_details"],
        "invoice_total": total_validation["stated_total"],
        "calculated_total": total_validation["calculated_total"],
        "total_matches": total_validation["matches"],
        "detected_damages": detected_damages,
        "repair_comparison": repair_comparison,
        "unbilled_damages": unbilled_damages,
        "risk_assessment": risk_assessment,
        "disclaimer": (
            "This is a preliminary automated audit. "
            "All flagged findings require human verification "
            "and do not establish fraud."
        )
    }
