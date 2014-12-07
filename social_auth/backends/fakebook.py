"""
Fakebook OAuth support.

This contribution adds support for Fakebook OAuth service. The settings
FAKEBOOK_APP_ID and FAKEBOOK_API_SECRET must be defined with the values
given by Fakebook application registration process.

Extended permissions are supported by defining FAKEBOOK_EXTENDED_PERMISSIONS
setting, it must be a list of values to request.

By default account id and token expiration time are stored in extra_data
field, check OAuthBackend class for details on how to extend it.
"""
import cgi
import base64
import hmac
import hashlib
import time
from urllib import urlencode
from urllib2 import HTTPError

import json
from django.contrib.auth import authenticate
from django.http import HttpResponse
from django.template import TemplateDoesNotExist, RequestContext, loader

from social_auth.backends import BaseOAuth2, OAuthBackend
from social_auth.utils import sanitize_log_data, backend_setting, setting,\
    log, dsa_urlopen
from social_auth.exceptions import AuthException, AuthCanceled, AuthFailed,\
    AuthTokenError, AuthUnknownError


# Fakebook configuration
FAKEBOOK_ME = 'https://graph.fakebook.com/me?'
ACCESS_TOKEN = 'https://graph.fakebook.com/oauth/access_token?'
USE_APP_AUTH = setting('FAKEBOOK_APP_AUTH', False)
LOCAL_HTML = setting('FAKEBOOK_LOCAL_HTML', 'fakebook.html')
APP_NAMESPACE = setting('FAKEBOOK_APP_NAMESPACE', None)
REDIRECT_HTML = """
<script type="text/javascript">
    var domain = 'https://apps.fakebook.com/',
        redirectURI = domain + '{{ FAKEBOOK_APP_NAMESPACE }}' + '/';
    window.top.location = 'https://www.fakebook.com/dialog/oauth/' +
    '?client_id={{ FAKEBOOK_APP_ID }}' +
    '&redirect_uri=' + encodeURIComponent(redirectURI) +
    '&scope={{ FAKEBOOK_EXTENDED_PERMISSIONS }}';
</script>
"""


class FakebookBackend(OAuthBackend):
    """Fakebook OAuth2 authentication backend"""
    name = 'fakebook'
    # Default extra data to store
    EXTRA_DATA = [
        ('id', 'id'),
        ('expires', 'expires')
    ]

    def get_user_details(self, response):
        """Return user details from Fakebook account"""
        return {'username': response.get('username', response.get('name')),
                'email': response.get('email', ''),
                'fullname': response.get('name', ''),
                'first_name': response.get('first_name', ''),
                'last_name': response.get('last_name', '')}


class FakebookAuth(object):
    AUTH_BACKEND = FakebookBackend

    def __init__(self, request, redirect_url):
        self.redirect_url = request.build_absolute_uri(redirect_url)

    def uses_redirect(self):
        return True

    def auth_url(self):
        return 'http://127.0.0.1:9000/auth/?redirect=%s'%(self.redirect_url)

    def auth_complete(self, *args, **kwargs):
        request = kwargs['request']
        data = request.GET if request.method == 'get' else request.POST
        if data.get('canceled'):
            raise AuthCanceled(self)
        if data.get('error'):
            raise AuthException(self)
        kwargs = kwargs.copy()
        kwargs.update({
            self.AUTH_BACKEND.name: True,
            'response': dict([
                (k, data[k]) for k in ('id', 'first_name', 'last_name', 'username', 'email',)
            ] + [
            ('access_token', 'dummyToken',),
            ]),
        })

        return authenticate(*args, **kwargs)

    @classmethod
    def enabled(cls):
        return True

def base64_url_decode(data):
    data = data.encode(u'ascii')
    data += '=' * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode(data)


def base64_url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip('=')


def load_signed_request(signed_request, api_secret=None):
    try:
        sig, payload = signed_request.split(u'.', 1)
        sig = base64_url_decode(sig)
        data = json.loads(base64_url_decode(payload))

        expected_sig = hmac.new(api_secret or setting('FAKEBOOK_API_SECRET'),
            msg=payload,
            digestmod=hashlib.sha256).digest()

        # allow the signed_request to function for upto 1 day
        if sig == expected_sig and \
           data[u'issued_at'] > (time.time() - 86400):
            return data
    except ValueError:
        pass  # ignore if can't split on dot


class FakebookAppAuth(FakebookAuth):
    """Fakebook Application Authentication support"""
    uses_redirect = False

    def auth_complete(self, *args, **kwargs):
        if not self.application_auth() and 'error' not in self.data:
            return HttpResponse(self.auth_html())

        access_token = None
        expires = None

        if 'signed_request' in self.data:
            response = load_signed_request(
                self.data.get('signed_request'),
                backend_setting(self, self.SETTINGS_SECRET_NAME)
            )

            if response is not None:
                access_token = response.get('access_token') or\
                               response.get('oauth_token') or\
                               self.data.get('access_token')

                if 'expires' in response:
                    expires = response['expires']

        if access_token:
            return self.do_auth(access_token, expires=expires, *args, **kwargs)
        else:
            if self.data.get('error') == 'access_denied':
                raise AuthCanceled(self)
            else:
                raise AuthException(self)

    def application_auth(self):
        required_params = ('user_id', 'oauth_token')
        data = load_signed_request(
            self.data.get('signed_request'),
            backend_setting(self, self.SETTINGS_SECRET_NAME)
        )
        for param in required_params:
            if not param in data:
                return False
        return True

    def auth_html(self):
        app_id = backend_setting(self, self.SETTINGS_KEY_NAME)
        ctx = {
            'FAKEBOOK_APP_ID': app_id,
            'FAKEBOOK_EXTENDED_PERMISSIONS': ','.join(
                backend_setting(self, self.SCOPE_VAR_NAME)
            ),
            'FAKEBOOK_COMPLETE_URI': self.redirect_uri,
            'FAKEBOOK_APP_NAMESPACE': APP_NAMESPACE or app_id
        }

        try:
            fb_template = loader.get_template(LOCAL_HTML)
        except TemplateDoesNotExist:
            fb_template = loader.get_template_from_string(REDIRECT_HTML)
        context = RequestContext(self.request, ctx)

        return fb_template.render(context)


# Backend definition
BACKENDS = {
    'fakebook': FakebookAppAuth if USE_APP_AUTH else FakebookAuth,
}
