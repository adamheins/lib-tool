
class LibraryException(Exception):
    ''' Generic exception thrown for library-specific errors. '''
    def __init__(self, message):
        self.message = message
