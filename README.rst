everpad package in ubuntu software center pending review - https://myapps.developer.ubuntu.com/dev/apps/1678/

Please vote for these bugs, they greatly hinder development:
============================================================
https://bugs.launchpad.net/ubuntu/+source/openssl/+bug/965371

https://bugs.launchpad.net/appmenu-qt/+bug/1057167


Everpad
=======

.. image:: http://ubuntuone.com/4ABojaepuBiaDVv2VsDB7o

Evernote client well integrated with linux desktop.

Client has:
 - unity lens
 - indicator applet
 - unity launcher

Client support:
 - notes
 - tags
 - notebooks
 - resources
 - places
 - en-* tags

Installation
============
Ubuntu 12.04+ users can use `ppa <https://launchpad.net/~nvbn-rm/+archive/ppa>`_:

``sudo add-apt-repository ppa:nvbn-rm/ppa``

``sudo apt-get update``

``sudo apt-get install everpad`` 

If you use gnome shell please `read wiki <https://github.com/nvbn/everpad/wiki/how-to-install>`_

You can see more about everpad installation, including method for other linux, in `wiki <https://github.com/nvbn/everpad/wiki/how-to-install>`_

Some errors?
============
For debug output you need:
``killall everpad everpad-provider everpad-lens``
``everpad-provider --verbose``
And in second terminal:
``everpad``
And in third:
``everpad-lens``

Want to help?
=============
`Write code here <https://github.com/nvbn/everpad/wiki/developing-for-everpad>`_

Or create bug reports.

Or donate:

 - **PayPal**: nvbn.rm@gmail.com
 - **Yandex Money**: 410011244953574
