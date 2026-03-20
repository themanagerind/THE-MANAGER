#!/usr/bin/env python3
"""
Backend API Testing for Housing Society Management PWA
Tests all major API endpoints with comprehensive coverage
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class HSMBackendTester:
    """Housing Society Management Backend API Tester"""
    
    def __init__(self, base_url: str = "https://dwelling-ops.preview.emergentagent.com"):
        self.base_url = base_url.rstrip('/')
        self.platform_owner_token = None
        self.admin_token = None
        self.test_admin_id = None
        self.test_admin_mobile = None
        self.test_society_id = None
        self.test_wing_id = None
        self.test_flat_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []

    def log_test(self, name: str, success: bool, message: str = ""):
        """Log test result"""
        self.tests_run += 1
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
        if message:
            print(f"    {message}")
        if success:
            self.tests_passed += 1
        else:
            self.failed_tests.append({"name": name, "message": message})
        print()

    def api_request(self, method: str, endpoint: str, data: Dict[Any, Any] = None, 
                   token: str = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make API request with error handling"""
        url = f"{self.base_url}/api/{endpoint.lstrip('/')}"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported method: {method}")

            return {
                'status_code': response.status_code,
                'data': response.json() if response.content else {},
                'success': 200 <= response.status_code < 300
            }
        except requests.exceptions.RequestException as e:
            return {
                'status_code': 0,
                'data': {'error': str(e)},
                'success': False
            }
        except json.JSONDecodeError:
            return {
                'status_code': response.status_code,
                'data': {'error': 'Invalid JSON response'},
                'success': False
            }

    def test_health_check(self):
        """Test basic health endpoints"""
        print("🔍 Testing Health Check...")
        
        # Test root endpoint
        result = self.api_request('GET', '/')
        success = result['success'] and 'Housing Society Management API' in str(result['data'])
        self.log_test("API Root Endpoint", success, 
                     f"Status: {result['status_code']}, Response: {result['data']}")

        # Test health endpoint
        result = self.api_request('GET', '/health')
        success = result['success'] and result['data'].get('status') == 'healthy'
        self.log_test("Health Check Endpoint", success,
                     f"Status: {result['status_code']}, Health: {result['data'].get('status')}")

    def test_platform_owner_login(self):
        """Test platform owner login"""
        print("🔍 Testing Platform Owner Login...")
        
        login_data = {
            "mobile": "9999999999",
            "password": "owner123"
        }
        
        result = self.api_request('POST', '/auth/login', login_data)
        
        if result['success'] and 'access_token' in result['data']:
            self.platform_owner_token = result['data']['access_token']
            user = result['data'].get('user', {})
            success = user.get('role') == 'platform_owner'
            message = f"Logged in as: {user.get('name')} ({user.get('role')})"
        else:
            success = False
            message = f"Login failed: {result['data']}"
            
        self.log_test("Platform Owner Login", success, message)

    def test_platform_stats(self):
        """Test platform statistics"""
        print("🔍 Testing Platform Statistics...")
        
        if not self.platform_owner_token:
            self.log_test("Platform Stats", False, "No platform owner token available")
            return
            
        result = self.api_request('GET', '/platform/stats', token=self.platform_owner_token)
        
        success = result['success'] and 'total_societies' in result['data']
        if success:
            stats = result['data']
            message = f"Stats: {stats['total_societies']} societies, {stats['total_admins']} admins"
        else:
            message = f"Failed: {result['data']}"
            
        self.log_test("Platform Statistics", success, message)

    def test_admin_registration(self):
        """Test admin registration flow"""
        print("🔍 Testing Admin Registration...")
        
        timestamp = datetime.now().strftime("%H%M%S")
        
        # Register admin with society - using correct URL format with query params
        url = f"{self.base_url}/api/auth/register-admin"
        params = {
            'society_name': f"Test Society {timestamp}",
            'society_address': f"Test Address {timestamp}"
        }
        register_data = {
            "mobile": f"98765{timestamp}",
            "name": f"Test Admin {timestamp}",
            "email": f"testadmin{timestamp}@example.com",
            "password": "testpass123"
        }
        
        try:
            response = requests.post(url, json=register_data, params=params, timeout=30)
            result = {
                'status_code': response.status_code,
                'data': response.json() if response.content else {},
                'success': 200 <= response.status_code < 300
            }
        except Exception as e:
            result = {'status_code': 0, 'data': {'error': str(e)}, 'success': False}
        
        success = result['success'] and result['data'].get('role') == 'admin'
        if success:
            self.test_admin_id = result['data']['id']
            self.test_admin_mobile = register_data['mobile']
            self.test_society_id = result['data']['society_id']
            message = f"Admin registered: {result['data']['name']} (Status: {result['data']['status']})"
        else:
            message = f"Registration failed: {result['data']}"
            
        self.log_test("Admin Registration", success, message)

    def test_admin_approval(self):
        """Test admin approval by platform owner"""
        print("🔍 Testing Admin Approval...")
        
        if not self.platform_owner_token or not self.test_admin_id:
            self.log_test("Admin Approval", False, "Prerequisites not met")
            return
            
        # First get all admins to verify the new admin exists
        result = self.api_request('GET', '/platform/admins', token=self.platform_owner_token)
        
        if result['success']:
            admins = result['data']
            pending_admin = next((a for a in admins if a['id'] == self.test_admin_id), None)
            if not pending_admin:
                self.log_test("Admin Approval", False, "Test admin not found in admin list")
                return
        
        # Approve the admin
        result = self.api_request('POST', f'/platform/admins/{self.test_admin_id}/approve', 
                                 token=self.platform_owner_token)
        
        success = result['success']
        message = result['data'].get('message', str(result['data']))
        self.log_test("Admin Approval", success, message)

    def test_admin_login(self):
        """Test admin login after approval"""
        print("🔍 Testing Admin Login...")
        
        if not self.test_admin_id or not self.test_admin_mobile:
            self.log_test("Admin Login", False, "No test admin available")
            return
            
        # Use the same mobile number from registration
        login_data = {
            "mobile": self.test_admin_mobile,
            "password": "testpass123"
        }
        
        result = self.api_request('POST', '/auth/login', login_data)
        
        if result['success'] and 'access_token' in result['data']:
            self.admin_token = result['data']['access_token']
            user = result['data'].get('user', {})
            success = user.get('role') == 'admin' and user.get('status') == 'active'
            message = f"Admin logged in: {user.get('name')} (Status: {user.get('status')})"
        else:
            success = False
            message = f"Login failed: {result['data']}"
            
        self.log_test("Admin Login", success, message)

    def test_wings_crud(self):
        """Test wings CRUD operations"""
        print("🔍 Testing Wings CRUD...")
        
        if not self.admin_token or not self.test_society_id:
            self.log_test("Wings CRUD", False, "Prerequisites not met")
            return
            
        # Create wing
        wing_data = {
            "society_id": self.test_society_id,
            "name": "A-Block"
        }
        
        result = self.api_request('POST', '/admin/wings', wing_data, token=self.admin_token)
        
        if result['success']:
            self.test_wing_id = result['data']['id']
            message = f"Wing created: {result['data']['name']} (ID: {self.test_wing_id})"
            success = True
        else:
            success = False
            message = f"Wing creation failed: {result['data']}"
            
        self.log_test("Create Wing", success, message)
        
        # Get wings
        result = self.api_request('GET', '/admin/wings', token=self.admin_token)
        success = result['success'] and len(result['data']) > 0
        if success:
            wings = result['data']
            message = f"Retrieved {len(wings)} wings"
        else:
            message = f"Failed to get wings: {result['data']}"
            
        self.log_test("Get Wings", success, message)

    def test_flats_bulk_creation(self):
        """Test bulk flat creation"""
        print("🔍 Testing Bulk Flat Creation...")
        
        if not self.admin_token or not self.test_wing_id:
            self.log_test("Bulk Flat Creation", False, "Prerequisites not met")
            return
            
        # Create flats in bulk - using correct URL format
        url = f"{self.base_url}/api/admin/flats/bulk"
        params = {
            'wing_id': self.test_wing_id,
            'floor_count': 2,
            'flats_per_floor': 3
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.admin_token}'
        }
        
        try:
            response = requests.post(url, params=params, headers=headers, timeout=30)
            result = {
                'status_code': response.status_code,
                'data': response.json() if response.content else {},
                'success': 200 <= response.status_code < 300
            }
        except Exception as e:
            result = {'status_code': 0, 'data': {'error': str(e)}, 'success': False}
        
        success = result['success'] and 'Created' in result['data'].get('message', '')
        if success:
            created_count = len(result['data'].get('flats', []))
            message = f"Created {created_count} flats"
        else:
            message = f"Bulk creation failed: {result['data']}"
            
        self.log_test("Bulk Flat Creation", success, message)
        
        # Get flats to verify
        result = self.api_request('GET', '/admin/flats', 
                                 params={'wing_id': self.test_wing_id},
                                 token=self.admin_token)
        
        if result['success'] and len(result['data']) > 0:
            self.test_flat_id = result['data'][0]['id']
            message = f"Retrieved {len(result['data'])} flats, first flat: {result['data'][0]['number']}"
            success = True
        else:
            message = f"Failed to get flats: {result['data']}"
            success = False
            
        self.log_test("Get Flats", success, message)

    def test_maintenance_preview(self):
        """Test maintenance bill preview"""
        print("🔍 Testing Maintenance Bill Preview...")
        
        if not self.admin_token:
            self.log_test("Maintenance Preview", False, "No admin token available")
            return
            
        # Test preview
        current_month = datetime.now().strftime("%Y-%m")
        result = self.api_request('GET', '/maintenance/admin/preview',
                                 params={
                                     'month': current_month,
                                     'amount_per_flat': 1500.0
                                 },
                                 token=self.admin_token)
        
        success = result['success'] and 'total_active_flats' in result['data']
        if success:
            preview = result['data']
            message = f"Preview: {preview['total_active_flats']} flats, ₹{preview['total_amount']} total"
        else:
            message = f"Preview failed: {result['data']}"
            
        self.log_test("Maintenance Bill Preview", success, message)

    def test_shopping_link_config(self):
        """Test shopping link configuration"""
        print("🔍 Testing Shopping Link Configuration...")
        
        if not self.platform_owner_token:
            self.log_test("Shopping Link Config", False, "No platform owner token")
            return
            
        # Get current link
        result = self.api_request('GET', '/platform/shopping-link', 
                                 token=self.platform_owner_token)
        
        success = result['success']
        if success:
            current_link = result['data'].get('shopping_link', 'None')
            message = f"Current link: {current_link}"
        else:
            message = f"Failed to get link: {result['data']}"
            
        self.log_test("Get Shopping Link", success, message)
        
        # Set new link
        test_link = "https://example-shop.com/test"
        result = self.api_request('PUT', '/platform/shopping-link',
                                 data={'shopping_link': test_link},
                                 token=self.platform_owner_token)
        
        success = result['success'] and test_link in str(result['data'])
        message = f"Set link result: {result['data']}"
        self.log_test("Set Shopping Link", success, message)

    def test_resident_registration(self):
        """Test resident registration (simulation)"""
        print("🔍 Testing Resident Registration...")
        
        if not self.test_society_id or not self.test_wing_id or not self.test_flat_id:
            self.log_test("Resident Registration", False, "Prerequisites not met")
            return
            
        timestamp = datetime.now().strftime("%H%M%S")
        register_data = {
            "mobile": f"91234{timestamp}",
            "name": f"Test Resident {timestamp}",
            "email": f"resident{timestamp}@example.com",
            "password": "respass123",
            "society_id": self.test_society_id,
            "wing_id": self.test_wing_id,
            "flat_id": self.test_flat_id
        }
        
        result = self.api_request('POST', '/auth/register', register_data)
        
        success = result['success'] and result['data'].get('role') == 'resident'
        if success:
            message = f"Resident registered: {result['data']['name']} (Status: {result['data']['status']})"
        else:
            message = f"Registration failed: {result['data']}"
            
        self.log_test("Resident Registration", success, message)

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Housing Society Management Backend Tests\n")
        print(f"Testing Backend URL: {self.base_url}")
        print("=" * 60)
        
        # Basic connectivity
        self.test_health_check()
        
        # Authentication flow
        self.test_platform_owner_login()
        self.test_platform_stats()
        
        # Admin management flow
        self.test_admin_registration()
        self.test_admin_approval()
        self.test_admin_login()
        
        # Society management
        self.test_wings_crud()
        self.test_flats_bulk_creation()
        self.test_maintenance_preview()
        
        # Platform settings
        self.test_shopping_link_config()
        
        # Resident registration
        self.test_resident_registration()
        
        # Print summary
        print("=" * 60)
        print(f"📊 TEST SUMMARY")
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {len(self.failed_tests)}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%" if self.tests_run > 0 else "0%")
        
        if self.failed_tests:
            print("\n❌ Failed Tests:")
            for test in self.failed_tests:
                print(f"  - {test['name']}: {test['message']}")
        
        return self.tests_passed == self.tests_run

def main():
    """Main test execution"""
    tester = HSMBackendTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())