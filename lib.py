#!/usr/bin/env python3

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

import bibtexparser
import editor

from liblib import style, confutil, bibtex


CONFIG_FILE_NAME = '.libconf.yaml'
CONFIG_SEARCH_DIRS = [os.path.dirname(os.path.realpath(__file__)), os.getcwd(),
                      os.path.expanduser('~')]


def parse_key(key):
    ''' Clean up a user-supplied document key. '''
    # When completing, the user may accidentally include a trailing slash.
    if key[-1] == '/':
        key = key[:-1]

    # If a nested path is given, we just want the last piece.
    return key.split(os.path.sep)[-1]


def do_open(config, **kwargs):
    ''' Open a document for viewing. '''
    key = parse_key(kwargs['key'])

    if kwargs['bib']:
        bib_path = os.path.join(config['archive'], key, key + '.bib')
        editor.edit(bib_path)
    else:
        pdf_path = os.path.join(config['archive'], key, key + '.pdf')
        cmd = 'nohup xdg-open {} >/dev/null 2>&1 &'.format(pdf_path)
        subprocess.run(cmd, shell=True)


def do_link(config, **kwargs):
    ''' Create a symlink to the document in the archive. '''
    key = parse_key(kwargs['key'])

    src = os.path.join(config['archive'], key)

    # The user may specify an (optional) new name, which could be an absolute
    # or relative path.
    dest_name = kwargs['name'] if kwargs['name'] is not None else key
    if os.path.isabs(dest_name):
        dest = dest_name
    else:
        dest = os.path.join(os.getcwd(), dest_name)

    os.symlink(src, dest)


def do_grep(config, **kwargs):
    ''' Search for a regex in the library. '''

    # Arguments
    regex = kwargs['regex']

    # Options
    bib = kwargs['bib']
    text = kwargs['text']
    case_sensitive = kwargs['case_sensitive']
    oneline = kwargs['oneline']

    search_either = bib or text
    search_bib = bib or not search_either
    search_text = text or not search_either

    if case_sensitive:
        regex = re.compile(regex)
    else:
        regex = re.compile(regex, re.IGNORECASE)

    def repl(match):
        return style.yellow(match.group(0))

    if search_bib:
        bib_dict = bibtex.load_bib_dict(config['archive'])
        output = []
        for key, info in bib_dict.items():
            count = 0
            detail = []
            for field, value in info.items():
                # Skip the ID field; it's already a composition of parts of
                # other fields.
                if field == 'ID':
                    continue

                # Find all the matches.
                result = regex.findall(value)
                count += len(result)
                if len(result) == 0:
                    continue

                # Highlight the matches.
                s = regex.sub(repl, value)
                detail.append('  {}: {}'.format(field, s))

            if count > 0:
                file_output = []
                if count == 1:
                    file_output.append('{}: 1 match'.format(style.bold(key)))
                else:
                    file_output.append('{}: {} matches'.format(style.bold(key), count))
                if not oneline:
                    file_output.append('\n'.join(detail))
                output.append('\n'.join(file_output))

        if len(output) == 0:
            return

        if oneline:
            print('\n'.join(output))
        else:
            print('\n\n'.join(output))


ENTRY_TEMPLATE = '''
<div class="post">
    <h2><a href={path}>{title}</a></h2>
    <div class="date">{year}</div>
    <p class="description">{authors}</p>
</div>'''


ARCHIVE_TEMPLATE = '''
<html>
    <head>
        <title>Archive</title>
        <link rel="stylesheet" href="https://static.adamheins.com/css/layout.css"/>
        <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Open+Sans:400,300,300italic"/>
    </head>
    <body>
        <div class="container">
            <div class="content">
                <section>
                    <h1>Archive</h1>
                </section>
                <section>{entries}</section>
            </div>
        </div>
    </body>
</html>
'''


def entry_html(key, data, archive_path):
    text_path = os.path.join(archive_path, key, key + '.pdf')
    entry = ENTRY_TEMPLATE.format(path=text_path, title=data['title'],
                                  year=data['year'], authors=data['author'])
    return entry


def do_index(config, **kwargs):
    ''' Create an index file with links and information for easy browsing. '''
    bib_dict = bibtex.load_bib_dict(config['archive'])
    entries = sorted(bib_dict.items(), key=lambda item: item[1]['year'],
                     reverse=True)
    entries = map(lambda item: entry_html(item[0], item[1], config['archive']),
                  entries)

    html = ARCHIVE_TEMPLATE.format(entries=''.join(entries))

    with open('index.html', 'w') as index_file:
        index_file.write(html)


def do_compile(config, **kwargs):
    ''' Compile a single bibtex file and/or a single directory of PDFs. '''
    if kwargs['bib']:
        with open('bibtex.bib', 'w') as bib_file:
            bib_file.write(bibtex.compile_bib_info())
        print('Compiled bibtex files to bibtex.bib.')

    if kwargs['text']:
        os.mkdir('text')
        pdf_list = glob.glob(config['archive'] + '/**/*.pdf')
        for pdf_path in pdf_list:
            shutil.copy(pdf_path, 'text')

        print('Copied PDFs to text/.')


