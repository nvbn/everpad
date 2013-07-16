from setuptools import setup, find_packages
import sys, os

version = '2.5'

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
        "BeautifulSoup",
        "html2text",
        "httplib2",
        "keyring",
        "py-oauth2 ",
        "pysqlite ",
        "regex",
        "sqlalchemy",
        'pyside',
        'mock',
    ],
    entry_points={
        'gui_scripts': [
            'everpad=everpad.pad.indicator:main'
        ], 'console_scripts': [
            'everpad-lens=everpad.specific.unity.lens:main',
            'everpad-provider=everpad.provider.daemon:main',
        ]
    },
    data_files=[
        ('share/icons/hicolor/24x24/actions', [
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
            'data/editor-icons/everpad-insert-image.png',
            'data/editor-icons/everpad-pin.png',
        ]),
        ('share/icons/hicolor/48x48/actions', [
            'data/everpad-file.png',
        ]),
        ('share/icons/hicolor/64x64/apps', [
            'data/everpad-mono.png', 'data/everpad-lens.png',
            'data/everpad-note.png', 'data/everpad-black.png',
        ]),
        ('share/icons/hicolor/128x128/apps', [
            'data/everpad.png',
        ]),
        ('share/pixmaps', [
            'data/everpad.png', 'data/everpad-mono.png',
            'data/everpad-lens.png', 'data/everpad-note.png',
            'data/everpad-black.png',
        ]),
        ('share/applications', ['data/everpad.desktop']),
        ('share/everpad/i18n/', [
            'i18n/ru_RU.qm',
            'i18n/ar_EG.qm',
    	    'i18n/zh_CN.qm',
            'i18n/zh_TW.qm',
            'i18n/ja.qm',
            'i18n/es.qm',
            'i18n/de_DE.qm',
            'i18n/de_AT.qm',
            'i18n/de_CH.qm',
        ]),
        ('share/everpad/', [
            'everpad/pad/editor/editor.html',
        ]),
        ('share/locale/ru/LC_MESSAGES', ['i18n/ru/LC_MESSAGES/everpad.mo']),
        ('share/locale/ar/LC_MESSAGES', ['i18n/ar/LC_MESSAGES/everpad.mo']),
        ('share/locale/zh_CN/LC_MESSAGES', ['i18n/zh_CN/LC_MESSAGES/everpad.mo']),
    	('share/locale/zh_TW/LC_MESSAGES', ['i18n/zh_TW/LC_MESSAGES/everpad.mo']),
        ('share/locale/ja/LC_MESSAGES', ['i18n/ja/LC_MESSAGES/everpad.mo']),
        ('share/locale/es/LC_MESSAGES', ['i18n/es/LC_MESSAGES/everpad.mo']),
        ('share/locale/de/LC_MESSAGES', ['i18n/de/LC_MESSAGES/everpad.mo']),
        ('share/unity/lenses/everpad', ['data/everpad.lens']),
        ('share/dbus-1/services', [
            'data/unity-lens-everpad.service',
            'data/everpad-provider.service',
            'data/everpad-app.service',
        ]),
        ('share/kde4/services/', [
            'data/plasma-runner-everpad.desktop',
        ]),
        ('share/kde4/apps/plasma/runners/everpad/', [
            'data/metadata.desktop',
        ]),
        ('share/kde4/apps/plasma/runners/everpad/contents/code/', [
            'everpad/specific/kde/everpad_runner.py',
        ]),
    ]
)
