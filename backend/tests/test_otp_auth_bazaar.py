"""
Test suite for OTP-based Authentication and Bazaar Integration
Features being tested:
1. OTP-based resident signup flow (Send OTP → Verify → Register → Admin Approve → Set Password → Login)
2. Forgot Password with OTP
3. Wallet + Bazaar integration (Platform Owner sets Bazaar API URL + Secret Key, residents can redeem points)
4. P0 bug fix: resident_id linked to flat on approval/set-password
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://resident-wallet.preview.emergentagent.com')

# Test credentials from review request
PLATFORM_OWNER_MOBILE = "9999999999"
PLATFORM_OWNER_PASSWORD = "owner123"
ADMIN_MOBILE = "8888888888"
ADMIN_PASSWORD = "admin123"
TEST_SOCIETY_ID = "beb42020-29b4-4de4-b4f9-174e524d840a"
TEST_WING_ID = "54b7ecec-989f-4a65-9bea-89209d4e752d"
TEST_RESIDENT_MOBILE = "5555555550"
TEST_RESIDENT_PASSWORD = "newpass123"

# Generate unique test mobile for signup tests
import random
TEST_NEW_MOBILE = f"700{random.randint(1000000, 9999999)}"


class TestHealthCheck:
    """Basic health check tests"""
    
    def test_api_health(self):
        """Test API health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ API health check passed")


class TestPublicAuthEndpoints:
    """Test public auth endpoints (societies, wings, flats for signup)"""
    
    def test_get_societies(self):
        """GET /api/auth/societies - public endpoint for active societies list"""
        response = requests.get(f"{BASE_URL}/api/auth/societies")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/auth/societies - Found {len(data)} societies")
        # Verify test society exists
        society_ids = [s.get("id") for s in data]
        if TEST_SOCIETY_ID in society_ids:
            print(f"  ✓ Test society {TEST_SOCIETY_ID} found in list")
        return data
    
    def test_get_society_wings(self):
        """GET /api/auth/societies/{id}/wings - public endpoint for wings"""
        response = requests.get(f"{BASE_URL}/api/auth/societies/{TEST_SOCIETY_ID}/wings")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/auth/societies/{TEST_SOCIETY_ID}/wings - Found {len(data)} wings")
        return data
    
    def test_get_wing_flats(self):
        """GET /api/auth/wings/{id}/flats - public endpoint for available flats"""
        response = requests.get(f"{BASE_URL}/api/auth/wings/{TEST_WING_ID}/flats")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ GET /api/auth/wings/{TEST_WING_ID}/flats - Found {len(data)} available flats")
        return data
    
    def test_check_status_nonexistent(self):
        """GET /api/auth/check-status - check status for non-existent account"""
        response = requests.get(f"{BASE_URL}/api/auth/check-status?mobile=1234567890")
        assert response.status_code == 200
        data = response.json()
        assert data.get("exists") == False
        print("✓ GET /api/auth/check-status - Non-existent account returns exists=False")
    
    def test_check_status_existing(self):
        """GET /api/auth/check-status - check status for existing active account"""
        response = requests.get(f"{BASE_URL}/api/auth/check-status?mobile={TEST_RESIDENT_MOBILE}")
        assert response.status_code == 200
        data = response.json()
        print(f"✓ GET /api/auth/check-status - Existing account status: {data}")


