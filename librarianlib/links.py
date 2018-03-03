import os


def fix_dir(manager, directory):
    ''' Fix all broken links in the directory. '''
    files = os.listdir(directory)
    for link in filter(os.path.islink, files):
        fix_one(manager, link)
    return 0


def fix_one(manager, link):
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
