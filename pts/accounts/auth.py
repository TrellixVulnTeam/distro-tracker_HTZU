# Copyright 2013 The Debian Package Tracking System Developers
# See the COPYRIGHT file at the top-level directory of this distribution and
# at http://deb.li/ptsauthors
#
# This file is part of the Package Tracking System. It is subject to the
# license terms in the LICENSE file found in the top-level directory of
# this distribution and at http://deb.li/ptslicense. No part of the Package
# Tracking System, including this file, may be copied, modified, propagated, or
# distributed except according to the terms contained in the LICENSE file.
from __future__ import unicode_literals
from django.contrib.auth import get_user_model

User = get_user_model()


class PtsUserBackend(object):
    def authenticate(self, username=None, password=None):
        """
        Implements the custom authentication method.

        Since a particular PTS user may have multiple email accounts associated
        with their account and they should be able to log in using any one of
        them, this authentication backend first matches the given email to the
        :class:`pts.accounts.models.User` instance to which the email is
        associated and then authenticates the credentials against that user
        instance.

        The signature of the method is adapted to take a username argument
        representing the email of the user. This way, it matches the default
        Django authentication backend method signature which allows admin users
        to log in to the admin console using any of their associated emails.

        :returns: :class:`pts.accounts.models.User` instance if the authentication
            is successful, or ``None`` otherwise.
        """
        email = username
        # Find a user with the given email
        try:
            user = User.objects.get(emails__email=email)
        except User.DoesNotExist:
            return None

        # Check if valid log in details were provided
        if user.check_password(password):
            return user
        else:
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
