#!/usr/bin/env python3

import argparse
import glob
import os
import re
import shutil
import sys

import bibtexparser
import colorama


LIB_ROOT = '/home/adam/doc/library'
ARCHIVE_ROOT = os.path.join(LIB_ROOT, 'archive')
SHELVES_ROOT = os.path.join(LIB_ROOT, 'shelves')


def yellow(s):
    return colorama.Fore.YELLOW + s + colorama.Fore.RESET

def bold(s):
    return colorama.Style.BRIGHT + s + colorama.Style.RESET_ALL


def get_archive_path(key):
    return os.path.join(ARCHIVE_ROOT, key)


def compile_bib_info():
    bib_list = glob.glob(ARCHIVE_ROOT + '/**/*.bib')
    bib_info_list = []

    for bib_path in bib_list:
        with open(bib_path) as bib_file:
            bib_info_list.append(bib_file.read().strip())

    return '\n\n'.join(bib_info_list)


def do_ln(**kwargs):
    doc = kwargs['document']
    cwd = os.getcwd()
    src = os.path.join(ARCHIVE_ROOT, doc)
    dest = os.path.join(cwd, doc)
    os.symlink(src, dest)


def do_grep(**kwargs):
    ''' Search for a regex in the library. '''
    if kwargs['ignore_case']:
        regex = re.compile(kwargs['regex'], re.IGNORECASE)
    else:
        regex = re.compile(kwargs['regex'])

    def repl(match):
        return yellow(match.group(0))

    if kwargs['bib']:
        bib_dict = bibtexparser.loads(compile_bib_info()).entries_dict
        output = []
        for key, info in bib_dict.items():
            count = 0
            detail = []
            for field, value in info.items():
                result = regex.findall(value)
                count += len(result)
                if len(result) == 0:
                    continue

                s = regex.sub(repl, value)
                detail.append('  {}: {}'.format(field, s))

            if count > 0:
                file_output = []
                if count == 1:
                    file_output.append('{}: 1 match'.format(bold(key)))
                else:
                    file_output.append('{}: {} matches'.format(bold(key), count))
                if not kwargs['oneline']:
                    file_output.append('\n'.join(detail))
                output.append('\n'.join(file_output))
        print('\n\n'.join(output))



def entry_html(key, data):
    title = '<h2>{}</h2>'.format(data['title'])
    year = '<p>{}</p>'.format(data['year'])
    author = '<p>{}</p>'.format(data['author'])

    text_link = '<a href="{}">(text)</a>'.format('')
    bib_link = '<a href="{}">(bib)</a>'.format('')
    links = '<div>{}{}</div>'.format(text_link, bib_link)

    return '<div>{}{}{}{}</div>'.format(title, links, year, author)


def do_index(**kwargs):
    # Create an index file with links and information for easy browsing.
    bib_dict = bibtexparser.loads(compile_bib_info()).entries_dict
    index_entries = []
    for key in bib_dict.keys():
        index_entries.append(entry_html(key, bib_dict[key]))
    index_html = '<html><body>' + ''.join(index_entries) + '</body></html>'
    with open('index.html', 'w') as index_file:
        index_file.write(index_html)


def do_compile(**kwargs):
    ''' Compile a single bibtex file and/or a single directory of PDFs. '''
    if kwargs['bib']:
        with open('bibtex.bib', 'w') as bib_file:
            bib_file.write(compile_bib_info())
        print('Compiled bibtex files to bibtex.bib.')

    # TODO parse compiled bib file to get information about PDFs in an HTML file
    if kwargs['text']:
        os.mkdir('text')
        pdf_list = glob.glob(ARCHIVE_ROOT + '/**/*.pdf')
        for pdf_path in pdf_list:
            shutil.copy(pdf_path, 'text')

        print('Copied PDFs to text/.')


def do_add(**kwargs):
    ''' Add a PDF and associated bibtex file to the archive. '''
    pdf_fn = kwargs['pdf']
    bib_fn = kwargs['bibtex']

    with open(bib_fn) as bib_file:
        bib_info = bibtexparser.load(bib_file)

    keys = list(bib_info.entries_dict.keys())
    if len(keys) > 1:
        print('It looks like there\'s more than one entry in the bibtex file. '
            + 'I\'m not sure what to do!')
        return 1

    key = keys[0]

    archive_path = get_archive_path(key)
    if os.path.exists(archive_path):
        print('Archive {} already exists! Aborting.'.format(key))
        return 1

    archive_pdf_path = os.path.join(archive_path, key + '.pdf')
    archive_bib_path = os.path.join(archive_path, key + '.bib')

    os.mkdir(archive_path)
    if kwargs['delete']:
        shutil.move(pdf_fn, archive_pdf_path)
        shutil.move(bib_fn, archive_bib_path)
    else:
        shutil.copy(pdf_fn, archive_pdf_path)
        shutil.copy(bib_fn, archive_bib_path)

    print('Archived to {}.'.format(key))
    return 0


def main():
    if len(sys.argv) <= 1:
        print('Usage: lib command [opts] [args]. Try --help.')
        return 1

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='Command.')

    ln_parser = subparsers.add_parser('ln')
    ln_parser.add_argument('document', help='Document to link')
    ln_parser.set_defaults(func=do_ln)

    ln_parser = subparsers.add_parser('index')
    ln_parser.set_defaults(func=do_index)

    grep_parser = subparsers.add_parser('grep')
    grep_parser.add_argument('regex', help='Search for the regex')
    grep_parser.add_argument('-b', '--bib', '--bibtex', action='store_true',
                             help='Search bibtex files.')
    grep_parser.add_argument('-t', '--text', action='store_true',
                             help='Search document text.')
    grep_parser.add_argument('-o', '--oneline', action='store_true',
                             help='Only output filename and match count.')
    grep_parser.add_argument('-i', '--ignore-case', action='store_true',
                             help='Case insensitive search.')
    grep_parser.set_defaults(func=do_grep)

    add_parser = subparsers.add_parser('add')
    add_parser.add_argument('pdf', help='PDF file.')
    add_parser.add_argument('bibtex', help='Associated bibtex file.')
    add_parser.add_argument('-d', '--delete', action='store_true',
                            help='Delete files after archiving.')
    add_parser.set_defaults(func=do_add)

    compile_parser = subparsers.add_parser('compile')
    compile_parser.add_argument('-b', '--bib', '--bibtex', action='store_true',
                                help='Compile bibtex files.')
    compile_parser.add_argument('-t', '--text', action='store_true',
                                help='Compile PDF documents.')
    compile_parser.set_defaults(func=do_compile)

    # Every subparser has an associated function that we call here, passing all
    # other options as arguments.
    args = parser.parse_args()
    args = vars(args)
    func = args.pop('func')
    return func(**args)


if __name__ == '__main__':
    ret = main()
    exit(ret)
