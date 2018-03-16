#!/usr/bin/env python3

import argparse
import os
import re
import shutil
import subprocess
import sys

import bibtexparser
import editor

from librarianlib import management, index, links, search
from librarianlib.exceptions import LibraryException


CONFIG_FILE_NAME = '.libconf.yaml'
CONFIG_SEARCH_DIRS = [os.path.dirname(os.path.realpath(__file__)), os.getcwd(),
                      os.path.expanduser('~')]


class LibraryCommandInterface(object):
    ''' Contains all user-facing commands. '''
    def __init__(self, manager):
        self.manager = manager

    def open(self, **kwargs):
        ''' Open a document for viewing. '''
        if kwargs['bib']:
            editor.edit(self.manager.archive.bib_path(kwargs['key']))
        else:
            pdf_path = self.manager.archive.pdf_path(kwargs['key'])
            cmd = 'nohup xdg-open {} >/dev/null 2>&1 &'.format(pdf_path)
            subprocess.run(cmd, shell=True)

    def link(self, **kwargs):
        ''' Create a symlink to the document in the archive. '''
        key = kwargs['key']

        if kwargs['fix']:
            if os.path.isdir(key):
                return links.fix_dir(self.manager, key)
            return links.fix_one(self.manager, key)
        else:
            self.manager.link(key, kwargs['name'])

    def grep(self, **kwargs):
        ''' Search for a regex in the library. '''

        # Construct search regex.
        regex = kwargs['regex']

        if kwargs['case_sensitive']:
            regex = re.compile(regex)
        else:
            regex = re.compile(regex, re.IGNORECASE)

        # If neither --bib nor --text are specified, search both. Likewise, if
        # both are specified, also search both. We only don't search one if
        # only the other is specified.
        search_bib = kwargs['bib'] or not kwargs['text']
        search_text = kwargs['text'] or not kwargs['bib']

        if search_bib:
            bibtex_results = search.search_bibtex(self.manager, regex,
                                                  kwargs['oneline'])
            print(bibtex_results)
        if search_text:
            text_results = search.search_text(self.manager, regex,
                                              kwargs['oneline'], verbose=True)
            print(text_results)

    def index(self, **kwargs):
        ''' Create an index file with links and information for easy browsing.
            '''
        bib_dict = self.manager.bibtex_dict()
        html = index.html(self.manager, bib_dict)

        if os.path.exists('library.html'):
            raise LibraryException('File library.html already exists. Aborting.')

        with open('library.html', 'w') as index_file:
            index_file.write(html)
        print('Wrote index to library.html.')

    def compile(self, **kwargs):
        ''' Compile a single bibtex file and/or a single directory of PDFs. '''
        if kwargs['bib']:
            with open('bibtex.bib', 'w') as bib_file:
                bib_file.write(self.manager.bibtex_string())
            print('Compiled bibtex files to bibtex.bib.')

        if kwargs['text']:
            os.mkdir('text')
            for pdf_path in self.manager.archive.all_pdf_files():
                shutil.copy(pdf_path, 'text')

            print('Copied PDFs to text/.')

    def add(self, **kwargs):
        ''' Add a PDF and associated bibtex file to the archive. '''
        pdf_file_name = kwargs['pdf']
        bib_file_name = kwargs['bibtex']

        with open(bib_file_name) as bib_file:
            bib_info = bibtexparser.load(bib_file)

        keys = list(bib_info.entries_dict.keys())
        if len(keys) > 1:
            print('It looks like there\'s more than one entry in the bibtex file. '
                  + 'I\'m not sure what to do!')
            return 1

        key = keys[0]

        self.manager.add(key, pdf_file_name, bib_file_name)

        if kwargs['delete']:
            os.remove(pdf_file_name)
            os.remove(bib_file_name)

        if kwargs['bookmark']:
            self.manager.bookmark(key, None)

        if kwargs['bookmark']:
            msg = 'Archived to {} and bookmarked.'.format(key)
        else:
            msg = 'Archived to {}.'.format(key)
        print(msg)

    def where(self, **kwargs):
        ''' Print out library directories. '''
        paths = self.manager.paths

        if kwargs['archive']:
            print(paths['archive'])
        elif kwargs['shelves']:
            print(paths['shelves'])
        elif kwargs['bookmarks']:
            if os.path.isdir(paths['bookmarks']):
                print(paths['bookmarks'])
            else:
                return 1
        else:
            print(paths['root'])
        return 0

    def bookmark(self, **kwargs):
        ''' Bookmark a document. This creates a symlink to the document in the
            bookmarks directory. '''
        self.manager.bookmark(kwargs['key'], kwargs['name'])


