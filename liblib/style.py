import colorama


def yellow(s):
    return colorama.Fore.YELLOW + s + colorama.Fore.RESET


def bold(s):
    return colorama.Style.BRIGHT + s + colorama.Style.RESET_ALL
