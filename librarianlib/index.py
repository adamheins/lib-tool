import os


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
    path = os.path.join(archive_path, key, key + '.pdf')
    return ENTRY_TEMPLATE.format(path=path, title=data['title'],
                                 year=data['year'], authors=data['author'])


def html(bib_dict, archive_path):
    # Sort the documents by year, with most recent first.
    entries = sorted(bib_dict.items(), key=lambda item: item[1]['year'],
                     reverse=True)

    # Generate HTML for each entry.
    entries = map(lambda item: entry_html(item[0], item[1], archive_path), entries)

    return ARCHIVE_TEMPLATE.format(entries=''.join(entries))
