import os
import re
import shutil
import subprocess

import bibtexparser
import editor

from librarianlib import index, links, search
from librarianlib.exceptions import LibraryException


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
