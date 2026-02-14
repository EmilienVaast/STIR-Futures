from decimal import Decimal, ROUND_HALF_UP


def round_half_up(x: float, decimals: int) -> float:
    """
    Decimal HALF_UP rounding (ties up), matching your existing quantize usage.
    """
    if decimals <= 0:
        q = Decimal("1")
    else:
        q = Decimal("0." + "0" * (decimals - 1) + "1")
    return float(Decimal(str(float(x))).quantize(q, rounding=ROUND_HALF_UP))
