import os
import yaml


def find_config(search_dirs, config_name):
    ''' Find the path to the configuration file. '''
    for search_dir in search_dirs:
        path = os.path.join(search_dir, config_name)
        if os.path.exists(path):
            return path
    return None


def load(search_dirs, config_name):
    ''' Load the configuration parameters from file. '''
    path = find_config(search_dirs, config_name)
    if path is None:
        print('Error: Could not find config file.')
        return None

    with open(path) as f:
        config = yaml.load(f)

    config['library'] = os.path.expanduser(config['library'])
    config['archive'] = os.path.join(config['library'], 'archive')
    config['shelves'] = os.path.join(config['library'], 'shelves')
    config['bookmarks'] = os.path.join(config['library'], 'bookmarks')

    # Check if each of these directories exist.
    # TODO perhaps just make the directory rather than raising an error
    for key in ['library', 'archive', 'shelves']:
        if not os.path.isdir(config[key]):
            print('Error: {} does not exist!'.format(config[key]))
            return None

    return config
