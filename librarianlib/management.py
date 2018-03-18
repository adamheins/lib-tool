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

    def bibtex_string(self):
        bib_list = []

        for bib_path in self.archive.all_bibtex_files():
            with open(bib_path) as bib_file:
                bib_list.append(bib_file.read().strip())

        return '\n\n'.join(bib_list)

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

        parser = bibtexparser.bparser.BibTexParser()
        parser.customization = customizations

        bibtex = self.bibtex_string()
        return bibtexparser.loads(bibtex, parser=parser).entries_dict

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

        path = os.path.join(self.paths['bookmarks'], name)
        self.link(key, path)