def do_add(config, **kwargs):
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

    archive_path = os.path.join(config['archive'], key)
    if os.path.exists(archive_path):
        print('Archive {} already exists! Aborting.'.format(key))
        return 1

    archive_pdf_path = os.path.join(archive_path, key + '.pdf')
    archive_bib_path = os.path.join(archive_path, key + '.bib')

    os.mkdir(archive_path)
    if kwargs['delete']:
        shutil.move(pdf_file_name, archive_pdf_path)
        shutil.move(bib_file_name, archive_bib_path)
    else:
        shutil.copy(pdf_file_name, archive_pdf_path)
        shutil.copy(bib_file_name, archive_bib_path)

    if kwargs['bookmark']:
        do_bookmark(config, key=key, name=None)

    if kwargs['bookmark']:
        msg = 'Archived to {} and bookmarked.'.format(key)
    else:
        msg = 'Archived to {}.'.format(key)
    print(msg)


def do_where(config, **kwargs):
    ''' Print out library directories. '''
    if kwargs['archive']:
        print(config['archive'])
    elif kwargs['shelves']:
        print(config['shelves'])
    elif kwargs['bookmarks']:
        if os.path.isdir(config['bookmarks']):
            print(config['bookmarks'])
        else:
            return 1
    else:
        print(config['library'])
    return 0


def do_bookmark(config, **kwargs):
    ''' Bookmark a document. This creates a symlink to the document in the
        bookmarks directory. '''

    # Create the bookmarks directory if it doesn't already exist.
    bm_dir = config['bookmarks']
    if not os.path.isdir(bm_dir):
        os.mkdir(bm_dir)
        print('Created bookmarks directory at: {}'.format(bm_dir))

    key = parse_key(kwargs['key'])
    dest_name = kwargs['name'] if kwargs['name'] is not None else key

    # Create the symlink to the document in the bookmarks directory.
    src = os.path.join(config['archive'], key)
    dest = os.path.join(config['bookmarks'], dest_name)
    os.symlink(src, dest)

    return 0


def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='Command.')

    # Link parser.
    link_parser = subparsers.add_parser(
            'link',
            aliases=['ln'],
            help='Create a symlink to a document in the archive.')
    link_parser.add_argument('key', help='Key for document to symlink.')
    link_parser.add_argument('name', nargs='?', help='Name for the link.')
    link_parser.set_defaults(func=do_link)

    # Index parser.
    index_parser = subparsers.add_parser('index')
    index_parser.set_defaults(func=do_index)

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
    grep_parser.set_defaults(func=do_grep)

    # Add parser.
    # TODO implement bookmark flag
    add_parser = subparsers.add_parser(
            'add',
            help='Add a new document to the library.')
    add_parser.add_argument('pdf', help='PDF file.')
    add_parser.add_argument('bibtex', help='Associated bibtex file.')
    add_parser.add_argument('-d', '--delete', action='store_true',
                            help='Delete files after archiving.')
    add_parser.add_argument('-b', '--bookmark', action='store_true',
                            help='Also create a bookmark to this document.')
    add_parser.set_defaults(func=do_add)

    # Open parser.
    open_parser = subparsers.add_parser('open',
                                        help='Open a document for viewing.')
    open_parser.add_argument('key', help='Key for document to open.')
    open_parser.add_argument('-b', '--bib', '--bibtex', action='store_true',
                             help='Open bibtex files.')
    open_parser.set_defaults(func=do_open)

    # Compile subcommand.
    compile_parser = subparsers.add_parser('compile')
    compile_parser.add_argument('-b', '--bib', '--bibtex', action='store_true',
                                help='Compile bibtex files.')
    compile_parser.add_argument('-t', '--text', action='store_true',
                                help='Compile PDF documents.')
    compile_parser.set_defaults(func=do_compile)

    # Where subcommand.
    where_parser = subparsers.add_parser('where',
                                         help='Print library directories.')
    where_parser.add_argument('-a', '--archive', action='store_true',
                              help='Print location of archive.')
    where_parser.add_argument('-s', '--shelves', action='store_true',
                              help='Print location of shelves.')
    where_parser.add_argument('-b', '--bookmarks', action='store_true',
                              help='Print location of bookmarks.')
    where_parser.set_defaults(func=do_where)

    # Bookmark subcommand.
    bookmark_parser = subparsers.add_parser('bookmark', aliases=['bm'],
                                            help='Bookmark a document.')
    bookmark_parser.add_argument('key', help='Key for document to bookmark.')
    bookmark_parser.add_argument('name', nargs='?',
                                 help='Name for the bookmark.')
    bookmark_parser.set_defaults(func=do_bookmark)

    # Every subparser has an associated function that we call here, passing all
    # other options as arguments.
    args = parser.parse_args()
    args = vars(args)
    func = args.pop('func')
    return args, func


def main():
    if len(sys.argv) <= 1:
        print('Usage: lib command [opts] [args]. Try --help.')
        return 1

    # Load the config.
    config = confutil.load(CONFIG_SEARCH_DIRS, CONFIG_FILE_NAME)
    if config is None:
        return 1

    args, func = parse_args()
    return func(config, **args)


if __name__ == '__main__':
    ret = main()
    exit(ret)
