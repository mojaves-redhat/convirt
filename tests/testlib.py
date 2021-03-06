from __future__ import absolute_import
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

from contextlib import contextmanager
import collections
import gzip
import os
import os.path
import shutil
import tarfile
import tempfile
import uuid
import unittest

import convirt.command
import convirt.config
import convirt.config.environ
import convirt.metrics.cgroups
import convirt.runtime
import convirt.runtimes
from convirt.runtimes import fake
from convirt.runtimes import rkt

from . import monkey


class TestCase(unittest.TestCase):

    def assertNotRaises(self, callableObj=None, *args, **kwargs):
        # This is required when any exception raised during the call should be
        # considered as a test failure.
        context = not_raises(self)
        if callableObj is None:
            return context
        with context:
            callableObj(*args, **kwargs)


@contextmanager
def not_raises(test_case):
    try:
        yield
    except Exception as e:
        raise test_case.failureException("Exception raised: %s" % e)


class TruePath(object):
    def cmd(self):
        return True


class NonePath(object):
    def __init__(self):
        self.cmd = None


TEMPDIR = '/tmp'


@contextmanager
def named_temp_dir(base=TEMPDIR):
    tmp_dir = tempfile.mkdtemp(dir=base)
    try:
        yield tmp_dir
    finally:
        shutil.rmtree(tmp_dir)


def make_conf(**kwargs):
    conf = convirt.config.environ.current()
    for k, v in list(kwargs.items()):
        setattr(conf, k, v)
    return conf


@contextmanager
def global_conf(**kwargs):
    saved_conf = convirt.config.environ.current()

    conf = make_conf(**kwargs)
    convirt.config.environ.setup(conf)
    try:
        yield conf
    finally:
        convirt.config.environ.setup(saved_conf)


def fake_executables():
    paths = ['.', './tests', './fake/bin', './tests/fake/bin']
    return {
        'machinectl': convirt.command.Path('true'),
        'systemctl': convirt.command.Path('systemctl', paths=paths),
        'docker': convirt.command.Path('docker', paths=paths),
        'rkt': convirt.command.Path('rkt', paths=paths),
        'systemd-run': convirt.command.Path('systemd-run', paths=paths),
    }


class RunnableTestCase(TestCase):

    def setUp(self):
        self.guid = uuid.uuid4()
        self.run_dir = tempfile.mkdtemp()
        self.patch = monkey.Patch([
            (rkt.Network, 'DIR', self.run_dir),
            (convirt.command, 'executables', fake_executables()),
        ])
        self.patch.apply()
        convirt.runtime.clear()
        convirt.runtime.configure()

    def tearDown(self):
        self.patch.revert()
        shutil.rmtree(self.run_dir)


@contextmanager
def move_into(path):
    oldpath = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(oldpath)


class CgroupTestCase(TestCase):

    def setUp(self):
        self.pid = 0
        testdir = os.path.dirname(os.path.abspath(__file__))
        self.root = os.path.join(testdir, 'fake')

        self.procfsroot = os.path.join(
            self.root, convirt.metrics.cgroups.PROCFS
        )
        self.cgroupfsroot = os.path.join(
            self.root, convirt.metrics.cgroups.CGROUPFS
        )

        with move_into(self.root):
            cgroupsdata = os.path.join(self.root, 'cgroups.tgz')
            with gzip.GzipFile(cgroupsdata) as gz:
                tar = tarfile.TarFile(fileobj=gz)
                tar.extractall()

        self.patch = monkey.Patch([
            (convirt.metrics.cgroups, '_PROCBASE', self.procfsroot),
            (convirt.metrics.cgroups, '_CGROUPBASE', self.cgroupfsroot),
        ])
        self.patch.apply()

    def tearDown(self):
        self.patch.revert()
        shutil.rmtree(self.procfsroot)
        shutil.rmtree(self.cgroupfsroot)


class FakeRunnableTestCase(TestCase):

    def setUp(self):
        def _fake_create(rt, conf, repo, **kwargs):
            return fake.Fake(
                conf,
                repo,
                **kwargs
            )

        self.patch = monkey.Patch([
            (convirt.runtime, 'create', _fake_create),
        ])
        self.patch.apply()
        self.dom = convirt.domain.Domain(
            minimal_dom_xml(),
            convirt.config.environ.current(),
            FakeRepo()
        )

    def tearDown(self):
        self.patch.revert()


class FakeRunner(object):
    def __init__(self):
        self.stopped = False
        self.started = False
        self.setup_done = False
        self.teardown_done = False
        self.configured = False
        self.resynced = False
        self.uuid = '00000000-0000-0000-0000-000000000000'

    def setup(self, *args, **kwargs):
        self.setup_done = True

    def teardown(self, *args, **kwargs):
        self.teardown_done = True

    def start(self, *args, **kwargs):
        self.started = True

    def resync(self):
        self.resynced = True

    def stop(self):
        self.stopped = True

    def configure(self, *args, **kwargs):
        self.configured = True


def minimal_dom_xml(vm_uuid=None):
    data = read_test_data('minimal_dom.xml')
    vm_uuid = str(uuid.uuid4()) if vm_uuid is None else vm_uuid
    return data.format(vm_uuid=vm_uuid)


def full_dom_xml(vm_uuid=None):
    data = read_test_data('full_dom.xml')
    vm_uuid = str(uuid.uuid4()) if vm_uuid is None else vm_uuid
    return data.format(vm_uuid=vm_uuid)


def only_disk_dom_xml():
    return read_test_data('only_disk.xml')


def only_mem_dom_xml():
    return read_test_data('only_mem.xml')


def disk_dev_dom_xml():
    return read_test_data('disk_dev.xml')


def disk_file_malformed_dom_xml():
    return read_test_data('disk_file_malformed.xml')


def bridge_down_dom_xml():
    return read_test_data('bridge_down.xml')


def bridge_no_source_dom_xml():
    return read_test_data('bridge_no_source.xml')


def metadata_drive_map_dom_xml():
    return read_test_data('metadata_drive_map.xml')


def read_test_data(name):
    testdir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(testdir, 'data', name)
    with open(path, 'rt') as src:
        return src.read()


class FakeRepo(convirt.command.Repo):

    def __init__(self):
        super(FakeRepo, self).__init__(execs=fake_executables())
        self._cmds = collections.defaultdict(
            lambda: convirt.command.FakeCommand
        )
