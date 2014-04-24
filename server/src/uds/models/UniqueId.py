# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''

from __future__ import unicode_literals

__updated__ = '2014-04-24'

from django.db import models
from uds.core.db.LockingManager import LockingManager

import logging

logger = logging.getLogger(__name__)


class UniqueId(models.Model):
    '''
    Unique ID Database. Used to store unique names, unique macs, etc...
    Managed via uds.core.util.UniqueIDGenerator.UniqueIDGenerator
    '''
    owner = models.CharField(max_length=128, db_index=True, default='')
    basename = models.CharField(max_length=32, db_index=True)
    seq = models.BigIntegerField(db_index=True)
    assigned = models.BooleanField(db_index=True, default=True)
    stamp = models.IntegerField(db_index=True, default=0)

    objects = LockingManager()

    class Meta:
        '''
        Meta class to declare default order and unique multiple field index
        '''
        unique_together = (('basename', 'seq'),)
        ordering = ('-seq',)
        app_label = 'uds'

    def __unicode__(self):
        return u"{0} {1}.{2}, assigned is {3}".format(self.owner, self.basename, self.seq, self.assigned)

