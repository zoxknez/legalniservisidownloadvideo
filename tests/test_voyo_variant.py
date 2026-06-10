import pytest
from backend.core.services.voyo.auth import VoyoAuth, VoyoConfig
from backend.services.voyo_adapter import VoyoAdapter

def test_voyo_config_variant():
    # Test setting and getting variant in VoyoConfig
    import tempfile
    from pathlib import Path
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = Path(tmpdir) / "config.json"
        vcfg = VoyoConfig(config_path=str(cfg_path))
        
        # Default variant should be 'rs'
        assert vcfg.get_variant() == "rs"
        
        # Set variant to 'hr'
        vcfg.set_credentials("test@example.com", "password", variant="hr")
        assert vcfg.get_variant() == "hr"
        
        # Load in another instance
        vcfg2 = VoyoConfig(config_path=str(cfg_path))
        assert vcfg2.get_variant() == "hr"

def test_voyo_auth_variant_endpoints():
    # Test default RS variant endpoints
    auth_rs = VoyoAuth()
    auth_rs.set_variant("rs")
    assert auth_rs.variant == "rs"
    assert auth_rs.site_id == 30005
    assert "rtlrs-api.com" in auth_rs.gql_url
    assert "rtlrs-api.com" in auth_rs.gqlc_url
    assert auth_rs.origin == "https://voyo.rs"

    # Test HR variant endpoints
    auth_hr = VoyoAuth()
    auth_hr.set_variant("hr")
    assert auth_hr.variant == "hr"
    assert auth_hr.site_id == 30057
    assert "rtl.hr" in auth_hr.gql_url
    assert "rtl.hr" in auth_hr.gqlc_url
    assert auth_hr.origin == "https://voyo.hr"

def test_voyo_auth_headers_updated():
    auth = VoyoAuth()
    auth.set_variant("hr")
    headers = auth.session.headers
    assert headers["Origin"] == "https://voyo.hr"
    assert headers["Referer"] == "https://voyo.hr/"
    assert headers["onl-location"] == "https://voyo.hr/"

def test_detect_voyo_variant_from_token():
    from backend.session_import import _detect_voyo_variant_from_token
    import base64
    import json
    
    # Helper to build a mock JWT
    def make_jwt(payload):
        header = base64.urlsafe_b64encode(b'{"alg":"HS256"}').decode().rstrip('=')
        payload_bytes = json.dumps(payload).encode()
        payload_encoded = base64.urlsafe_b64encode(payload_bytes).decode().rstrip('=')
        return f"{header}.{payload_encoded}.signature"

    # Test with siteId 30057 (HR)
    jwt_hr = make_jwt({"siteId": 30057})
    assert _detect_voyo_variant_from_token(jwt_hr) == "hr"

    # Test with siteId 30005 (RS)
    jwt_rs = make_jwt({"siteId": 30005})
    assert _detect_voyo_variant_from_token(jwt_rs) == "rs"

    # Test with iss containing voyo.hr
    jwt_iss_hr = make_jwt({"iss": "https://voyo.hr"})
    assert _detect_voyo_variant_from_token(jwt_iss_hr) == "hr"

    # Test default/unknown is rs
    assert _detect_voyo_variant_from_token("invalid-token") == "rs"
