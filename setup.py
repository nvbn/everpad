from setuptools import setup, find_packages
import sys, os

version = '0.3'

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
        'BeautifulSoup',
    ],
    entry_points={
        'gui_scripts': [
            'everpad=everpad.pad:main'
        ], 'console_scripts': [
            'everpad-lens=everpad.lens:main',
            'everpad-provider=everpad.provider:main',
        ]
    },
    data_files=[
        ('share/icons/hicolor/64x64/apps', ['everpad.png']),
        ('share/pixmaps', ['everpad.png']),
        ('share/applications', ['everpad.desktop']),
        ('share/everpad/lang', ['everpad/i18n/ru_RU.qm']),
        ('share/unity/lenses/everpad', ['everpad.lens']),
        ('share/dbus-1/services', [
            'unity-lens-everpad.service',
            'everpad-provider.service'
        ]),
    ]
)


