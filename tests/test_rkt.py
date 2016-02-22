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


import uuid
import unittest

import convirt
import convirt.rkt


class RktTests(unittest.TestCase):

    def setUp(self):
        self.rkt_uuid = str(uuid.uuid4())
        self.rkt = convirt.rkt.Rkt(self.rkt_uuid)

    def test_created_not_running(self):
        self.assertFalse(self.rkt.running)

    def test_runtime_name_none_before_start(self):
        self.assertEqual(self.rkt.runtime_name(), None)
