import os
import shutil
import subprocess

import editor


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
        doc = self.manager.get_doc(key)
        doc.access()
        if kwargs['bib']:
            editor.edit(doc.paths.bib_path)
        elif kwargs['tag']:
            try:
                editor.edit(doc.paths.tag_path)
            # FileNotFoundError is thrown if file doesn't exist and isn't
            # created during the editing process. Just ignore this.
            except FileNotFoundError:
                pass
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

    def browse(self, **kwargs):
        ''' Browse/search documents. '''
        # Filters.
        author = kwargs['author']
        year = kwargs['year']
        title = kwargs['title']
        key = kwargs['key']
        venue = kwargs['venue']
        entrytype = kwargs['type']
        text = kwargs['text']
        tags = kwargs['tags']

        # Display options.
        sort = kwargs['sort']
        number = kwargs['number']
        reverse = kwargs['reverse']
        verbosity = kwargs['verbose'] if kwargs['verbose'] else 0

        results = self.manager.search_docs(key=key, title=title, author=author,
                                           year=year, venue=venue,
                                           entrytype=entrytype, text=text,
                                           tags=tags, sort=sort, number=number,
                                           reverse=reverse,
                                           verbosity=verbosity)
        if results:
            print(results)

    def compile(self, **kwargs):
        ''' Compile a single bibtex file and/or a single directory of PDFs. '''
        docs = self.manager.all_docs()

        # Compile all bibtex into a single file.
        if kwargs['bib']:
            bibtex = '\n\n'.join([doc.bibtex_str for doc in docs])
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

        if kwargs['tag']:
            self.manager.tag(doc.key, kwargs['tag'])

        print('Archived to {}.'.format(doc.key))

    def where(self, **kwargs):
        ''' Print out library directories. '''
        print(self.manager.archive_path)
        return 0

    def bookmark(self, **kwargs):
        ''' Bookmark a document. This creates a symlink to the document in the
            bookmarks directory. '''
        key = sanitize_key(kwargs['key'])
        self.manager.bookmark(key, kwargs['name'])

    def complete(self, **kwargs):
        ''' Print completions for commands. '''
        keys = self.manager.all_keys()
        print(' '.join(keys))

    def rekey(self, **kwargs):
        ''' Change the name of a key. '''
        key = sanitize_key(kwargs['key'])
        new_key = self.manager.rekey(key, kwargs['new-key'])
        print('Renamed {} to {}.'.format(key, new_key))

    def list_tags(self, **kwargs):
        ''' List all tags. '''
        if kwargs['rename']:
            current_tag, new_tag = kwargs['rename'][0], kwargs['rename'][1]
            self.manager.rename_tag(current_tag, new_tag)
            print('Renamed all instances of {} to {}.'.format(current_tag, new_tag))
        else:
            tag_count_list = self.manager.get_tags()
            n = kwargs['number'] if kwargs['number'] else len(tag_count_list)
            for item in tag_count_list[0:n]:
                print('{} ({})'.format(item[0], item[1]))
