import pytest

from app.core.config import Settings


@pytest.mark.parametrize("provider,old_url,expected", [
    ("nominatim", "https://photon.komoot.io", "https://nominatim.openstreetmap.org"),
    ("photon", "https://nominatim.openstreetmap.org/", "https://photon.komoot.io"),
])
def test_aligns_stale_public_geocoder_url(provider, old_url, expected, caplog):
    settings = Settings(_env_file=None, routes_geocoder_provider=provider,
                        routes_geocoder_url=old_url)
    assert settings.routes_geocoder_provider == provider
    assert settings.routes_geocoder_url == expected
    assert "incompatible" in caplog.text


@pytest.mark.parametrize("url", [
    "https://maps.example.com/geocoder", "", "https://nominatim.openstreetmap.org/",
])
def test_preserves_custom_empty_and_matching_geocoder_urls(url):
    settings = Settings(_env_file=None, routes_geocoder_provider="nominatim",
                        routes_geocoder_url=url)
    assert settings.routes_geocoder_url == url
