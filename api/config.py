import os
import json
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Read the public keys from the secure Vercel environment variables
        config_data = {
            'supabaseUrl': os.environ.get('SUPABASE_URL'),
            'supabaseKey': os.environ.get('SUPABASE_KEY') # This is the public anon key
        }

        # Send the configuration back to the frontend
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(config_data).encode('utf-8'))
        return
