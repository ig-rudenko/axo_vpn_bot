def days_verbose(days: int) -> str:
    if days > 20:
        days %= 10
    if days == 1:
        return "день"
    elif days <= 4:
        return "дня"
    return "дней"


def month_verbose(month: int) -> str:
    if month > 20:
        month %= 10

    if month == 1:
        return "месяц"
    elif month <= 4:
        return "месяца"
    return "месяцев"
