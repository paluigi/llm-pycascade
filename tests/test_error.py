"""Tests for the error module."""

from llm_pycascade.error import CascadeError, ProviderError


class TestProviderError:
    """Tests for ProviderError variant constructors and properties."""

    def test_http_variant_basic(self):
        err = ProviderError.http(500, "Internal Server Error")
        assert err.variant == "http"
        assert err.http_status == 500
        assert err.retry_after_seconds is None
        assert "500" in str(err)
        assert "Internal Server Error" in str(err)

    def test_http_variant_with_retry_after(self):
        err = ProviderError.http(429, "Rate limited", retry_after=60)
        assert err.variant == "http"
        assert err.http_status == 429
        assert err.retry_after_seconds == 60
        assert "60" in str(err)

    def test_request_variant(self):
        err = ProviderError.request("Connection refused")
        assert err.variant == "request"
        assert err.http_status is None
        assert err.retry_after_seconds is None
        assert "Connection refused" in str(err)

    def test_parse_variant(self):
        err = ProviderError.parse("Malformed JSON")
        assert err.variant == "parse"
        assert "Malformed JSON" in str(err)

    def test_missing_api_key_variant(self):
        err = ProviderError.missing_api_key("openai", "OPENAI_API_KEY")
        assert err.variant == "missing_api_key"
        assert "openai" in str(err)
        assert "OPENAI_API_KEY" in str(err)

    def test_missing_api_key_no_env_var(self):
        err = ProviderError.missing_api_key("custom")
        assert err.variant == "missing_api_key"
        assert "custom" in str(err)

    def test_other_variant(self):
        err = ProviderError.other("Something weird")
        assert err.variant == "other"
        assert "Something weird" in str(err)

    def test_is_exception(self):
        err = ProviderError.http(500, "fail")
        assert isinstance(err, Exception)

    def test_raisable(self):
        try:
            raise ProviderError.http(429, "rate limited")
        except ProviderError as exc:
            assert exc.http_status == 429

    def test_repr(self):
        err = ProviderError.http(500, "fail")
        r = repr(err)
        assert "ProviderError" in r
        assert "http" in r


class TestCascadeError:
    """Tests for CascadeError."""

    def test_basic(self):
        err = CascadeError("primary", "all providers failed")
        assert err.cascade_name == "primary"
        assert err.failed_prompt_path is None
        assert "primary" in str(err)
        assert "all providers failed" in str(err)

    def test_with_path(self, tmp_path):
        path = tmp_path / "failed.json"
        err = CascadeError("fast", "timeout", failed_prompt_path=path)
        assert err.cascade_name == "fast"
        assert err.failed_prompt_path == path
        assert str(path) in str(err)

    def test_is_exception(self):
        err = CascadeError("primary", "fail")
        assert isinstance(err, Exception)

    def test_raisable(self):
        try:
            raise CascadeError("primary", "fail")
        except CascadeError as exc:
            assert exc.cascade_name == "primary"
