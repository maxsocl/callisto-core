from unittest import skip

from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.sites.models import Site
from django.http import HttpRequest
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from callisto_core.accounts.forms import ReportingVerificationEmailForm
from callisto_core.accounts.models import Account
from callisto_core.accounts.tokens import StudentVerificationTokenGenerator
from callisto_core.accounts.views import CustomSignupView
from callisto_core.tests.test_base import (
    ReportFlowHelper as ReportFlowTestCase,
)
from callisto_core.utils.api import NotificationApi
from callisto_core.utils.sites import TempSiteID
from callisto_core.wizard_builder.models import Page, SingleLineText

from ..tokens import StudentVerificationTokenGenerator
from ..views import CustomSignupView

User = get_user_model()


class AcccountsTestCase(ReportFlowTestCase):

    def _setup_user(self, *args, **kwargs):
        pass


class SignupViewIntegratedTest(AcccountsTestCase):
    signup_url = reverse('signup')

    def test_signup_page_renders_signup_template(self):
        response = self.client.get(self.signup_url)
        self.assertTemplateUsed(response, 'callisto_core/accounts/signup.html')

    def test_displays_signup_form(self):
        response = self.client.get(self.signup_url)
        self.assertIsInstance(response.context['form'], UserCreationForm)
        self.assertContains(response, 'name="password2"')

    def test_displays_signup_form_without_errors_initially(self):
        response = self.client.get(self.signup_url)
        form = response.context['form']
        self.assertEqual(form.errors, {})

    def test_password_fields_must_match(self):
        response = self.client.post(
            self.signup_url,
            {
                'username': 'test',
                'password1': 'p@ssw0rd',
                'password2': 'p@ssw0rd3',
            },
        )
        self.assertFalse(response.context['form'].is_valid())

    def test_user_gets_logged_in_after_signup(self):
        response = self.client.post(
            self.signup_url,
            {
                'username': 'test',
                'password1': 'p@ssw0rd',
                'password2': 'p@ssw0rd',
                'terms': 'true',
            },
        )
        self.assertEqual(
            response.client.session[SESSION_KEY],
            str(User.objects.get(username="test").pk),
        )

    def test_redirects_to_next(self):
        page1 = Page.objects.create()
        page1.sites.add(self.site.id)
        SingleLineText.objects.create(text="a question", page=page1)
        response = self.client.post(
            self.signup_url + '?next=' + reverse('report_new'),
            {
                'username': 'test',
                'password1': 'p@ssw0rd',
                'password2': 'p@ssw0rd',
                'terms': 'true',
            },
        )
        self.assertRedirects(response, reverse('report_new'))

    def test_accepts_optional_email(self):
        self.client.post(
            self.signup_url,
            {
                'username': 'test',
                'email': 'test@email.co.uk',
                'password1': 'p@ssw0rd',
                'password2': 'p@ssw0rd',
                'terms': 'true',
            },
        )
        self.assertEqual(
            User.objects.get(username='test').email,
            'test@email.co.uk',
        )

    def test_newly_created_user_has_valid_account(self):
        self.client.post(
            self.signup_url, {
                'username': 'test',
                'password1': 'p@ssw0rd',
                'password2': 'p@ssw0rd',
                'terms': 'true',
            },
        )
        user = User.objects.get(username='test')
        self.assertIsNotNone(user.account)
        self.assertFalse(user.account.is_verified)
        self.assertFalse(user.account.invalid)

    def test_sets_site_id(self):
        Site.objects.create()
        tem_site_id = 2
        with TempSiteID(tem_site_id):
            response = self.client.post(
                self.signup_url,
                {
                    'username': 'test',
                    'email': 'test@email.in',
                    'password1': 'p@ssw0rd',
                    'password2': 'p@ssw0rd',
                    'terms': 'true',
                },
            )
            self.assertIn(response.status_code, self.valid_statuses)
            self.assertEqual(
                User.objects.get(username='test').account.site_id,
                tem_site_id,
            )

    @override_settings(SITE_ID=2)
    def test_disable_signup_redirects_from_signup(self):
        Site.objects.create()
        response = self.client.get(self.signup_url)
        self.assertRedirects(response, reverse('login'))


class SignupViewUnitTest(AcccountsTestCase):

    def setUp(self):
        super().setUp()
        self.request = HttpRequest()
        self.request.session = self.client.session
        self.request.META['HTTP_HOST'] = 'testserver'
        self.request.POST = {
            'username': 'test',
            'password1': 'p@ssw0rd',
            'password2': 'p@ssw0rd',
            'terms': 'true',
        }
        self.request.site = Site.objects.first()
        self.request.method = 'POST'

    def test_redirects_to_dashboard(self):
        response = CustomSignupView.as_view()(self.request)
        self.assertEqual(response.get('location'), reverse('dashboard'))

    def test_redirects_to_next(self):
        self.request.GET['next'] = reverse('report_new')

        response = CustomSignupView.as_view()(self.request)
        self.assertEqual(response.get('location'), reverse('report_new'))


