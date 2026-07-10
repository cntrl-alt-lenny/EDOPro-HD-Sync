import os
import tempfile
import unittest
from unittest import mock

import main


class HttpSessionTests(unittest.TestCase):
    def test_ca_bundle_prefers_existing_edopro_bundle(self):
        with tempfile.NamedTemporaryFile() as bundle, mock.patch.dict(
            os.environ, {"EDOPRO_CA_BUNDLE": bundle.name}, clear=True
        ):
            self.assertEqual(main._custom_ca_bundle_path(), os.path.abspath(bundle.name))

    def test_ca_bundle_falls_back_to_certifi_for_missing_paths(self):
        with mock.patch.dict(
            os.environ,
            {
                "EDOPRO_CA_BUNDLE": "/does/not/exist",
                "SSL_CERT_FILE": "/also/not/exist",
                "REQUESTS_CA_BUNDLE": "/still/not/exist",
            },
            clear=True,
        ):
            self.assertIsNone(main._custom_ca_bundle_path())

    def test_http_session_uses_selected_ca_and_connection_limits(self):
        ssl_context = mock.Mock()
        connector = mock.Mock()
        session = mock.Mock()
        certifi_bundle = "/certifi.pem"
        with tempfile.NamedTemporaryFile() as bundle, mock.patch.dict(
            os.environ, {"EDOPRO_CA_BUNDLE": bundle.name}, clear=True
        ), mock.patch.object(
            main.ssl, "create_default_context", return_value=ssl_context
        ) as create_context, mock.patch.object(
            main.certifi, "where", return_value=certifi_bundle
        ), mock.patch.object(
            main.aiohttp, "TCPConnector", return_value=connector
        ) as connector_mock, mock.patch.object(
            main.aiohttp, "ClientSession", return_value=session
        ) as session_mock:
            result = main._create_http_session(limit=50, limit_per_host=25)

        self.assertIs(result, session)
        create_context.assert_called_once_with(cafile=certifi_bundle)
        ssl_context.load_verify_locations.assert_called_once_with(
            cafile=os.path.abspath(bundle.name)
        )
        connector_mock.assert_called_once_with(
            ssl=ssl_context, limit=50, limit_per_host=25
        )
        session_mock.assert_called_once_with(connector=connector, trust_env=True)

    def test_http_session_uses_default_connector_limits_when_unspecified(self):
        connector = mock.Mock()
        with (
            mock.patch.object(main.aiohttp, "TCPConnector", return_value=connector) as connector_mock,
            mock.patch.object(main.aiohttp, "ClientSession", return_value=mock.Mock()),
            mock.patch.object(main.ssl, "create_default_context", return_value=mock.Mock()),
        ):
            main._create_http_session()

        connector_mock.assert_called_once_with(ssl=mock.ANY)


if __name__ == "__main__":
    unittest.main()