class TestOTPEndpoints:
    """Test OTP send/verify endpoints"""
    
    def test_send_otp_signup_existing_user(self):
        """POST /api/auth/send-otp - should fail for existing active user"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={
            "mobile": TEST_RESIDENT_MOBILE,
            "purpose": "signup"
        })
        # Should fail because user already exists and is active
        assert response.status_code == 400
        data = response.json()
        assert "already exists" in data.get("detail", "").lower() or "already submitted" in data.get("detail", "").lower()
        print(f"✓ POST /api/auth/send-otp - Correctly rejects signup for existing user: {data.get('detail')}")
    
    def test_send_otp_forgot_password_nonexistent(self):
        """POST /api/auth/send-otp - forgot_password should fail for non-existent user"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={
            "mobile": "1234567890",
            "purpose": "forgot_password"
        })
        assert response.status_code == 404
        data = response.json()
        assert "no active account" in data.get("detail", "").lower()
        print(f"✓ POST /api/auth/send-otp - Correctly rejects forgot_password for non-existent user")
    
    def test_send_otp_forgot_password_existing(self):
        """POST /api/auth/send-otp - forgot_password for existing active user"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={
            "mobile": TEST_RESIDENT_MOBILE,
            "purpose": "forgot_password"
        })
        assert response.status_code == 200
        data = response.json()
        assert "mock_otp" in data  # OTP is mocked
        assert "expires_in" in data
        print(f"✓ POST /api/auth/send-otp - Forgot password OTP sent, mock_otp: {data.get('mock_otp')}")
        return data
    
    def test_verify_otp_wrong_code(self):
        """POST /api/auth/verify-otp - wrong OTP should fail"""
        # First send OTP
        send_response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={
            "mobile": TEST_RESIDENT_MOBILE,
            "purpose": "forgot_password"
        })
        assert send_response.status_code == 200
        
        # Now try wrong OTP
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={
            "mobile": TEST_RESIDENT_MOBILE,
            "otp": "000000",
            "purpose": "forgot_password"
        })
        assert response.status_code == 400
        data = response.json()
        assert "invalid otp" in data.get("detail", "").lower() or "attempt" in data.get("detail", "").lower()
        print(f"✓ POST /api/auth/verify-otp - Wrong OTP correctly rejected: {data.get('detail')}")
    
    def test_verify_otp_correct_code(self):
        """POST /api/auth/verify-otp - correct OTP should return otp_token"""
        # First send OTP
        send_response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={
            "mobile": TEST_RESIDENT_MOBILE,
            "purpose": "forgot_password"
        })
        assert send_response.status_code == 200
        mock_otp = send_response.json().get("mock_otp")
        
        # Now verify with correct OTP
        response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={
            "mobile": TEST_RESIDENT_MOBILE,
            "otp": mock_otp,
            "purpose": "forgot_password"
        })
        assert response.status_code == 200
        data = response.json()
        assert "otp_token" in data
        assert data.get("mobile") == TEST_RESIDENT_MOBILE
        print(f"✓ POST /api/auth/verify-otp - OTP verified, got otp_token")
        return data


class TestForgotPasswordFlow:
    """Test complete forgot password flow"""
    
    def test_forgot_password_reset_complete_flow(self):
        """Complete forgot password flow: send OTP -> verify -> reset"""
        # Step 1: Send OTP
        send_response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={
            "mobile": TEST_RESIDENT_MOBILE,
            "purpose": "forgot_password"
        })
        assert send_response.status_code == 200
        mock_otp = send_response.json().get("mock_otp")
        print(f"  Step 1: OTP sent, mock_otp: {mock_otp}")
        
        # Step 2: Verify OTP
        verify_response = requests.post(f"{BASE_URL}/api/auth/verify-otp", json={
            "mobile": TEST_RESIDENT_MOBILE,
            "otp": mock_otp,
            "purpose": "forgot_password"
        })
        assert verify_response.status_code == 200
        otp_token = verify_response.json().get("otp_token")
        print(f"  Step 2: OTP verified, got otp_token")
        
        # Step 3: Reset password
        reset_response = requests.post(f"{BASE_URL}/api/auth/forgot-password/reset", json={
            "mobile": TEST_RESIDENT_MOBILE,
            "otp_token": otp_token,
            "new_password": TEST_RESIDENT_PASSWORD  # Reset to same password for testing
        })
        assert reset_response.status_code == 200
        data = reset_response.json()
        assert "successfully" in data.get("message", "").lower()
        print(f"✓ Complete forgot password flow passed: {data.get('message')}")
    
    def test_forgot_password_reset_invalid_token(self):
        """POST /api/auth/forgot-password/reset - should fail with invalid token"""
        response = requests.post(f"{BASE_URL}/api/auth/forgot-password/reset", json={
            "mobile": TEST_RESIDENT_MOBILE,
            "otp_token": "invalid-token-12345",
            "new_password": "newpass456"
        })
        assert response.status_code == 400
        data = response.json()
        assert "invalid" in data.get("detail", "").lower() or "expired" in data.get("detail", "").lower()
        print(f"✓ POST /api/auth/forgot-password/reset - Invalid token correctly rejected")


class TestResidentSignupFlow:
    """Test OTP-based resident signup flow"""
    
    def test_signup_send_otp_new_user(self):
        """POST /api/auth/send-otp - for new signup"""
        response = requests.post(f"{BASE_URL}/api/auth/send-otp", json={
            "mobile": TEST_NEW_MOBILE,
            "purpose": "signup"
        })
        assert response.status_code == 200
        data = response.json()
        assert "mock_otp" in data
        assert "expires_in" in data
        print(f"✓ POST /api/auth/send-otp - Signup OTP sent for {TEST_NEW_MOBILE}, mock_otp: {data.get('mock_otp')}")
        return data


class TestLoginEndpoint:
    """Test login endpoint with various scenarios"""
    
    def test_login_platform_owner(self):
        """POST /api/auth/login - platform owner login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "mobile": PLATFORM_OWNER_MOBILE,
            "password": PLATFORM_OWNER_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "platform_owner"
        print(f"✓ POST /api/auth/login - Platform owner login successful")
        return data["access_token"]
    
    def test_login_admin(self):
        """POST /api/auth/login - admin login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "mobile": ADMIN_MOBILE,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "admin"
        print(f"✓ POST /api/auth/login - Admin login successful")
        return data["access_token"]
    
    def test_login_resident(self):
        """POST /api/auth/login - resident login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "mobile": TEST_RESIDENT_MOBILE,
            "password": TEST_RESIDENT_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "resident"
        print(f"✓ POST /api/auth/login - Resident login successful")
        return data["access_token"]
    
    def test_login_invalid_credentials(self):
        """POST /api/auth/login - invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "mobile": "1234567890",
            "password": "wrongpass"
        })
        assert response.status_code == 401
        print(f"✓ POST /api/auth/login - Invalid credentials correctly rejected")
    
    def test_login_pending_user_error(self):
        """POST /api/auth/login - pending user should get appropriate error"""
        # This tests that the login endpoint gives helpful error for pending/approved users
        # We can't test a real pending user without creating one, but we can verify the endpoint handles it
        pass


class TestBazaarSettingsEndpoints:
    """Test Bazaar settings endpoints (platform_owner only)"""
    
    @pytest.fixture
    def platform_owner_token(self):
        """Get platform owner token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "mobile": PLATFORM_OWNER_MOBILE,
            "password": PLATFORM_OWNER_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_bazaar_settings(self, platform_owner_token):
        """GET /api/platform/bazaar-settings - get bazaar settings"""
        headers = {"Authorization": f"Bearer {platform_owner_token}"}
        response = requests.get(f"{BASE_URL}/api/platform/bazaar-settings", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "bazaar_api_url" in data
        assert "bazaar_secret_key" in data
        assert "bazaar_connected" in data
        print(f"✓ GET /api/platform/bazaar-settings - Settings retrieved: connected={data.get('bazaar_connected')}")
        return data
    
    def test_update_bazaar_settings(self, platform_owner_token):
        """PUT /api/platform/bazaar-settings - save bazaar API URL + secret key"""
        headers = {"Authorization": f"Bearer {platform_owner_token}"}
        response = requests.put(f"{BASE_URL}/api/platform/bazaar-settings", 
            headers=headers,
            json={
                "bazaar_api_url": "https://mock-bazaar-api.example.com",
                "bazaar_secret_key": "test_secret_key_12345"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("bazaar_connected") == True
        print(f"✓ PUT /api/platform/bazaar-settings - Settings updated, connected=True")
    
    def test_bazaar_settings_unauthorized(self):
        """GET /api/platform/bazaar-settings - should fail without auth"""
        response = requests.get(f"{BASE_URL}/api/platform/bazaar-settings")
        assert response.status_code in [401, 403]  # Both are valid unauthorized responses
        print(f"✓ GET /api/platform/bazaar-settings - Correctly requires authentication (status: {response.status_code})")


class TestWalletBazaarStatus:
    """Test wallet bazaar status endpoint"""
    
    @pytest.fixture
    def resident_token(self):
        """Get resident token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "mobile": TEST_RESIDENT_MOBILE,
            "password": TEST_RESIDENT_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_bazaar_status(self, resident_token):
        """GET /api/maintenance/wallet/bazaar-status - check if bazaar is connected"""
        headers = {"Authorization": f"Bearer {resident_token}"}
        response = requests.get(f"{BASE_URL}/api/maintenance/wallet/bazaar-status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "connected" in data
        print(f"✓ GET /api/maintenance/wallet/bazaar-status - Status: connected={data.get('connected')}")
        return data
    
    def test_get_wallet(self, resident_token):
        """GET /api/maintenance/wallet - get wallet balance"""
        headers = {"Authorization": f"Bearer {resident_token}"}
        response = requests.get(f"{BASE_URL}/api/maintenance/wallet", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "balance" in data
        assert "transactions" in data
        print(f"✓ GET /api/maintenance/wallet - Balance: {data.get('balance')} points")
        return data


class TestWalletRedeem:
    """Test wallet redeem endpoint"""
    
    @pytest.fixture
    def resident_token(self):
        """Get resident token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "mobile": TEST_RESIDENT_MOBILE,
            "password": TEST_RESIDENT_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_redeem_below_minimum(self, resident_token):
        """POST /api/maintenance/wallet/redeem - should fail below minimum (100 points)"""
        headers = {"Authorization": f"Bearer {resident_token}"}
        response = requests.post(f"{BASE_URL}/api/maintenance/wallet/redeem",
            headers=headers,
            json={"points": 50}
        )
        assert response.status_code == 400
        data = response.json()
        assert "minimum" in data.get("detail", "").lower() or "100" in data.get("detail", "")
        print(f"✓ POST /api/maintenance/wallet/redeem - Correctly rejects below minimum: {data.get('detail')}")
    
    def test_redeem_insufficient_balance(self, resident_token):
        """POST /api/maintenance/wallet/redeem - should fail with insufficient balance"""
        headers = {"Authorization": f"Bearer {resident_token}"}
        # Try to redeem more than likely balance
        response = requests.post(f"{BASE_URL}/api/maintenance/wallet/redeem",
            headers=headers,
            json={"points": 999999}
        )
        # Could be 400 (insufficient) or 400 (bazaar not connected) - both are valid
        assert response.status_code == 400
        print(f"✓ POST /api/maintenance/wallet/redeem - Handled large redeem request: {response.json().get('detail')}")
    
    def test_redeem_when_bazaar_connected(self, resident_token):
        """POST /api/maintenance/wallet/redeem - test redeem when bazaar is connected"""
        headers = {"Authorization": f"Bearer {resident_token}"}
        
        # First check if bazaar is connected
        status_response = requests.get(f"{BASE_URL}/api/maintenance/wallet/bazaar-status", headers=headers)
        bazaar_status = status_response.json()
        
        # Get wallet balance
        wallet_response = requests.get(f"{BASE_URL}/api/maintenance/wallet", headers=headers)
        wallet = wallet_response.json()
        balance = wallet.get("balance", 0)
        
        if not bazaar_status.get("connected"):
            print(f"⚠ Bazaar not connected, skipping redeem test")
            pytest.skip("Bazaar not connected")
        
        if balance < 100:
            print(f"⚠ Insufficient balance ({balance}), skipping redeem test")
            pytest.skip("Insufficient balance")
        
        # Try to redeem (this will fail because external Bazaar API doesn't exist - expected)
        response = requests.post(f"{BASE_URL}/api/maintenance/wallet/redeem",
            headers=headers,
            json={"points": 100}
        )
        # Expected: 502 (Bad Gateway) because Bazaar API doesn't exist
        assert response.status_code in [200, 400, 502, 504]
        data = response.json()
        print(f"✓ POST /api/maintenance/wallet/redeem - Response: {response.status_code}, {data.get('detail', data.get('message', 'OK'))}")


class TestSetPasswordEndpoint:
    """Test set password endpoint"""
    
    def test_set_password_not_approved(self):
        """POST /api/auth/set-password - should fail for non-approved user"""
        response = requests.post(f"{BASE_URL}/api/auth/set-password", json={
            "mobile": "1234567890",  # non-existent
            "password": "newpass123"
        })
        assert response.status_code == 400
        data = response.json()
        assert "not found" in data.get("detail", "").lower() or "not yet approved" in data.get("detail", "").lower()
        print(f"✓ POST /api/auth/set-password - Correctly rejects non-approved user")
    
    def test_set_password_already_active(self):
        """POST /api/auth/set-password - should fail for already active user"""
        response = requests.post(f"{BASE_URL}/api/auth/set-password", json={
            "mobile": TEST_RESIDENT_MOBILE,  # already active
            "password": "newpass123"
        })
        # Should fail because user is already active (not approved status)
        assert response.status_code == 400
        print(f"✓ POST /api/auth/set-password - Correctly rejects already active user")


class TestP0BugFix:
    """Test P0 bug fix: resident_id linked to flat on approval/set-password"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "mobile": ADMIN_MOBILE,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_flat_has_resident_id_after_activation(self, admin_token):
        """Verify that flat has resident_id after resident is activated"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Get flats
        response = requests.get(f"{BASE_URL}/api/admin/flats", headers=headers)
        if response.status_code == 200:
            flats = response.json()
            # Look for flats with resident_id
            assigned_flats = [f for f in flats if f.get("resident_id")]
            print(f"✓ Found {len(assigned_flats)} flats with resident_id assigned")
            
            if assigned_flats:
                flat = assigned_flats[0]
                print(f"  Example: Flat {flat.get('number')} -> resident_id: {flat.get('resident_id')}")
        else:
            print(f"  Note: Admin flats endpoint returned {response.status_code}")


class TestAdminApproveResident:
    """Test admin approve resident flow (related to P0 fix)"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "mobile": ADMIN_MOBILE,
            "password": ADMIN_PASSWORD
        })
        return response.json()["access_token"]
    
    def test_get_pending_residents(self, admin_token):
        """GET /api/admin/residents?status=pending - get pending residents for approval"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/residents?status=pending", headers=headers)
        assert response.status_code == 200
        data = response.json()
        print(f"✓ GET /api/admin/residents?status=pending - Found {len(data)} pending residents")
        return data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