def parse_args(cmd_interface):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='Command.')

    # Link parser.
    link_parser = subparsers.add_parser(
            'link',
            aliases=['ln'],
            help='Create a symlink to a document in the archive.')
    link_parser.add_argument('-f', '--fix', action='store_true',
                             help='Fix a broken symlink into the library.')
    link_parser.add_argument('key', help='Key for document to symlink.')
    link_parser.add_argument('name', nargs='?', help='Name for the link.')
    link_parser.set_defaults(func=cmd_interface.link)

    # Index parser.
    index_parser = subparsers.add_parser('index')
    index_parser.set_defaults(func=cmd_interface.index)

    # Grep parser.
    grep_parser = subparsers.add_parser('grep', aliases=['search'],
                                        help='Search the library.')
    grep_parser.add_argument('regex', help='Search for the regex')
    grep_parser.add_argument('-b', '--bib', '--bibtex', action='store_true',
                             help='Search bibtex files.')
    grep_parser.add_argument('-t', '--text', action='store_true',
                             help='Search document text.')
    grep_parser.add_argument('-o', '--oneline', action='store_true',
                             help='Only output filename and match count.')
    grep_parser.add_argument('-c', '--case-sensitive', action='store_true',
                             help='Case sensitive search.')
    grep_parser.set_defaults(func=cmd_interface.grep)

    # Add parser.
    add_parser = subparsers.add_parser(
            'add',
            help='Add a new document to the library.')
    add_parser.add_argument('pdf', help='PDF file.')
    add_parser.add_argument('bibtex', help='Associated bibtex file.')
    add_parser.add_argument('-d', '--delete', action='store_true',
                            help='Delete files after archiving.')
    add_parser.add_argument('-b', '--bookmark', action='store_true',
                            help='Also create a bookmark to this document.')
    add_parser.set_defaults(func=cmd_interface.add)

    # Open parser.
    open_parser = subparsers.add_parser('open',
                                        help='Open a document for viewing.')
    open_parser.add_argument('key', help='Key for document to open.')
    open_parser.add_argument('-b', '--bib', '--bibtex', action='store_true',
                             help='Open bibtex files.')
    open_parser.set_defaults(func=cmd_interface.open)

    # Compile subcommand.
    compile_parser = subparsers.add_parser('compile')
    compile_parser.add_argument('-b', '--bib', '--bibtex', action='store_true',
                                help='Compile bibtex files.')
    compile_parser.add_argument('-t', '--text', action='store_true',
                                help='Compile PDF documents.')
    compile_parser.set_defaults(func=cmd_interface.compile)

    # Where subcommand.
    where_parser = subparsers.add_parser('where',
                                         help='Print library directories.')
    where_parser.add_argument('-a', '--archive', action='store_true',
                              help='Print location of archive.')
    where_parser.add_argument('-s', '--shelves', action='store_true',
                              help='Print location of shelves.')
    where_parser.add_argument('-b', '--bookmarks', action='store_true',
                              help='Print location of bookmarks.')
    where_parser.set_defaults(func=cmd_interface.where)

    # Bookmark subcommand.
    bookmark_parser = subparsers.add_parser('bookmark', aliases=['bm'],
                                            help='Bookmark a document.')
    bookmark_parser.add_argument('key', help='Key for document to bookmark.')
    bookmark_parser.add_argument('name', nargs='?',
                                 help='Name for the bookmark.')
    bookmark_parser.set_defaults(func=cmd_interface.bookmark)

    # Every subparser has an associated function, that we extract here.
    args = parser.parse_args()
    args = vars(args)
    func = args.pop('func')
    return args, func


def main():
    if len(sys.argv) <= 1:
        print('Usage: lib command [opts] [args]. Try --help.')
        return 1

    # Load the library manager and command interface.
    try:
        manager = management.init(CONFIG_SEARCH_DIRS, CONFIG_FILE_NAME)
        cmd_interface = LibraryCommandInterface(manager)
    except LibraryException as e:
        print(e.message)
        return 1

    args, func = parse_args(cmd_interface)

    try:
        func(**args)
    except LibraryException as e:
        print(e.message)
        return 1
    return 0


if __name__ == '__main__':
    ret = main()
    exit(ret)
