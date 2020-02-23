"""Test rendering errors as JSON responses."""

from pyramid.config import Configurator
from pyramid.httpexceptions import HTTPForbidden
from pyramid.view import view_config
from wsgiref.simple_server import make_server
from pyramid.testing import testConfig
from pyramid.httpexceptions import exception_response

import tempfile
import unittest


def app(spec, view):
    """Prepare a Pyramid app."""
    with Configurator() as config:
        config.include("pyramid_openapi3")
        config.pyramid_openapi3_spec(spec)
        config.pyramid_openapi3_JSONify_errors()
        config.add_route("foo", "/foo")
        config.add_view(openapi=True, renderer="json", view=view, route_name="foo")
        return config.make_wsgi_app()


class BadRequestsTests(unittest.TestCase):
    """A suite of tests that make sure bad requests are handled."""

    OPENAPI_YAML = """
        openapi: "3.0.0"
        info:
          version: "1.0.0"
          title: Foo
        paths:
          /foo:
            get:
              parameters:
                {parameters}
              responses:
                200:
                  description: Say hello
                400:
                  description: Bad Request
    """

    def _testapp(self, view, parameters):
        """Start up the app so that tests can send requests to it."""
        from webtest import TestApp

        with tempfile.NamedTemporaryFile() as document:
            document.write(self.OPENAPI_YAML.format(parameters=parameters).encode())
            document.seek(0)

            return TestApp(app(document.name, view))

    def test_missing_path_parameter(self):
        """Render nice ValidationError if path parameter is missing."""

        parameters = """
                - name: bar
                  in: query
                  required: true
                  schema:
                    type: integer
        """

        def foo(*args):
            """Say foobar."""
            return {"foo": "bar"}

        res = self._testapp(view=foo, parameters=parameters).get("/foo", status=400)
        assert res.json == [
            {
                "exception": "MissingRequiredParameter",
                "message": "Missing required parameter: bar",
                "field": "bar",
            }
        ]

    def test_missing_header_parameter(self):
        """Render nice ValidationError if header parameter is missing."""

        parameters = """
                - name: bar
                  in: header
                  required: true
                  schema:
                    type: integer
        """

        def foo(*args):
            """Say foobar."""
            return {"foo": "bar"}

        res = self._testapp(view=foo, parameters=parameters).get("/foo", status=400)
        assert res.json == [
            {
                "exception": "MissingRequiredParameter",
                "message": "Missing required parameter: bar",
                "field": "bar",
            }
        ]

    def test_missing_cookie_parameter(self):
        """Render nice ValidationError if cookie parameter is missing."""

        parameters = """
                - name: bar
                  in: cookie
                  required: true
                  schema:
                    type: integer
        """

        def foo(*args):
            """Say foobar."""
            return {"foo": "bar"}

        res = self._testapp(view=foo, parameters=parameters).get("/foo", status=400)
        assert res.json == [
            {
                "exception": "MissingRequiredParameter",
                "message": "Missing required parameter: bar",
                "field": "bar",
            }
        ]


class BadResponsesTests(unittest.TestCase):
    """A suite of tests that make sure bad responses are prevented."""

    OPENAPI_YAML = b"""
        openapi: "3.0.0"
        info:
          version: "1.0.0"
          title: Foo
        paths:
          /foo:
            get:
              responses:
                200:
                  description: Say foo
                400:
                  description: Bad Request
                  content:
                    application/json:
                      schema:
                        type: string
    """

    def _testapp(self, view):
        """Start up the app so that tests can send requests to it."""
        from webtest import TestApp

        with tempfile.NamedTemporaryFile() as document:
            document.write(self.OPENAPI_YAML)
            document.seek(0)

            return TestApp(app(document.name, view))

    def test_foo(self):
        """Say foo."""

        def foo(*args):
            """Say foobar."""
            return {"foo": "bar"}

        res = self._testapp(view=foo).get("/foo", status=200)
        self.assertIn('{"foo": "bar"}', res.text)

    def test_invalid_response_code(self):
        """Prevent responding with undefined response code."""
        from pyramid.httpexceptions import HTTPConflict

        def foo(*args):
            raise exception_response(409, json_body={})

        res = self._testapp(view=foo).get("/foo", status=500)
        assert res.json == [
            {
                "exception": "InvalidResponse",
                "message": "Unknown response http status: 409",
            }
        ]

    def test_invalid_response_schema(self):
        """Prevent responding with unmatching response schema."""
        from pyramid.httpexceptions import exception_response

        def foo(*args):
            raise exception_response(400, json_body={"foo": "bar"})

        res = self._testapp(view=foo).get("/foo", status=500)
        assert res.json == [
            {
                "exception": "ValidationError",
                "message": "{'foo': 'bar'} is not of type string",
                "field": "type",
            }
        ]
