from setuptools import setup, find_packages
import sys
import os

version = '0.9999'

def get_files():
    packages = find_packages(exclude=['tests'])
    files = []
    for package in packages:
        path = package.replace('.', '/')
        files.append((
            os.path.join('/opt/extras.ubuntu.com/everpad/', path),
            filter(lambda name: not (name[-4:] == '.pyc' or os.path.isdir(name)),
                map(lambda name: os.path.join(path, name), 
            os.listdir(path))),
        ))
    return files


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
    packages=[],
    include_package_data=True,
    zip_safe=True,
    install_requires=[],
    entry_points={},
    data_files=[
        ('/usr/share/icons/hicolor/64x64/apps', [
            'everpad.png', 'everpad-mono.png', 
            'everpad-lens.png', 'everpad-note.png',
        ]),
        ('/usr/share/pixmaps', [
            'everpad.png', 'everpad-mono.png',
            'everpad-lens.png', 'everpad-note.png',
        ]),
        ('/usr/share/applications', ['everpad.desktop']),
        ('/usr/share/unity/lenses/everpad', ['everpad.lens']),
        ('/usr/share/dbus-1/services', [
            'unity-lens-everpad.service',
            'everpad-provider.service',
            'everpad-app.service',
        ]),
        ('/usr/bin/', [
            'bin/everpad', 'bin/everpad-lens',
            'bin/everpad-provider', 'bin/everpad-web-auth',
        ])
    ] + get_files(),
)
