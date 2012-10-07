from setuptools import setup, find_packages
import sys, os

version = '1.11.1'

setup(name='everpad',
    version=version,
    description="Ubuntu integrated evernote client",
    long_description="""\
""",
    classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
    keywords='ubuntu python evernote',
    author='Vladimir Yakovlev',
    author_email='nvbn.rm@gmail.com',
    url='https://github.com/nvbn/everpad/',
    license='X11',
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    include_package_data=True,
    zip_safe=True,
    install_requires=[
        'BeautifulSoup'
    ],
    entry_points={
        'gui_scripts': [
            'everpad=everpad.pad.indicator:main'
        ], 'console_scripts': [
            'everpad-lens=everpad.lens:main',
            'everpad-provider=everpad.provider.daemon:main',
            'everpad-web-auth=everpad.auth:main',
        ]
    },
    data_files=[
        ('/usr/share/icons/hicolor/24x24/actions', [
            'data/editor-icons/everpad-text-bold.png',
            'data/editor-icons/everpad-list-unordered.png',
            'data/editor-icons/everpad-text-strikethrough.png',
            'data/editor-icons/everpad-text-italic.png',
            'data/editor-icons/everpad-list-ordered.png',
            'data/editor-icons/everpad-justify-center.png',
            'data/editor-icons/everpad-justify-left.png',
            'data/editor-icons/everpad-justify-fill.png',
            'data/editor-icons/everpad-text-underline.png',
            'data/editor-icons/everpad-justify-right.png',
            'data/editor-icons/everpad-checkbox.png',
            'data/editor-icons/everpad-link.png',
            'data/editor-icons/everpad-insert-table.png',
        ]),
        ('/usr/share/icons/hicolor/64x64/apps', [
            'data/everpad-mono.png', 'data/everpad-lens.png',
            'data/everpad-note.png',
        ]),
        ('/usr/share/icons/hicolor/128x128/apps', [
            'data/everpad.png', 
        ]),
        ('/usr/share/pixmaps', [
            'data/everpad.png', 'data/everpad-mono.png',
            'data/everpad-lens.png', 'data/everpad-note.png',
        ]),
        ('/usr/share/applications', ['data/everpad.desktop']),
        ('/usr/share/everpad/i18n/', ['i18n/ru_RU.qm']),
        ('share/locale/ru/LC_MESSAGES', ['i18n/ru/LC_MESSAGES/everpad.mo']),
        ('/usr/share/unity/lenses/everpad', ['data/everpad.lens']),
        ('/usr/share/dbus-1/services', [
            'data/unity-lens-everpad.service',
            'data/everpad-provider.service',
            'data/everpad-app.service',
        ]),
    ]
)
