import datetime
import glob
import os
import shutil
import yaml

import bibtexparser
import bibtexparser.customization as customization

from .exceptions import LibraryException


def find_config(search_dirs, config_name):
    ''' Find the path to the configuration file. '''
    for search_dir in search_dirs:
        path = os.path.join(search_dir, config_name)
        if os.path.exists(path):
            return path
    return None


def parse_key(key):
    ''' Clean up a user-supplied document key. '''
    # When completing, the user may accidentally include a trailing slash.
    if key[-1] == '/':
        key = key[:-1]

    # If a nested path is given, we just want the last piece.
    return key.split(os.path.sep)[-1]


class Document(object):
    # archive agnostic constructor?
    # only access documents through the associated archive
    # file paths should be absolute

    def __init__(self, key, bibtex, text=None, fhash=None):
        self.key = key
        self.bibtex = bibtex
        self.text = text
        self.hash = fhash

    def index(self):
        pass

    def hash(self):
        pass


class ArchivalDocument(object):
    def __init__(self, archive, doc, added, accessed):
        self.doc = doc
        self.archive = archive

        # TODO may be redundant
        self.key_path = os.path.join(archive.path, doc.key)
        self.pdf_path = os.path.join(archive.path, doc.key, '.pdf')
        self.bib_path = os.path.join(archive.path, doc.key, '.bib')

        # Dates.
        self.added = added
        self.accessed = accessed

    @staticmethod
    def new(archive, doc):
        today = datetime.date.today()
        return ArchivalDocument(archive, doc, today, today)

    @staticmethod
    def load(archive, key):
        added, accessed, text, fhash = ArchivalDocument._load_metadata(archive, key)
        doc = Document(key, text=text, fhash=fhash)
        return ArchivalDocument(archive, doc, added, accessed)

    def save(self):
        pass

    def _save_metadata(self, archive, key):
        pass

    @staticmethod
    def _load_metadata(archive, key):
        path = os.path.join(archive.path, key, '.metadata')

        with open(os.path.join(path, 'added.txt')) as f:
            added = datetime.date.strptime(f.read(), '%Y-%m-%d')
        with open(os.path.join(path, 'accessed.txt')) as f:
            accessed = datetime.date.strptime(f.read(), '%Y-%m-%d')
        with open(os.path.join(path, 'text.txt')) as f:
            text = f.read()
        with open(os.path.join(path, 'hash.md5')) as f:
            fhash = f.read()

        return added, accessed, text, fhash

    def files(self):
        return self.key_path, self.pdf_path, self.bib_path


class Archive(object):
    ''' Provides convenience functions to interact with the library's archive.
        '''
    def __init__(self, path):
        self.path = path

    def has_key(self, key):
        ''' Returns True if the key is in the archive, false otherwise. '''
        path = os.path.join(self.path, key)
        return os.path.isdir(path)

    def all_keys(self):
        ''' Returns a list of all keys in the archive. '''
        return os.listdir(self.path)

    def all_bibtex_files(self):
        ''' Returns a list of paths of all bibtex files in the archive. '''
        return glob.glob(self.path + '/**/*.bib')

    def all_pdf_files(self):
        ''' Returns a list of paths of all PDF files in the archive. '''
        return glob.glob(self.path + '/**/*.pdf')

    def key_path(self, key):
        ''' Returns the path to the key. '''
        return os.path.join(self.path, key)

    def bib_path(self, key):
        ''' Returns the path to the bibtex file of the key. '''
        return os.path.join(self.key_path(key), key + '.bib')

    def pdf_path(self, key):
        ''' Returns the path to the PDF file of the key. '''
        return os.path.join(self.key_path(key), key + '.pdf')

    def pdf_to_key(self, pdf):
        ''' Convert a PDF path to its key name. '''
        base = os.path.basename(pdf)
        return base.split('.')[0]

    def pdfs():
        pass

    def keys():
        pass


