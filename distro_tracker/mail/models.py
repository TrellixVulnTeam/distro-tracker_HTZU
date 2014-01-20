# Copyright 2013 The Distro Tracker Developers
# See the COPYRIGHT file at the top-level directory of this distribution and
# at http://deb.li/DTAuthors
#
# This file is part of Distro Tracker. It is subject to the license terms
# in the LICENSE file found in the top-level directory of this
# distribution and at http://deb.li/DTLicense. No part of Distro Tracker,
# including this file, may be copied, modified, propagated, or distributed
# except according to the terms contained in the LICENSE file.
"""
Defines models specific for the :py:mod:`distro_tracker.mail` app.
"""
from __future__ import unicode_literals
from django.db import models
from django.conf import settings
from django.utils.encoding import python_2_unicode_compatible
from distro_tracker.core.models import EmailUser
from distro_tracker.core.models import Confirmation, ConfirmationManager


class CommandConfirmationManager(ConfirmationManager):
    """
    A custom manager for the :py:class:`CommandConfirmation` model.
    """
    def create_for_commands(self, commands):
        """
        Creates a :py:class:`CommandConfirmation` object for the given commands.

        :param commands: An iterable of commands for which a confirmation is requested.
        :raises distro_tracker.mail.models.CommandConfirmationException: If it is unable to generate a unique key.
        """
        commands = '\n'.join(commands)
        return self.create_confirmation(commands, **{
            'commands': commands,
        })


@python_2_unicode_compatible
class CommandConfirmation(Confirmation):
    """
    A model representing pending confirmations for email interface commands.
    """
    commands = models.TextField()

    objects = CommandConfirmationManager()

    def __str__(self):
        return self.commands

    @property
    def command_list(self):
        """
        :return: A list of strings representing commands which are confirmed
                  by this instance.
        """
        return self.commands.splitlines()


class EmailUserBounceStatsManager(models.Manager):
    """
    A custom :py:class:`Manager <django.db.models.Manager>` for the
    :py:class:`EmailUserBounceStats` model.
    """
    def get_bounce_stats(self, email, date):
        """
        Gets the :py:class:`EmailUserBounceStats` instance for the given
        :py:class:`EmailUser <distro_tracker.core.models.EmailUser>` on the given ``date``

        :param email: The email of the
            :py:class:`EmailUser <distro_tracker.core.models.EmailUser>`
        :type email: string

        :param date: The date of the required stats
        :type date: :py:class:`datetime.datetime`
        """
        user = self.get(user_email__email=email)
        bounce_stats, created = user.bouncestats_set.get_or_create(date=date)
        if created:
            self.limit_bounce_information(email)
        return bounce_stats

    def add_bounce_for_user(self, email, date):
        """
        Registers a bounced email for a given
        :py:class:`EmailUser <distro_tracker.core.models.EmailUser>`

        :param email: The email of the
            :py:class:`EmailUser <distro_tracker.core.models.EmailUser>` for which a
            bounce will be logged
        :type email: string

        :param date: The date of the bounce
        :type date: :py:class:`datetime.datetime`
        """
        bounce_stats = self.get_bounce_stats(email, date)
        bounce_stats.mails_bounced += 1
        bounce_stats.save()

    def add_sent_for_user(self, email, date):
        """
        Registers a sent email for a given
        :py:class:`EmailUser <distro_tracker.core.models.EmailUser>`

        :param email: The email of the
            :py:class:`EmailUser <distro_tracker.core.models.EmailUser>` for which a
            sent email will be logged
        :type email: string

        :param date: The date of the sent email
        :type date: :py:class:`datetime.datetime`
        """
        bounce_stats = self.get_bounce_stats(email, date)
        bounce_stats.mails_sent += 1
        bounce_stats.save()

    def limit_bounce_information(self, email):
        """
        Makes sure not to keep more records than the number of days set by
        :py:attr:`PTS_MAX_DAYS_TOLERATE_BOUNCE <distro_tracker.project.settings.PTS_MAX_DAYS_TOLERATE_BOUNCE>`
        """
        user = self.get(user_email__email=email)
        days = settings.PTS_MAX_DAYS_TOLERATE_BOUNCE
        for info in user.bouncestats_set.all()[days:]:
            info.delete()


class EmailUserBounceStats(EmailUser):
    """
    A proxy model for the :py:class:`EmailUser <distro_tracker.core.models.EmailUser>`
    model.
    It is defined in order to implement additional bounce stats-related
    methods without needlessly adding them to the public interface of
    :py:class:`EmailUser <distro_tracker.core.models.EmailUser>` when only the
    :py:mod:`distro_tracker.mail.dispatch` app should use them.
    """
    class Meta:
        proxy = True

    objects = EmailUserBounceStatsManager()

    def has_too_many_bounces(self):
        """
        Checks if the user has too many bounces.
        """
        days = settings.PTS_MAX_DAYS_TOLERATE_BOUNCE
        count = 0
        for stats in self.bouncestats_set.all()[:days]:
            # If no mails were sent on a particular day nothing could bounce
            if stats.mails_sent:
                if stats.mails_bounced >= stats.mails_sent:
                    count += 1
        return count == days


@python_2_unicode_compatible
class BounceStats(models.Model):
    """
    A model representing a user's bounce statistics.

    It stores the number of sent and bounced mails for a particular date.
    """
    email_user = models.ForeignKey(EmailUserBounceStats)
    mails_sent = models.IntegerField(default=0)
    mails_bounced = models.IntegerField(default=0)
    date = models.DateField()

    class Meta:
        ordering = ['-date']
        unique_together = ('email_user', 'date')

    def __str__(self):
        return (
            'Got {bounced} bounces out of {sent} mails to {email} on {date}'.format(
                email=self.email_user,
                date=self.date,
                sent=self.mails_sent,
                bounced=self.mails_bounced)
        )
