"""Comprehensive income page package."""

__all__ = ["ComprehensiveIncomePage"]


def __getattr__(name):
    """Load the page lazily so step tests can import on non-Windows hosts."""
    if name != "ComprehensiveIncomePage":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from tax_rpa.pages.comprehensive_income.page import ComprehensiveIncomePage

    globals()[name] = ComprehensiveIncomePage
    return ComprehensiveIncomePage
