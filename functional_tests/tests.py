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
Functional tests for the Package Tracking System.
"""
from __future__ import unicode_literals
from django.test import LiveServerTestCase
from django.core.urlresolvers import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from pts.core.models import SourcePackageName, BinaryPackageName
from pts.accounts.models import UserRegistrationConfirmation
from pts.accounts.models import ResetPasswordConfirmation
from pts.accounts.models import AddEmailConfirmation
from pts.accounts.models import MergeAccountConfirmation
from pts.core.models import EmailUser
from pts.core.models import ContributorName
from pts.accounts.models import UserEmail
from pts.core.models import Team
from pts.core.models import SourcePackage
from pts.core.models import PackageName
from pts.core.models import Subscription
from pts.core.models import TeamMembership
from pts.core.panels import BasePanel

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
import selenium.webdriver.support.ui as ui
from selenium.webdriver.common.keys import Keys
from django.utils.six.moves import mock
import os
import time


class SeleniumTestCase(LiveServerTestCase):
    """
    A class which includes some common functionality for all tests which use
    Selenium.
    """
    def setUp(self):
        os.environ['NO_PROXY'] = 'localhost,127.0.0.1,127.0.1.1'
        fp = webdriver.FirefoxProfile()
        fp.set_preference('network.proxy.type', 0)
        self.browser = webdriver.Firefox(firefox_profile=fp)
        self.browser.implicitly_wait(3)

    def tearDown(self):
        self.browser.close()

    def get_page(self, relative):
        """
        Helper method which points the browser to the absolute URL based on the
        given relative URL and the server's live_server_url.
        """
        self.browser.get(self.absolute_url(relative))

    def wait_response(self, seconds):
        time.sleep(seconds)

    def absolute_url(self, relative):
        """
        Helper method which builds an absolute URL where the live_server_url is
        the root.
        """
        return self.live_server_url + relative

    def input_to_element(self, id, text):
        """
        Helper method which sends the text to the element with the given ID.
        """
        element = self.browser.find_element_by_id(id)
        element.send_keys(text)

    def clear_element_text(self, id):
        """
        Helper method which removes any text already found in the element with
        the given ID.
        """
        element = self.browser.find_element_by_id(id)
        element.clear()

    def click_link(self, link_text):
        """
        Helper method which clicks on the link with the given text.
        """
        element = self.browser.find_element_by_link_text(link_text)
        element.click()

    def send_enter(self, id):
        """
        Helper method which sends the enter key to the element with the given
        ID.
        """
        element = self.browser.find_element_by_id(id)
        element.send_keys(Keys.ENTER)

    def assert_in_page_body(self, text):
        body = self.browser.find_element_by_tag_name('body')
        self.assertIn(text, body.text)

    def assert_not_in_page_body(self, text):
        body = self.browser.find_element_by_tag_name('body')
        self.assertNotIn(text, body.text)

    def assert_element_with_id_in_page(self, element_id, custom_message=None):
        """
        Helper method which asserts that the element with the given ID can be
        found in the current browser page.
        """
        if custom_message is None:
            custom_message = element_id + " not found in the page."
        try:
            self.browser.find_element_by_id(element_id)
        except NoSuchElementException:
            self.fail(custom_message)

    def assert_element_with_class_in_page(self, class_name, custom_message=None):
        if custom_message is None:
            custom_message = class_name + " not found in the page."
        try:
            self.browser.find_element_by_class_name(class_name)
        except NoSuchElementException:
            self.fail(custom_message)

    def get_element_by_id(self, element_id):
        try:
            return self.browser.find_element_by_id(element_id)
        except NoSuchElementException:
            return None

    def get_element_by_class(self, class_name):
        try:
            return self.browser.find_element_by_class_name(class_name)
        except NoSuchElementException:
            return None

    def assert_current_url_equal(self, url):
        """
        Helper method which asserts that the given URL equals the current
        browser URL.
        The given URL should not include the domain.
        """
        self.assertEqual(
            self.browser.current_url,
            self.absolute_url(url))

    def set_mock_http_response(self, mock_requests, text, status_code=200):
        mock_response = mock_requests.models.Response()
        mock_response.status_code = status_code
        mock_response.text = text
        mock_requests.get.return_value = mock_response


def create_test_panel(panel_position):
    """
    Helper test decorator which creates a TestPanel before running the test and
    unregisters it when it completes, making sure all tests are ran in
    isolation.
    """
    def decorator(func):
        def wrap(self):
            class TestPanel(BasePanel):
                html_output = "Hello, world"
                position = panel_position
            try:
                ret = func(self)
            finally:
                TestPanel.unregister_plugin()
            return ret

        return wrap

    return decorator


class PackagePageTest(SeleniumTestCase):
    def setUp(self):
        super(PackagePageTest, self).setUp()
        self.package = SourcePackageName.objects.create(name='dummy-package')
        SourcePackageName.objects.create(name='second-package')
        self.binary_package = BinaryPackageName.objects.create(
            name='binary-package')
        self.binary_package.sourcepackage_set.create(
            source_package_name=self.package,
            version='1.0.0')

    def get_package_url(self, package_name):
        """
        Helper method returning the URL of the package with the given name.
        """
        return reverse('pts-package-page', kwargs={
            'package_name': package_name,
        })

    def send_text_to_package_search_form(self, text):
        """
        Helper function to send text input to the package search form.
        """
        search_form = self.browser.find_element_by_id('package-search-form')
        text_box = search_form.find_element_by_name('package_name')
        # Make sure any old text is removed.
        text_box.clear()
        text_box.send_keys(text)
        text_box.send_keys(Keys.ENTER)

    def test_access_source_package_page_by_url(self):
        """
        Tests that users can get to a package's page by going straight to its
        URL.
        """
        # The user tries to visit a package's page.
        self.get_page(self.get_package_url(self.package.name))

        # He has reached the package's page which is indicated in the tab's
        # title.
        self.assertIn(self.package.name, self.browser.title)
        # It is displayed in the content, as well.
        package_name_element = self.browser.find_element_by_tag_name('h1')
        self.assertEqual(package_name_element.text, self.package.name)

        # The user sees a footer with general information about PTS
        self.assert_element_with_id_in_page('footer')

        # There is a header with a form with a text box where the user can
        # type in the name of a package to get to its page.
        self.assert_element_with_id_in_page('package-search-form',
                                            "Form not found")

        # So, the uer types the name of another source package...
        self.send_text_to_package_search_form('second-package')

        # This causes the new pacakge's page to open.
        self.assertEqual(
            self.browser.current_url,
            self.absolute_url(self.get_package_url('second-package')))

        # The user would like to see the source package page for a binary
        # package that he types in the search form.
        self.send_text_to_package_search_form('binary-package')
        self.assertEqual(
            self.browser.current_url,
            self.absolute_url(self.get_package_url(self.package.name)))

        # However, when the user tries a package name which does not exist,
        # he expects to see a page informing him of this
        self.send_text_to_package_search_form('no-exist')
        self.assert_in_page_body('Package no-exist does not exist')

    def test_access_package_page_from_index(self):
        """
        Tests that the user can access a package page starting from the index
        and using the provided form.
        """
        # The user opens the start page of the PTS
        self.get_page('/')

        # He sees it is the index page of the PTS
        self.assertIn('Package Tracking System', self.browser.title)

        # There is a form which he can use for access to pacakges.
        self.assert_element_with_id_in_page('package-search-form')

        # He types in a name of a known source package...
        self.send_text_to_package_search_form(self.package.name)
        # ...and expects to see the package page open.
        self.assertEqual(
            self.browser.current_url,
            self.absolute_url(self.package.get_absolute_url()))

        # The user goes back to the index...
        self.browser.back()
        # ...and tries using the form to access a package page, but the package
        # does not exist.
        self.send_text_to_package_search_form('no-exist')
        self.assert_in_page_body('Package no-exist does not exist')

    @create_test_panel('left')
    def test_include_panel_left(self):
        """
        Tests whether a package page includes a panel in the left side column.
        """
        self.get_page(self.get_package_url(self.package.name))

        self.assert_element_with_id_in_page('pts-package-left')
        column = self.browser.find_element_by_id('pts-package-left')
        self.assertIn("Hello, world", column.text)

    @create_test_panel('center')
    def test_include_panel_center(self):
        """
        Tests whether a package page includes a panel in the center column.
        """
        self.get_page(self.get_package_url(self.package.name))

        self.assert_element_with_id_in_page('pts-package-center')
        column = self.browser.find_element_by_id('pts-package-center')
        self.assertIn("Hello, world", column.text)

    @create_test_panel('right')
    def test_include_panel_right(self):
        """
        Tests whether a package page includes a panel in the right side column.
        """
        self.get_page(self.get_package_url(self.package.name))

        self.assert_element_with_id_in_page('pts-package-right')
        column = self.browser.find_element_by_id('pts-package-right')
        self.assertIn("Hello, world", column.text)


User = get_user_model()


class RepositoryAdminTest(SeleniumTestCase):
    def setUp(self):
        super(RepositoryAdminTest, self).setUp()
        # Create a superuser which will be used for the tests
        User.objects.create_superuser(
            main_email='admin',
            password='admin'
        )

    def login_to_admin(self, username='admin', password='admin'):
        """
        Helper method which logs the user with the given credentials to the
        admin console.
        """
        self.get_page('/admin/')
        self.input_to_element('id_username', username)
        self.input_to_element('id_password', password)
        self.send_enter('id_password')

    @mock.patch('pts.core.retrieve_data.requests')
    def test_repository_add(self, mock_requests):
        """
        Tests that an admin user is able to add a new repository.
        """
        # The user first logs in to the admin panel.
        self.login_to_admin()

        # He expects to be able to successfully access it with his credentials.
        self.assertIn('Site administration', self.browser.title)

        # He now wants to go to the repositories management page.
        # The necessary link can be found in the page.
        try:
            self.browser.find_element_by_link_text("Repositories")
        except NoSuchElementException:
            self.fail("Link for repositories management not found in the admin")

        # Clicking on it opens a new page to manage repositories.
        self.click_link("Repositories")
        self.assertIn(
            'Repositories',
            self.browser.find_element_by_class_name('breadcrumbs').text
        )

        # He now wants to create a new repository...
        self.click_link("Add repository")
        self.assert_in_page_body("Add repository")
        try:
            save_button = self.browser.find_element_by_css_selector(
                'input.default')
        except NoSuchElementException:
            self.fail("Could not find the save button")

        # The user tries clicking the save button immediately
        save_button.click()
        # But this causes an error since there are some required fields...
        self.assert_in_page_body('Please correct the errors below')

        # He enters a name and shorthand for the repository
        self.input_to_element('id_name', 'stable')
        self.input_to_element('id_shorthand', 'stable')
        # He wants to create the repository by using a sources.list entry
        self.input_to_element(
            'id_sources_list_entry',
            'deb http://ftp.ba.debian.org/debian stable'
        )
        ## Make sure that no actual HTTP requests are sent out
        self.set_mock_http_response(mock_requests,
            'Suite: stable\n'
            'Codename: wheezy\n'
            'Architectures: amd64 armel armhf i386 ia64 kfreebsd-amd64'
            ' kfreebsd-i386 mips mipsel powerpc s390 s390x sparc\n'
            'Components: main contrib non-free\n'
            'Version: 7.1\n'
            'Description: Debian 7.1 Released 15 June 2013\n'
        )
        # The user decides to save by hitting the enter key
        self.send_enter('id_sources_list_entry')
        # The user sees a message telling him the repository has been added.
        self.assert_in_page_body("added successfully")
        # He also sees the information of the newly added repository
        self.assert_in_page_body('Codename')
        self.assert_in_page_body('wheezy')
        self.assert_in_page_body('Components')
        self.assert_in_page_body('main contrib non-free')

        # The user now wants to add another repository
        self.click_link("Add repository")
        # This time, he wants to enter all the necessary data manually.
        self.input_to_element('id_name', 'testing')
        self.input_to_element('id_shorthand', 'testing')
        self.input_to_element('id_uri', 'http://ftp.ba.debian.org/debian')
        self.input_to_element('id_suite', 'testing')
        self.input_to_element('id_codename', 'jessie')
        self.input_to_element('id_components', 'main non-free')
        architecture_option = self.browser.find_element_by_css_selector(
            '.field-architectures select option[value="1"]')
        architecture_option.click()
        # Finally the user clicks the save button
        self.browser.find_element_by_css_selector('input.default').click()

        # He sees that the new repository has also been created.
        self.assert_in_page_body("added successfully")
        # He also sees the information of the newly added repository
        self.assert_in_page_body('jessie')
        self.assert_in_page_body('main non-free')


class UserAccountsTestMixin(object):
    """
    Defines some common methods for all user account tests.
    """
    def setUp(self):
        super(UserAccountsTestMixin, self).setUp()
        self.package = SourcePackageName.objects.create(name='dummy-package')
        self.password = 'asdf'
        self.user = User.objects.create_user(
            main_email='user@domain.com', password=self.password,
            first_name='', last_name='')

    def refresh_user_object(self):
        """
        The method retrieves the user instance from the database forcing any
        cached properties to reload. This can be used when the user's
        properties need to be tested for updated values.
        """
        self.user = User.objects.get(main_email=self.user.main_email)

    def get_login_url(self):
        return reverse('pts-accounts-login')

    def get_profile_url(self):
        return reverse('pts-accounts-profile')

    def get_package_url(self, package_name):
        return reverse('pts-package-page', kwargs={
            'package_name': package_name,
        })

    def create_user(self, main_email, password, associated_emails=()):
        u = User.objects.create_user(main_email, password=password)
        for associated_email in associated_emails:
            u.emails.create(email=associated_email)
        return u

    def log_in(self, user=None, password=None):
        """
        Helper method which logs the user in, without taking any shortcuts (it goes
        through the steps to fill in the form and submit it).
        """
        if user is None:
            user = self.user
        if password is None:
            password = self.password

        self.get_page(self.get_login_url())
        self.input_to_element('id_username', user.main_email)
        self.input_to_element('id_password', password)
        self.send_enter('id_password')



class UserRegistrationTest(UserAccountsTestMixin, SeleniumTestCase):
    """
    Tests for the user registration story.
    """
    def setUp(self):
        super(UserRegistrationTest, self).setUp()
        # User registration tests do not want any already registered users
        EmailUser.objects.all().delete()
        User.objects.all().delete()

    def get_confirmation_url(self, message):
        """
        Extracts the confirmation URL from the given email message.
        Returns ``None`` if the message did not contain a confirmation URL.
        """
        match = self.re_confirmation_url.search(message.body)
        if not match:
            return None
        return match.group(1)

    def get_registration_url(self):
        return reverse('pts-accounts-register')

    def test_user_register(self):
        profile_url = self.get_profile_url()
        password_form_id = 'form-reset-password'
        user_email = 'user@domain.com'
        ## Preconditions:
        ## No registered users or command confirmations
        self.assertEqual(0, User.objects.count())
        self.assertEqual(0, UserRegistrationConfirmation.objects.count())

        ## Start of the test.
        # The user opens the front page
        self.get_page('/')
        # He can see a link to a registration page
        try:
            self.browser.find_element_by_link_text("Register")
        except NoSuchElementException:
            self.fail("Link for user registration not found on the front page")

        # Upon clicking the link, the user is taken to the registration page
        self.click_link("Register")
        self.assert_current_url_equal(self.get_registration_url())

        # He can see a registration form
        self.assert_element_with_id_in_page('form-register')

        # The user inputs only the email address
        self.input_to_element("id_main_email", user_email)
        self.send_enter('id_main_email')

        # The user is notified of a successful registration
        self.assert_current_url_equal(reverse('pts-accounts-register-success'))

        # The user receives an email with the confirmation URL
        self.assertEqual(1, len(mail.outbox))
        ## Get confirmation key from the database
        self.assertEqual(1, UserRegistrationConfirmation.objects.count())
        confirmation = UserRegistrationConfirmation.objects.all()[0]
        self.assertIn(confirmation.confirmation_key, mail.outbox[0].body)

        # The user goes to the confirmation URL
        confirmation_url = reverse(
            'pts-accounts-confirm-registration', kwargs={
                'confirmation_key': confirmation.confirmation_key
            })
        self.get_page(confirmation_url)

        # The user is asked to enter his password
        self.assert_element_with_id_in_page(password_form_id)

        # However, the user first goes back to the index...
        self.get_page('/')
        # ...and then goes back to the confirmation page which is still valid
        self.get_page(confirmation_url)

        password = 'asdf'
        self.input_to_element('id_password1', password)
        self.input_to_element('id_password2', password)
        self.send_enter('id_password2')

        # The user is now successfully logged in with his profile page open
        self.assert_current_url_equal(profile_url)

        # A message is provided telling the user that he has been registered
        self.assert_in_page_body('successfully registered')

        # When the user tries opening the confirmation page for the same key
        # again, it is no longer valid
        self.get_page(confirmation_url)
        with self.assertRaises(NoSuchElementException):
            self.browser.find_element_by_id(password_form_id)
        ## This is because the confirmation model instance has been removed...
        self.assertEqual(0, UserRegistrationConfirmation.objects.count())

        # The user goes back to the profile page and this time there is no
        # message saying he has been registered.
        self.get_page(profile_url)
        self.assert_not_in_page_body('successfully registered')

        # The user now wishes to log out
        self.assert_in_page_body('Log out')
        self.click_link('Log out')
        # The user is redirected back to the index page since he was found on
        # a private page prior to logging out.
        self.assert_current_url_equal('/')

        # From there, he tries logging in with his new account
        self.click_link('Log in')
        self.input_to_element('id_username', user_email)
        self.input_to_element('id_password', password)
        self.send_enter('id_password')
        # He is now back at the profile page
        self.assert_current_url_equal(self.get_profile_url())

    def test_register_email_already_has_subscriptions(self):
        """
        Tests that a user can register using an email which already has
        subscriptions to some packages.
        """
        ## Set up such an email
        email = EmailUser.objects.create(email='user@domain.com')
        package_name = 'dummy-package'
        Subscription.objects.create_for(
            email=email,
            package_name=package_name)
        # The user opens the registration page and enters the email
        self.get_page(self.get_registration_url())
        self.input_to_element('id_main_email', email.email)
        self.send_enter('id_main_email')
        self.wait_response(1)

        # The user is successfully registered
        self.assertEqual(1, User.objects.count())
        user = User.objects.all()[0]
        self.assertEqual(email.email, user.main_email)
        self.assertEqual(
            [email.email],
            [e.email for e in user.emails.all()])
        # ...a notification is displayed informing him of that
        self.assert_in_page_body('successfully registered')

        # The existing subscriptions are not removed
        self.assertTrue(user.is_subscribed_to(package_name))

    def test_user_registered(self):
        """
        Tests that a user registration fails when there is already a registered
        user with the given email.
        """
        ## Set up a registered user
        user_email = 'user@domain.com'
        associated_email = 'email@domain.com'
        self.create_user(user_email, 'asdf', [associated_email])

        # The user goes to the registration page
        self.get_page(self.get_registration_url())

        # The user enters the already existing user's email
        self.input_to_element('id_main_email', user_email)
        self.send_enter('id_main_email')

        # He stays on the same page and receives an error message
        self.assert_current_url_equal(self.get_registration_url())
        self.assert_in_page_body('email address is already in use')

        # The user now tries using the other email associated with the already
        # existing user account.
        self.clear_element_text('id_main_email')
        self.input_to_element('id_main_email', associated_email)
        self.send_enter('id_main_email')

        # He stays on the same page and receives an error message
        self.assert_current_url_equal(self.get_registration_url())
        self.assert_in_page_body('email address is already in use')

    def test_login(self):
        """
        Tests that a user can log in when he already has an existing account.
        """
        ## Set up an account
        user_email = 'user@domain.com'
        associated_emails = ['email@domain.com']
        password = 'asdf'
        self.create_user(user_email, password, associated_emails)

        # The user opens the front page and tries going to the log in page
        self.get_page('/')
        self.assert_in_page_body('Log in')
        self.click_link('Log in')
        # The user is now found in the log in page
        self.assert_current_url_equal(self.get_login_url())

        # There he can see a log in form
        self.assert_element_with_id_in_page('form-login')

        # He enters the correct email, but an incorrect password
        self.input_to_element('id_username', user_email)
        self.input_to_element('id_password', 'fdsa')
        self.send_enter('id_password')
        # He is met with an error message
        self.assert_in_page_body('Please enter a correct email and password')

        # Now the user correctly enters the password. The email should not
        # need to be entered again.
        self.input_to_element('id_password', password)
        self.send_enter('id_password')
        # The user is redirected to his profile page
        self.assert_current_url_equal(self.get_profile_url())

    def test_login_associated_email(self):
        """
        Tests that a user can log in with an associated email.
        """
        ## Set up an account
        user_email = 'user@domain.com'
        associated_emails = ['email@domain.com']
        password = 'asdf'
        self.create_user(user_email, password, associated_emails)

        # The user goes to the log in page
        self.get_page(self.get_login_url())
        # There he can see a log in form
        self.assert_element_with_id_in_page('form-login')

        # He enters the associated email and account password
        self.input_to_element('id_username', associated_emails[0])
        self.input_to_element('id_password', password)
        self.send_enter('id_password')

        # The user is redirected to his profile page
        self.assert_current_url_equal(self.get_profile_url())

    def test_logout_from_package_page(self):
        """
        If a user logs out when on the package page, he should not be
        redirected to the index.
        """
        ## Set up an account
        user_email = 'user@domain.com'
        associated_emails = ['email@domain.com']
        password = 'asdf'
        self.create_user(user_email, password, associated_emails)
        ## Set up an existing package
        package_name = 'dummy'
        SourcePackageName.objects.create(name=package_name)

        # The user logs in
        self.get_page(self.get_login_url())
        self.input_to_element('id_username', associated_emails[0])
        self.input_to_element('id_password', password)
        self.send_enter('id_password')

        # The user goes to the package page
        self.get_page('/' + package_name)
        # From there he can log out...
        self.assert_in_page_body('Log out')
        self.click_link('Log out')
        # The user is still at the package page, but no longer logged in
        self.assert_current_url_equal(self.get_package_url(package_name))
        self.assert_not_in_page_body('Log out')
        self.assert_in_page_body('Log in')
        # The user tries going to his profile page, but he is definitely
        # logged out...
        self.get_page(self.get_profile_url())
        # ...which means he is redirected to the log in page
        self.assert_current_url_equal(
            self.get_login_url() + '?next=' + self.get_profile_url())


class SubscribeToPackageTest(UserAccountsTestMixin, SeleniumTestCase):
    """
    Tests for stories regarding subscribing to a package over the Web.
    """
    def test_subscribe_from_package_page(self):
        """
        Tests that a user that has only one email address can subscribe to a
        package directly from the package page.
        """
        # The user first logs in to the PTS
        self.log_in()
        # The user opens a package page
        self.get_page('/' + self.package.name)

        # There he sees a button allowing him to subscribe to the package
        self.assert_element_with_id_in_page('subscribe-button')
        # So he clicks it.
        button = self.get_element_by_id('subscribe-button')
        button.click()

        # The subscribe button is no longer found in the page
        button = self.get_element_by_id('subscribe-button')
        ## Give the page a chance to refresh
        wait = ui.WebDriverWait(self.browser, 1)
        wait.until(lambda browser: not button.is_displayed())
        self.assertFalse(button.is_displayed())

        # It has been replaced by the unsubscribe button
        self.assert_element_with_id_in_page('unsubscribe-button')
        unsubscribe_button = self.get_element_by_id('unsubscribe-button')
        self.assertTrue(unsubscribe_button.is_displayed())

        ## The user has really been subscribed to the package?
        self.assertTrue(self.user.is_subscribed_to(self.package))

    def test_subscribe_not_logged_in(self):
        """
        Tests that when a user is not logged in, he is redirected to the log in
        page instead of being subscribed to the package.
        """
        # The user opens the package page
        self.get_page('/' + self.package.name)
        # ...and tries subscribing to the package
        self.get_element_by_id('subscribe-not-logged-in-button').click()
        # ...only to find himself redirected to the log in page.
        self.assert_current_url_equal(self.get_login_url())

    def test_subscribe_multiple_associated_emails(self):
        """
        Tests that a user is offered a choice which email to use to subscribe
        to a package when he has multiple associated emails.
        """
        ## Set up such a user
        other_email = 'other-email@domain.com'
        self.user.emails.create(email=other_email)

        # The user logs in to the PTS
        self.log_in()
        # The user opens a package page and clicks to subscribe button
        self.get_page('/' + self.package.name)
        self.get_element_by_id('subscribe-button').click()
        self.wait_response(1)

        # The user is presented with a choice of his emails
        for email in self.user.emails.all():
            self.assert_in_page_body(email.email)
        # The user decides to cancel the subscription by dismissing the popup
        self.get_element_by_id('cancel-choose-email').click()
        self.wait_response(1)

        ## The user is not subscribed to anything yet
        self.assertEqual(0, Subscription.objects.count())
        # The user clicks the subscribe button again
        self.get_element_by_id('subscribe-button').click()
        self.wait_response(1)
        # ...and chooses to subscribe using his associated email
        self.assert_element_with_id_in_page('choose-email-1')
        self.get_element_by_id('choose-email-1').click()
        self.wait_response(1)

        ## The user is now subscribed to the package with only the clicked email
        self.assertEqual(1, Subscription.objects.count())
        sub = Subscription.objects.all()[0]
        self.assertEqual(other_email, sub.email_user.email)

        # The UI that the user sees reflects this
        self.assert_element_with_id_in_page('unsubscribe-button')
        unsubscribe_button = self.get_element_by_id('unsubscribe-button')
        self.assertTrue(unsubscribe_button.is_displayed())

    def test_unsubscribe_all_emails(self):
        """
        Tests unsubscribing all user's emails from a package.
        """
        ## Set up a user with multiple emails subscribed to a package
        other_email = 'other-email@domain.com'
        self.user.emails.create(email=other_email)
        for email in self.user.emails.all():
            Subscription.objects.create_for(
                email=email.email,
                package_name=self.package.name)

        # The user logs in and opens the package page
        self.log_in()
        self.get_page('/' + self.package.name)
        # There he sees a button allowing him to unsubscribe from the package
        self.assert_in_page_body('Unsubscribe')
        self.assert_element_with_id_in_page('unsubscribe-button')
        # The user decides to unsubscribe and clicks the button...
        self.get_element_by_id('unsubscribe-button').click()
        self.wait_response(1)

        ## The user is really unsubscribed from the package
        self.assertFalse(self.user.is_subscribed_to(self.package))

        # The user sees the subscribe button instead of the unsubscribe button
        sub_button = self.get_element_by_id('subscribe-button')
        self.assertTrue(sub_button.is_displayed())
        unsub_button = self.get_element_by_id('unsubscribe-button')
        self.assertFalse(unsub_button.is_displayed())


class ChangeProfileTest(UserAccountsTestMixin, SeleniumTestCase):
    def test_modify_personal_info(self):
        """
        Tests that the user is able to change his personal info upon logging
        in.
        """
        # The user logs in
        self.log_in()
        # He can see a link for a page letting him modify his personal info
        self.assert_in_page_body('Personal Information')
        self.click_link('Personal Information')

        # In the page there is a form allowing him to change his first/last
        # name.
        self.assert_element_with_id_in_page('form-change-profile')

        # The user decides to input a new name
        name = 'Name'
        old_last_name = self.user.last_name
        self.input_to_element('id_first_name', name)
        # ...and submits the form
        self.send_enter('id_first_name')
        # The user is met with a notification that the information has been
        # updated.
        self.assert_in_page_body('Successfully changed your information')
        ## The user's name has really changed
        self.refresh_user_object()
        self.assertEqual(name, self.user.first_name)
        ## But the last name has not
        self.assertEqual(old_last_name, self.user.last_name)

        # The user now wants to update both his first and last name
        self.clear_element_text('id_first_name')
        new_first_name, new_last_name = 'Name', 'Last Name'
        # The user fills in the form
        self.input_to_element('id_first_name', new_first_name)
        self.input_to_element('id_last_name', new_last_name)
        # ...and submits it.
        self.send_enter('id_last_name')

        # He is faced with another notification of success
        self.assert_in_page_body('Successfully changed your information')
        ## The information has actually been updated
        self.refresh_user_object()
        self.assertEqual(new_first_name, self.user.first_name)
        self.assertEqual(new_last_name, self.user.last_name)

        # The user navigates away from the page now
        self.get_page(self.get_profile_url())
        # And then goes back
        self.click_link('Personal Information')
        # There are no notifications about modification in the page nw
        self.assert_not_in_page_body('Successfully changed your information')
        # And the user's first/last name is already filled in the form
        self.assertEqual(
            new_first_name,
            self.get_element_by_id('id_first_name').get_attribute('value'))
        self.assertEqual(
            new_last_name,
            self.get_element_by_id('id_last_name').get_attribute('value'))

    def test_change_password(self):
        """
        Tests that the user can change his password upon logging in.
        """
        # The user logs in
        self.log_in()
        # He can see a link for a page letting him change his password
        self.assert_in_page_body('Change Password')
        self.click_link('Change Password')

        # He can see the form which is used to enter the new password
        self.assert_element_with_id_in_page('form-change-password')
        # The user first enters a wrong current password
        new_password = 'new-password'
        self.input_to_element('id_old_password', 'this-password-is-incorrect')
        self.input_to_element('id_new_password1', new_password)
        self.input_to_element('id_new_password2', new_password)
        self.send_enter('id_new_password2')
        # The user is met with an error saying his current password was
        # incorrect.
        self.assert_in_page_body('Your old password was entered incorrectly')

        # The user enters his current password correctly, but forgets the new
        # password.
        self.input_to_element('id_old_password', self.password)
        self.send_enter('id_old_password')
        # He gets a message informing him that the field is required
        self.assert_in_page_body('This field is required')

        # This time, the user enters both the old password and fills in the new
        # password fields, but they are mismatched
        self.input_to_element('id_old_password', self.password)
        self.input_to_element('id_new_password1', new_password)
        self.input_to_element('id_new_password2', new_password + '-miss-match')
        self.send_enter('id_new_password2')
        # He gets a message informing him that the password change failed once
        # again.
        self.assert_in_page_body("The two password fields didn't match")

        # In the end, the user manages to fill in the form correctly!
        self.input_to_element('id_old_password', self.password)
        self.input_to_element('id_new_password1', new_password)
        self.input_to_element('id_new_password2', new_password)
        self.send_enter('id_new_password2')
        # He gets a message informing him of a successful change
        self.assert_in_page_body('Successfully updated your password')

        # The user logs out in order to try using his new password
        self.click_link('Log out')
        # The user tries logging in using his old account password
        self.log_in()
        # He is met with an error
        self.assert_in_page_body('Please enter a correct email and password')
        # Now he tries with his new password
        self.password = new_password
        self.log_in()
        # The user is finally logged in using his new account details
        self.assert_current_url_equal(self.get_profile_url())

    def test_reset_password(self):
        """
        Tests that a user is able to reset his password if he forgot it.
        """
        # The user goes to the login page
        self.get_page(self.get_login_url())
        # There he sees a convenient link letting him get to a page where he
        # can reset his password.
        self.assert_in_page_body('Forgot your password?')
        self.click_link('Forgot your password?')
        # The user sees a form which lets him reset his password
        self.assert_element_with_id_in_page('form-reset-password')
        # First he enters an invalid email: one not associated with any account
        self.input_to_element('id_email', 'this-does-not-exist@domain.com')
        self.send_enter('id_email')
        # The user still stays in the same page with a warning that no user
        # with the email exists.
        self.assert_in_page_body('No user with the given email is registered')
        # The user now correctly enters his own email
        self.clear_element_text('id_email')
        self.input_to_element('id_email', self.user.main_email)
        self.send_enter('id_email')
        # The user is taken to another page where he is informed that he must
        # check his email for a confirmation email
        self.assert_in_page_body('Please check your email inbox for details')
        ## A confirmation email is actually sent?
        self.assertEqual(1, len(mail.outbox))
        confirmation = ResetPasswordConfirmation.objects.all()[0]
        # The user goes to the confirmation URL!
        self.get_page(reverse('pts-accounts-reset-password', kwargs={
            'confirmation_key': confirmation.confirmation_key,
        }))
        # There, he is asked to enter a new password...
        self.assert_in_page_body('please enter a new password for your account')
        # ...so he does
        new_password = self.password + '-new'
        self.input_to_element('id_password1', new_password)
        self.input_to_element('id_password2', new_password)
        self.send_enter('id_password2')
        # He is redirected back to the profile page with a message that his
        # password has been reset.
        self.assert_current_url_equal(self.get_profile_url())
        self.assert_in_page_body('You have successfully reset your password')

        # The user decides to log out and try logging back in with his new
        # password
        self.click_link('Log out')
        self.password = new_password
        self.log_in()
        # The user has successfully logged in using his new password
        self.assert_current_url_equal(self.get_profile_url())

    def test_manage_account_emails(self):
        """
        Tests that users are able to manage which emails are associated with
        their accounts.
        """
        # The user logs in and goes to the account email management page
        self.log_in()
        self.click_link('Account Emails')
        # There he sees a form letting him add new emails to his account
        self.assert_element_with_id_in_page('form-add-account-email')
        # He decides to add a new email.
        new_email = 'completely-new-email@domain.com'
        self.input_to_element('id_email', new_email)
        self.send_enter('id_email')
        # The user is notified that in order to activate the email association
        # he must confirm the ownership of the email address.
        self.assert_in_page_body('you must follow the confirmation link')
        self.assert_not_in_page_body(new_email)
        ## The confirmation email sent?
        self.assertEqual(1, len(mail.outbox))
        self.assertIn(new_email, mail.outbox[0].to)
        ## Confirmation created?
        self.assertEqual(1, AddEmailConfirmation.objects.count())
        confirmation = AddEmailConfirmation.objects.all()[0]

        # The user now visits he confirmation URL
        self.get_page(reverse('pts-accounts-confirm-add-email', kwargs={
            'confirmation_key': confirmation.confirmation_key,
        }))
        # And is notified that the address has becomes associated with a PTS
        # account.
        self.assert_in_page_body('now associated with a PTS account')

        # The user goes back to his profile page to check if the email can be
        # found there
        self.click_link('Profile')
        self.click_link('Account Emails')
        # The new email is now in the list of all emails
        self.assert_in_page_body(new_email)

        # The user tries adding an email he is already associated with again
        self.input_to_element('id_email', new_email)
        self.send_enter('id_email')
        # He gets a warning telling him his account is already associated with
        # the given email.
        self.assert_in_page_body(
            'This email is already associated with your account')

    def test_merge_accounts(self):
        ## Set up an additional existing user account
        password = 'other-password'
        other_email = 'other@domain.com'
        other_user = self.create_user(other_email, password)
        # A user logs in and goes to the form to add an additional account
        self.log_in()
        self.click_link('Account Emails')
        # He inputs the email of a user that is already registered
        self.input_to_element('id_email', other_email)
        self.send_enter('id_email')
        # The user is taken to a confirmation page
        self.assert_in_page_body('Are you sure you want to merge the accounts')
        # There is a button letting him confirm the merge
        self.assert_element_with_id_in_page('confirm-merge-button')
        self.get_element_by_id('confirm-merge-button').click()
        # The user is notified that the merge is ineffective until confirmed
        self.assert_in_page_body('you must follow a confirmation link')
        # A confirmation mail is sent
        self.assertEqual(1, len(mail.outbox))
        # The mail was not sent to the logged in user, rather the one being
        # merged to the account
        self.assertIn(other_email, mail.outbox[0].to)
        ## A confirmation instance is created?
        self.assertEqual(1, MergeAccountConfirmation.objects.count())
        confirmation = MergeAccountConfirmation.objects.all()[0]

        # The user tries going to the confirmation URL without logging in to
        # the other account
        confirmation_url = reverse('pts-accounts-merge-finalize', kwargs={
            'confirmation_key': confirmation.confirmation_key,
        })
        self.get_page(confirmation_url)
        # ...which is forbidden and has no effect
        self.assertEqual(2, User.objects.count())

        # The user now logs in with the other account
        self.log_in(other_user, password)
        self.get_page(confirmation_url)
        # He accesses the page which asks for a final confirmation
        self.assert_in_page_body(
            'Are you sure you want to finalize the accounts merge')
        self.assert_element_with_id_in_page('finalize-merge-button')
        # The user decides to go on with the merge
        self.get_element_by_id('finalize-merge-button').click()

        # The user is notified that the merge was successful
        self.assert_in_page_body('The two accounts have been successfully merged')
        ## User accounts are really changed?
        self.assertEqual(1, User.objects.count())
        # He tries logging in with the merged account's password
        self.log_in(password=password)
        # ...which fails
        self.assert_in_page_body('Please enter a correct email and password')
        # He logs in with the original account details
        self.log_in()
        # ...which works
        self.assert_current_url_equal(self.get_profile_url())

        # He goes to check that his associated emails contain all the emails
        self.click_link('Account Emails')
        self.assert_in_page_body(self.user.main_email)
        self.assert_in_page_body(other_email)

class TeamTests(SeleniumTestCase):
    def setUp(self):
        super(TeamTests, self).setUp()
        self.password = 'asdf'
        self.user = User.objects.create_user(
            main_email='user@domain.com', password=self.password,
            first_name='', last_name='')

    def get_login_url(self):
        return reverse('pts-accounts-login')

    def get_create_team_url(self):
        return reverse('pts-teams-create')

    def get_team_url(self, team_name):
        team = Team.objects.get(name=team_name)
        return team.get_absolute_url()

    def get_delete_team_url(self, team_name):
        team = Team.objects.get(name=team_name)
        return reverse('pts-team-delete', kwargs={
            'slug': team.slug,
        })

    def get_team_deleted_url(self):
        return reverse('pts-team-deleted')

    def get_update_team_url(self, team_name):
        team = Team.objects.get(name=team_name)
        return reverse('pts-team-update', kwargs={
            'slug': team.slug,
        })

    def get_subscriptions_url(self):
        return reverse('pts-accounts-subscriptions')

    def assert_team_packages_equal(self, team, package_names):
        team_package_names = [p.name for p in team.packages.all()]
        self.assertEqual(len(package_names), len(team_package_names))
        for package_name in package_names:
            self.assertIn(package_name, team_package_names)

    def log_in(self, user=None, password=None):
        """
        Helper method which logs the user in, without taking any shortcuts (it goes
        through the steps to fill in the form and submit it).
        """
        if user is None:
            user = self.user
        if password is None:
            password = self.password

        self.get_page(self.get_login_url())
        self.input_to_element('id_username', user.main_email)
        self.input_to_element('id_password', password)
        self.send_enter('id_password')

    def log_out(self):
        """
        Logs the currently logged in user out.
        """
        self.click_link("Log out")

    def test_create_team(self):
        """
        Tests that a logged in user can create a new team.
        """
        # The user tries going to the page to create a new team
        self.get_page(self.get_create_team_url())
        # However, he is not signed in so he is redirected to the login
        self.assertIn(self.get_login_url(), self.browser.current_url)
        self.wait_response(1)
        # The user then logs in
        self.log_in()
        # ...and tries again
        self.get_page(self.get_create_team_url())
        # This time he is presented with a page that has a form allowing him to
        # create a new team.
        self.assert_element_with_id_in_page('create-team-form')
        # The user forgets to input the team name, initialy.
        self.send_enter('id_name')
        # Since a name is required, an error is returned
        self.assert_in_page_body('This field is required')
        # The user inputs the team name, but not a maintainer email
        team_name = 'New team'
        self.input_to_element('id_name', team_name)
        self.send_enter('id_name')
        self.wait_response(1)
        # The user is now redirected to the team's page
        self.assert_current_url_equal(self.get_team_url(team_name))
        ## The team actually exists
        self.assertEqual(1, Team.objects.filter(name=team_name).count())
        ## The user is its owner
        team = Team.objects.get(name=team_name)
        self.assertEqual(self.user, team.owner)
        # The user goes back to the team creation page now
        self.get_page(self.get_create_team_url())
        # He tries creating a new team with the same name
        self.input_to_element('id_name', team_name)
        self.send_enter('id_name')
        # This time, the team creation process fails because the team name is
        # not unique.
        self.assert_in_page_body('Team with this Name already exists')

    def test_create_team_maintainer_email(self):
        """
        Tests creating a team with a maintainer email set.
        The team should become automatically associated with the maintainer's
        packages.
        """
        ## Set up some packages maintained by the same maintainer
        package_names = [
            'pkg1',
            'pkg2',
        ]
        maintainer_email = 'maintainer@domain.com'
        maintainer = ContributorName.objects.create(
            contributor_email=UserEmail.objects.create(
                email=maintainer_email))
        for package_name in package_names:
            SourcePackage.objects.create(
                source_package_name=SourcePackageName.objects.create(
                    name=package_name),
                version='1.0.0',
                maintainer=maintainer)
        ## Create a package with no maintainer
        SourcePackageName.objects.create(name='dummy-package')
        ## --

        # The user logs in and accesses the create team page.
        self.log_in()
        self.get_page(self.get_create_team_url())

        # He inputs both the team name and the maintaner name.
        team_name = 'Team name'
        self.input_to_element('id_name', team_name)
        self.input_to_element('id_maintainer_email', maintainer_email)
        self.send_enter('id_maintainer_email')
        self.wait_response(1)

        # The team is successfully created and the user can see the
        # maintainer's packages already in the team's page
        for package_name in package_names:
            self.assert_in_page_body(package_name)
        ## The team really is associated with the packages?
        team = Team.objects.all()[0]
        self.assert_team_packages_equal(team, package_names)

        # The user now wants to associate the team with a different maintainer
        # that maintains other packages
        new_package_name = 'pkg3'
        new_maintainer_email = 'new-maintainer@domain.com'
        new_maintainer = ContributorName.objects.create(
            contributor_email=UserEmail.objects.create(
                email=new_maintainer_email))
        SourcePackage.objects.create(
            source_package_name=SourcePackageName.objects.create(
                name=new_package_name),
            version='1.0.0',
            maintainer=new_maintainer)
        self.get_element_by_id('update-team-button').click()
        # The user modifies the maintainer field
        self.clear_element_text('id_maintainer_email')
        self.input_to_element('id_maintainer_email', new_maintainer_email)
        self.send_enter('id_maintainer_email')
        self.wait_response(1)

        # The user is directed back to the team page where he can see all the
        # packages previously associated with the team, as well as the ones
        # associated to the new maintainer.
        self.assert_in_page_body(new_package_name)
        for package_name in package_names:
            self.assert_in_page_body(package_name)

        ## The team is really associated with all these packages?
        self.assert_team_packages_equal(
            team, package_names + [new_package_name])

    def test_delete_team(self):
        """
        Tests that the owner can delete a team.
        """
        ## Set up a team owned by the user
        team_name = 'Team name'
        Team.objects.create_with_slug(owner=self.user, name=team_name)

        # Before logging in the user opens the team page
        self.get_page(self.get_team_url(team_name))
        # He does not see the delete button
        self.assert_not_in_page_body("Delete")
        # He goes directly to the deletion URL
        self.get_page(self.get_delete_team_url(team_name))
        # But permission is denied to the user
        self.assert_not_in_page_body(team_name)

        # He now logs in
        self.log_in()
        self.get_page(self.get_team_url(team_name))
        # The delete button is now offered to the user
        self.assert_element_with_id_in_page('delete-team-button')
        # So the user decides to click it.
        self.get_element_by_id('delete-team-button').click()
        self.wait_response(1)
        # He is now faced with a popup asking him to confirm the team deletion
        cancel_button = self.get_element_by_id('team-delete-cancel-button')
        confirm_button = self.get_element_by_id('confirm-team-delete-button')
        self.assertTrue(confirm_button.is_displayed())
        self.assertTrue(cancel_button.is_displayed())
        # The user decides to cancel the deletion
        cancel_button.click()
        self.wait_response(1)
        # He is still found in the team page and the team has not been deleted
        self.assert_current_url_equal(self.get_team_url(team_name))
        ## The team is still here
        self.assertEqual(1, Team.objects.count())
        # The user now decides he really wants to delete the team
        self.get_element_by_id('delete-team-button').click()
        self.wait_response(1)
        self.get_element_by_id('confirm-team-delete-button').click()
        self.wait_response(1)

        # He is now taken to a page informing him the team has been
        # successfully deleted.
        self.assert_current_url_equal(self.get_team_deleted_url())
        ## The team is also really deleted?
        self.assertEqual(0, Team.objects.count())

    def test_update_team(self):
        """
        Tests that the team owner can update the team's basic info.
        """
        ## Set up a team owned by the user
        team_name = 'Team name'
        Team.objects.create_with_slug(owner=self.user, name=team_name)

        # Before logging in the user opens the team page
        self.get_page(self.get_team_url(team_name))
        # He does not see the update button
        self.assert_not_in_page_body("Update")
        # He goes directly to the update URL
        self.get_page(self.get_update_team_url(team_name))
        # But permission is denied to the user
        self.assert_not_in_page_body(team_name)

        # The user now logs in
        self.log_in()
        self.get_page(self.get_team_url(team_name))
        # He can now see the update button
        self.assert_element_with_id_in_page('update-team-button')
        self.get_element_by_id('update-team-button').click()

        # He is found on the update page now
        self.assert_current_url_equal(self.get_update_team_url(team_name))
        # ...with a form that lets him update the team's info
        self.assert_element_with_id_in_page('update-team-form')
        # The user modifies the team's description
        new_description = "This is a new description"
        self.input_to_element('id_description', new_description)
        self.send_enter('id_name')
        self.wait_response(1)

        # The user is taken back to the team's page
        self.assert_current_url_equal(self.get_team_url(team_name))
        # The updated information is displayed in the page already
        self.assert_in_page_body(new_description)
        ## The team's info is actually updated?
        team = Team.objects.all()[0]
        self.assertEqual(new_description, team.description)

        # The user now wants to update the team's name without affecting the
        # team's URL.
        old_url = self.get_team_url(team_name)
        self.get_element_by_id('update-team-button').click()
        self.clear_element_text('id_name')
        new_name = team_name + ' new name'
        self.input_to_element('id_name', new_name)
        self.send_enter('id_name')
        self.wait_response(1)

        # The user is now found back at the team page which contains the
        # updated name
        self.assert_in_page_body(new_name)
        # However, the package's URL is still the same
        self.assert_current_url_equal(old_url)

        # Now the user wants to modify the team's url without modifying its
        # name.
        self.get_element_by_id('update-team-button').click()
        old_slug = team.slug
        self.clear_element_text('id_slug')
        new_slug = old_slug + '-new-slug'
        self.input_to_element('id_slug', new_slug)
        self.send_enter('id_slug')
        self.wait_response(1)

        # The user is once again back on the team page.
        # The URL has been modified now to contain the new team slug.
        self.assertIn(new_slug, self.browser.current_url)
        ## The slug really is updated?
        self.assertEqual(new_slug, Team.objects.all()[0].slug)

    def test_package_management(self):
        """
        Tests that adding/removing packages from the team works as expected.
        """
        ## Set up a team owned by the user
        team_name = 'Team name'
        team = Team.objects.create_with_slug(owner=self.user, name=team_name)
        ## Set up some packages which the user can add to the team
        package_names = [
            'pkg1',
            'pkg2',
        ]
        for package_name in package_names:
            PackageName.objects.create(name=package_name)
        ## --

        # The user opens the team page without logging in
        self.get_page(self.get_team_url(team_name))
        # He cannot see the form to add a package
        form = self.get_element_by_id('add-team-package-form')
        self.assertIsNone(form)
        # The user logs in and opens the team page
        self.log_in()
        self.get_page(self.get_team_url(team_name))
        # He can see the form to add packages now
        self.assert_element_with_id_in_page('add-team-package-form')
        # He types the name of the package he wants to add
        self.input_to_element('id_package_name', package_names[0])
        # ...and submits the form
        self.send_enter('id_package_name')
        self.wait_response(1)

        # The user is still in the team page
        self.assert_current_url_equal(self.get_team_url(team_name))
        # He can now see the package he added in the list of packages
        self.assert_in_page_body(package_names[0])

        # He tries adding a new package: one that does not exist
        self.input_to_element('id_package_name', 'this-does-not-exist')
        self.send_enter('id_package_name')
        self.wait_response(1)
        # The user is still in the team page, but nothing is changed when it
        # comes to the list of packages.
        self.assert_not_in_page_body('this-does-not-exist')

        # The user now wants to remove the package from the team
        # He can see a button next to the team's name

        remove_button = self.browser.find_element_by_css_selector(
            '.remove-package-from-team-button')
        remove_button.click()
        self.wait_response(1)
        # A popup is displayed asking the user to confirm the removal
        # The user decides to cancel the operation
        self.get_element_by_id('remove-package-cancel-button').click()
        self.wait_response(1)
        # He is still found on the team page and the package is not removed
        self.assert_current_url_equal(self.get_team_url(team_name))
        ## The package is not removed?
        self.assertEqual(1, team.packages.count())

        # The user decides to definitely remove the package now
        remove_button.click()
        self.wait_response(1)
        self.get_element_by_id('confirm-remove-package-button').click()
        self.wait_response(1)

        # The user is still on the team page, but the package is not longer
        # a part of the team.
        self.assert_current_url_equal(self.get_team_url(team_name))
        self.assert_not_in_page_body(package_names[0])
        ## The package is really removed from the team
        self.assertEqual(0, team.packages.count())

    def test_team_access(self):
        """
        Tests joining and leaving a team.
        """
        ## Set up a team and a user who isn't the owner of the team
        team_name = 'Team name'
        team = Team.objects.create_with_slug(owner=self.user, name=team_name)
        user = User.objects.create_user(
            main_email='other@domain.com',
            password=self.password)
        EmailUser.objects.get_or_create(email=user.main_email)
        ## --

        # The user logs in and goes to the team page
        self.log_in(user)
        self.get_page(self.get_team_url(team_name))
        # He can see a button allowing him to join the team.
        self.assert_element_with_id_in_page('join-team-button')
        # ...so he clicks it!
        self.get_element_by_id('join-team-button').click()
        self.wait_response(1)

        # The user is still found in the team page, but now he is a member of
        # the team.
        self.assert_element_with_id_in_page('add-team-package-form')
        ## The user is really a member?
        self.assertTrue(team.user_is_member(user))
        # Which means he can leave the team now.
        self.assert_element_with_id_in_page('leave-team-button')
        # So he does that.
        self.get_element_by_id('leave-team-button').click()
        self.wait_response(1)

        # The user is now again not a member of the team
        self.assert_element_with_id_in_page('join-team-button')
        ## He really isn't a member any more.
        self.assertFalse(team.user_is_member(user))

        # The user now logs out
        self.log_out()
        # And tries clicking the join team button
        self.get_element_by_id('join-team-button').click()
        self.wait_response(1)
        # But he is redirected to the login page
        self.assert_element_with_id_in_page('form-login')

        ## The privacy of the team is switched to private.
        team.public = False
        team.save()

        # When the user opens the page again, the join button is replaced with
        # a link to contact the owner.
        self.get_page(self.get_team_url(team_name))
        self.assert_in_page_body('Contact the owner')

    def test_owner_members_management(self):
        """
        Tests that a team owner is able to add/remove members from a separate
        panel.
        """
        ## --
        team_name = 'Team name'
        team = Team.objects.create_with_slug(owner=self.user, name=team_name)
        ## --

        self.log_in()
        self.get_page(self.get_team_url(team_name))
        # The user opens the member management page
        self.get_element_by_id('manage-team-button').click()

        # The user wants to add a new team member
        new_team_member = 'member@domain.com'
        self.input_to_element('id_email', new_team_member)
        self.send_enter('id_email')
        self.wait_response(1)
        # The user is still in the same page, but can see the new member in the
        # list of all members
        self.assert_in_page_body(new_team_member)
        ## The membership is marked muted, though
        membership = TeamMembership.objects.all()[0]
        self.assertTrue(membership.muted)
        ## And an email was sent to the new member asking him to confirm it
        self.assertEqual(1, len(mail.outbox))
        self.assertIn(new_team_member, mail.outbox[0].to)

        # The user now decides to remove the team member
        button = self.browser.find_element_by_css_selector('.remove-user-button')
        button.click()
        self.wait_response(1)
        # The user is no longer a part of the team
        self.assert_not_in_page_body(new_team_member)

    def test_toggle_team_mute(self):
        """
        Tests that a team member is able to mute and unmute a team membership
        from the subscription details page.
        """
        ## --
        team_name = 'Team name'
        team = Team.objects.create_with_slug(owner=self.user, name=team_name)
        membership = team.add_members([self.user.emails.all()[0]])[0]
        ## --
        # The user logs in and goes to his subscriptions page
        self.log_in()
        self.get_page(self.get_subscriptions_url())
        # He can see a button offering him to mute the team membership
        self.assert_in_page_body('Mute')
        # So he clicks it!
        btn = self.get_element_by_class('toggle-team-mute')
        btn.click()
        self.wait_response(1)
        # The user is still in he same page, but now he has a warning that his
        # team membership is muted
        self.assert_element_with_class_in_page('mute-warning')
        ## The membership is actually muted?
        membership = TeamMembership.objects.get(pk=membership.pk)
        self.assertTrue(membership.muted)

        # The user now wants to revert this.
        # He can see the unmute button
        self.assert_in_page_body('Unmute')
        # He clicks it.
        btn = self.get_element_by_class('toggle-team-mute')
        btn.click()
        self.wait_response(1)
        # Once again, the user is still in the subscriptions page, but the
        # button has reverted back to the mute button
        self.assert_in_page_body('Mute')
        # And the warning is gone
        self.assertIsNone(self.get_element_by_class('mute-warning'))
