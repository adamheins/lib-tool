import sys

import colorama


def yellow(s):
    if sys.stdout.isatty():
        return colorama.Fore.YELLOW + s + colorama.Fore.RESET
    return s


def bold(s):
    if sys.stdout.isatty():
        return colorama.Style.BRIGHT + s + colorama.Style.RESET_ALL
    return s