class LoginViewTest(AcccountsTestCase):
    login_url = reverse('login')

    def test_login_page_renders_login_template(self):
        response = self.client.get(self.login_url)
        self.assertTemplateUsed(response, 'callisto_core/accounts/login.html')

    def test_displays_login_form(self):
        response = self.client.get(self.login_url)
        self.assertIsInstance(response.context['form'], AuthenticationForm)

    def test_user_doesnt_get_logged_in_if_authenticate_fails(self):
        response = self.client.post(
            self.login_url,
            {
                'username': 'thisuserdoesntexist',
                'password': 'password',
            },
        )
        self.assertNotIn(SESSION_KEY, response.client.session)
        self.assertFalse(response.context['form'].is_valid())

    def test_user_gets_logged_in_if_authenticate_succeeds(self):
        with TempSiteID(1):
            user = User.objects.create_user(
                username='test_login', password='password')
            Account.objects.create(user=user)
            response = self.client.post(
                self.login_url,
                {
                    'username': 'test_login',
                    'password': 'password',
                },
            )
            self.assertEqual(
                response.client.session[SESSION_KEY],
                str(User.objects.get(username="test_login").pk),
            )

    @skip('needs tenants')
    def test_user_on_non_default_site_can_login(self):
        with tenant_context(Tenant.objects.get(site_id=2)):
            user = User.objects.create_user(
                username='test_login_site_2',
                password='password')
            Account.objects.create(
                user=user,
                site_id=2)
        with TempSiteID(2):
            response = self.client.post(
                self.login_url,
                {
                    'username': 'test_login_site_2',
                    'password': 'password',
                },
            )
            self.assertEqual(
                response.client.session[SESSION_KEY],
                str(User.objects.get(username="test_login_site_2").pk),
            )

    @skip('needs tenants')
    def test_user_cannot_login_to_another_site(self):
        User.objects.create_user(
            username='test_login_site_2',
            password='password',
            site_id=2)
        with TempSiteID(1):
            response = self.client.post(
                self.login_url,
                {
                    'username': 'test_login_site_2',
                    'password': 'password',
                },
            )
            self.assertNotIn(SESSION_KEY, response.client.session)
            self.assertFalse(response.context['form'].is_valid())

    @override_settings(SITE_ID=2)
    def test_disable_signups_has_special_instructions(self):
        Site.objects.create()
        response = self.client.get(self.login_url)
        self.assertIsInstance(response.context['form'], AuthenticationForm)
        self.assertContains(response, 'You should have gotten an email')


class StudentVerificationTest(AcccountsTestCase):

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username='username',
            password='password')
        Account.objects.create(
            user=self.user,
            school_email='tech@projectcallisto.org',
        )
        self.client.login(
            username='username',
            password='password',
        )
        with TempSiteID(1):
            self.client_post_report_creation()
        self.verify_url = reverse(
            'reporting_email_confirmation',
            kwargs={'uuid': self.report.uuid},
        )

    def test_verification_get(self):
        response = self.client.get(self.verify_url)
        self.assertIsInstance(
            response.context['form'],
            ReportingVerificationEmailForm,
        )

    @skip('skip pending NotificationApi update')
    @override_settings(SITE_ID=1)
    def test_verification_post(self):
        response = self.client.post(
            self.verify_url,
            data={'email': 'test@projectcallisto.org'},
            follow=True,
        )
        self.assertTemplateUsed(
            response, 'callisto_site/school_email_sent.html')

        self.assertEqual(len(self.cassette), 1)
        self.assertEqual(
            self.cassette.requests[0].uri,
            NotificationApi.mailgun_post_route,
        )

    def test_verification_get_confirmation(self):
        self.user.account.refresh_from_db()
        self.assertFalse(self.user.account.is_verified)
        uidb64 = urlsafe_base64_encode(
            force_bytes(self.user.pk)).decode("utf-8")
        token = StudentVerificationTokenGenerator().make_token(self.user)
        self.client.get(reverse(
            'reporting_email_confirmation',
            kwargs={
                'uidb64': uidb64,
                'token': token,
                'uuid': self.report.uuid,
            },
        ))
        self.user.account.refresh_from_db()
        self.assertTrue(self.user.account.is_verified)
