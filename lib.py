#!/usr/bin/env python3

import argparse
import os
import re
import shutil
import subprocess
import sys

import bibtexparser
import editor
import textract

from liblib import style, management


CONFIG_FILE_NAME = '.libconf.yaml'
CONFIG_SEARCH_DIRS = [os.path.dirname(os.path.realpath(__file__)), os.getcwd(),
                      os.path.expanduser('~')]


def do_open(manager, **kwargs):
    ''' Open a document for viewing. '''
    if kwargs['bib']:
        editor.edit(manager.archive.bib_path(kwargs['key']))
    else:
        pdf_path = manager.archive.pdf_path(kwargs['key'])
        cmd = 'nohup xdg-open {} >/dev/null 2>&1 &'.format(pdf_path)
        subprocess.run(cmd, shell=True)


def fix_links(manager, directory):
    ''' Fix all broken links in the directory. '''
    files = os.listdir(directory)
    for link in filter(os.path.islink, files):
        fix_link(manager, link)
    return 0


def fix_link(manager, link):
    ''' Fix a link that has broken due to the library being moved. '''
    if not os.path.islink(link):
        print('{} is not a symlink.'.format(link))
        return 1

    path = os.readlink(link)
    base = os.path.basename(path)

    if not manager.archive.has_key(base):
        print('{} does not point to a document in the archive.'.format(link))
        return 1

    # Recreate the link, pointing to the correct location.
    os.remove(link)
    manager.link(base, link)


def do_link(manager, **kwargs):
    ''' Create a symlink to the document in the archive. '''
    key = kwargs['key']

    if kwargs['fix']:
        if os.path.isdir(key):
            return fix_links(manager, key)
        return fix_link(manager, key)
    else:
        manager.link(key, kwargs['name'])


def do_grep(manager, **kwargs):
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
        bib_dict = manager.bibtex_dict()
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


def entry_html(key, data, pdf_path):
    return ENTRY_TEMPLATE.format(path=pdf_path, title=data['title'],
                                 year=data['year'], authors=data['author'])


def do_index(manager, **kwargs):
    ''' Create an index file with links and information for easy browsing. '''
    bib_dict = manager.bibtex_dict()
    entries = sorted(bib_dict.items(), key=lambda item: item[1]['year'],
                     reverse=True)
    entries = map(lambda item: entry_html(item[0], item[1],
                                          manager.paths['archive']), entries)

    html = ARCHIVE_TEMPLATE.format(entries=''.join(entries))

    with open('index.html', 'w') as index_file:
        index_file.write(html)


def do_compile(manager, **kwargs):
    ''' Compile a single bibtex file and/or a single directory of PDFs. '''
    if kwargs['bib']:
        with open('bibtex.bib', 'w') as bib_file:
            bib_file.write(manager.bibtex_string())
        print('Compiled bibtex files to bibtex.bib.')

    if kwargs['text']:
        os.mkdir('text')
        for pdf_path in manager.archive.all_pdf_files():
            shutil.copy(pdf_path, 'text')

        print('Copied PDFs to text/.')


def do_add(manager, **kwargs):
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

    manager.add(key, pdf_file_name, bib_file_name)

    if kwargs['delete']:
        os.remove(pdf_file_name)
        os.remove(bib_file_name)

    if kwargs['bookmark']:
        manager.bookmark(key, None)

    if kwargs['bookmark']:
        msg = 'Archived to {} and bookmarked.'.format(key)
    else:
        msg = 'Archived to {}.'.format(key)
    print(msg)


def do_where(manager, **kwargs):
    ''' Print out library directories. '''
    paths = manager.paths

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


def do_bookmark(manager, **kwargs):
    ''' Bookmark a document. This creates a symlink to the document in the
        bookmarks directory. '''
    manager.bookmark(kwargs['key'], kwargs['name'])


def parse_args():
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

    # Every subparser has an associated function, that we extract here.
    args = parser.parse_args()
    args = vars(args)
    func = args.pop('func')
    return args, func


def main():
    if len(sys.argv) <= 1:
        print('Usage: lib command [opts] [args]. Try --help.')
        return 1

    # Load the LibraryManager.
    try:
        manager = management.init(CONFIG_SEARCH_DIRS, CONFIG_FILE_NAME)
    except management.LibraryException as e:
        print(e.message)
        return 1

    args, func = parse_args()

    try:
        func(manager, **args)
    except management.LibraryException as e:
        print(e.message)
        return 1
    return 0


if __name__ == '__main__':
    ret = main()
    exit(ret)
