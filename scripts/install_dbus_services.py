#!/usr/bin/env python

"""
Install dbus service files in a custom prefix.
This is needed when installing in user directory, as the standard search
path is not aware of the virtualenv.
"""

from __future__ import with_statement
import sys
import os

if len(sys.argv) > 1:
    services_dir = sys.argv[1]
else:
    services_dir = "~/.local/share/dbus-1/services/"

services_dir = os.path.expanduser(services_dir)
if not os.path.isdir(services_dir):
    os.makedirs(services_dir)


service_files = {}

service_files["everpad-app.service"] = """\
[D-BUS Service]
Name=com.everpad.App
Exec={prefix}/bin/everpad
"""

service_files["everpad-provider.service"] = """\
[D-BUS Service]
Name=com.everpad.Provider
Exec={prefix}/bin/everpad-provider
"""

service_files["unity-lens-everpad.service"] = """\
[D-BUS Service]
Name=net.launchpad.Unity.Lens.EverpadLens
Exec={prefix}/bin/everpad-lens
"""

if __name__ == '__main__':
    for filename, filetpl in service_files.iteritems():
        print "Installing {} -> {}".format(filename, services_dir)
        with open(os.path.join(services_dir, filename), 'w') as f:
            f.write(filetpl.format(prefix=sys.prefix))
