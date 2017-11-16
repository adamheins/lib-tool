#!/usr/bin/env python
from __future__ import print_function

import os
import sys

import bibtexparser


def main():
    args = sys.argv[1:]

    if args[0].endswith('pdf'):
        pdf_file = args[0]
        bib_file = args[1]
    else:
        pdf_file = args[1]
        bib_file = args[2]

    with open(bib_file) as f:
        bib_data = bibtexparser.load(f)

    bib_key = bib_data.entries_dict.keys()[0]

    os.mkdir(bib_key)
    os.rename(pdf_file, os.path.join(bib_key, bib_key + '.pdf'))
    os.rename(bib_file, os.path.join(bib_key, bib_key + '.bib'))


if __name__ == '__main__':
    main()
