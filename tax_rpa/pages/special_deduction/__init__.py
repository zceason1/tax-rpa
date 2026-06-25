"""Special deduction page package."""

__all__ = ["SpecialDeductionPage"]


def __getattr__(name):
    """Load the page lazily so step tests can import on non-Windows hosts."""
    if name != "SpecialDeductionPage":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from tax_rpa.pages.special_deduction.page import SpecialDeductionPage

    globals()[name] = SpecialDeductionPage
    return SpecialDeductionPage
