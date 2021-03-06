#
# Copyright 2015-2016 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#
from __future__ import absolute_import

import logging
import uuid
import xml.etree.ElementTree as ET

import libvirt


from . import errors
from . import events
from . import doms
from . import runner
from . import runtime
from . import runtimes
from . import xmlfile
from . import xmlconstants


class Domain(object):

    _log = logging.getLogger('convirt.Domain')

    @classmethod
    def create(cls, xmldesc, conf, repo):  # FIXME
        inst = cls(xmldesc, conf=conf, repo=repo)
        inst._startup()
        doms.add(inst)
        return inst

    @classmethod
    def recover(cls, rt_uuid, xmldesc, conf, repo):  # FIXME
        inst = cls(xmldesc, conf=conf, repo=repo, rt_uuid=rt_uuid)
        inst._resync()
        doms.add(inst)
        return inst

    def __init__(self, xmldesc, conf, repo,
                 rt_uuid=None):  # FIXME
        self._xmldesc = xmldesc
        self._root = ET.fromstring(xmldesc)
        self._vm_uuid = uuid.UUID(self._root.find('./uuid').text)
        rt_name = _find_container_type(self._root)
        self._log.debug('initializing %r container %r',
                        rt_name, self.UUIDString())
        self._rt = runtime.create(
            rt_name, conf=conf, repo=repo, rt_uuid=rt_uuid
        )
        self._xml_file = xmlfile.XMLFile(self._rt.uuid, conf)
        self._log.debug('initializing container %r runtime %r',
                        self.UUIDString(), self._rt.uuid)
        self.events = events.Handler(
            name='Domain(%s)' % self._vm_uuid,
            parent=events.root)

    def destroyFlags(self, flags):
        #  flags are unused
        vm_uuid = self.UUIDString()

        self._log.debug('shutting down container %r', vm_uuid)
        try:
            self._shutdown()
            doms.remove(vm_uuid)
        except runner.OperationFailed:
            errors.throw()  # FIXME: specific error
        except KeyError:
            errors.throw()  # FIXME: specific error

    def destroy(self):
        return self.destroyFlags(0)

    def reset(self, flags):
        self._log.debug('resetting container %r', self.UUIDString())
        self._rt.stop()
        self._log.debug('stopped container %r', self.UUIDString())
        self._rt.start()
        self._log.debug('restarted container %r', self.UUIDString())

    def runtimeUUIDString(self):
        return str(self._rt.uuid)

    def ID(self):
        return self._vm_uuid.int

    def UUIDString(self):
        return str(self._vm_uuid)

    def XMLDesc(self, flags):
        # TODO: raise warning to signal we ignore flags?
        return self._xmldesc

    def controlInfo(self):
        # TODO: do it better
        return (libvirt.VIR_DOMAIN_CONTROL_OK, 0, 0)

#    def blockInfo(self, path, flags):
#        pass
#
#    def setTime(self, time):
#        pass

    def info(self):
        # TODO: check all but the first value
        return [libvirt.VIR_DOMAIN_RUNNING, 0, 0, 1, 0]

    def vcpus(self):
        # TODO: does this count as hack?
        return [[], []]

    def _startup(self):
        self._log.debug('clearing XML cache for %r', self.UUIDString())
        self._xml_file.clear()
        self._log.debug('setting up container %r', self.UUIDString())
        self._rt.setup()
        self._log.debug('configuring container %r', self.UUIDString())
        self._rt.configure(self._root)
        self._log.debug('saving domain XML for %r', self.UUIDString())
        self._xml_file.save(self._root)
        self._log.debug('starting container %r', self.UUIDString())
        self._rt.start()
        self._log.debug('started container %r', self.UUIDString())

    def _resync(self):
        self._log.debug('resyncing container %r', self.UUIDString())
        self._rt.resync()
        self._log.debug('resynced container %r', self.UUIDString())

    def _shutdown(self):
        self._log.debug('shutting down container %r', self.UUIDString())
        self._rt.stop()
        self._log.debug('stopped container %r', self.UUIDString())
        self._rt.teardown()
        self._xml_file.clear()
        self._log.debug('turn down container %r', self.UUIDString())

    def __getattr__(self, name):
        # virDomain does not expose non-callable attributes.
        return self._fake_method

    def _fake_method(self, *args):
        errors.throw()


def _find_container_type(root):
    cont = root.find(
        './metadata/{%s}container' % xmlconstants.METADATA_CONTAINERS_URI
    )
    if cont is None:
        raise runtimes.ConfigError('missing container type')
    return cont.text.strip()
