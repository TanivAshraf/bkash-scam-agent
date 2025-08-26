import os
import json
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Get the real password from the secure environment variables
        REAL_PASSWORD = os.environ.get('DASHBOARD_PASSWORD')

        try:
            # Read the password submitted by the user from the request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data)
            submitted_password = body.get('password')

            # Check if the submitted password is correct
            if submitted_password == REAL_PASSWORD:
                response = {'authorized': True}
                self.send_response(200)
            else:
                response = {'authorized': False}
                self.send_response(401) # 401 Unauthorized

        except:
            response = {'authorized': False}
            self.send_response(400) # 400 Bad Request

        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))
        return

    def do_GET(self):
        # Block GET requests to this endpoint for security
        self.send_response(405)
        self.end_headers()
        return```
5.  Scroll down and click **"Commit new file"**.

---

### **Step 3: Update the Config API (`api/config.py`)**

We need to update this file to tell the dashboard whether password protection is turned on or off.

1.  Go back to your `api` folder on GitHub and click on the **`api/config.py`** file.
2.  Click the **pencil icon (✏️)** to edit it.
3.  **Delete all the code** and **replace it** with the code below.

```python
import os
import json
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Check the 'on/off switch' from the environment variables
        # Defaults to 'false' if not set
        protection_on = os.environ.get('PASSWORD_PROTECTION_ENABLED', 'false').lower() == 'true'

        # Send the configuration back to the frontend
        config_data = {
            'supabaseUrl': os.environ.get('SUPABASE_URL'),
            'supabaseKey': os.environ.get('SUPABASE_KEY'),
            'protectionEnabled': protection_on
        }

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(config_data).encode('utf-8'))
        return