class LibraryManager(object):
    def __init__(self, search_dirs, config_name):
        config_file_path = find_config(search_dirs, config_name)
        if config_file_path is None:
            raise LibraryException('Could not find config file.')

        with open(config_file_path) as f:
            config = yaml.load(f)

        self.root = os.path.expanduser(config['library'])

        self.paths = {
            'root': self.root,
            'archive': os.path.join(self.root, 'archive'),
            'shelves': os.path.join(self.root, 'shelves'),
            'bookmarks': os.path.join(self.root, 'bookmarks'),
        }

        self.archive = Archive(self.paths['archive'])

        # Check if each of these directories exist.
        # TODO perhaps just make the directory rather than raising an error
        for key in ['root', 'archive', 'shelves']:
            if not os.path.isdir(self.paths[key]):
                message = '{} does not exist!'.format(self.paths[key])
                raise LibraryException(message)

    def bibtex_list(self):
        ''' Create a list of the contents of all bibtex files in the archive. '''
        bib_list = []
        bib_files = self.archive.all_bibtex_files()

        for bib_path in bib_files:
            with open(bib_path) as bib_file:
                bib_list.append(bib_file.read().strip())

        return zip(bib_list, bib_files)

    def bibtex_dict(self, extra_customization=None):
        ''' Load bibtex information as a dictionary. '''
        def customizations(record):
            record = customization.convert_to_unicode(record)

            # Make authors semicolon-separated rather than and-separated.
            record['author'] = record['author'].replace(' and', ';')

            # Apply extra customization function is applicable.
            if extra_customization:
                record = extra_customization(record)
            return record

        # We parse each string of bibtex separately and then merge the
        # resultant dictionaries together, so that we can handle malformed
        # bibtex files individually.
        entries_dict = {}
        bibtex = self.bibtex_list()
        for bibstr, bibfile in bibtex:
            # common_strings=True lets us parse the month field as "jan",
            # "feb", etc.
            parser = bibtexparser.bparser.BibTexParser(
                    customization=customizations,
                    common_strings=True)
            try:
                d = bibtexparser.loads(bibstr, parser=parser).entries_dict
            except:
                print('Encountered an error while processing {}.'.format(bibfile))
                continue
            entries_dict.update(d)
        return entries_dict

    def add(self, key, pdf_src_path, bib_src_path):
        key = parse_key(key)

        if self.archive.has_key(key):
            message = 'Archive {} already exists! Aborting.'.format(key)
            raise LibraryException(message)

        os.mkdir(self.archive.key_path(key))

        pdf_dest_path = self.archive.pdf_path(key)
        bib_dest_path = self.archive.bib_path(key)

        shutil.copy(pdf_src_path, pdf_dest_path)
        shutil.copy(bib_src_path, bib_dest_path)

    def rekey(self, key, new_key):
        pdf_src_path = self.archive.pdf_path(key)
        bib_src_path = self.archive.bib_path(key)

        # First rename the PDF and bibtex files.
        key_path = self.archive.key_path(key)
        pdf_dest_path = os.path.join(key_path, new_key + '.pdf')
        bib_dest_path = os.path.join(key_path, new_key + '.bib')

        shutil.move(pdf_src_path, pdf_dest_path)
        shutil.move(bib_src_path, bib_dest_path)

        # Rename the directory.
        new_key_path = self.archive.key_path(new_key)
        shutil.move(key_path, new_key_path)

    def link(self, key, path):
        key = parse_key(key)
        path = path if path is not None else key

        src = self.archive.key_path(key)

        if os.path.isabs(path):
            dest = path
        else:
            dest = os.path.join(os.getcwd(), path)

        if os.path.exists(dest):
            message = 'Symlink {} already exists. Aborting.'.format(path)
            raise LibraryException(message)

        os.symlink(src, dest)

    def bookmark(self, key, name):
        # Create the bookmarks directory if it doesn't already exist.
        if not os.path.isdir(self.paths['bookmarks']):
            os.mkdir(self.paths['bookmarks'])
            print('Created bookmarks directory at: {}'.format(self.paths['bookmarks']))

        name = name if name is not None else key
        path = os.path.join(self.paths['bookmarks'], name)
        self.link(key, path)
