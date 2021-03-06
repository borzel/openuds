# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2018 Virtual Cable S.L.
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

"""

@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _
from uds.core.ui.UserInterface import gui
from uds.core import auths
from uds.core.auths.Exceptions import AuthenticatorException
from uds.core.util import ldaputil

import ldap
import re
import logging

__updated__ = '2018-02-01'

logger = logging.getLogger(__name__)

LDAP_RESULT_LIMIT = 100


class RegexLdap(auths.Authenticator):

    host = gui.TextField(length=64, label=_('Host'), order=1, tooltip=_('Ldap Server Host'), required=True)
    port = gui.NumericField(length=5, label=_('Port'), defvalue='389', order=2, tooltip=_('Ldap port (usually 389 for non ssl and 636 for ssl)'), required=True)
    ssl = gui.CheckBoxField(label=_('Use SSL'), order=3, tooltip=_('If checked, the connection will be ssl, using port 636 instead of 389'))
    username = gui.TextField(length=64, label=_('User'), order=4, tooltip=_('Username with read privileges on the base selected'), required=True, tab=gui.CREDENTIALS_TAB)
    password = gui.PasswordField(lenth=32, label=_('Password'), order=5, tooltip=_('Password of the ldap user'), required=True, tab=gui.CREDENTIALS_TAB)
    timeout = gui.NumericField(length=3, label=_('Timeout'), defvalue='10', order=6, tooltip=_('Timeout in seconds of connection to LDAP'), required=True, minValue=1)

    ldapBase = gui.TextField(length=64, label=_('Base'), order=7, tooltip=_('Common search base (used for "users" and "groups")'), required=True, tab=_('Ldap info'))
    userClass = gui.TextField(length=64, label=_('User class'), defvalue='posixAccount', order=8, tooltip=_('Class for LDAP users (normally posixAccount)'), required=True, tab=_('Ldap info'))
    userIdAttr = gui.TextField(length=64, label=_('User Id Attr'), defvalue='uid', order=9, tooltip=_('Attribute that contains the user id'), required=True, tab=_('Ldap info'))
    userNameAttr = gui.TextField(length=640, label=_('User Name Attr'), multiline=2, defvalue='uid', order=10, tooltip=_('Attributes that contains the user name (list of comma separated values)'), required=True, tab=_('Ldap info'))
    groupNameAttr = gui.TextField(length=640, label=_('Group Name Attr'), multiline=2, defvalue='cn', order=11, tooltip=_('Attribute that contains the group name'), required=True, tab=_('Ldap info'))
    # regex = gui.TextField(length=64, label = _('Regular Exp. for groups'), defvalue = '^(.*)', order = 12, tooltip = _('Regular Expression to extract the group name'), required = True)

    altClass = gui.TextField(length=64, label=_('Alt. class'), defvalue='', order=20, tooltip=_('Class for LDAP objects that will be also checked for groups retrieval (normally empty)'), required=False, tab=_('Advanced'))

    typeName = _('Regex LDAP Authenticator')
    typeType = 'RegexLdapAuthenticator'
    typeDescription = _('Regular Expressions LDAP authenticator')
    iconFile = 'auth.png'

    # If it has and external source where to get "new" users (groups must be declared inside UDS)
    isExternalSource = True
    # If we need to enter the password for this user
    needsPassword = False
    # Label for username field
    userNameLabel = _('Username')
    # Label for group field
    groupNameLabel = _("Group")
    # Label for password field
    passwordLabel = _("Password")

    def __init__(self, dbAuth, environment, values=None):
        super(RegexLdap, self).__init__(dbAuth, environment, values)
        if values is not None:
            self.__validateField(values['userNameAttr'], str(self.userNameAttr.label))
            self.__validateField(values['userIdAttr'], str(self.userIdAttr.label))
            self.__validateField(values['groupNameAttr'], str(self.groupNameAttr.label))

            self._host = values['host']
            self._port = values['port']
            self._ssl = gui.strToBool(values['ssl'])
            self._username = values['username']
            self._password = values['password']
            self._timeout = values['timeout']
            self._ldapBase = values['ldapBase']
            self._userClass = values['userClass']
            self._userIdAttr = values['userIdAttr']
            self._groupNameAttr = values['groupNameAttr']
            # self._regex = values['regex']
            self._userNameAttr = values['userNameAttr']
            self._altClass = values['altClass']
        else:
            self._host = None
            self._port = None
            self._ssl = None
            self._username = None
            self._password = None
            self._timeout = None
            self._ldapBase = None
            self._userClass = None
            self._userIdAttr = None
            self._groupNameAttr = None
            # self._regex = None
            self._userNameAttr = None
            self._altClass = None

        self._connection = None

    def __validateField(self, field, fieldLabel):
        """
        Validates the multi line fields refering to attributes
        """
        for line in field.splitlines():
            if line.find('=') != -1:
                _, pattern = line.split('=')[0:2]
                if pattern.find('(') == -1:
                    pattern = '(' + pattern + ')'
                try:
                    re.search(pattern, '')
                except Exception:
                    raise auths.Authenticator.ValidationException('Invalid pattern in {0}: {1}'.format(fieldLabel, line))

    def __getAttrsFromField(self, field):
        res = []
        for line in field.splitlines():
            equalPos = line.find('=')
            if equalPos != -1:
                attr = line[:equalPos]
            else:
                attr = line
            res.append(attr)
        return res

    def __processField(self, field, attributes):
        res = []
        logger.debug('Attributes: {}'.format(attributes))
        for line in field.splitlines():
            equalPos = line.find('=')
            if equalPos == -1:
                line += '=(.*)'
                equalPos = line.find('=')
            attr, pattern = (line[:equalPos], line[equalPos + 1:])
            attr = attr.lower()
            # if pattern do not have groups, define one with full re
            if pattern.find('(') == -1:
                pattern = '(' + pattern + ')'
            val = attributes.get(attr, [])
            if type(val) is not list:  # May we have a single value
                val = [val]

            logger.debug('Pattern: {0}'.format(pattern))

            for v in val:
                try:
                    srch = re.search(pattern, v, re.IGNORECASE)
                    logger.debug("Found against {0}: {1} ".format(v, srch.groups()))
                    if srch is None:
                        continue
                    res.append(''.join(srch.groups()))
                except Exception:
                    pass  # Ignore exceptions here
        logger.debug('Res: {}'.format(res))
        return res

    def valuesDict(self):
        return {
            'host': self._host, 'port': self._port, 'ssl': gui.boolToStr(self._ssl),
            'username': self._username, 'password': self._password, 'timeout': self._timeout,
            'ldapBase': self._ldapBase, 'userClass': self._userClass,
            'userIdAttr': self._userIdAttr, 'groupNameAttr': self._groupNameAttr,
            'userNameAttr': self._userNameAttr, 'altClass': self._altClass,
        }

    def __str__(self):
        return "Ldap Auth: {}:{}@{}:{}, base = {}, userClass = {}, userIdAttr = {}, groupNameAttr = {}, userName attr = {}, altClass={}".format(
               self._username, self._password, self._host, self._port, self._ldapBase, self._userClass, self._userIdAttr, self._groupNameAttr,
               self._userNameAttr, self._altClass)

    def marshal(self):
        return '\t'.join([
            'v3',
            self._host, self._port, gui.boolToStr(self._ssl), self._username, self._password,
            self._timeout, self._ldapBase, self._userClass, self._userIdAttr,
            self._groupNameAttr, self._userNameAttr, self._altClass
        ]).encode('utf8')

    def unmarshal(self, val):
        data = val.decode('utf8').split('\t')
        if data[0] == 'v1':
            logger.debug("Data: {0}".format(data[1:]))
            self._host, self._port, self._ssl, self._username, self._password, \
                self._timeout, self._ldapBase, self._userClass, self._userIdAttr, \
                self._groupNameAttr, _regex, self._userNameAttr = data[1:]
            self._ssl = gui.strToBool(self._ssl)
            self._groupNameAttr = self._groupNameAttr + '=' + _regex
            self._userNameAttr = '\n'.join(self._userNameAttr.split(','))
        elif data[0] == 'v2':
            logger.debug("Data v2: {0}".format(data[1:]))
            self._host, self._port, self._ssl, self._username, self._password, \
                self._timeout, self._ldapBase, self._userClass, self._userIdAttr, \
                self._groupNameAttr, self._userNameAttr = data[1:]
            self._ssl = gui.strToBool(self._ssl)
        elif data[0] == 'v3':
            logger.debug("Data v3: {0}".format(data[1:]))
            self._host, self._port, self._ssl, self._username, self._password, \
                self._timeout, self._ldapBase, self._userClass, self._userIdAttr, \
                self._groupNameAttr, self._userNameAttr, self._altClass = data[1:]
            self._ssl = gui.strToBool(self._ssl)

    def __connection(self):
        """
        Tries to connect to ldap. If username is None, it tries to connect using user provided credentials.
        @return: Connection established
        @raise exception: If connection could not be established
        """
        if self._connection is None:  # We want this method also to check credentials
            self._connection = ldaputil.connection(self._username, self._password, self._host, port=self._port, ssl=self._ssl, timeout=self._timeout, debug=False)

        return self._connection

    def __connectAs(self, username, password):
        return ldaputil.connection(username, password, self._host, ssl=self._ssl, timeout=self._timeout, debug=False)

    def __getUser(self, username):
        """
        Searchs for the username and returns its LDAP entry
        @param username: username to search, using user provided parameters at configuration to map search entries.
        @return: None if username is not found, an dictionary of LDAP entry attributes if found.
        @note: Active directory users contains the groups it belongs to in "memberOf" attribute
        """
        return ldaputil.getFirst(
            con=self.__connection(),
            base=self._ldapBase,
            objectClass=self._userClass,
            field=self._userIdAttr,
            value=username,
            attributes=[self._userIdAttr] + self.__getAttrsFromField(self._userNameAttr) + self.__getAttrsFromField(self._groupNameAttr),
            sizeLimit=LDAP_RESULT_LIMIT
        )

    def __getGroups(self, usr):
        return self.__processField(self._groupNameAttr, usr)

    def __getUserRealName(self, usr):
        return ' '.join(self.__processField(self._userNameAttr, usr))

    def authenticate(self, username, credentials, groupsManager):
        """
        Must authenticate the user.
        We can have to different situations here:
           1.- The authenticator is external source, what means that users may be unknown to system before callig this
           2.- The authenticator isn't external source, what means that users have been manually added to system and are known before this call
        We receive the username, the credentials used (normally password, but can be a public key or something related to pk) and a group manager.
        The group manager is responsible for letting know the authenticator which groups we currently has active.
        @see: uds.core.auths.GroupsManager
        """
        try:
            # Locate the user at LDAP
            usr = self.__getUser(username)

            if usr is None:
                return False

            # Let's see first if it credentials are fine
            self.__connectAs(usr['dn'], credentials)  # Will raise an exception if it can't connect

            groupsManager.validate(self.__getGroups(usr))

            return True

        except Exception:
            return False

    def createUser(self, usrData):
        """
        We must override this method in authenticators not based on external sources (i.e. database users, text file users, etc..)
        External sources already has the user  cause they are managed externally, so, it can at most test if the users exists on external source
        before accepting it.
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @param usrData: Contains data received from user directly, that is, a dictionary with at least: name, real_name, comments, state & password
        @return:  Raises an exception (AuthException) it things didn't went fine
        """
        res = self.__getUser(usrData['name'])
        if res is None:
            raise AuthenticatorException(_('Username not found'))
        # Fills back realName field
        usrData['real_name'] = self.__getUserRealName(res)

    def getRealName(self, username):
        """
        Tries to get the real name of an user
        """
        res = self.__getUser(username)
        if res is None:
            return username
        return self.__getUserRealName(res)

    def modifyUser(self, usrData):
        """
        We must override this method in authenticators not based on external sources (i.e. database users, text file users, etc..)
        Modify user has no reason on external sources, so it will never be used (probably)
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @param usrData: Contains data received from user directly, that is, a dictionary with at least: name, realName, comments, state & password
        @return:  Raises an exception it things doesn't go fine
        """
        return self.createUser(usrData)

    def createGroup(self, groupData):
        """
        We must override this method in authenticators not based on external sources (i.e. database users, text file users, etc..)
        External sources already has its own groups and, at most, it can check if it exists on external source before accepting it
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @params groupData: a dict that has, at least, name, comments and active
        @return:  Raises an exception it things doesn't go fine
        """
        pass

    def getGroups(self, username, groupsManager):
        """
        Looks for the real groups to which the specified user belongs
        Updates groups manager with valid groups
        Remember to override it in derived authentication if needed (external auths will need this, for internal authenticators this is never used)
        """
        user = self.__getUser(username)
        if user is None:
            raise AuthenticatorException(_('Username not found'))
        groups = self.__getGroups(user)
        groupsManager.validate(groups)

    def searchUsers(self, pattern):
        try:
            res = []
            for r in ldaputil.getAsDict(
                con=self.__connection(),
                base=self._ldapBase,
                ldapFilter='(&(&(objectClass={})({}={}*))(objectCategory=person))'.format(self._userClass, self._userIdAttr, ldaputil.escape(pattern)),
                attrList=None,  # All attrs
                sizeLimit=LDAP_RESULT_LIMIT
            ):
                logger.debug('R: {0}'.format(r))
                res.append({
                    'id': r.get(self._userIdAttr.lower(), '')[0],
                    'name': self.__getUserRealName(r)
                })
            logger.debug(res)
            return res
        except Exception:
            logger.exception("Exception: ")
            raise AuthenticatorException(_('Too many results, be more specific'))

    @staticmethod
    def test(env, data):
        try:
            auth = RegexLdap(None, env, data)
            return auth.testConnection()
        except Exception as e:
            logger.error("Exception found testing Simple LDAP auth {0}: {1}".format(e.__class__, e))
            return [False, "Error testing connection"]

    def testConnection(self):
        try:
            con = self.__connection()
        except Exception as e:
            return [False, str(e)]

        try:
            con.search_s(base=self._ldapBase, scope=ldap.SCOPE_BASE)
        except Exception:
            return [False, _('Ldap search base is incorrect')]

        try:
            if len(con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE, filterstr='(objectClass=%s)' % self._userClass, sizelimit=1)) == 1:
                raise Exception()
            return [False, _('Ldap user class seems to be incorrect (no user found by that class)')]
        except Exception:
            # If found 1 or more, all right
            pass

        # Now test objectclass and attribute of users
        try:
            if len(con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE, filterstr='(&(objectClass=%s)(%s=*))' % (self._userClass, self._userIdAttr), sizelimit=1)) == 1:
                raise Exception()
            return [False, _('Ldap user id attr is probably wrong (can\'t find any user with both conditions)')]
        except Exception:
            # If found 1 or more, all right
            pass

        for grpNameAttr in self._groupNameAttr.split('\n'):
            vals = grpNameAttr.split('=')[0]
            if vals == 'dn':
                continue
            try:
                if len(con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE, filterstr='(%s=*)' % vals, sizelimit=1)) == 1:
                    continue
            except Exception:
                continue
            return [False, _('Ldap group id attribute seems to be incorrect (no group found by that attribute)')]

        # Now try to test regular expression to see if it matches anything (
        try:
            # Check the existence of at least a () grouping
            # Check validity of regular expression (try to compile it)
            # this only right now
            pass
        except Exception:
            pass

        return [True, _("Connection params seem correct, test was succesfully executed")]
