from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel

class ValidationIssue(BaseModel):
    field: str
    issue_type: str # MATH_MISMATCH, GST_DETECTED, DUPLICATE_BILL, MISSING_FIELD, LOW_CONFIDENCE
    message: str
    severity: str # WARNING, ERROR

class AccountingValidationResult(BaseModel):
    is_valid: bool
    issues: List[ValidationIssue] = []
    calculated_subtotal: float
    calculated_final_amount: float
    discrepancy_amount: float = 0.0

class AccountingValidator:
    """
    Validates arithmetic, Non-GST compliance, item math (qty x rate),
    subtotals, discounts, rounding, and duplicate entries.
    """

    @staticmethod
    def validate_bill(
        bill_data: Dict[str, Any],
        existing_invoices: Optional[List[Dict[str, Any]]] = None
    ) -> AccountingValidationResult:
        issues: List[ValidationIssue] = []

        # 1. Non-GST check
        if bill_data.get("is_gst_detected", False):
            issues.append(
                ValidationIssue(
                    field="is_gst_detected",
                    issue_type="GST_DETECTED",
                    message="GST tax elements were detected on this invoice. This application is configured strictly for Non-GST accounting vouchers. Please review or confirm how to proceed.",
                    severity="ERROR"
                )
            )

        # 2. Line Items arithmetic check
        items = bill_data.get("items", [])
        if not items:
            issues.append(
                ValidationIssue(
                    field="items",
                    issue_type="MISSING_FIELD",
                    message="No line items detected on this bill.",
                    severity="ERROR"
                )
            )

        calc_subtotal = 0.0
        for idx, item in enumerate(items):
            qty = float(item.get("quantity", 0.0))
            rate = float(item.get("rate", 0.0))
            amt = float(item.get("amount", 0.0))
            item_name = item.get("raw_item_name", f"Item #{idx+1}")

            # Verify Qty x Rate
            expected_amt = round(qty * rate, 2)
            if rate > 0 and qty > 0 and abs(expected_amt - amt) > 0.10:
                issues.append(
                    ValidationIssue(
                        field=f"items[{idx}].amount",
                        issue_type="MATH_MISMATCH",
                        message=f"{item_name}: Quantity ({qty}) × Rate ({rate}) = ₹{expected_amt:.2f}, but bill states ₹{amt:.2f}.",
                        severity="ERROR"
                    )
                )

            calc_subtotal += amt

        calc_subtotal = round(calc_subtotal, 2)

        # 3. Subtotal check
        stated_subtotal = float(bill_data.get("subtotal", 0.0))
        if stated_subtotal > 0 and abs(calc_subtotal - stated_subtotal) > 0.50:
            issues.append(
                ValidationIssue(
                    field="subtotal",
                    issue_type="MATH_MISMATCH",
                    message=f"Sum of items (₹{calc_subtotal:.2f}) does not match stated subtotal (₹{stated_subtotal:.2f}).",
                    severity="ERROR"
                )
            )

        effective_subtotal = stated_subtotal if stated_subtotal > 0 else calc_subtotal

        # 4. Final Total Check
        discount = float(bill_data.get("discount", 0.0))
        charges = float(bill_data.get("additional_charges", 0.0))
        round_off = float(bill_data.get("round_off", 0.0))
        stated_final = float(bill_data.get("final_amount", 0.0))

        calc_final = round(effective_subtotal - discount + charges + round_off, 2)
        discrepancy = round(abs(calc_final - stated_final), 2)

        if stated_final > 0 and discrepancy > 0.50:
            issues.append(
                ValidationIssue(
                    field="final_amount",
                    issue_type="MATH_MISMATCH",
                    message=f"Calculated final amount ₹{calc_final:.2f} differs from bill total ₹{stated_final:.2f} by ₹{discrepancy:.2f}.",
                    severity="ERROR"
                )
            )

        # 5. Duplicate Check
        inv_no = bill_data.get("invoice_number")
        party = bill_data.get("party_name")
        if inv_no and party and existing_invoices:
            for past in existing_invoices:
                if (past.get("invoice_number", "").strip().lower() == inv_no.strip().lower() and
                    past.get("party_name", "").strip().lower() == party.strip().lower()):
                    issues.append(
                        ValidationIssue(
                            field="invoice_number",
                            issue_type="DUPLICATE_BILL",
                            message=f"Possible duplicate invoice! Invoice #{inv_no} for party '{party}' already exists in your records.",
                            severity="WARNING"
                        )
                    )
                    break

        has_errors = any(i.severity == "ERROR" for i in issues)
        return AccountingValidationResult(
            is_valid=not has_errors,
            issues=issues,
            calculated_subtotal=calc_subtotal,
            calculated_final_amount=calc_final,
            discrepancy_amount=discrepancy
        )

accounting_validator = AccountingValidator()

