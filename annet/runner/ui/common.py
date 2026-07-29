# ruff: noqa: T201
import colorama


def show_header(text: str, bg: str) -> None:
    if text:
        text = f" {text} "
    print(bg, f"# --------------------{text}--------------------", colorama.Back.RESET, sep="")


def format_header(name: str, gen: str, file: str | None) -> str:
    file = f": {colorama.Style.BRIGHT}{file}{colorama.Style.NORMAL}" if file else ""
    host, sep, domain = name.partition(".")
    name = f"{colorama.Style.BRIGHT}{host}{colorama.Style.NORMAL}{sep}{domain}"
    if gen:
        gen = f" ({gen})"
    return f"{name}{file}{gen}"


def group_similar(data: dict[str, str]) -> dict[str, str]:
    inversed: dict[str, list[str]] = {}
    for header, output in data.items():
        inversed.setdefault(output, []).append(header)
    return {", ".join(headers): output for output, headers in inversed.items()}


def show_result(data: dict[str, str], bg: str) -> None:
    data = group_similar(data)
    for header, output in data.items():
        show_header(header, bg)
        print(output)
