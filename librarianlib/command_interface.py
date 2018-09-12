import os
import re
import shutil
import subprocess

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
import editor

from librarianlib import index, links, search
from librarianlib.exceptions import LibraryException


def sanitize_key(key):
    ''' Clean up a user-supplied document key. '''
    if key is None:
        return None

    # When completing, the user may accidentally include a trailing slash.
    if key[-1] == '/':
        key = key[:-1]

    # If a nested path is given, we just want the last piece.
    return key.split(os.path.sep)[-1]


class LibraryCommandInterface(object):
    ''' Contains all user-facing commands. '''
    def __init__(self, manager):
        self.manager = manager

    def open(self, **kwargs):
        ''' Open a document for viewing. '''
        key = sanitize_key(kwargs['key'])
        doc = self.manager.archive.retrieve(key)
        if kwargs['bib']:
            editor.edit(doc.paths.bib_path)
        else:
            cmd = 'nohup xdg-open {} >/dev/null 2>&1 &'.format(doc.paths.pdf_path)
            subprocess.run(cmd, shell=True)

    def link(self, **kwargs):
        ''' Create a symlink to the document in the archive. '''
        key = sanitize_key(kwargs['key'])

        if kwargs['fix']:
            if os.path.isdir(key):
                self.manager.fix_links(key)
            else:
                self.manager.fix_link(key)
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
        docs = self.manager.archive.retrieve()

        # Compile all bibtex into a single file.
        if kwargs['bib']:
            bibtex = '\n\n'.join([doc.bibtex for doc in docs])
            with open('bibtex.bib', 'w') as f:
                f.write(bibtex)
            print('Compiled bibtex files to bibtex.bib.')

        # Compile all PDFs into a single directory.
        if kwargs['text']:
            os.mkdir('text')
            for doc in docs:
                shutil.copy(doc.paths.pdf_path, 'text')
            print('Copied PDFs to text/.')

    def add(self, **kwargs):
        ''' Add a PDF and associated bibtex file to the archive. '''
        pdf_file_name = kwargs['pdf']
        bib_file_name = kwargs['bibtex']

        doc = self.manager.add(pdf_file_name, bib_file_name)

        if kwargs['delete']:
            os.remove(pdf_file_name)
            os.remove(bib_file_name)

        if kwargs['bookmark']:
            self.manager.bookmark(doc.key, None)

        if kwargs['bookmark']:
            msg = 'Archived to {} and bookmarked.'.format(doc.key)
        else:
            msg = 'Archived to {}.'.format(doc.key)
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
        key = sanitize_key(kwargs['key'])
        self.manager.bookmark(key, kwargs['name'])

    def complete(self, **kwargs):
        ''' Print completions for commands. '''
        cmd = kwargs['cmd']
        keys = [doc.key for doc in self.manager.archive.retrieve()]

        # Completion just for keys in the archive.
        if cmd == 'keys':
            completions = keys

        # Completion for keys as well as symlinks that point to keys.
        elif cmd == 'keys-and-links':
            def link_points_to_key(f):
                if not os.path.islink(f):
                    return False
                path = os.readlink(f)
                key = sanitize_key(os.path.basename(path))
                return self.manager.archive.contains(key)

            # We also allow autocompletion of symlinks in the cwd
            files = os.listdir(os.getcwd())
            files = list(filter(link_points_to_key, files))

            completions = files + keys

        print(' '.join(completions))

    def rekey(self, **kwargs):
        ''' Change the name of a key. '''
        key = sanitize_key(kwargs['key'])
        new_key = kwargs['new-key']
        self.manager.rekey(key, new_key)
        print('Renamed {} to {}.'.format(key, new_key))
